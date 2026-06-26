"""
聊天屏幕
"""

import os
import json
from typing import Dict, TYPE_CHECKING
from datetime import datetime

from rich.layout import Layout

if TYPE_CHECKING:
    from ..app import CLIApp

try:
    from nbot.core import build_cli_session_id
except ImportError:
    import uuid

    def build_cli_session_id():
        return f"cli_{uuid.uuid4().hex}"

from .base import BaseScreen
from ..components.layout import Sidebar
from ..components.panels import MessagePanel
from ..components.input import InputBox, Message


class ChatScreen(BaseScreen):
    """聊天屏幕"""

    def __init__(self, app: "CLIApp"):
        super().__init__(app)
        self.name = "chat"
        self.message_panel = MessagePanel()
        self.input_box = InputBox("输入消息，按Enter发送...")
        self.sidebar = Sidebar(width=25)
        self.current_session_id = None

        # 设置侧边栏项目
        self.sidebar.set_items(
            [
                {"icon": "➕", "label": "新对话", "action": "new_chat"},
                {"icon": "📜", "label": "历史", "action": "history"},
                {"icon": "💾", "label": "保存", "action": "save"},
                {"icon": "🗑️", "label": "清空", "action": "clear"},
                {"icon": "🔙", "label": "返回", "action": "back"},
            ]
        )

        # 加载历史会话或创建新会话
        self._init_session()

    def _init_session(self):
        """初始化会话"""
        # 尝试加载最新的会话
        sessions_file = os.path.join("data", "web", "sessions.json")
        if os.path.exists(sessions_file):
            try:
                with open(sessions_file, "r", encoding="utf-8") as f:
                    sessions = json.load(f)
                    if sessions:
                        # 获取最新的会话
                        latest_session = max(
                            sessions.values(), key=lambda x: x.get("updated_at", "")
                        )
                        self.current_session_id = latest_session.get("id")
                        self._load_session_messages(latest_session)
            except Exception as e:
                print(f"加载会话失败: {e}")

        if not self.current_session_id:
            self._create_new_session()

    def _create_new_session(self):
        """创建新会话"""
        self.current_session_id = build_cli_session_id()
        self.message_panel.clear()
        self.message_panel.add_message(
            Message(
                role="system",
                content="开始新的对话，我是NekoBot，有什么可以帮助你的吗？喵~",
            )
        )

    def _load_session_messages(self, session: Dict):
        """加载会话消息"""
        self.message_panel.clear()
        messages = session.get("messages", [])
        for msg in messages:
            self.message_panel.add_message(
                Message(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    timestamp=datetime.fromisoformat(
                        msg.get("timestamp", datetime.now().isoformat())
                    ),
                )
            )

    def build_layout(self) -> Layout:
        """构建聊天界面布局"""
        layout = Layout()

        layout.split_column(
            Layout(self.header.render(self.name), size=3),
            Layout(name="body"),
            Layout(self.input_box.render(), size=3),
            Layout(self.footer.render(), size=3),
        )

        # 主体部分
        layout["body"].split_row(
            Layout(self.sidebar.render("操作"), size=25), Layout(self.message_panel.render())
        )

        return layout

    def handle_input(self, key: str) -> bool:
        """处理输入"""
        if key == "enter":
            content = self.input_box.get_content().strip()
            if content:
                if content.startswith("/"):
                    # 处理命令
                    return self._handle_command(content)
                else:
                    # 发送消息
                    self._send_message(content)
                self.input_box.clear()
        elif key == "backspace":
            self.input_box.backspace()
        elif key == "delete":
            self.input_box.delete()
        elif key == "left":
            self.input_box.move_cursor_left()
        elif key == "right":
            self.input_box.move_cursor_right()
        elif key == "up":
            self.sidebar.select_previous()
        elif key == "down":
            self.sidebar.select_next()
        elif key == "tab":
            selected = self.sidebar.get_selected()
            if selected:
                action = selected.get("action")
                if action == "back":
                    self.app.switch_screen("main")
                elif action == "new_chat":
                    self._create_new_session()
                elif action == "clear":
                    self.message_panel.clear()
                elif action == "save":
                    self._save_session()
        elif key == "escape":
            self.app.switch_screen("main")
        elif len(key) == 1:
            self.input_box.append_char(key)

        return True

    def _handle_command(self, command: str) -> bool:
        """处理命令"""
        cmd = command.lower().strip()

        if cmd == "/quit" or cmd == "/exit":
            return False
        elif cmd == "/back":
            self.app.switch_screen("main")
        elif cmd == "/clear":
            self.message_panel.clear()
        elif cmd == "/help":
            self.message_panel.add_message(
                Message(
                    role="system",
                    content="""可用命令：
/help - 显示帮助
/clear - 清空消息
/back - 返回主菜单
/quit - 退出CLI""",
                )
            )
        else:
            self.message_panel.add_message(
                Message(role="system", content=f"未知命令: {command}")
            )

        return True

    def _send_message(self, content: str):
        """发送消息"""
        # 添加用户消息
        self.message_panel.add_message(Message(role="user", content=content))

        # TODO: 调用AI服务获取回复
        # 这里先模拟一个回复
        self.message_panel.add_message(
            Message(
                role="assistant",
                content=f"收到你的消息: {content}\n\n(注意：AI回复功能需要配置API密钥才能使用)",
            )
        )

        # 保存会话
        self._save_session()

    def _save_session(self):
        """保存会话到文件"""
        try:
            sessions_file = os.path.join("data", "web", "sessions.json")
            sessions = {}

            if os.path.exists(sessions_file):
                with open(sessions_file, "r", encoding="utf-8") as f:
                    sessions = json.load(f)

            # 构建会话数据
            session_data = {
                "id": self.current_session_id,
                "name": "CLI会话",
                "type": "cli",
                "messages": [
                    {
                        "id": str(i),
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "sender": "user" if msg.role == "user" else "AI",
                        "source": "cli",
                        "session_id": self.current_session_id,
                    }
                    for i, msg in enumerate(self.message_panel.messages)
                ],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            sessions[self.current_session_id] = session_data

            # 保存到文件
            os.makedirs(os.path.dirname(sessions_file), exist_ok=True)
            with open(sessions_file, "w", encoding="utf-8") as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"保存会话失败: {e}")

    def update(self):
        """更新屏幕"""
        pass
