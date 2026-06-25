#!/usr/bin/env python3
"""Tests for nbot.utils.paths."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from nbot.utils.paths import (
    DownloadType,
    get_cache_dir,
    get_data_dir,
    get_downloads_dir,
    get_project_root,
    get_resources_dir,
    get_workspace_dir,
    make_download_path,
    normalize_file_path,
)


class TestGetProjectRoot:
    """Tests for get_project_root."""

    def test_returns_existing_directory(self):
        root = get_project_root()
        assert os.path.isdir(root)

    def test_returns_absolute_path(self):
        root = get_project_root()
        assert os.path.isabs(root)

    def test_contains_expected_files(self):
        root = get_project_root()
        assert os.path.exists(os.path.join(root, "bot.py"))


class TestGetCacheDir:
    """Tests for get_cache_dir."""

    def test_creates_directory(self):
        path = get_cache_dir("test_sub")
        assert os.path.isdir(path)

    def test_returns_absolute_path(self):
        path = get_cache_dir()
        assert os.path.isabs(path)

    def test_subpath_nested(self):
        path = get_cache_dir("a/b/c")
        assert os.path.isdir(path)
        assert path.endswith(os.path.join("cache", "a", "b", "c"))


class TestGetDataDir:
    """Tests for get_data_dir."""

    def test_creates_directory(self):
        path = get_data_dir("test_sub")
        assert os.path.isdir(path)

    def test_returns_absolute_path(self):
        path = get_data_dir()
        assert os.path.isabs(path)


class TestGetDownloadsDir:
    """Tests for get_downloads_dir."""

    def test_creates_directory(self):
        path = get_downloads_dir("test_sub")
        assert os.path.isdir(path)

    def test_returns_absolute_path(self):
        path = get_downloads_dir()
        assert os.path.isabs(path)


class TestGetWorkspaceDir:
    """Tests for get_workspace_dir."""

    def test_creates_directory(self):
        path = get_workspace_dir()
        assert os.path.isdir(path)

    def test_returns_absolute_path(self):
        path = get_workspace_dir()
        assert os.path.isabs(path)

    def test_under_data(self):
        path = get_workspace_dir()
        assert "data" in path


class TestGetResourcesDir:
    """Tests for get_resources_dir."""

    def test_creates_directory(self):
        path = get_resources_dir("config")
        assert os.path.isdir(path)

    def test_returns_absolute_path(self):
        path = get_resources_dir()
        assert os.path.isabs(path)


class TestNormalizeFilePath:
    """Tests for normalize_file_path."""

    def test_expands_tilde(self):
        home = os.path.expanduser("~")
        result = normalize_file_path("~/test.txt")
        assert result.startswith(home)

    def test_resolves_relative(self):
        result = normalize_file_path(".")
        assert os.path.isabs(result)

    def test_already_absolute(self):
        abs_path = os.path.abspath("/tmp/test.txt")
        result = normalize_file_path(abs_path)
        assert os.path.isabs(result)


class TestDownloadType:
    """Tests for DownloadType enum."""

    def test_members(self):
        assert DownloadType.VIDEO == "videos"
        assert DownloadType.IMAGE == "images"
        assert DownloadType.PDF == "pdfs"
        assert DownloadType.AUDIO == "audio"
        assert DownloadType.OTHER == "others"

    def test_is_str_enum(self):
        assert isinstance(DownloadType.VIDEO, str)


class TestMakeDownloadPath:
    """Tests for make_download_path."""

    def test_creates_directory(self):
        path = make_download_path("bili", "BV123", "mp4")
        assert os.path.isdir(os.path.dirname(path))

    def test_returns_absolute_path(self):
        path = make_download_path("bili", "BV123", "mp4")
        assert os.path.isabs(path)

    def test_filename_contains_source_and_id(self):
        path = make_download_path("bili", "BV123", "mp4")
        filename = os.path.basename(path)
        assert filename.startswith("bili_BV123")
        assert filename.endswith(".mp4")

    def test_includes_timestamp_when_provided(self):
        path = make_download_path("bili", "BV123", "mp4", timestamp="20240101_120000")
        filename = os.path.basename(path)
        assert "_20240101_120000" in filename

    def test_sanitizes_invalid_chars(self):
        path = make_download_path("bi/li", "BV:123", "mp4")
        filename = os.path.basename(path)
        assert "/" not in filename
        assert ":" not in filename

    def test_uses_download_type_subdirectory(self):
        path = make_download_path("bili", "BV123", "mp4", dtype=DownloadType.VIDEO)
        assert os.path.sep + "videos" + os.path.sep in path

    def test_strips_leading_dot_from_ext(self):
        path = make_download_path("bili", "BV123", ".mp4")
        assert path.endswith(".mp4")
        assert not os.path.basename(path).endswith("..mp4")
