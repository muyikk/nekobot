#!/usr/bin/env python3
"""NekoBot 单一 ``.env`` 配置入口。

提供 :class:`Config` 单例类，使用 ``python-dotenv`` 加载 ``.env`` 文件，
并允许 ``os.environ`` 覆盖。所有键名使用 ``UPPER_SNAKE_CASE``，
section 分隔符为双下划线 ``__``。

Example:
    >>> from nbot.config import get_config
    >>> config = get_config()
    >>> bot_uin = config.get("BOT__UIN", fallback="")
    >>> ws_uri = config.get("BOT__WS_URI", fallback="ws://127.0.0.1:30051")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


class Config:
    """NekoBot 配置单例。

    优先使用 ``os.environ`` 中的值，其次从 ``.env`` 文件读取。
    支持按 ``PREFIX__`` 前缀提取配置子集。
    """

    _instance: Config | None = None
    _env_path: str | None = None

    def __new__(cls) -> Config:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        """加载 ``.env`` 文件到环境变量。"""
        # 优先查找项目根目录的 .env
        root = Path(__file__).resolve().parent.parent
        env_path = root / ".env"
        if env_path.exists():
            load_dotenv(str(env_path), override=True)
            self._env_path = str(env_path)
        else:
            # 回退到当前工作目录
            load_dotenv(override=True)
            self._env_path = str(Path(".env").resolve()) if Path(".env").exists() else None

    def reload(self) -> None:
        """重新加载 ``.env`` 文件并刷新环境变量。"""
        self._load()

    def get(self, key: str, fallback: str = "") -> str:
        """获取字符串配置值。

        Args:
            key: 配置键名，如 ``"BOT__UIN"``。
            fallback: 默认值。

        Returns:
            配置值字符串，未找到则返回 *fallback*。
        """
        return os.getenv(key, fallback)

    def get_int(self, key: str, fallback: int = 0) -> int:
        """获取整数配置值。

        Args:
            key: 配置键名。
            fallback: 默认值。

        Returns:
            整数值，解析失败或不存在时返回 *fallback*。
        """
        value = os.getenv(key)
        if value is None:
            return fallback
        try:
            return int(value)
        except ValueError:
            return fallback

    def get_bool(self, key: str, fallback: bool = False) -> bool:
        """获取布尔配置值。

        支持 ``true`` / ``1`` / ``yes`` / ``on``（大小写不敏感）为真，
        ``false`` / ``0`` / ``no`` / ``off`` 为假。

        Args:
            key: 配置键名。
            fallback: 默认值。

        Returns:
            布尔值，解析失败或不存在时返回 *fallback*。
        """
        value = os.getenv(key)
        if value is None:
            return fallback
        return value.lower() in ("true", "1", "yes", "on")

    def get_list(self, key: str, sep: str = ",", fallback: list[str] | None = None) -> list[str]:
        """获取列表配置值。

        按分隔符拆分字符串，去除空白并过滤空值。

        Args:
            key: 配置键名。
            sep: 分隔符，默认逗号。
            fallback: 默认值。

        Returns:
            字符串列表，未找到时返回 *fallback*。
        """
        value = os.getenv(key)
        if value is None:
            return fallback if fallback is not None else []
        return [item.strip() for item in value.split(sep) if item.strip()]

    def get_section(self, prefix: str) -> dict[str, str]:
        """获取指定前缀的配置子集。

        返回所有以 ``prefix + "__"`` 开头的环境变量，键名去除前缀。

        Args:
            prefix: Section 前缀，如 ``"BOT"``。

        Returns:
            去除前缀后的键值对字典。
        """
        section: dict[str, str] = {}
        prefix_key = f"{prefix}__"
        for key, value in os.environ.items():
            if key.startswith(prefix_key):
                section[key[len(prefix_key):]] = value
        return section


def get_config() -> Config:
    """获取 :class:`Config` 单例实例。

    Returns:
        全局唯一的 :class:`Config` 实例。
    """
    return Config()
