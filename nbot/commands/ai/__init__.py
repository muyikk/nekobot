"""
AI 命令子包

提供 AI 增强命令的注册和处理。
"""

from nbot.commands.ai.registry import register_ai_commands
from nbot.commands.ai.utils import (
    get_group_history_items,
    history_items_to_text,
)

__all__ = [
    "register_ai_commands",
    "get_group_history_items",
    "history_items_to_text",
]
