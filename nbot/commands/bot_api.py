"""Bot API raw command handler (/bot)."""

from __future__ import annotations

import re
from typing import Any

from nbot.commands.state import admin
from nbot.utils.message_sender import send_text


def parse_command_string(cmd_str: str) -> dict:
    """Parse a /bot.api.xxx(param=\"value\") string.

    Args:
        cmd_str: Raw command text.

    Returns:
        Dict with ``func`` and ``params`` keys, or ``None`` on parse failure.
    """
    func_match = re.match(r"^/([\w.]+)\((.*)\)$", cmd_str)
    if not func_match:
        return None

    func_name = func_match.group(1)
    params_str = func_match.group(2)

    params = {}
    for param in re.finditer(r"([\w.]+)\s*=\s*\"([^\"]*)\"", params_str):
        key = param.group(1)
        value = param.group(2)
        params[key] = value

    return {"func": func_name, "params": params}


async def handle_api(msg: Any, is_group: bool = True) -> None:
    """Execute a raw bot.api method call.

    Args:
        msg: The ncatbot message object.
        is_group: Whether the message came from a group.
    """
    parsed = parse_command_string(msg.raw_message)
    command = parsed.get("func", "")
    params = parsed.get("params", {})
    if not command:
        return
    if str(msg.user_id) not in admin:
        text = "没有权限喵~"
        await send_text(msg, text, is_group=is_group)
        return

    # Lazy import bot to avoid circular
    from nbot.commands import bot
    try:
        func = getattr(bot.api, command.split(".")[-1])
        res = await func(**params)
        res = str(res)
        await send_text(msg, res, is_group=is_group)
    except Exception as e:
        text = f"执行命令时出错喵~：{e}"
        await send_text(msg, text, is_group=is_group)
