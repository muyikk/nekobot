"""Chat subpackage."""
from nbot.commands.chat.tts import handle_tts
from nbot.commands.chat.del_message import handle_del_message
from nbot.commands.chat.translate import handle_translate
from nbot.commands.chat.fortune import handle_fortune
from nbot.commands.chat.remind import handle_remind, handle_precise_remind
from nbot.commands.chat.task import (
    handle_smtp_config_command,
    handle_task,
    handle_list_tasks,
    handle_cancel_tasks,
)

__all__ = [
    "handle_tts",
    "handle_del_message",
    "handle_translate",
    "handle_fortune",
    "handle_remind",
    "handle_precise_remind",
    "handle_smtp_config_command",
    "handle_task",
    "handle_list_tasks",
    "handle_cancel_tasks",
]
