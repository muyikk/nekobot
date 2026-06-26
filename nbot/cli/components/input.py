"""CLI 输入相关组件 - Message、InputBox、LoadingSpinner"""
from datetime import datetime
from typing import Dict, Any
from dataclasses import dataclass

from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED
from rich.progress import Progress, SpinnerColumn, TextColumn


@dataclass
class Message:
    """消息数据类"""

    role: str  # 'user', 'assistant', 'system', 'tool'
    content: str
    timestamp: datetime = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}


class InputBox:
    """输入框组件"""

    def __init__(self, placeholder: str = "输入消息..."):
        self.placeholder = placeholder
        self.content = ""
        self.cursor_position = 0

    def render(self) -> Panel:
        """渲染输入框"""
        if self.content:
            display_text = Text(f"> {self.content}", style="white")
            # 添加光标
            display_text.append("█", style="bold cyan")
        else:
            display_text = Text(f"> {self.placeholder}", style="dim")
            display_text.append("█", style="bold cyan")

        return Panel(display_text, box=ROUNDED, style="green", padding=(0, 1), height=3)

    def set_content(self, content: str):
        """设置内容"""
        self.content = content
        self.cursor_position = len(content)

    def append_char(self, char: str):
        """追加字符"""
        self.content = (
            self.content[: self.cursor_position] + char + self.content[self.cursor_position :]
        )
        self.cursor_position += 1

    def backspace(self):
        """退格"""
        if self.cursor_position > 0:
            self.content = (
                self.content[: self.cursor_position - 1] + self.content[self.cursor_position :]
            )
            self.cursor_position -= 1

    def delete(self):
        """删除"""
        if self.cursor_position < len(self.content):
            self.content = (
                self.content[: self.cursor_position] + self.content[self.cursor_position + 1 :]
            )

    def move_cursor_left(self):
        """光标左移"""
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def move_cursor_right(self):
        """光标右移"""
        if self.cursor_position < len(self.content):
            self.cursor_position += 1

    def clear(self):
        """清空"""
        self.content = ""
        self.cursor_position = 0

    def get_content(self) -> str:
        """获取内容"""
        return self.content


class LoadingSpinner:
    """加载动画组件"""

    def __init__(self, message: str = "加载中..."):
        self.message = message
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        )
        self.task = None

    def start(self):
        """开始加载动画"""
        self.task = self.progress.add_task(self.message, total=None)
        return self.progress

    def stop(self):
        """停止加载动画"""
        if self.task is not None:
            self.progress.stop()
