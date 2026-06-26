"""Proactive chat (chatter) utilities."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

from nbot.commands.state import running, tasks
from nbot.commands.shared.data_persistence import write_running, normalize_timestamp
from nbot.utils.logger import get_logger

_log = get_logger(__name__)


async def chatter(user_id: str) -> None:
    """Send a proactive chat message to a user.

    Args:
        user_id: Target QQ user ID.
    """
    # Lazy imports to avoid circular dependencies
    from nbot.commands import bot
    from nbot.commands.state import if_tts
    from nbot.services.chat_service import chat, safe_parse_chat_response
    from nbot.services.tts import tts

    content = chat(content="现在请你根据上下文，主动和用户聊天", user_id=user_id)
    content, _ = safe_parse_chat_response(content)
    if if_tts:
        rtf = tts(content)
        await bot.api.post_private_msg(user_id, rtf=rtf)
        await bot.api.post_private_msg(user_id, text=content)
    else:
        await bot.api.post_private_msg(user_id, text=content)


async def chat_loop(user_id: str) -> None:
    """Run the proactive chat loop for a single user.

    Args:
        user_id: Target QQ user ID.
    """
    running[user_id]["state"] = True
    write_running()

    while True:
        if not running.get(user_id, {}).get("active", False):
            running[user_id]["state"] = False
            write_running()
            break

        try:
            date_time = datetime.now()
            current_time = time.time()
            last_time = running[user_id].get("last_time", 0)

            # Only run between 08:00 and 24:00
            if date_time.hour < 8 or date_time.hour >= 24:
                await asyncio.sleep(60 * 10)
                continue

            time_remaining = (
                60 * 60 * running[user_id]["interval"]
            ) - (current_time - last_time)

            if time_remaining > 0:
                await asyncio.sleep(min(time_remaining, 60 * 10))
                continue

            await chatter(user_id)
            running[user_id]["last_time"] = current_time
            write_running()
            await asyncio.sleep(60 * 60 * running[user_id]["interval"])

        except Exception as e:
            _log.error(f"主动聊天循环出错: {e}")
            await asyncio.sleep(60)


def update_user_active_chat_time(user_id: Any) -> None:
    """Bump the last-active timestamp when a user sends a message.

    Args:
        user_id: The user's QQ ID.
    """
    user_id = str(user_id)
    if user_id in running and running[user_id].get("active", False):
        running[user_id]["last_time"] = time.time()
        write_running()


def update_running(user_id: str) -> None:
    """Restart the chat loop task for a user.

    Args:
        user_id: The user's QQ ID.
    """
    if user_id in tasks:
        tasks[user_id].cancel()
        tasks[user_id] = asyncio.create_task(chat_loop(user_id))
