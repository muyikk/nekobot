"""
配置和帮助屏幕 - ConfigScreen 和 HelpScreen
"""

import os
import json
from typing import TYPE_CHECKING

from rich.layout import Layout
from nbot.web.secure_store import read_secure_json, write_secure_json

if TYPE_CHECKING:
    from ..app import CLIApp

from .base import BaseScreen
from ..components.layout import Sidebar
from ..components.panels import ConfigPanel, HelpPanel


class ConfigScreen(BaseScreen):
    """配置管理屏幕"""

    def __init__(self, app: "CLIApp"):
        super().__init__(app)
        self.name = "config"
        self.config_panel = ConfigPanel()
        self.sidebar = Sidebar(width=25)

        # 设置侧边栏项目
        self.sidebar.set_items(
            [
                {"icon": "💾", "label": "保存", "action": "save"},
                {"icon": "🔄", "label": "刷新", "action": "refresh"},
                {"icon": "🔙", "label": "返回", "action": "back"},
            ]
        )

        self._load_configs()

    def _load_configs(self):
        """加载配置"""
        configs = {
            "AI": {},
            "系统": {},
            "工具": {},
        }

        # 加载AI配置
        ai_config_file = os.path.join("data", "web", "ai_config.json")
        if os.path.exists(ai_config_file):
            try:
                data_dir = os.path.join("data", "web")
                ai_config, was_plaintext = read_secure_json(ai_config_file, data_dir, {})
                if was_plaintext:
                    write_secure_json(ai_config_file, data_dir, ai_config)
                configs["AI"] = ai_config if isinstance(ai_config, dict) else {}
            except Exception:
                pass

        # 加载系统配置
        settings_file = os.path.join("data", "web", "settings.json")
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    configs["系统"] = json.load(f)
            except Exception:
                pass

        self.config_panel.set_configs(configs)

    def build_layout(self) -> Layout:
        """构建配置界面布局"""
        layout = Layout()

        layout.split_column(
            Layout(self.header.render(self.name), size=3),
            Layout(name="body"),
            Layout(self.footer.render(), size=3),
        )

        layout["body"].split_row(
            Layout(self.sidebar.render("操作"), size=25), Layout(self.config_panel.render())
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
                    self._load_configs()
        elif key == "escape":
            self.app.switch_screen("main")
        elif key == "b":
            self.app.switch_screen("main")

        return True

    def update(self):
        """更新屏幕"""
        self._load_configs()


class HelpScreen(BaseScreen):
    """帮助屏幕"""

    def __init__(self, app: "CLIApp"):
        super().__init__(app)
        self.name = "help"
        self.help_panel = HelpPanel()

    def build_layout(self) -> Layout:
        """构建帮助界面布局"""
        layout = Layout()

        layout.split_column(
            Layout(self.header.render(self.name), size=3),
            Layout(self.help_panel.render()),
            Layout(self.footer.render(), size=3),
        )

        return layout

    def handle_input(self, key: str) -> bool:
        """处理输入"""
        if key == "escape" or key == "q" or key == "enter":
            self.app.switch_screen("main")

        return True

    def update(self):
        """更新屏幕"""
        pass
