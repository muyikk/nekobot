"""Chat delete message command."""
import json

from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.services.chat_service import group_messages, user_messages, delete_session_workspace
from nbot.utils.message_sender import send_text
from nbot.commands.state import admin


@register_command("/del_message", "/dm", help_text="/del_message 或者 /dm -> 删除对话记录(仅群admin)", category="3")
async def handle_del_message(msg, is_group=True):
    if (str(msg.user_id) not in admin) and is_group:
        await msg.reply(text="你没有权限喵~")
        return

    if is_group:
        try:
            del group_messages[str(msg.group_id)]
        except KeyError:
            await msg.reply(text="你没有对话记录喵~")
            return
        with open("saved_message/group_messages.json", "w", encoding="utf-8") as f:
            json.dump(group_messages, f, ensure_ascii=False, indent=4)
        delete_session_workspace(group_id=str(msg.group_id), group_user_id=str(msg.user_id))
        await msg.reply(text="主人要离我而去了吗？呜呜呜……好吧，那我们以后再见喵~")
    else:
        try:
            del user_messages[str(msg.user_id)]
        except KeyError:
            await bot.api.post_private_msg(msg.user_id, text="你没有对话记录喵~")
            return
        with open("saved_message/user_messages.json", "w", encoding="utf-8") as f:
            json.dump(user_messages, f, ensure_ascii=False, indent=4)
        delete_session_workspace(user_id=str(msg.user_id))
        await bot.api.post_private_msg(msg.user_id, text="主人要离我而去了吗？呜呜呜……好吧，那我们以后再见喵~")
