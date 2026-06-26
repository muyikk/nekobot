"""
工具管理屏幕
"""

import os
import json
from typing import TYPE_CHECKING

from rich.layout import Layout

if TYPE_CHECKING:
    from ..app import CLIApp

from .base import BaseScreen
from ..components.layout import Sidebar
from ..components.panels import ToolPanel


class ToolsScreen(BaseScreen):
    """工具管理屏幕"""

    def __init__(self, app: "CLIApp"):
        super().__init__(app)
        self.name = "tools"
        self.tool_panel = ToolPanel()
        self.sidebar = Sidebar(width=25)

        # 设置侧边栏项目
        self.sidebar.set_items(
            [
                {"icon": "✓", "label": "启用", "action": "enable"},
                {"icon": "✗", "label": "禁用", "action": "disable"},
                {"icon": "🔄", "label": "刷新", "action": "refresh"},
                {"icon": "🔙", "label": "返回", "action": "back"},
            ]
        )

        self._load_tools()

    def _load_tools(self):
        """加载工具列表"""
        tools = []
        tools_file = os.path.join("data", "web", "tools.json")

        if os.path.exists(tools_file):
            try:
                with open(tools_file, "r", encoding="utf-8") as f:
                    tools = json.load(f)
            except Exception:
                pass

        self.tool_panel.set_tools(tools)

    def build_layout(self) -> Layout:
        """构建工具界面布局"""
        layout = Layout()

        layout.split_column(
            Layout(self.header.render(self.name), size=3),
            Layout(name="body"),
            Layout(self.footer.render(), size=3),
        )

        layout["body"].split_row(
            Layout(self.sidebar.render("操作"), size=25), Layout(self.tool_panel.render())
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
                    self._load_tools()
        elif key == "escape":
            self.app.switch_screen("main")
        elif key == "b":
            self.app.switch_screen("main")

        return True

    def update(self):
        """更新屏幕"""
        self._load_tools()
