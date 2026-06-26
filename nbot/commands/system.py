"""System commands."""
import os
import sys

from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.utils.message_sender import send_text
from nbot.commands.state import admin


@register_command("/agree", help_text="/agree -> 同意好友请求(admin)", category="4", admin_show=True)
async def handle_agree(msg, is_group=True):
    if str(msg.user_id) not in admin:
        reply = "你没有权限喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    if not is_group:
        await bot.api.set_friend_add_request(flag=msg.user_id, approve=True, remark=msg.user_id)
        await bot.api.post_private_msg(msg.user_id, text="已同意好友请求喵~")
    else:
        await bot.api.set_friend_add_request(flag=msg.user_id, approve=True, remark=msg.user_id)
        await msg.reply(text="已同意好友请求喵~")


@register_command("/restart", help_text="/restart -> 重启机器人(admin)", category="4", admin_show=True)
async def handle_restart(msg, is_group=True):
    if str(msg.user_id) not in admin:
        await send_text(msg, "只有管理员才能重启机器人喵~", is_group=is_group)
        return
    reply_text = "正在重启喵~"
    await send_text(msg, reply_text, is_group=is_group)
    os.execv(sys.executable, [sys.executable] + sys.argv)


@register_command("/shutdown", help_text="/shutdown -> 关闭机器人(admin)", category="4", admin_show=True)
async def handle_shutdown(msg, is_group=True):
    if str(msg.user_id) not in admin:
        await send_text(msg, "只有管理员才能关闭机器人喵~", is_group=is_group)
        return
    reply_text = "主人，下次再见喵~"
    await send_text(msg, reply_text, is_group=is_group)
    sys.exit()
