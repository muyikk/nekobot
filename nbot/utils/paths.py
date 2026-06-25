#!/usr/bin/env python3
"""NekoBot 路径助手。

统一项目内各类目录的绝对路径获取，并自动创建缺失目录。
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Final


_PROJECT_ROOT: Final[str] = str(Path(__file__).resolve().parents[2])


def get_project_root() -> str:
    """返回项目根目录的绝对路径。

    Returns:
        项目根目录绝对路径字符串。
    """
    return _PROJECT_ROOT


def get_cache_dir(subpath: str = "") -> str:
    """返回 ``cache/`` 目录的绝对路径。

    Args:
        subpath: 可选子目录，如 ``"pdf"``、``"jm_cover_cache"``。

    Returns:
        绝对路径字符串。
    """
    path = Path(_PROJECT_ROOT) / "cache" / subpath
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_data_dir(subpath: str = "") -> str:
    """返回 ``data/`` 目录的绝对路径。

    Args:
        subpath: 可选子目录。

    Returns:
        绝对路径字符串。
    """
    path = Path(_PROJECT_ROOT) / "data" / subpath
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_downloads_dir(subpath: str = "") -> str:
    """返回 ``tmp/`` 下载目录的绝对路径。

    Args:
        subpath: 可选子目录。

    Returns:
        绝对路径字符串。
    """
    path = Path(_PROJECT_ROOT) / "tmp" / subpath
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_workspace_dir() -> str:
    """返回工作区目录的绝对路径。

    工作区用于存放运行时生成的各类数据文件。

    Returns:
        绝对路径字符串。
    """
    path = Path(_PROJECT_ROOT) / "data" / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_resources_dir(subpath: str = "") -> str:
    """返回 ``resources/`` 目录的绝对路径。

    Args:
        subpath: 可选子目录，如 ``"config"``。

    Returns:
        绝对路径字符串。
    """
    path = Path(_PROJECT_ROOT) / "resources" / subpath
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def normalize_file_path(path: str) -> str:
    """规范化文件路径：展开用户目录、解析相对路径、返回绝对路径。

    Args:
        path: 原始路径字符串。

    Returns:
        规范化后的绝对路径字符串。
    """
    return str(Path(path).expanduser().resolve())


class DownloadType(str, Enum):
    """下载资源类型枚举。"""

    VIDEO = "videos"
    IMAGE = "images"
    PDF = "pdfs"
    AUDIO = "audio"
    OTHER = "others"


def make_download_path(
    source: str,
    resource_id: str,
    ext: str,
    dtype: DownloadType = DownloadType.OTHER,
    timestamp: str | None = None,
) -> str:
    """生成标准化的下载文件路径。

    路径格式：``tmp/<dtype>/<source>_<resource_id>[_<timestamp>].<ext>``

    Args:
        source: 来源标识，如 ``"bili"``、``"douyin"``。
        resource_id: 资源唯一标识，如 BV 号、视频 ID。
        ext: 文件扩展名（不含点），如 ``"mp4"``、``"jpg"``。
        dtype: 资源类型，默认 :attr:`DownloadType.OTHER`。
        timestamp: 可选时间戳字符串，用于避免文件名冲突。

    Returns:
        绝对路径字符串。
    """
    # 清理资源 ID 中的非法字符
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in resource_id)
    safe_source = "".join(c if c.isalnum() or c in "-_" else "_" for c in source)

    filename = f"{safe_source}_{safe_id}"
    if timestamp:
        safe_ts = "".join(c if c.isalnum() or c in "-_" else "_" for c in timestamp)
        filename = f"{filename}_{safe_ts}"
    filename = f"{filename}.{ext.lstrip('.')}"

    dir_path = Path(get_downloads_dir(dtype.value))
    dir_path.mkdir(parents=True, exist_ok=True)
    return str(dir_path / filename)
