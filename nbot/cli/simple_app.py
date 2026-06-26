"""
NekoBot CLI - 简化版命令行界面核心
包含 SimpleCLI 类的初始化、模型管理、会话管理、AI 调用、聊天模式与主循环。
"""

import os
import json
import uuid
import requests
import copy
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from rich.console import Console
from rich.markdown import Markdown
from nbot.web.secure_store import read_secure_json, write_secure_json

# 尝试导入pyfiglet用于ASCII艺术字
try:
    from pyfiglet import Figlet

    PYFIGLET_AVAILABLE = True
except ImportError:
    PYFIGLET_AVAILABLE = False

# 导入项目核心模块
try:
    from nbot.services.tools import TOOL_DEFINITIONS, execute_tool

    TOOLS_AVAILABLE = True
except ImportError:
    TOOLS_AVAILABLE = False
    TOOL_DEFINITIONS = []

try:
    from nbot.core import build_cli_session_id
except ImportError:

    def build_cli_session_id():
        return f"cli_{uuid.uuid4().hex}"


def _silence_cli_loggers():
    """在 CLI 模式下屏蔽所有常见日志输出。"""
    logger_names = [
        "",
        "nbot",
        "werkzeug",
        "urllib3",
        "requests",
        "socketio",
        "engineio",
        "apscheduler",
    ]
    for name in logger_names:
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL + 1)
        logger.propagate = False
        for handler in logger.handlers:
            handler.setLevel(logging.CRITICAL + 1)


_silence_cli_loggers()


