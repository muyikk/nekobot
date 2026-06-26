"""
屏幕基类 - BaseScreen 抽象类
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from rich.console import Console
from rich.layout import Layout

if TYPE_CHECKING:
    from ..app import CLIApp

from ..components.layout import Header, Footer


class BaseScreen(ABC):
    """屏幕基类"""

    def __init__(self, app: "CLIApp"):
        self.app = app
        self.console = Console()
        self.header = Header()
        self.footer = Footer()
        self.layout = Layout()
        self.name = "base"

    @abstractmethod
    def build_layout(self) -> Layout:
        """构建布局"""
        pass

    @abstractmethod
    def handle_input(self, key: str) -> bool:
        """处理输入，返回是否继续运行"""
        pass

    @abstractmethod
    def update(self):
        """更新屏幕内容"""
        pass

    def render(self) -> Layout:
        """渲染屏幕"""
        return self.build_layout()
