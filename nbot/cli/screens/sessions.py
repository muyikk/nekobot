"""
会话列表屏幕
"""

import os
import json
from typing import TYPE_CHECKING

from rich.layout import Layout

if TYPE_CHECKING:
    from ..app import CLIApp

from .base import BaseScreen
from ..components.layout import Sidebar
from ..components.panels import SessionPanel


class SessionsScreen(BaseScreen):
    """会话列表屏幕"""

    def __init__(self, app: "CLIApp"):
        super().__init__(app)
        self.name = "sessions"
        self.session_panel = SessionPanel()
        self.sidebar = Sidebar(width=25)

        # 设置侧边栏项目
        self.sidebar.set_items(
            [
                {"icon": "📂", "label": "打开", "action": "open"},
                {"icon": "🗑️", "label": "删除", "action": "delete"},
                {"icon": "🔄", "label": "刷新", "action": "refresh"},
                {"icon": "🔙", "label": "返回", "action": "back"},
            ]
        )

        self._load_sessions()

    def _load_sessions(self):
        """加载会话列表"""
        sessions = []
        sessions_file = os.path.join("data", "web", "sessions.json")

        if os.path.exists(sessions_file):
            try:
                with open(sessions_file, "r", encoding="utf-8") as f:
                    sessions_data = json.load(f)
                    sessions = list(sessions_data.values())
            except Exception:
                pass

        self.session_panel.set_sessions(sessions)

    def build_layout(self) -> Layout:
        """构建会话界面布局"""
        layout = Layout()

        layout.split_column(
            Layout(self.header.render(self.name), size=3),
            Layout(name="body"),
            Layout(self.footer.render(), size=3),
        )

        layout["body"].split_row(
            Layout(self.sidebar.render("操作"), size=25), Layout(self.session_panel.render())
        )

        return layout

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
                if action == "back":
                    self.app.switch_screen("main")
                elif action == "refresh":
                    self._load_sessions()
        elif key == "escape":
            self.app.switch_screen("main")
        elif key == "b":
            self.app.switch_screen("main")

        return True

    def update(self):
        """更新屏幕"""
        self._load_sessions()
