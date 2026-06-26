"""CLI 界面面板组件 - MessagePanel、ToolPanel、SessionPanel、ConfigPanel、HelpPanel"""
from datetime import datetime
from typing import List, Dict, Any

from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.box import ROUNDED
from rich.align import Align
from rich.console import Group


class MessagePanel:
    """消息面板组件 - 显示聊天消息"""

    def __init__(self):
        self.messages: List = []
        self.max_messages = 100

    def add_message(self, message):
        """添加消息"""
        self.messages.append(message)
        # 限制消息数量
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def clear(self):
        """清空消息"""
        self.messages = []

    def render(self) -> Panel:
        """渲染消息面板"""
        if not self.messages:
            return Panel(
                Align.center(Text("暂无消息，开始聊天吧~", style="dim")),
                title="[bold]消息[/bold]",
                box=ROUNDED,
                style="cyan",
            )

        message_texts = []

        for msg in self.messages[-20:]:  # 只显示最近20条
            time_str = msg.timestamp.strftime("%H:%M")

            if msg.role == "user":
                header = Text(f"[{time_str}] ", style="dim")
                header.append("你", style="bold green")
                content = Text(msg.content, style="white")

            elif msg.role == "assistant":
                header = Text(f"[{time_str}] ", style="dim")
                header.append("🐱 NekoBot", style="bold cyan")
                content = Text(msg.content, style="white")

            elif msg.role == "system":
                header = Text(f"[{time_str}] ", style="dim")
                header.append("系统", style="bold yellow")
                content = Text(msg.content, style="dim")

            elif msg.role == "tool":
                header = Text(f"[{time_str}] ", style="dim")
                header.append("🔧 工具", style="bold blue")
                content = Text(msg.content, style="dim")

            else:
                header = Text(f"[{time_str}] ", style="dim")
                header.append(msg.role, style="bold")
                content = Text(msg.content, style="white")

            message_texts.append(header)
            message_texts.append(content)
            message_texts.append(Text())  # 空行

        content_group = Group(*message_texts)

        return Panel(
            content_group,
            title="[bold]消息[/bold]",
            box=ROUNDED,
            style="cyan",
            padding=(1, 2),
        )


class ToolPanel:
    """工具面板组件"""

    def __init__(self):
        self.tools: List[Dict[str, Any]] = []
        self.selected_index = 0

    def set_tools(self, tools: List[Dict[str, Any]]):
        """设置工具列表"""
        self.tools = tools

    def render(self) -> Panel:
        """渲染工具面板"""
        if not self.tools:
            return Panel(
                Align.center(Text("暂无可用工具", style="dim")),
                title="[bold]工具[/bold]",
                box=ROUNDED,
                style="cyan",
            )

        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        table.add_column("名称", style="cyan", width=20)
        table.add_column("描述", style="white")
        table.add_column("状态", style="green", width=10)

        for i, tool in enumerate(self.tools):
            name = tool.get("name", "Unknown")
            description = tool.get("description", "")
            enabled = tool.get("enabled", True)

            status = "✓ 启用" if enabled else "✗ 禁用"
            status_style = "green" if enabled else "red"

            if i == self.selected_index:
                name = f"> {name}"

            table.add_row(
                Text(name, style="bold" if i == self.selected_index else ""),
                description,
                Text(status, style=status_style),
            )

        return Panel(
            table,
            title="[bold]可用工具[/bold]",
            box=ROUNDED,
            style="cyan",
            padding=(1, 1),
        )


class SessionPanel:
    """会话列表面板"""

    def __init__(self):
        self.sessions: List[Dict[str, Any]] = []
        self.selected_index = 0

    def set_sessions(self, sessions: List[Dict[str, Any]]):
        """设置会话列表"""
        self.sessions = sessions

    def render(self) -> Panel:
        """渲染会话面板"""
        if not self.sessions:
            return Panel(
                Align.center(Text("暂无会话", style="dim")),
                title="[bold]会话[/bold]",
                box=ROUNDED,
                style="cyan",
            )

        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        table.add_column("ID", style="dim", width=12)
        table.add_column("名称", style="cyan")
        table.add_column("类型", style="blue", width=10)
        table.add_column("消息数", style="green", width=8)
        table.add_column("更新时间", style="dim", width=16)

        for i, session in enumerate(self.sessions[:20]):  # 只显示前20个
            session_id = session.get("id", "")[:8]
            name = session.get("name", "未命名")
            session_type = session.get("type", "unknown")
            message_count = len(session.get("messages", []))
            updated_at = session.get("updated_at", "")

            # 格式化时间
            if updated_at:
                try:
                    dt = datetime.fromisoformat(updated_at)
                    updated_at = dt.strftime("%m-%d %H:%M")
                except Exception:
                    pass

            if i == self.selected_index:
                table.add_row(
                    Text(session_id, style="bold"),
                    Text(name, style="bold white"),
                    session_type,
                    str(message_count),
                    updated_at,
                )
            else:
                table.add_row(session_id, name, session_type, str(message_count), updated_at)

        return Panel(
            table,
            title=f"[bold]会话列表 ({len(self.sessions)})[/bold]",
            box=ROUNDED,
            style="cyan",
            padding=(1, 1),
        )


class ConfigPanel:
    """配置面板组件"""

    def __init__(self):
        self.configs: Dict[str, Any] = {}
        self.categories: List[str] = []
        self.selected_category = 0

    def set_configs(self, configs: Dict[str, Any]):
        """设置配置数据"""
        self.configs = configs
        self.categories = list(configs.keys())

    def render(self) -> Panel:
        """渲染配置面板"""
        if not self.configs:
            return Panel(
                Align.center(Text("暂无配置", style="dim")),
                title="[bold]配置[/bold]",
                box=ROUNDED,
                style="cyan",
            )

        # 创建分类标签
        tabs = Text()
        for i, cat in enumerate(self.categories):
            if i == self.selected_category:
                tabs.append(f" [{cat}] ", style="bold white on cyan")
            else:
                tabs.append(f" {cat} ", style="dim")

        # 当前分类的配置项
        current_cat = self.categories[self.selected_category] if self.categories else ""
        config_items = self.configs.get(current_cat, {})

        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        table.add_column("配置项", style="cyan", width=25)
        table.add_column("值", style="white")

        for key, value in config_items.items():
            # 截断过长的值
            value_str = str(value)
            if len(value_str) > 50:
                value_str = value_str[:50] + "..."
            table.add_row(key, value_str)

        content = Group(tabs, Text(), table)

        return Panel(
            content,
            title="[bold]系统配置[/bold]",
            box=ROUNDED,
            style="cyan",
            padding=(1, 1),
        )


class HelpPanel:
    """帮助面板组件"""

    def __init__(self):
        self.commands = {
            "/help": "显示帮助信息",
            "/quit": "退出CLI",
            "/clear": "清空屏幕",
            "/sessions": "查看会话列表",
            "/tools": "查看可用工具",
            "/config": "查看配置",
            "/chat": "进入聊天模式",
            "/back": "返回上一级",
        }

    def render(self) -> Panel:
        """渲染帮助面板"""
        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        table.add_column("命令", style="cyan", width=15)
        table.add_column("说明", style="white")

        for cmd, desc in self.commands.items():
            table.add_row(cmd, desc)

        return Panel(
            table,
            title="[bold]可用命令[/bold]",
            box=ROUNDED,
            style="cyan",
            padding=(1, 1),
        )
