"""Command registry and help-text utilities."""

from typing import Dict, Any

from nbot.commands.state import command_handlers


def register_command(
    *command: str,
    help_text: str = None,
    admin_show: bool = False,
    category: str = "1",
) -> Any:
    """Decorator that registers a slash-command handler.

    Args:
        *command: One or more command triggers (e.g. "/help", "/h").
        help_text: Human-readable description shown in /help.
        admin_show: Whether the command is visible only to admins.
        category: Numeric category string for grouping in /help.

    Returns:
        The decorator function.
    """

    def decorator(func: Any) -> Any:
        command_handlers[command] = func
        func.help_text = help_text
        func.admin_show = admin_show
        func.category = category
        return func

    return decorator


def get_all_help_text_for_prompt() -> str:
    """Build a flat help string of every registered command.

    Returns:
        A multi-line string with all command help_text entries.
    """
    command_categories = {
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
    command_categories["8"] = {
        "name": "全部功能",
        "commands": [
            cmd
            for category in command_categories.values()
            for cmd in category["commands"]
        ]
        + ["/help 或者 /h -> 查看帮助"],
    }
    help_text = "以下是全部命令：\n"
    for cmd_text in command_categories["8"]["commands"]:
        if cmd_text:
            help_text += f"{cmd_text}\n"
    help_text += "\n一共有" + str(len(command_handlers)) + "个命令"
    return help_text
