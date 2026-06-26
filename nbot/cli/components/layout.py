"""CLI 界面布局组件 - Header、Footer、Sidebar"""
from datetime import datetime
from typing import List, Dict, Any, Optional

from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.box import HEAVY, ROUNDED


class Header:
    """顶部标题栏组件"""

    def __init__(self, title: str = "NekoBot CLI", subtitle: str = ""):
        self.title = title
        self.subtitle = subtitle

    def render(self, current_screen: str = "main") -> Panel:
        """渲染标题栏"""
        # 构建标题文本
        title_text = Text()
        title_text.append("🐱 ", style="bold yellow")
        title_text.append(self.title, style="bold cyan")

        if self.subtitle:
            title_text.append(f" | {self.subtitle}", style="dim")

        # 当前屏幕指示器
        screen_indicators = {
            "main": "[cyan]●[/cyan] 主页",
            "chat": "[green]●[/green] 聊天",
            "tools": "[blue]●[/blue] 工具",
            "config": "[magenta]●[/magenta] 配置",
            "sessions": "[yellow]●[/yellow] 会话",
        }

        right_text = Text()
        for screen, label in screen_indicators.items():
            if screen == current_screen:
                right_text.append(f"{label}  ", style="bold")
            else:
                right_text.append(
                    f"{label.replace('[cyan]', '').replace('[green]', '').replace('[blue]', '').replace('[magenta]', '').replace('[yellow]', '').replace('[/cyan]', '').replace('[/green]', '').replace('[/blue]', '').replace('[/magenta]', '').replace('[/yellow]', '')}  ",
                    style="dim",
                )

        # 时间显示
        time_str = datetime.now().strftime("%H:%M:%S")
        right_text.append(f"| {time_str}", style="dim")

        content = Table.grid(expand=True)
        content.add_column(justify="left", ratio=1)
        content.add_column(justify="right")
        content.add_row(title_text, right_text)

        return Panel(content, box=HEAVY, style="cyan", padding=(0, 1), height=3)


class Footer:
    """底部状态栏组件"""

    def __init__(self):
        self.status = "就绪"
        self.shortcuts = [
            ("Ctrl+C", "退出"),
            ("Tab", "切换"),
            ("Enter", "确认"),
            ("/", "命令"),
            ("?", "帮助"),
        ]

    def render(self) -> Panel:
        """渲染底部状态栏"""
        # 快捷键显示
        shortcut_text = Text()
        for key, desc in self.shortcuts:
            shortcut_text.append(f"[{key}]", style="bold cyan")
            shortcut_text.append(f"{desc}  ", style="dim")

        # 状态显示
        status_text = Text()
        status_text.append("状态: ", style="dim")
        status_text.append(self.status, style="green" if "就绪" in self.status else "yellow")

        content = Table.grid(expand=True)
        content.add_column(justify="left", ratio=1)
        content.add_column(justify="right")
        content.add_row(shortcut_text, status_text)

        return Panel(content, box=HEAVY, style="dim", padding=(0, 1), height=3)

    def set_status(self, status: str):
        """设置状态文本"""
        self.status = status


class Sidebar:
    """侧边栏组件"""

    def __init__(self, width: int = 30):
        self.width = width
        self.items: List[Dict[str, Any]] = []
        self.selected_index = 0

    def set_items(self, items: List[Dict[str, Any]]):
        """设置侧边栏项目"""
        self.items = items

    def select_next(self):
        """选择下一个"""
        if self.items:
            self.selected_index = (self.selected_index + 1) % len(self.items)

    def select_previous(self):
        """选择上一个"""
        if self.items:
            self.selected_index = (self.selected_index - 1) % len(self.items)

    def get_selected(self) -> Optional[Dict[str, Any]]:
        """获取当前选中的项目"""
        if self.items and 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return None

    def render(self, title: str = "菜单") -> Panel:
        """渲染侧边栏"""
        content = Text()

        for i, item in enumerate(self.items):
            icon = item.get("icon", "•")
            label = item.get("label", "Unknown")
            desc = item.get("description", "")

            if i == self.selected_index:
                # 选中项高亮
                content.append(f" {icon} ", style="bold cyan")
                content.append(f"{label}", style="bold white on cyan")
                if desc:
                    content.append(f" - {desc}", style="dim")
                content.append("\n")
            else:
                content.append(f" {icon} ", style="dim")
                content.append(f"{label}", style="white")
                if desc:
                    content.append(f" - {desc}", style="dim")
                content.append("\n")

        return Panel(
            content,
            title=f"[bold]{title}[/bold]",
            box=ROUNDED,
            style="cyan",
            width=self.width,
            padding=(1, 1),
        )
