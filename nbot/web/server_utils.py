"""Web 服务器工具函数与共享助手。

提供模块级别的辅助函数，被多个 server mixin 共享。
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from nbot.utils.logger import get_logger

_log = get_logger(__name__)

# 尝试导入消息模块（可选）
try:
    from nbot.core import ChatResponse
    from nbot.channels.registry import get_channel_adapter
    from nbot.channels.web import WebChannelAdapter

    _MESSAGE_MODULE_AVAILABLE = True
except ImportError:
    _MESSAGE_MODULE_AVAILABLE = False
    ChatResponse = None  # type: ignore[misc,assignment]
    WebChannelAdapter = None  # type: ignore[misc,assignment]
    get_channel_adapter = None  # type: ignore[misc,assignment]


# 固定的核心指令 - 这些功能不会因为用户修改提示词而丢失
CORE_INSTRUCTIONS = """【重要】你必须严格遵循以下要求：

1. 直接回复用户的问题，不要使用任何特殊格式
2. 你的回答应该是自然的对话形式
3. 如果需要执行操作（如搜索新闻、查询天气、保存记忆等），请使用可用的工具

【工具调用规则 - 非常重要】
- 当需要使用工具时，**必须通过 tool_calls 格式调用**，不要把工具信息作为普通文本输出
- **绝对不要**输出类似 `[TOOL_CALL]` 或 `minimax:tool_call` 这样的格式
- 工具调用由系统自动处理，你只需要描述你需要执行的操作
- 工具返回结果后，用自然的语言向用户解释结果
- 如果你不确定如何调用工具，直接回答用户问题而不是尝试使用工具

【文件写入规则】
- 调用 write_file 工具写入文件内容时，每次写入的内容不宜过长（建议不超过 2000 字符）
- 如果需要写入大量内容，应该分多次调用 write_file 工具，每次写入一部分
- 例如要写入 5000 字的内容，应该分 3 次写入，每次数百到一千多字
- 不要尝试一次性写入过长的内容，这会导致写入失败

【文件处理指南】
当用户上传文件时，会显示文件元数据（类型、大小、页数等）。
- 如果需要查看文件内容，调用 workspace_parse_file 工具
- 工具返回结果后，用自然的语言向用户解释文件内容
- 不要直接返回原始JSON，要格式化和总结重要信息

【文件发送指南】
当用户要求发送文件时，调用 workspace_send_file 工具。
- 工具执行成功后，文件会自动发送给用户
- 你不需要在回复中提及文件路径或重复文件内容
- 只需简单告知用户文件已发送即可

