"""@all group toggle handler."""

from __future__ import annotations

from typing import Any

from nbot.commands.state import admin, at_all_group
from nbot.commands.shared.data_persistence import write_at_all_group


async def handle_at_all_group(msg: Any, is_group: bool = True) -> None:
    """Toggle @all mention detection for the current group.

    Args:
        msg: The ncatbot message object.
        is_group: Whether the message came from a group.
    """
    if is_group:
        if str(msg.user_id) not in admin:
            await msg.reply(text="只有管理员才能使用该命令喵~")
            return
        if str(msg.group_id) in at_all_group:
            at_all_group.remove(str(msg.group_id))
            write_at_all_group()
            await msg.reply(text="关闭成功喵~")
            return
        at_all_group.append(str(msg.group_id))
        write_at_all_group()
        await msg.reply(text="开启成功喵~")
    else:
        # Lazy import bot to avoid circular
        from nbot.commands import bot
        await bot.api.post_private_msg(msg.user_id, text="请在群聊中使用该命令")
