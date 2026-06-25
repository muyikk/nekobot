#!/usr/bin/env python3
"""NekoBot 统一日志门面。

提供集中式的日志配置与获取接口，支持控制台与文件双输出、
上下文过滤、以及第三方 noisy logger 的静默管理。
"""

from __future__ import annotations

import logging
import logging.config
import os
import sys
import threading
from pathlib import Path
from typing import Any


class ContextFilter(logging.Filter):
    """通过 threading.local() 注入上下文标签的日志过滤器。

    支持的上下文标签：``server``、``cli``、``qq`` 等。
    在日志格式中可通过 ``%(context)s`` 引用。

    Example:
        >>> filter = ContextFilter()
        >>> filter.set_context("server")
        >>> logger.addFilter(filter)
    """

    _local = threading.local()

    def filter(self, record: logging.LogRecord) -> bool:
        """为日志记录注入当前上下文标签。"""
        record.context = getattr(self._local, "context", "-")
        return True

    @classmethod
    def set_context(cls, value: str) -> None:
        """在当前线程设置上下文标签。

        Args:
            value: 上下文标识，如 ``"server"``、``"cli"``、``"qq"``。
        """
        cls._local.context = value

    @classmethod
    def clear_context(cls) -> None:
        """清除当前线程的上下文标签。"""
        if hasattr(cls._local, "context"):
            delattr(cls._local, "context")


def setup_logging(
    level: str = "INFO",
    log_dir: str = "logs",
    max_bytes: int = 10_000_000,
    backup_count: int = 5,
    console: bool = True,
) -> None:
    """配置 NekoBot 全局日志体系。

    使用 ``logging.config.dictConfig`` 构建以下结构：

    - ``nbot`` logger：console + file，级别由 *level* 控制。
    - ``ncatbot``、``werkzeug``、``urllib3``、``apscheduler`` 等 noisy logger：
      仅 file handler，级别 ``WARNING`` / ``ERROR``。
    - root logger：仅 file handler，级别 ``WARNING``。

    Args:
        level: nbot 主 logger 的级别（``DEBUG`` / ``INFO`` / ``WARNING`` / ``ERROR``）。
        log_dir: 日志文件存放目录，默认 ``logs``。
        max_bytes: 单个日志文件最大字节数，默认 10 MB。
        backup_count: 保留的旧日志文件数，默认 5。
        console: 是否启用控制台输出，默认 ``True``。

    Returns:
        None
    """
    log_path = Path(log_dir).resolve()
    log_path.mkdir(parents=True, exist_ok=True)

    log_file = log_path / "nekobot.log"

    handlers: dict[str, Any] = {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "standard",
            "filename": str(log_file),
            "maxBytes": max_bytes,
            "backupCount": backup_count,
            "encoding": "utf-8",
        },
    }

    if console:
        handlers["console"] = {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        }

    # 构建 nbot logger 的 handlers 列表
    nbot_handlers = ["file"]
    if console:
        nbot_handlers.append("console")

    config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": handlers,
        "loggers": {
            "nbot": {
                "level": level,
                "handlers": nbot_handlers,
                "propagate": False,
            },
            # Noisy third-party loggers: 仅文件，避免控制台刷屏
            "ncatbot": {
                "level": "WARNING",
                "handlers": ["file"],
                "propagate": False,
            },
            "werkzeug": {
                "level": "ERROR",
                "handlers": ["file"],
                "propagate": False,
            },
            "urllib3": {
                "level": "WARNING",
                "handlers": ["file"],
                "propagate": False,
            },
            "apscheduler": {
                "level": "WARNING",
                "handlers": ["file"],
                "propagate": False,
            },
        },
        "root": {
            "level": "WARNING",
            "handlers": ["file"],
        },
    }

    logging.config.dictConfig(config)

    # 安装上下文过滤器到所有 nbot handler
    nbot_logger = logging.getLogger("nbot")
    ctx_filter = ContextFilter()
    for h in nbot_logger.handlers:
        h.addFilter(ctx_filter)


def get_logger(name: str) -> logging.Logger:
    """获取以 ``nbot.`` 为前缀的 logger。

    若 *name* 不以 ``nbot`` 开头，自动补全前缀，确保继承 ``nbot`` logger
    的配置（级别、handlers、filters）。

    Args:
        name: logger 名称，通常传 ``__name__``。

    Returns:
        配置好的 :class:`logging.Logger` 实例。
    """
    if not name.startswith("nbot"):
        name = f"nbot.{name}"
    return logging.getLogger(name)


def silence_loggers(*names: str, level: int = logging.CRITICAL + 1) -> None:
    """将指定 logger 的级别设为极高值，从而完全静默。

    Args:
        names: 要静默的 logger 名称序列。
        level: 提升到的级别，默认 ``CRITICAL + 1``（高于任何标准级别）。

    Returns:
        None
    """
    for n in names:
        logging.getLogger(n).setLevel(level)