现在你可以开始与用户对话了。"""


def _resolve_web_adapter(adapter):
    """解析并返回 Web 频道适配器实例。"""
    if adapter:
        return adapter
    try:
        if get_channel_adapter:
            web_adapter = get_channel_adapter("web")
            if web_adapter:
                return web_adapter
        return WebChannelAdapter() if WebChannelAdapter else None
    except NameError:
        return None


def _build_heartbeat_user_message(adapter, session_id: str, content: str) -> dict:
    """构建 Heartbeat 用户消息。"""
    web_adapter = _resolve_web_adapter(adapter)
    if web_adapter and hasattr(web_adapter, "build_heartbeat_user_message"):
        return web_adapter.build_heartbeat_user_message(session_id, content)
    if web_adapter:
        return web_adapter.build_message(
            role="user",
            content=f"【Heartbeat 任务】\n{content}",
            sender="system",
            conversation_id=session_id,
            metadata={
                "source": "heartbeat",
                "is_heartbeat": True,
                "hide_in_web": False,
            },
        )
    return {
        "role": "user",
        "content": f"【Heartbeat 任务】\n{content}",
        "timestamp": datetime.now().isoformat(),
        "sender": "system",
        "source": "heartbeat",
        "is_heartbeat": True,
        "hide_in_web": False,
    }


def _build_heartbeat_assistant_message(adapter, session_id: str, content: str) -> dict:
    """构建 Heartbeat 助手消息。"""
    web_adapter = _resolve_web_adapter(adapter)
    if web_adapter and hasattr(web_adapter, "build_heartbeat_assistant_message"):
        return web_adapter.build_heartbeat_assistant_message(session_id, content)
    if web_adapter:
        return web_adapter.build_assistant_message(
            ChatResponse(final_content=content),
            conversation_id=session_id,
            sender="AI",
            metadata={
                "source": "heartbeat",
                "is_heartbeat": True,
                "hide_in_web": False,
            },
        )
    return {
        "role": "assistant",
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "sender": "AI",
        "source": "heartbeat",
        "is_heartbeat": True,
        "hide_in_web": False,
    }


def _build_workflow_user_message(
    adapter, session_id: str, content: str, workflow_id: str
) -> dict:
    """构建工作流用户消息。"""
    web_adapter = _resolve_web_adapter(adapter)
    if web_adapter and hasattr(web_adapter, "build_workflow_user_message"):
        return web_adapter.build_workflow_user_message(session_id, content, workflow_id)
    if web_adapter:
        return web_adapter.build_message(
            role="user",
            content=content,
            sender="user",
            conversation_id=session_id,
            metadata={"workflow_id": workflow_id},
        )
    return {
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "sender": "user",
        "workflow_id": workflow_id,
    }


def _build_workflow_assistant_message(
    adapter, session_id: str, content: str, workflow_id: str
) -> dict:
    """构建工作流助手消息。"""
    web_adapter = _resolve_web_adapter(adapter)
    if web_adapter and hasattr(web_adapter, "build_workflow_assistant_message"):
        return web_adapter.build_workflow_assistant_message(
            session_id, content, workflow_id
        )
    if web_adapter:
        return web_adapter.build_assistant_message(
            ChatResponse(final_content=content),
            conversation_id=session_id,
            sender="AI",
            metadata={"workflow_id": workflow_id},
        )
    return {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "sender": "AI",
        "workflow_id": workflow_id,
    }


def _build_web_manager_payload(
    adapter,
    message: dict,
    *,
    default_role: str,
    default_content: str,
    default_sender: str,
    default_conversation_id: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> dict:
    """构建 Web 消息管理器负载。"""
    manager_adapter = _resolve_web_adapter(adapter)
    if manager_adapter:
        return manager_adapter.build_manager_payload_from_message(
            message,
            default_role=default_role,
            default_content=default_content,
            default_sender=default_sender,
            default_conversation_id=default_conversation_id,
            metadata=metadata,
        )
    payload = {
        "role": default_role,
        "content": default_content,
        "sender": default_sender,
        "source": "web",
        "session_id": default_conversation_id,
    }
    if metadata:
        payload["metadata"] = dict(metadata)
    return payload


def _format_uptime(seconds: float) -> str:
    """格式化运行时间。

    Args:
        seconds: 运行秒数。

    Returns:
        人类可读的时长字符串。
    """
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)

    if days > 0:
        return f"{days}天{hours}小时"
    elif hours > 0:
        return f"{hours}小时{minutes}分钟"
    else:
        return f"{minutes}分钟"


def parse_document_with_mineru(
    file_path: str, api_key: str, file_relative_url: str = None
) -> Optional[str]:
    """使用 MinerU API 解析文档（PDF、DOC、PPT 等）。

    Args:
        file_path: 本地文件路径。
        api_key: MinerU API Key。
        file_relative_url: 文件相对 URL（可选，如 /static/uploads/xxx.pdf）。

    Returns:
        提取的文本内容，失败时返回 None。
    """
    import requests

    url = "https://mineru.net/api/v4/extract/task"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    try:
        _log.info(f"开始使用 MinerU API 解析文件: {file_path}")

        server_host = os.environ.get("SERVER_HOST", "http://127.0.0.1:5000")
        file_url = f"{server_host}{file_relative_url}"
        _log.info(f"文件访问 URL: {file_url}")

        data = {"url": file_url, "model_version": "vlm"}

        response = requests.post(url, headers=headers, json=data, timeout=120)

        if response.status_code == 200:
            result = response.json()
            _log.info(f"MinerU API 返回结果: {str(result)[:200]}...")

            if "data" in result:
                content = result["data"]
                if isinstance(content, str):
                    _log.info(f"MinerU 提取到 {len(content)} 字符内容")
                    return content
                elif isinstance(content, dict) and "content" in content:
                    _log.info(f"MinerU 提取到 {len(content['content'])} 字符内容")
                    return content["content"]
            elif "content" in result:
                content = result["content"]
                _log.info(f"MinerU 提取到 {len(content)} 字符内容")
                return content
            else:
                _log.warning(f"MinerU API 返回格式未知: {result}")
                return None
        else:
            _log.error(f"MinerU API 请求失败: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        _log.error(f"MinerU API 调用失败: {e}")
        return None
