from __future__ import annotations

import os
from typing import Any, Optional

_bot = None


def set_bot_client(bot: Any) -> None:
    """Set the shared bot client used by message sender helpers.

    Args:
        bot: The NCatBot client instance (or any object exposing ``api``).
    """
    global _bot
    _bot = bot


async def send_text(msg, text: str, is_group: bool = True, **kwargs: Any) -> None:
    """Send a text message to either a group or a private chat.

    Args:
        msg: The incoming message object (provides ``reply`` and ``user_id``).
        text: Text content to send.
        is_group: Whether ``msg`` came from a group.
        **kwargs: Extra arguments forwarded to the underlying send method.

    Raises:
        RuntimeError: If the bot client has not been set.
    """
    if _bot is None:
        raise RuntimeError("Bot client not set; call set_bot_client first")
    if is_group:
        await msg.reply(text=text, **kwargs)
    else:
        await _bot.api.post_private_msg(msg.user_id, text=text, **kwargs)


async def send_file(
    msg,
    file_path: str,
    is_group: bool = True,
    filename: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Send a file to either a group or a private chat.

    Args:
        msg: The incoming message object.
        file_path: Absolute path to the file.
        is_group: Whether ``msg`` came from a group.
        filename: Optional display filename (defaults to basename).
        **kwargs: Extra arguments forwarded to the underlying upload method.

    Raises:
        RuntimeError: If the bot client has not been set.
    """
    if _bot is None:
        raise RuntimeError("Bot client not set; call set_bot_client first")
    filename = filename or os.path.basename(file_path)
    if is_group:
        await _bot.api.post_group_file(msg.group_id, file=file_path, filename=filename, **kwargs)
    else:
        await _bot.api.upload_private_file(msg.user_id, file_path, filename)


async def reply_to(msg, text: str, is_group: bool = True, **kwargs: Any) -> None:
    """Alias for :func:`send_text`."""
    await send_text(msg, text, is_group=is_group, **kwargs)
