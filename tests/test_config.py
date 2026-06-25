#!/usr/bin/env python3
"""Tests for nbot.config."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from nbot.config import Config, get_config


class TestConfigSingleton:
    """Tests for Config singleton behavior."""

    def test_same_instance(self):
        c1 = Config()
        c2 = Config()
        assert c1 is c2

    def test_get_config_returns_same(self):
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2


class TestConfigGet:
    """Tests for Config.get."""

    def test_returns_env_value(self, monkeypatch):
        monkeypatch.setenv("TEST__KEY", "hello")
        config = Config()
        assert config.get("TEST__KEY") == "hello"

    def test_returns_fallback_when_missing(self):
        config = Config()
        assert config.get("NONEXISTENT__KEY", fallback="default") == "default"

    def test_returns_empty_string_default(self):
        config = Config()
        assert config.get("NONEXISTENT__KEY") == ""


class TestConfigGetInt:
    """Tests for Config.get_int."""

    def test_parses_integer(self, monkeypatch):
        monkeypatch.setenv("TEST__INT", "42")
        config = Config()
        assert config.get_int("TEST__INT") == 42

    def test_returns_fallback_when_missing(self):
        config = Config()
        assert config.get_int("NONEXISTENT__INT", fallback=7) == 7

    def test_returns_fallback_on_invalid(self, monkeypatch):
        monkeypatch.setenv("TEST__INT", "not_a_number")
        config = Config()
        assert config.get_int("TEST__INT", fallback=0) == 0


class TestConfigGetBool:
    """Tests for Config.get_bool."""

    def test_true_values(self, monkeypatch):
        config = Config()
        for val in ("true", "True", "TRUE", "1", "yes", "YES", "on", "ON"):
            monkeypatch.setenv("TEST__BOOL", val)
            assert config.get_bool("TEST__BOOL") is True

    def test_false_values(self, monkeypatch):
        config = Config()
        for val in ("false", "False", "FALSE", "0", "no", "NO", "off", "OFF"):
            monkeypatch.setenv("TEST__BOOL", val)
            assert config.get_bool("TEST__BOOL") is False

    def test_returns_fallback_when_missing(self):
        config = Config()
        assert config.get_bool("NONEXISTENT__BOOL", fallback=True) is True


class TestConfigGetList:
    """Tests for Config.get_list."""

    def test_splits_by_comma(self, monkeypatch):
        monkeypatch.setenv("TEST__LIST", "a,b,c")
        config = Config()
        assert config.get_list("TEST__LIST") == ["a", "b", "c"]

    def test_trims_whitespace(self, monkeypatch):
        monkeypatch.setenv("TEST__LIST", " a , b , c ")
        config = Config()
        assert config.get_list("TEST__LIST") == ["a", "b", "c"]

    def test_filters_empty_items(self, monkeypatch):
        monkeypatch.setenv("TEST__LIST", "a,,b")
        config = Config()
        assert config.get_list("TEST__LIST") == ["a", "b"]

    def test_custom_separator(self, monkeypatch):
        monkeypatch.setenv("TEST__LIST", "a;b;c")
        config = Config()
        assert config.get_list("TEST__LIST", sep=";") == ["a", "b", "c"]

    def test_returns_fallback_when_missing(self):
        config = Config()
        assert config.get_list("NONEXISTENT__LIST", fallback=["x"]) == ["x"]

    def test_returns_empty_list_default(self):
        config = Config()
        assert config.get_list("NONEXISTENT__LIST") == []


class TestConfigGetSection:
    """Tests for Config.get_section."""

    def test_extracts_prefix(self, monkeypatch):
        monkeypatch.setenv("BOT__UIN", "12345")
        monkeypatch.setenv("BOT__WS_URI", "ws://localhost")
        monkeypatch.setenv("OTHER__KEY", "value")
        config = Config()
        section = config.get_section("BOT")
        assert section == {"UIN": "12345", "WS_URI": "ws://localhost"}

    def test_empty_when_no_match(self):
        config = Config()
        section = config.get_section("NONEXISTENT")
        assert section == {}

    def test_only_includes_exact_prefix(self, monkeypatch):
        monkeypatch.setenv("BOT__UIN", "12345")
        monkeypatch.setenv("BOTEXTRA__KEY", "value")
        config = Config()
        section = config.get_section("BOT")
        assert section == {"UIN": "12345"}


class TestConfigReload:
    """Tests for Config.reload."""

    def test_reloads_env_changes(self, monkeypatch):
        monkeypatch.setenv("TEST__RELOAD", "before")
        config = Config()
        assert config.get("TEST__RELOAD") == "before"
        monkeypatch.setenv("TEST__RELOAD", "after")
        config.reload()
        assert config.get("TEST__RELOAD") == "after"
