"""
CLI 工具与实用函数 - 工具执行、工作区操作、文件处理、模型管理、会话管理
用于 CCStyleCLI 的工具函数集合。
"""

import os
import json
import copy
import re
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional

from nbot.web.secure_store import read_secure_json, write_secure_json
from nbot.cli.cc_workspace import execute_workspace_tool

# 尝试导入工具定义
try:
    from nbot.services.tools import TOOL_DEFINITIONS, WORKSPACE_TOOL_DEFINITIONS, execute_tool

    TOOLS_AVAILABLE = True
except ImportError:
    TOOLS_AVAILABLE = False
    TOOL_DEFINITIONS = []
    WORKSPACE_TOOL_DEFINITIONS = []

# 尝试导入工具注册表
try:
    from nbot.services.tool_registry import get_all_tool_definitions as get_registered_tools

    TOOL_REGISTRY_AVAILABLE = True
except ImportError:
    TOOL_REGISTRY_AVAILABLE = False

    def get_registered_tools():
        return []


def get_tool_definitions() -> List[Dict]:
    """获取工具定义列表（包括内置工具和注册表工具）"""
    tools = []

    if TOOLS_AVAILABLE:
        tools.extend(TOOL_DEFINITIONS)

    if TOOLS_AVAILABLE and WORKSPACE_TOOL_DEFINITIONS:
        existing_names = {t.get("function", {}).get("name", "") for t in tools}
        for tool in WORKSPACE_TOOL_DEFINITIONS:
            name = tool.get("function", {}).get("name", "")
            if name and name not in existing_names:
                tools.append(tool)
                existing_names.add(name)

    if TOOL_REGISTRY_AVAILABLE:
        try:
            registered = get_registered_tools()
            existing_names = {t.get("function", {}).get("name", "") for t in tools}
            for tool in registered:
                name = tool.get("function", {}).get("name", "")
                if name and name not in existing_names:
                    tools.append(tool)
                    existing_names.add(name)
        except Exception:
            pass

    return tools


def get_all_tool_names() -> List[str]:
    """获取所有工具名称列表（用于显示）"""
    tools = get_tool_definitions()
    names = []
    for tool in tools:
        func = tool.get("function", {})
        name = func.get("name", "")
        if name:
            names.append(name)
    return names


def execute_tool_fn(tool_name: str, arguments: Dict, session_id: str = None) -> Dict:
    """执行工具"""
    if not TOOLS_AVAILABLE:
        return {"success": False, "error": "tools not available"}
    try:
        if tool_name.startswith("workspace_"):
            return execute_workspace_tool(tool_name, arguments)

        tool_context = {"session_id": session_id} if session_id else {}
        result = execute_tool(tool_name, arguments, tool_context)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def process_file_references(message: str, console=None, workspace_root: str = None) -> tuple:
    """处理消息中的 @filepath 引用，返回 (处理后的消息, 附件列表)"""
    if workspace_root is None:
        workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    attachments = []
    processed_message = message

    pattern = r"@([^\s@]+)"
    matches = list(re.finditer(pattern, message))

    for match in matches:
        filepath = match.group(1)
        start, end = match.span()

        resolved_path = resolve_file_path(filepath, workspace_root)

        if resolved_path and os.path.isfile(resolved_path):
            try:
                file_size = os.path.getsize(resolved_path)
                max_size = 100 * 1024

                if file_size > max_size:
                    if console:
                        console.print(f"[yellow]文件过大，跳过: {filepath} ({file_size} bytes)[/yellow]")
                    continue

                with open(resolved_path, "r", encoding="utf-8") as f:
                    file_content = f.read()

                rel_path = os.path.relpath(resolved_path, workspace_root)
                attachment = {
                    "type": "file",
                    "path": resolved_path,
                    "relative_path": rel_path,
                    "content": file_content,
                    "source": filepath,
                }
                attachments.append(attachment)

                file_info = f"[文件: {rel_path}]\n```\n{file_content}\n```"
                processed_message = processed_message[:start] + file_info + processed_message[end:]

                attachments[-1]["content"] = file_info
                attachments[-1]["source"] = match.group(0)

            except Exception as e:
                if console:
                    console.print(f"[red]读取文件失败: {filepath} - {str(e)}[/red]")
        else:
            if console:
                console.print(f"[yellow]文件不存在: {filepath}[/yellow]")

    return processed_message, attachments


