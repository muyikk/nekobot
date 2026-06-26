"""
CCStyleCLI 核心类 - Claude Code 风格的 CLI 主类
包含初始化、AI 调用、流式响应处理、主循环和聊天消息处理。
"""

import os
import sys
import json
import uuid
import copy
import shutil
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional

from rich.console import Console
from rich.text import Text

from nbot.cli.completer import (
    CommandCompleter,
    PROMPT_TOOLKIT_AVAILABLE,
    _silence_cli_loggers,
)
from nbot.cli.styles import (
    print_welcome,
    render_input_box,
    show_input_hint,
    show_command_candidates,
    render_inline_thinking,
    render_tool_call_and_result,
    display_user_message,
    print_footer,
)
from nbot.cli.markdown import render_markdown, render_markdown_to_text
from nbot.cli.cc_ai import call_ai, process_stream_response
from nbot.cli.cc_utils import (
    get_tool_definitions,
    get_all_tool_names,
    execute_tool_fn,
    process_file_references,
    resolve_file_path,
    load_models,
    get_current_model,
    set_active_model,
    load_tools,
    load_sessions,
    save_session,
    expand_messages_for_ai,
    extract_turn_tool_history,
    open_file,
)
from nbot.cli.cc_commands import handle_command
from nbot.cli.cc_personality import (
    get_current_personality,
    show_personality,
    switch_personality,
    apply_personality,
    apply_personality_to_session,
    reset_personality_to_default,
    get_personality_presets,
)

try:
    from nbot.core import build_cli_session_id
except ImportError:

    def build_cli_session_id():
        return f"cli_{uuid.uuid4().hex}"


_silence_cli_loggers()


