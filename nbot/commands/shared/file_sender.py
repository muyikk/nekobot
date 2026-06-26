"""Async file sending helpers."""

from __future__ import annotations

import asyncio
import configparser
import json
import os
import random
from typing import Any, Callable, Optional

from nbot.utils.http_client import get_sync
from nbot.utils.logger import get_logger

_log = get_logger(__name__)


async def async_send_file(
    is_group: bool,
    send_method: Callable,
    target_id: Any,
    file_type: str,
    url: str,
    file_name: Optional[str] = None,
) -> None:
    """Download a file from URL and send it via the bot API.

    Args:
        is_group: Whether the target is a group.
        send_method: ``bot.api.post_group_file`` or similar.
        target_id: Group ID or user ID.
        file_type: ``image``, ``record``, ``video``, ``file``, ``markdown``.
        url: Source URL.
        file_name: Optional file name hint.
    """
    try:
        loop = asyncio.get_event_loop()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        response = await loop.run_in_executor(
            None,
            lambda: get_sync(url, allow_redirects=True, timeout=10, headers=headers),
        )
        final_url = response.url

        if is_group:
            await send_method(target_id, **{file_type: final_url})
        else:
            await send_method(target_id, **{file_type: final_url})
    except Exception as e:
        error_msg = f"发送失败喵~: {str(e)}"
        # Lazy import bot to avoid circular
        from nbot.commands import bot
        if is_group:
            # msg is not available here; caller should handle errors
            _log.error(error_msg)
        else:
            await bot.api.post_private_msg(target_id, text=error_msg)


async def handle_generic_file(
    msg: Any,
    is_group: bool,
    section: str,
    file_type: str,
    custom_url: Optional[str] = None,
    file_name: Optional[str] = None,
    custom_send_method: Optional[Callable] = None,
) -> None:
    """Generic file handler for random-URL commands.

    Args:
        msg: The ncatbot message object.
        is_group: Whether the message is from a group.
        section: ``urls.ini`` section name (ignored when ``custom_url`` is set).
        file_type: ``image``, ``record``, ``video``, ``file``, ``markdown``.
        custom_url: Optional direct URL (skips config read).
        file_name: Optional file name.
        custom_send_method: Optional override send method.
    """
    from nbot.utils.message_sender import send_text

    try:
        if section:
            loop = asyncio.get_event_loop()

            def _read_config() -> configparser.ConfigParser:
                cfg = configparser.ConfigParser()
                cfg.read("resources/config/urls.ini")
                if not cfg.has_section(section):
                    raise Exception(f"配置文件中缺少 [{section}] 段落")
                return cfg

            config = await loop.run_in_executor(None, _read_config)
            urls = json.loads(config.get(section, "urls"))
            selected_url = random.choice(urls)
        else:
            selected_url = custom_url

        # Lazy import bot
        from nbot.commands import bot
        send_method = (
            custom_send_method
            if custom_send_method
            else (
                bot.api.post_group_file if is_group else bot.api.post_private_file
            )
        )
        target_id = msg.group_id if is_group else msg.user_id
        if custom_send_method:
            await async_send_file(
                is_group, custom_send_method, target_id, file_type, selected_url, file_name
            )
        else:
            asyncio.create_task(
                async_send_file(
                    is_group, send_method, target_id, file_type, selected_url, file_name
                )
            )

    except Exception as e:
        error_msg = (
            f"配置错误喵~: {str(e)}"
            if "配置" in str(e)
            else f"获取失败喵~: {str(e)}"
        )
        await send_text(msg, error_msg, is_group=is_group)
