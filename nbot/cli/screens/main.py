"""
主屏幕 - 欢迎界面和导航
"""

import os
import json
from typing import TYPE_CHECKING

from rich.console import Group
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.layout import Layout
from rich import box

if TYPE_CHECKING:
    from ..app import CLIApp

from .base import BaseScreen
from ..components.layout import Sidebar
from ..components.panels import HelpPanel


class MainScreen(BaseScreen):
    """主屏幕 - 欢迎界面和导航"""

    def __init__(self, app: "CLIApp"):
        super().__init__(app)
        self.name = "main"
        self.sidebar = Sidebar(width=35)
        self.help_panel = HelpPanel()
        self.info_panel = None

        # 设置侧边栏项目
        self.sidebar.set_items(
            [
                {"icon": "💬", "label": "聊天", "description": "开始新的对话", "action": "chat"},
                {"icon": "📜", "label": "会话", "description": "查看历史会话", "action": "sessions"},
                {"icon": "🔧", "label": "工具", "description": "管理工具", "action": "tools"},
                {"icon": "⚙️", "label": "配置", "description": "系统设置", "action": "config"},
                {"icon": "❓", "label": "帮助", "description": "查看帮助", "action": "help"},
                {"icon": "🚪", "label": "退出", "description": "退出CLI", "action": "quit"},
            ]
        )

        self._load_system_info()

    def _load_system_info(self):
        """加载系统信息"""
        info = {
            "version": "1.0.0",
            "data_dir": "data/",
            "sessions_count": 0,
            "tools_count": 0,
        }

        # 加载会话数量
        sessions_file = os.path.join("data", "web", "sessions.json")
        if os.path.exists(sessions_file):
            try:
                with open(sessions_file, "r", encoding="utf-8") as f:
                    sessions = json.load(f)
                    info["sessions_count"] = len(sessions)
            except Exception:
                pass

        # 加载工具数量
        tools_file = os.path.join("data", "web", "tools.json")
        if os.path.exists(tools_file):
            try:
                with open(tools_file, "r", encoding="utf-8") as f:
                    tools = json.load(f)
                    info["tools_count"] = len(tools)
            except Exception:
                pass

        self.info = info

    def build_layout(self) -> Layout:
        """构建主界面布局"""
        layout = Layout()

        # 分割布局
        layout.split_column(
            Layout(self.header.render(self.name), size=3),
            Layout(name="body"),
            Layout(self.footer.render(), size=3),
        )

        # 主体部分分割为左右
        layout["body"].split_row(
            Layout(self.sidebar.render("导航"), size=35), Layout(name="content")
        )

        # 内容区域显示欢迎信息和快捷操作
        welcome_text = self._build_welcome_panel()
        layout["content"].update(welcome_text)

        return layout

    def _build_welcome_panel(self) -> Panel:
        """构建欢迎面板"""
        # ASCII Art Logo
        logo = Text()
        logo.append(
            """
    ╭─────────────────────────────────────╮
    │                                     │
    │   🐱 NekoBot CLI                    │
    │                                     │
    │   智能助手命令行界面                 │
    │                                     │
    ╰─────────────────────────────────────╯
        """,
            style="cyan",
        )

        # 系统信息
        info_table = Table(show_header=False, box=box.SIMPLE)
        info_table.add_column("项目", style="cyan", width=15)
        info_table.add_column("值", style="white")
        info_table.add_row("版本", self.info.get("version", "unknown"))
        info_table.add_row("数据目录", self.info.get("data_dir", "data/"))
        info_table.add_row("会话数量", str(self.info.get("sessions_count", 0)))
        info_table.add_row("工具数量", str(self.info.get("tools_count", 0)))

        # 快捷提示
        tips = Text()
        tips.append("\n快捷操作:\n", style="bold cyan")
        tips.append("  ↑/↓  - 导航菜单\n", style="dim")
        tips.append("  Enter - 确认选择\n", style="dim")
        tips.append("  /help - 显示帮助\n", style="dim")
        tips.append("  Ctrl+C - 退出\n", style="dim")

        content = Group(logo, info_table, tips)

        return Panel(
            content, title="[bold]欢迎[/bold]", box=box.ROUNDED, style="cyan", padding=(1, 2)
        )

    def handle_input(self, key: str) -> bool:
        """处理输入"""
        if key == "up":
            self.sidebar.select_previous()
        elif key == "down":
            self.sidebar.select_next()
        elif key == "enter":
            selected = self.sidebar.get_selected()
            if selected:
                action = selected.get("action")
                if action == "quit":
                    return False
                elif action == "help":
                    self.app.show_help()
                else:
                    self.app.switch_screen(action)
        elif key == "/":
            self.app.show_help()
        elif key == "q":
            return False

        return True

    def update(self):
        """更新屏幕"""
        self._load_system_info()