def resolve_file_path(filepath: str, workspace_root: str) -> str:
    """解析文件路径，支持绝对路径、相对路径"""
    filepath = filepath.strip()

    if os.path.isabs(filepath):
        return filepath

    if filepath.startswith("."):
        return os.path.abspath(filepath)

    return os.path.join(workspace_root, filepath)


def load_models(cli) -> None:
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
            cli.available_models = [
                m for m in data.get("models", []) if m.get("enabled", True)
            ]
            cli.current_model_id = data.get("active_model_id")
        except Exception:
            pass


def get_current_model(cli) -> Optional[Dict]:
    """获取当前选中的模型"""
    for model in cli.available_models:
        if model.get("id") == cli.current_model_id:
            return model
    if cli.available_models:
        return cli.available_models[0]
    return None


def set_active_model(cli, model_id: str) -> None:
    """设置活动模型"""
    cli.current_model_id = model_id
    models_file = os.path.join("data", "web", "ai_models.json")
    try:
        data_dir = os.path.join("data", "web")
        data, was_plaintext = read_secure_json(models_file, data_dir, {})
        if not isinstance(data, dict):
            data = {}
        data["active_model_id"] = model_id
        write_secure_json(models_file, data_dir, data)
    except Exception as e:
        cli.console.print(f"[red]保存模型配置失败: {e}[/red]")


def load_tools() -> list:
    """加载工具列表"""
    tools_file = os.path.join("data", "web", "tools.json")
    if os.path.exists(tools_file):
        try:
            with open(tools_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def load_sessions() -> list:
    """加载会话列表"""
    sessions_file = os.path.join("data", "web", "sessions.json")
    if not os.path.exists(sessions_file):
        return []
    try:
        with open(sessions_file, "r", encoding="utf-8") as f:
            sessions_data = json.load(f)
        return list(sessions_data.values())
    except Exception:
        return []


def save_session(cli) -> None:
    """保存当前会话"""
    if not cli.session_id or not cli.messages:
        return
    try:
        sessions_file = os.path.join("data", "web", "sessions.json")
        sessions = {}
        if os.path.exists(sessions_file):
            with open(sessions_file, "r", encoding="utf-8") as f:
                sessions = json.load(f)

        session_name = "CLI Session"
        for msg in cli.messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if len(content) > 30:
                    content = content[:30] + "..."
                session_name = content
                break

        system_prompt = ""
        for msg in cli.messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
                break

        session_data = {
            "id": cli.session_id,
            "name": session_name,
            "type": "cli",
            "messages": [],
            "system_prompt": system_prompt,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        for i, msg in enumerate(cli.messages):
            stored_message = copy.deepcopy(msg)
            stored_message.setdefault("id", str(i))
            stored_message.setdefault("timestamp", datetime.now().isoformat())
            stored_message.setdefault(
                "sender", "user" if stored_message.get("role") == "user" else "AI"
            )
            stored_message.setdefault("source", "cli")
            stored_message.setdefault("session_id", cli.session_id)
            session_data["messages"].append(stored_message)

        sessions[cli.session_id] = session_data
        os.makedirs(os.path.dirname(sessions_file), exist_ok=True)
        with open(sessions_file, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def expand_messages_for_ai(messages: List[Dict]) -> List[Dict]:
    """展开会话中隐藏保存的工具历史，供后续请求继续使用。"""
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


def extract_turn_tool_history(tool_messages: List[Dict], initial_message_count: int) -> List[Dict]:
    """只提取当前轮新增的 assistant/tool 历史。"""
    return [
        copy.deepcopy(msg)
        for msg in tool_messages[initial_message_count:]
        if msg.get("role") in ("assistant", "tool")
    ]


def open_file(file_path: str) -> bool:
    """打开文件，返回是否成功"""
    try:
        if sys.platform == "win32":
            os.startfile(file_path)
        elif sys.platform == "darwin":
            import subprocess

            subprocess.run(["open", file_path], check=True)
        else:
            import subprocess

            subprocess.run(["xdg-open", file_path], check=True)
        return True
    except Exception:
        return False
