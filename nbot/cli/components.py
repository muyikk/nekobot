"""
CLI 界面组件 - 向后兼容 shim
原始内容已拆分到 nbot/cli/components/ 子包中。
"""

from nbot.cli.components.input import Message, InputBox, LoadingSpinner
from nbot.cli.components.layout import Header, Footer, Sidebar
from nbot.cli.components.panels import (
    MessagePanel,
    ToolPanel,
    SessionPanel,
    ConfigPanel,
    HelpPanel,
)

__all__ = [
    "Message",
    "InputBox",
    "LoadingSpinner",
    "Header",
    "Footer",
    "Sidebar",
    "MessagePanel",
    "ToolPanel",
    "SessionPanel",
    "ConfigPanel",
    "HelpPanel",
]
