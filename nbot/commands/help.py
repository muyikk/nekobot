"""Help command handler."""

from __future__ import annotations

from typing import Any

from nbot.commands.state import command_handlers, admin
from nbot.utils.message_sender import send_text


async def handle_help(msg: Any, is_group: bool = True) -> None:
    """Display the help menu.

    Args:
        msg: The ncatbot message object.
        is_group: Whether the message came from a group.
    """
    command_categories = {
        "1": {"name": "漫画相关"},
        "2": {"name": "聊天设置"},
        "3": {"name": "娱乐功能"},
        "4": {"name": "系统处理"},
        "5": {"name": "群聊管理"},
        "6": {"name": "轻小说"},
        "7": {"name": "定时任务"},
        "8": {"name": "全部功能"},
    }

    # Show category detail
    if not msg.raw_message.strip().endswith("help") and not msg.raw_message.strip().endswith("h"):
        selected_category = msg.raw_message.split()[-1]
        if selected_category in command_categories:
            help_text = f"{command_categories[selected_category]['name']}命令喵~\n"
            if str(msg.user_id) in admin:
                command_categories_detail = {
                    "1": {
                        "name": "漫画相关",
                        "commands": [
                            handler.help_text
                            for handler in command_handlers.values()
                            if handler.category == "1"
                        ],
                    },
                    "2": {
                        "name": "聊天设置",
                        "commands": [
                            handler.help_text
                            for handler in command_handlers.values()
                            if handler.category == "2"
                        ],
                    },
                    "3": {
                        "name": "娱乐功能",
                        "commands": [
                            handler.help_text
                            for handler in command_handlers.values()
                            if handler.category == "3"
                        ],
                    },
                    "4": {
                        "name": "系统处理",
                        "commands": [
                            handler.help_text
                            for handler in command_handlers.values()
                            if handler.category == "4"
                        ],
                    },
                    "5": {
                        "name": "群聊管理",
                        "commands": [
                            handler.help_text
                            for handler in command_handlers.values()
                            if handler.category == "5"
                        ],
                    },
                    "6": {
                        "name": "轻小说",
                        "commands": [
                            handler.help_text
                            for handler in command_handlers.values()
                            if handler.category == "6"
                        ],
                    },
                    "7": {
                        "name": "定时任务",
                        "commands": [
                            handler.help_text
                            for handler in command_handlers.values()
                            if handler.category == "7"
                        ],
                    },
                }
                command_categories_detail["8"] = {
                    "name": "全部功能",
                    "commands": [
                        cmd
                        for category in command_categories_detail.values()
                        for cmd in category["commands"]
                    ]
                    + ["/help 或者 /h -> 查看帮助"],
                }
                for cmd_text in command_categories_detail[selected_category]["commands"]:
                    help_text += f"{cmd_text}\n"
            else:
                command_categories_detail = {
                    "1": {
                        "name": "漫画相关",
                        "commands": [
                            handler.help_text
                            for handler in command_handlers.values()
                            if handler.category == "1" and handler.admin_show == False
                        ],
                    },
                    "2": {
                        "name": "聊天设置",
                        "commands": [
                            handler.help_text
                            for handler in command_handlers.values()
                            if handler.category == "2" and handler.admin_show == False
                        ],
                    },
                    "3": {
                        "name": "娱乐功能",
                        "commands": [
                            handler.help_text
                            for handler in command_handlers.values()
                            if handler.category == "3" and handler.admin_show == False
                        ],
                    },
                    "4": {
                        "name": "系统处理",
                        "commands": [
                            handler.help_text
                            for handler in command_handlers.values()
                            if handler.category == "4" and handler.admin_show == False
                        ],
                    },
                    "5": {
                        "name": "群聊管理",
                        "commands": [
                            handler.help_text
                            for handler in command_handlers.values()
                            if handler.category == "5" and handler.admin_show == False
                        ],
                    },
                    "6": {
                        "name": "轻小说",
                        "commands": [
                            handler.help_text
                            for handler in command_handlers.values()
                            if handler.category == "6" and handler.admin_show == False
                        ],
                    },
                    "7": {
                        "name": "定时任务",
                        "commands": [
                            handler.help_text
                            for handler in command_handlers.values()
                            if handler.category == "7" and handler.admin_show == False
                        ],
                    },
                }
                command_categories_detail["8"] = {
                    "name": "全部功能",
                    "commands": [
                        cmd
                        for category in command_categories_detail.values()
                        for cmd in category["commands"]
                    ]
                    + ["/help 或者 /h -> 查看帮助"],
                }
                if len(command_categories_detail[selected_category]["commands"]) == 0:
                    help_text += "你没有权限查看当前分类的命令喵~\n"
                for cmd_text in command_categories_detail[selected_category]["commands"]:
                    help_text += f"{cmd_text}\n"

            await send_text(msg, help_text, is_group=is_group)
            return

    # Show main help menu
    help_text = "欢迎使用喵~ 请选择分类查看详细命令喵~\n"
    for num, category in command_categories.items():
        help_text += f"{num}. {category['name']}\n"

    help_text += "\n输入 /help 或者 /h 加分类编号查看详细命令，例如: /help 1"
    help_text += "\n\n 一共有" + str(len(command_handlers)) + "个命令"

    await send_text(msg, help_text, is_group=is_group)
