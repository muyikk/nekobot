"""
NekoBot CLI 模块 - 类似Claude Code的命令行界面

子模块：
- app.py: CLIApp 主类
- cc_app.py: CCStyleCLI 主类（Claude Code 风格）
- simple_app.py: SimpleCLI 主类（简化版）
- simple_handlers.py: SimpleCLI 显示与交互处理器
- completer.py: 命令补全器
- styles.py: 显示样式与渲染
- markdown.py: Markdown 渲染器
- cc_utils.py: 工具执行与实用函数
- cc_commands.py: 命令处理器
- cc_personality.py: 人格管理
- screens/: 屏幕类子包
- components/: UI 组件子包
"""

from .app import CLIApp
from .cc_app import CCStyleCLI
from .screens import MainScreen, ChatScreen, ToolsScreen, ConfigScreen, HelpScreen, SessionsScreen
from .components import Header, Footer, Sidebar, MessagePanel, InputBox, Message

__all__ = [
    "CLIApp",
    "CCStyleCLI",
    "MainScreen",
    "ChatScreen",
    "ToolsScreen",
    "ConfigScreen",
    "HelpScreen",
    "SessionsScreen",
    "Header",
    "Footer",
    "Sidebar",
    "MessagePanel",
    "InputBox",
    "Message",
]