class SimpleCLI:
    """简化版CLI - 使用简单的输入循环"""

    def __init__(self):
        self.console = Console()
        self.running = True
        self.current_screen = "main"
        self.session_id = None
        self.messages = []
        self.current_model_id = None
        self.available_models = []
        self.show_thinking = True  # 是否显示思考过程
        self.max_tool_iterations = 10  # 最大工具调用轮数

        # 确保数据目录存在
        os.makedirs(os.path.join("data", "web"), exist_ok=True)

        # 加载可用模型
        self._load_models()
        # 注册显示和交互方法
        from nbot.cli.simple_handlers import register_handlers

        register_handlers(self)

    def _load_models(self):
        """加载可用模型列表"""
        models_file = os.path.join("data", "web", "ai_models.json")
        if os.path.exists(models_file):
            try:
                data_dir = os.path.join("data", "web")
                data, was_plaintext = read_secure_json(models_file, data_dir, {})
                if was_plaintext:
                    write_secure_json(models_file, data_dir, data)
                if not isinstance(data, dict):
                    data = {}
                self.available_models = [
                    m for m in data.get("models", []) if m.get("enabled", True)
                ]
                self.current_model_id = data.get("active_model_id")
            except Exception as e:
                self.console.print(f"[dim]加载模型配置失败: {e}[/dim]")

    def _get_current_model(self) -> Optional[Dict]:
        """获取当前选中的模型"""
        for model in self.available_models:
            if model.get("id") == self.current_model_id:
                return model
        if self.available_models:
            return self.available_models[0]
        return None

    def _set_active_model(self, model_id: str):
        """设置活动模型"""
        self.current_model_id = model_id
        models_file = os.path.join("data", "web", "ai_models.json")
        try:
            data_dir = os.path.join("data", "web")
            data, was_plaintext = read_secure_json(models_file, data_dir, {})
            if not isinstance(data, dict):
                data = {}
            data["active_model_id"] = model_id
            write_secure_json(models_file, data_dir, data)
        except Exception as e:
            self.console.print(f"[red]保存模型配置失败: {e}[/red]")

    def save_session(self):
        """保存当前会话"""
        if not self.session_id or not self.messages:
            return

        try:
            sessions_file = os.path.join("data", "web", "sessions.json")
            sessions = {}

            if os.path.exists(sessions_file):
                with open(sessions_file, "r", encoding="utf-8") as f:
                    sessions = json.load(f)

            session_name = "CLI会话"
            for msg in self.messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    if len(content) > 30:
                        content = content[:30] + "..."
                    session_name = content
                    break

            session_data = {
                "id": self.session_id,
                "name": session_name,
                "type": "cli",
                "messages": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            for i, msg in enumerate(self.messages):
                stored_message = copy.deepcopy(msg)
                stored_message.setdefault("id", str(i))
                stored_message.setdefault("timestamp", datetime.now().isoformat())
                stored_message.setdefault(
                    "sender", "user" if stored_message.get("role") == "user" else "AI"
                )
                stored_message.setdefault("source", "cli")
                stored_message.setdefault("session_id", self.session_id)
                session_data["messages"].append(stored_message)

            sessions[self.session_id] = session_data

            os.makedirs(os.path.dirname(sessions_file), exist_ok=True)
            with open(sessions_file, "w", encoding="utf-8") as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)

        except Exception as e:
            self.console.print(f"[red]保存会话失败: {e}[/red]")

    def _get_tool_definitions(self) -> List[Dict]:
        """获取工具定义列表"""
        if not TOOLS_AVAILABLE:
            return []
        return TOOL_DEFINITIONS

    def _execute_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """执行工具"""
        if not TOOLS_AVAILABLE:
            return {"success": False, "error": "工具系统未启用"}

        try:
            tool_context = {"session_id": self.session_id} if self.session_id else {}
            result = execute_tool(tool_name, arguments, tool_context)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _expand_messages_for_ai(self, messages: List[Dict]) -> List[Dict]:
        """展开隐藏保存的工具历史，保证后续请求能看到它们。"""
        expanded_messages = []
        for msg in copy.deepcopy(messages):
            hidden_tool_history = msg.pop("tool_call_history", None)
            expanded_messages.append(msg)
            if not isinstance(hidden_tool_history, list):
                continue
            for hidden_msg in hidden_tool_history:
                if not isinstance(hidden_msg, dict):
                    continue
                if hidden_msg.get("role") not in ("assistant", "tool"):
                    continue
                expanded_messages.append(copy.deepcopy(hidden_msg))
        return expanded_messages

    def _extract_turn_tool_history(
        self, tool_messages: List[Dict], initial_message_count: int
    ) -> List[Dict]:
        return [
            copy.deepcopy(msg)
            for msg in tool_messages[initial_message_count:]
            if msg.get("role") in ("assistant", "tool")
        ]

    def _call_ai_with_tools(self, messages: List[Dict]) -> Dict[str, Any]:
        """调用AI，支持工具调用和多轮思考（委托到 simple_ai）"""
        from nbot.cli.simple_ai import call_ai_with_tools

        return call_ai_with_tools(self, messages)

    def chat_mode(self):
        """聊天模式"""
        self.console.clear()
        self.print_header()

        if not self.session_id:
            self.session_id = build_cli_session_id()
            self.messages = []

        current_model = self._get_current_model()
        if current_model:
            self.console.print(
                f"[dim]当前模型: [cyan]{current_model.get('name', 'Unknown')}[/cyan][/dim]"
            )
        else:
            self.console.print("[yellow]警告：没有配置AI模型，聊天功能不可用[/yellow]")

        if TOOLS_AVAILABLE:
            self.console.print("[dim]工具支持: [green]已启用[/green] - 输入 /tools 查看可用工具[/dim]")

        self.console.print("[dim]输入 /back 返回主菜单，/help 查看帮助[/dim]")
        self.console.print()

        while True:
            try:
                from rich.prompt import Prompt

                user_input = Prompt.ask("[bold green]你[/bold green]").strip()

                if not user_input:
                    continue

                if user_input == "/back":
                    self.save_session()
                    break
                elif user_input == "/quit" or user_input == "/exit":
                    self.save_session()
                    self.running = False
                    return
                elif user_input == "/clear":
                    self.messages = []
                    self.console.print("[dim]消息已清空[/dim]")
                    continue
                elif user_input == "/help":
                    self.console.print(
                        """
[dim]可用命令：
/back - 返回主菜单
/clear - 清空消息
/help - 显示帮助
/quit - 退出CLI
/model - 切换模型
/tools - 查看可用工具
/thinking - 切换思考过程显示[/dim]
"""
                    )
                    continue
                elif user_input == "/model":
                    self._switch_model_in_chat()
                    continue
                elif user_input == "/tools":
                    self._show_tools_in_chat()
                    continue
                elif user_input == "/thinking":
                    self.show_thinking = not self.show_thinking
                    status = "开启" if self.show_thinking else "关闭"
                    self.console.print(f"[dim]思考过程显示已{status}[/dim]")
                    continue

                # 添加用户消息到历史
                self.messages.append(
                    {
                        "role": "user",
                        "content": user_input,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                # 调用AI获取回复（支持工具调用和多轮思考）
                with self.console.status("[cyan]AI思考中...[/cyan]", spinner="dots"):
                    result = self._call_ai_with_tools(self.messages)

                content = result.get("content", "")
                thinking = result.get("thinking", "")
                tool_calls = result.get("tool_calls", [])
                tool_call_history = result.get("tool_call_history", [])
                iterations = result.get("iterations", 1)

                # 显示思考过程
                if thinking and self.show_thinking:
                    self._render_thinking(thinking)

                # 显示迭代信息（如果有工具调用）
                if tool_calls:
                    self.console.print(
                        f"[dim]完成 {iterations} 轮工具调用，共 {len(tool_calls)} 个工具[/dim]"
                    )

                # 添加AI消息
                assistant_message = {
                    "role": "assistant",
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                }
                if tool_call_history:
                    assistant_message["tool_call_history"] = tool_call_history
                self.messages.append(assistant_message)

                # 显示AI回复（使用Markdown渲染）
                self.console.print("[bold cyan]🐱 NekoBot:[/bold cyan]")
                self._render_markdown(content)
                self.console.print()

                # 自动保存会话
                self.save_session()

            except (KeyboardInterrupt, EOFError):
                self.save_session()
                break

    def run(self):
        """运行CLI"""
        try:
            while self.running:
                self.console.clear()
                self.print_header()
                self.print_main_menu()

                choice = self.get_input("请选择操作")

                if choice == "0":
                    self.running = False
                elif choice == "1":
                    self.chat_mode()
                elif choice == "2":
                    self.show_sessions()
                elif choice == "3":
                    self.show_tools()
                elif choice == "4":
                    self.show_config()
                elif choice == "5":
                    self.switch_model()
                elif choice == "6":
                    self.show_help()
                elif choice.lower() in ["q", "quit", "exit"]:
                    self.running = False
                else:
                    self.console.print("[red]无效的选择，请重试[/red]")
                    import time

                    time.sleep(1)

        except KeyboardInterrupt:
            pass
        finally:
            self.save_session()
            self.console.print("\n[dim]再见！喵~ 🐱[/dim]")
