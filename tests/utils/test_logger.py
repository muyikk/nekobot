#!/usr/bin/env python3
"""Tests for nbot.utils.logger."""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from nbot.utils.logger import (
    ContextFilter,
    get_logger,
    setup_logging,
    silence_loggers,
)


class TestSetupLogging:
    """Tests for setup_logging."""

    def test_creates_log_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = os.path.join(tmpdir, "test_logs")
            setup_logging(log_dir=log_dir, console=False)
            assert os.path.isdir(log_dir)

    def test_creates_rotating_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = os.path.join(tmpdir, "test_logs")
            setup_logging(log_dir=log_dir, console=False)
            log_file = os.path.join(log_dir, "nekobot.log")
            assert os.path.exists(log_file)

    def test_log_level_applied(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(level="ERROR", log_dir=tmpdir, console=False)
            logger = logging.getLogger("nbot.test")
            assert logger.level == 0  # inherits from nbot parent
            assert logging.getLogger("nbot").level == logging.ERROR

    def test_console_handler_present_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir, console=True)
            nbot_logger = logging.getLogger("nbot")
            handler_types = [type(h).__name__ for h in nbot_logger.handlers]
            assert "StreamHandler" in handler_types

    def test_console_handler_absent_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir, console=False)
            nbot_logger = logging.getLogger("nbot")
            handler_types = [type(h).__name__ for h in nbot_logger.handlers]
            assert "StreamHandler" not in handler_types

    def test_noisy_loggers_only_file_handlers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir, console=True)
            for name in ("ncatbot", "werkzeug", "urllib3", "apscheduler"):
                logger = logging.getLogger(name)
                assert len(logger.handlers) == 1
                assert isinstance(logger.handlers[0], logging.handlers.RotatingFileHandler)

    def test_root_logger_file_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir, console=True)
            root = logging.getLogger()
            assert "RotatingFileHandler" in [type(h).__name__ for h in root.handlers]

    def test_log_rotation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(level="DEBUG", log_dir=tmpdir, max_bytes=100, console=False)
            logger = get_logger("test.rotation")
            for _ in range(50):
                logger.info("x" * 50)
                time.sleep(0.001)
            log_files = list(Path(tmpdir).glob("*.log*"))
            assert len(log_files) >= 2


class TestGetLogger:
    """Tests for get_logger."""

    def test_prefixes_non_nbot_names(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir, console=False)
            logger = get_logger("my_module")
            assert logger.name == "nbot.my_module"

    def test_preserves_nbot_prefix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir, console=False)
            logger = get_logger("nbot.core.something")
            assert logger.name == "nbot.core.something"

    def test_returns_logger_instance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir, console=False)
            logger = get_logger("test")
            assert isinstance(logger, logging.Logger)


class TestSilenceLoggers:
    """Tests for silence_loggers."""

    def test_sets_level_above_critical(self):
        logger = logging.getLogger("test_silence_1")
        logger.setLevel(logging.DEBUG)
        silence_loggers("test_silence_1")
        assert logger.level == logging.CRITICAL + 1

    def test_multiple_loggers(self):
        loggers = ["test_silence_a", "test_silence_b"]
        for name in loggers:
            logging.getLogger(name).setLevel(logging.DEBUG)
        silence_loggers(*loggers)
        for name in loggers:
            assert logging.getLogger(name).level == logging.CRITICAL + 1

    def test_custom_level(self):
        logger = logging.getLogger("test_silence_custom")
        logger.setLevel(logging.DEBUG)
        silence_loggers("test_silence_custom", level=logging.ERROR)
        assert logger.level == logging.ERROR


class TestContextFilter:
    """Tests for ContextFilter."""

    def test_injects_context_attribute(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        f = ContextFilter()
        f.filter(record)
        assert hasattr(record, "context")
        assert record.context == "-"

    def test_set_context_per_thread(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        f = ContextFilter()
        ContextFilter.set_context("server")
        f.filter(record)
        assert record.context == "server"
        ContextFilter.clear_context()

    def test_thread_isolation(self):
        results = {}

        def worker(label):
            ContextFilter.set_context(label)
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="hello",
                args=(),
                exc_info=None,
            )
            f = ContextFilter()
            f.filter(record)
            results[label] = record.context
            ContextFilter.clear_context()

        t1 = threading.Thread(target=worker, args=("qq",))
        t2 = threading.Thread(target=worker, args=("cli",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results["qq"] == "qq"
        assert results["cli"] == "cli"

    def test_clear_context(self):
        ContextFilter.set_context("server")
        ContextFilter.clear_context()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        f = ContextFilter()
        f.filter(record)
        assert record.context == "-"