class CCStyleCLI:
    """Claude Code 风格的 CLI - 简化同步版本"""

    # 命令定义
    COMMANDS = {
        "quit": {"desc": "退出CLI", "aliases": ["exit", "q"]},
        "clear": {"desc": "清屏", "aliases": []},
        "model": {"desc": "切换模型", "aliases": []},
        "models": {"desc": "列出所有模型", "aliases": []},
        "tools": {"desc": "列出可用工具", "aliases": []},
        "sessions": {"desc": "列出最近会话", "aliases": []},
        "thinking": {"desc": "切换思考过程显示", "aliases": []},
        "reset": {"desc": "重置当前会话", "aliases": []},
        "new": {"desc": "创建新会话", "aliases": ["n"]},
        "help": {"desc": "显示帮助信息", "aliases": ["h", "?"]},
        "memory": {"desc": "查看记忆列表", "aliases": ["mem"]},
        "knowledge": {"desc": "查看知识库", "aliases": ["kb", "know"]},
        "personality": {"desc": "查看/切换人格", "aliases": ["persona", "p"]},
        "tasks": {"desc": "查看定时任务", "aliases": ["task"]},
        "workflows": {"desc": "查看工作流", "aliases": ["flow", "wf"]},
        "config": {"desc": "查看系统配置", "aliases": ["cfg"]},
        "status": {"desc": "查看系统状态", "aliases": ["st"]},
    }

    def __init__(self):
        self.console = Console()
        self.running = True
        self.session_id = None
        self.messages = []
        self.current_model_id = None
        self.available_models = []
        self.show_thinking = True
        self.max_tool_iterations = 10
        self.current_path = os.getcwd()
        self.interrupt_requested = False

        # 消息队列
        self.message_queue = []
        self.queue_lock = threading.Lock()
        self.ai_processing = False

        # 确保数据目录存在
        os.makedirs(os.path.join("data", "web"), exist_ok=True)

        # 加载可用模型
        load_models(self)

        # 初始化prompt_toolkit session（如果可用）
        self.prompt_session = None
        if PROMPT_TOOLKIT_AVAILABLE:
            try:
                workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                from prompt_toolkit import PromptSession

                self.prompt_session = PromptSession(
                    completer=CommandCompleter(self.COMMANDS, workspace_root),
                    complete_while_typing=True,
                )
            except Exception:
                pass

    # 委托方法 - 资源/工具相关
    def _get_tool_definitions(self) -> List[Dict]:
        return get_tool_definitions()

    def _get_all_tool_names(self) -> List[str]:
        return get_all_tool_names()

    def _execute_tool(self, tool_name: str, arguments: Dict) -> Dict:
        return execute_tool_fn(tool_name, arguments, self.session_id)

    def _process_file_references(self, message: str) -> tuple:
        return process_file_references(message, self.console)

    def _resolve_file_path(self, filepath: str, workspace_root: str = None) -> str:
        if workspace_root is None:
            workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return resolve_file_path(filepath, workspace_root)

    # 委托方法 - 模型管理
    def _load_models(self) -> None:
        load_models(self)

    def _get_current_model(self) -> Optional[Dict]:
        return get_current_model(self)

    def _set_active_model(self, model_id: str) -> None:
        set_active_model(self, model_id)

    def load_tools(self) -> list:
        return load_tools()

    def load_sessions(self) -> list:
        return load_sessions()

    # 委托方法 - 显示/渲染
    def _get_ascii_art_two_lines(self) -> str:
        from nbot.cli.styles import get_ascii_art_two_lines

        return get_ascii_art_two_lines()

    def print_welcome(self) -> None:
        print_welcome(self.console, self)

    def _render_input_box(self, mode: str = "chat") -> str:
        return render_input_box(self, mode)

    def _show_input_hint(self) -> None:
        show_input_hint(self.console, self)

    def _show_command_candidates(self, partial: str) -> None:
        show_command_candidates(self.console, self, partial)

    def _render_inline_thinking(self, thinking: str) -> None:
        render_inline_thinking(self.console, thinking, self.show_thinking)

    def _render_tool_call_and_result(
        self, tool_name: str, arguments: Dict, result: Dict, success: bool
    ) -> None:
        render_tool_call_and_result(self.console, tool_name, arguments, result, success)

    def _display_user_message(self, content: str, attachments: list = None) -> None:
        display_user_message(self.console, content, attachments)

    def _render_markdown(self, content: str) -> None:
        render_markdown(self.console, content)

    def _render_markdown_to_text(self, content: str) -> Text:
        return render_markdown_to_text(content)

    def _print_footer(self) -> None:
        print_footer(self.console, self)

    # 委托方法 - 人格管理
    def _get_current_personality(self) -> Dict:
        return get_current_personality(self)

    def _show_personality(self, args: str = "") -> None:
        show_personality(self, args)

    def _apply_personality_to_session(self, personality: Dict) -> None:
        apply_personality_to_session(self, personality)

    # 委托方法 - 命令处理
    def _handle_command(self, cmd_line: str) -> bool:
        return handle_command(self, cmd_line)

    # 委托方法 - 工具历史
    def _expand_messages_for_ai(self, messages: List[Dict]) -> List[Dict]:
        return expand_messages_for_ai(messages)

    def _extract_turn_tool_history(
        self, tool_messages: List[Dict], initial_message_count: int
    ) -> List[Dict]:
        return extract_turn_tool_history(tool_messages, initial_message_count)

    # 委托方法 - 文件打开
    def _open_file(self, file_path: str) -> bool:
        return open_file(file_path)

    # 委托方法 - 会话保存
    def save_session(self) -> None:
        save_session(self)

    def _get_input(self) -> tuple:
        """
        获取用户输入，支持命令候选和动态效果
        返回: (输入内容, 是否打断)
        """
        self._show_input_hint()

        prompt = self._render_input_box("chat")
        line_char = "─"
        width = shutil.get_terminal_size().columns
        top_line = f"\033[90m{line_char * width}\033[0m\n"
        bottom_line = f"\033[90m{line_char * width}\033[0m\n"

        sys.stdout.write(top_line)
        sys.stdout.flush()

        try:
            if self.prompt_session:
                try:
                    from prompt_toolkit.formatted_text import ANSI

                    user_input = self.prompt_session.prompt(ANSI(f"{prompt} ")).strip()
                except Exception:
                    user_input = self.console.input(f"{prompt} ").strip()
            else:
                user_input = self.console.input(f"{prompt} ").strip()

            sys.stdout.write(bottom_line)
            sys.stdout.flush()
            return user_input, False

        except (KeyboardInterrupt, EOFError):
            sys.stdout.write(bottom_line)
            sys.stdout.flush()
            return "", True

    def _process_stream_response(self, response, supports_tools: bool) -> Dict:
        """处理流式响应，实时渲染 Markdown（委托到 cc_ai）"""
        return process_stream_response(self.console, response, supports_tools, self)

    def _call_ai(self, messages: List[Dict]) -> Dict[str, Any]:
        """调用AI，支持工具调用和多轮思考（委托到 cc_ai）"""
        return call_ai(self.console, self, messages)

    def run(self):
        """运行CLI - 直接进入输入模式，加载最新会话"""
        if not self.session_id:
            sessions = self.load_sessions()
            if sessions:
                sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
                latest_session = sessions[0]
                self.session_id = latest_session.get("id")
                self.messages = latest_session.get("messages", [])

                system_prompt = latest_session.get("system_prompt", "")
                has_system_msg = any(msg.get("role") == "system" for msg in self.messages)
                if system_prompt and not has_system_msg:
                    self.messages.insert(
                        0,
                        {
                            "role": "system",
                            "content": system_prompt,
                            "timestamp": datetime.now().isoformat(),
                        },
                    )
            else:
                self.session_id = build_cli_session_id()
                self.messages = []

        self.console.clear()
        self.print_welcome()

        if self.messages:
            display_limit = 10
            total = len(self.messages)
            if total > display_limit:
                self.console.print(
                    f"[dim]Showing latest {display_limit} of {total} messages[/dim]\n"
                )
            else:
                self.console.print(f"[dim]Loaded {total} messages from history[/dim]\n")
            self._display_history(limit=display_limit)

        # 主循环 - 同步处理
        while self.running:
            try:
                with self.queue_lock:
                    if self.message_queue and not self.ai_processing:
                        msg = self.message_queue.pop(0)
                        self._process_chat_message(msg)
                        continue

                self._print_footer()

                user_input, interrupted = self._get_input()

                if interrupted:
                    self.running = False
                    break

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    self._handle_command(user_input[1:])
                    continue
                else:
                    with self.queue_lock:
                        if self.ai_processing:
                            self.message_queue.append(user_input)
                            self.console.print(
                                f"[dim][message queued: {len(self.message_queue)}][/dim]"
                            )
                            continue

                    self._process_chat_message(user_input)

            except KeyboardInterrupt:
                if self.ai_processing and not self.interrupt_requested:
                    self.interrupt_requested = True
                    self.console.print("\n[dim][interrupting...][/dim]")
                else:
                    self.running = False
                    break
            except Exception as e:
                self.console.print(f"[red]error: {e}[/red]")

        self.save_session()
        self.console.print("\n[dim]Goodbye! 🐱[/dim]")

    def _display_history(self, limit: int = 10, skip_last: bool = False):
        """显示历史消息"""
        recent_messages = self.messages[-limit:] if len(self.messages) > limit else self.messages

        if skip_last and len(recent_messages) > 0:
            recent_messages = recent_messages[:-1]

        for msg in recent_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            original_content = msg.get("original_content", content)
            attachments = msg.get("attachments", [])

            if not content:
                continue

            if role == "user":
                self._display_user_message(original_content, attachments)
            elif role == "assistant":
                self._render_markdown(content)
                self.console.print()

    def _process_chat_message(self, message: str):
        """处理聊天消息（同步版本）"""
        with self.queue_lock:
            self.ai_processing = True

        self.interrupt_requested = False

        original_message = message
        processed_message, attachments = self._process_file_references(message)

        if attachments:
            for att in attachments:
                if att.get("type") == "file":
                    sys.stdout.write(
                        f"[dim]📎 {att.get('relative_path', att.get('source'))}[/dim]\n"
                    )
                    sys.stdout.flush()

        self.messages.append({
            "role": "user",
            "content": processed_message,
            "original_content": original_message,
            "attachments": attachments,
            "timestamp": datetime.now().isoformat(),
        })

        result = self._call_ai(self.messages)

        content = result.get("content", "")
        interrupted = result.get("interrupted", False)
        tool_call_history = result.get("tool_call_history", [])

        assistant_message = {
            "role": "assistant",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        if tool_call_history:
            assistant_message["tool_call_history"] = tool_call_history
        self.messages.append(assistant_message)

        if interrupted:
            self.console.print("[dim][interrupted][/dim]")

        self.save_session()

        with self.queue_lock:
            self.ai_processing = False


def main():
    """CLI入口"""
    cli = CCStyleCLI()
    cli.run()


if __name__ == "__main__":
    main()
