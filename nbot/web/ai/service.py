"""Web AI 服务核心模块——工具函数、管道入口与 AI 回复方法。"""

import threading
import uuid
from datetime import datetime
from typing import Dict, List

from nbot.utils.logger import get_logger
from nbot.channels.registry import get_channel_adapter
from nbot.channels.web import WebChannelAdapter
from nbot.core import (
    ChatRequest,
    ChatResponse,
    WebSessionStore,
)
from nbot.core.ai_pipeline import (
    AIPipeline,
    PipelineContext,
)

_log = get_logger(__name__)


def _feature_enabled(server, name: str, default: bool = True) -> bool:
    """检查功能开关是否启用。"""
    settings = getattr(server, "settings", {}) or {}
    features = settings.get("features")
    if isinstance(features, dict) and name in features:
        return bool(features.get(name))
    return bool(settings.get(name, default))


def _looks_like_tool_request(content: str) -> bool:
    """判断用户消息是否可能涉及工具调用。"""
    text = (content or "").lower()
    if not text:
        return False
    keywords = (
        "搜索",
        "查询",
        "天气",
        "新闻",
        "待办",
        "文件",
        "工作区",
        "创建",
        "编辑",
        "删除",
        "读取",
        "列出",
        "运行",
        "执行",
        "命令",
        "todo",
        "search",
        "weather",
        "file",
        "workspace",
        "command",
    )
    return any(keyword in text for keyword in keywords)


def _build_channel_assistant_message(
    chat_response: ChatResponse,
    *,
    session_id: str,
    adapter=None,
    sender: str = "AI",
):
    """构建频道适配器格式的 assistant 消息。"""
    channel_adapter = adapter or get_channel_adapter("web") or WebChannelAdapter()
    return channel_adapter.build_assistant_message(
        chat_response,
        conversation_id=session_id,
        sender=sender,
    )


def _build_change_card(
    *,
    session_id: str,
    parent_message_id: str,
    file_changes,
):
    """构建文件变更卡片数据结构。"""
    normalized_changes = []
    summary = {"total": 0, "created": 0, "modified": 0, "deleted": 0}
    change_by_path = {}

    for change in file_changes or []:
        if not isinstance(change, dict):
            continue
        action = str(change.get("action") or "modified")
        if action not in summary:
            action = "modified"
        normalized_change = {
            "action": action,
            "path": change.get("path") or change.get("filename") or "",
            "scope": change.get("scope") or "private",
            "before_preview": change.get("before_preview"),
            "after_preview": change.get("after_preview"),
            "diff_preview": change.get("diff_preview"),
        }
        change_key = normalized_change["path"] or f"unnamed_{len(change_by_path)}"
        change_by_path[change_key] = normalized_change

    normalized_changes = list(change_by_path.values())
    for change in normalized_changes:
        action = change["action"]
        summary[action] += 1
        summary["total"] += 1

    if not normalized_changes:
        return None

    return {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "parent_message_id": parent_message_id,
        "role": "system",
        "type": "change_card",
        "content": "本轮文件变更",
        "summary": summary,
        "file_changes": normalized_changes,
        "timestamp": datetime.now().isoformat(),
        "is_complete": True,
    }


def _emit_change_card(
    server,
    session_store,
    *,
    session_id: str,
    parent_message_id: str,
    file_changes,
):
    """发送文件变更卡片到前端。"""
    if not parent_message_id:
        return None

    change_card = _build_change_card(
        session_id=session_id,
        parent_message_id=parent_message_id,
        file_changes=file_changes,
    )
    if not change_card:
        return None

    session = session_store.get_session(session_id)
    if not session:
        return None

    for msg in session.get("messages", []):
        if (
            msg.get("id") == parent_message_id
            or msg.get("tempId") == parent_message_id
            or msg.get("originalTempId") == parent_message_id
        ):
            if "change_cards" not in msg:
                msg["change_cards"] = []
            msg["change_cards"] = [
                card
                for card in msg["change_cards"]
                if card.get("type") != "change_card"
            ]
            msg["change_cards"].append(change_card)
            break

    if session_store.save_callback:
        session_store.save_callback()
    server.socketio.emit("new_message", change_card, room=session_id)
    return change_card


def _get_tool_display_name(tool_name: str) -> str:
    """获取工具的中文显示名称。"""
    names = {
        "search_web": "网页搜索",
        "search_news": "新闻搜索",
        "get_weather": "天气查询",
        "get_date_time": "日期时间",
        "http_get": "HTTP 请求",
        "exec_command": "命令执行",
        "download_file": "文件下载",
        "save_to_memory": "保存记忆",
        "read_memory": "读取记忆",
        "workspace_create_file": "创建工作区文件",
        "workspace_read_file": "读取工作区文件",
        "workspace_edit_file": "编辑工作区文件",
        "workspace_delete_file": "删除工作区文件",
        "workspace_list_files": "列出工作区文件",
        "workspace_send_file": "发送工作区文件",
        "workspace_parse_file": "解析文件",
        "todo_add": "添加待办",
        "todo_list": "列出待办",
        "todo_complete": "完成待办",
        "todo_delete": "删除待办",
    }
    return names.get(tool_name, tool_name)


def trigger_ai_response(
    server,
    session_id: str,
    user_content: str,
    sender: str,
    attachments=None,
    parent_message_id=None,
):
    """为 Web 会话触发 AI 回复。"""
    adapter = getattr(server, "web_channel_adapter", None) or get_channel_adapter("web") or WebChannelAdapter()
    chat_request = adapter.build_chat_request(
        conversation_id=session_id,
        content=user_content,
        sender=sender,
        attachments=attachments,
        parent_message_id=parent_message_id,
    )
    return trigger_ai_response_for_request(server, chat_request, adapter=adapter)


def trigger_ai_response_for_request(server, chat_request: ChatRequest, adapter=None):
    """通过统一管道处理 Web 频道的 AI 请求。"""
    from nbot.web.ai.callbacks import WebCallbacks
    from nbot.web.ai.progress import WebProgressReporter

    adapter = adapter or getattr(server, "web_channel_adapter", None) or get_channel_adapter("web") or WebChannelAdapter()
    session_store = WebSessionStore(
        server.sessions, save_callback=lambda: server._save_data("sessions")
    )
    session_id = chat_request.conversation_id
    user_content = chat_request.content
    attachments = list(chat_request.attachments or [])
    parent_message_id = chat_request.parent_message_id
    channel_capabilities = adapter.get_capabilities()

    if not isinstance(attachments, list):
        attachments = []

    session = session_store.get_session(session_id)
    if not session:
        _log.warning(f"Session not found: {session_id}")
        return ChatResponse(error=f"Session not found: {session_id}")

    has_image = False
    try:
        for att in attachments:
            if isinstance(att, dict) and str(att.get("type", "")).startswith("image/"):
                has_image = True
                break
    except Exception:
        attachments = []

    server.log_message(
        "info",
        f"开始生成AI回复 for session {session_id[:8]}... (附件: {len(attachments)}, 图片: {has_image})",
    )

    # 创建停止事件
    stop_event = threading.Event()
    server.stop_events[session_id] = stop_event

    # 进度/待办卡片
    progress_reporter = None
    if (
        channel_capabilities.supports_progress_updates
        and server.PROGRESS_CARD_AVAILABLE
        and server.progress_card_manager
    ):
        progress_reporter = WebProgressReporter(
            server, session_id, parent_message_id, session_store
        )

    # 确定是否启用工具
    tools = None
    has_tools = (
        _looks_like_tool_request(user_content)
        and getattr(server, "ai_config", {}).get("supports_tools", True)
    )
    if has_tools:
        try:
            from nbot.services.tools import get_enabled_tools
            tools = get_enabled_tools()
        except Exception:
            tools = None

    # 构建管道上下文和回调
    ctx = PipelineContext(
        chat_request=chat_request,
        adapter=adapter,
        stop_event=stop_event,
    )
    callbacks = WebCallbacks(
        server=server,
        session_store=session_store,
        session_id=session_id,
        adapter=adapter,
        parent_message_id=parent_message_id,
        progress_reporter=progress_reporter,
    )

    # 上下文字符预算
    try:
        context_char_budget = int(
            getattr(server, "ai_config", {}).get("max_context_length", 100000)
        )
    except (TypeError, ValueError):
        context_char_budget = 100000
    context_char_budget = max(100000, context_char_budget)

    def run_pipeline():
        try:
            pipeline = AIPipeline()
            result = pipeline.process(
                ctx, callbacks,
                tools=tools,
                max_context_chars=context_char_budget,
            )

            # 更新 token 统计
            _update_web_token_stats(server, result.usage, session_id)

            return result
        finally:
            server.stop_events.pop(session_id, None)
            if progress_reporter:
                progress_reporter.dispose()

    # 使用后台任务执行管道
    server.socketio.start_background_task(run_pipeline)
    return ChatResponse(metadata={"scheduled": True, "session_id": session_id})


def _update_web_token_stats(server, usage: dict, session_id: str):
    """更新 Web 频道的 token 统计（统一持久化到磁盘）。"""
    try:
        if not usage:
            return
        total = usage.get("total_tokens", 0)
        if not total:
            return

        from nbot.core.token_stats import get_token_stats_manager

        get_token_stats_manager().record_usage(
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
            model=getattr(server, "ai_model", "") or "",
            session_id=session_id,
            channel_type="web",
            user_id=session_id,
        )
    except Exception:
        pass


def get_ai_response(self, messages: List[Dict]) -> str:
    """获取 AI 回复。"""
    if not self.ai_client:
        _log.warning("AI client not initialized")
        return "AI 服务未配置，请在 AI 配置页面设置 API Key 和 Base URL。"

    try:
        response = self.ai_client.chat_completion(
            model=self.ai_model, messages=messages, stream=False
        )

        # 检查 choices 是否有效
        if not response.choices or len(response.choices) == 0:
            base_resp = getattr(response, "base_resp", {}) or {}
            status_msg = base_resp.get("status_msg", "API 返回空响应")
            _log.warning(f"[AI] API 返回空 choices: {status_msg}")
            return f"AI 服务暂时不可用: {status_msg}"

        content = response.choices[0].message.content

        # 清理响应内容
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
        elif content.startswith("```"):
            content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

        return content.strip()
    except Exception as e:
        _log.error(f"AI response error: {e}", exc_info=True)
        return f"AI 服务出错: {str(e)}"


def stream_ai_response(self, messages: List[Dict], session_id: str, callback):
    """流式获取 AI 回复，通过回调逐段发送内容。

    Args:
        messages: 消息列表
        session_id: 会话 ID
        callback: 回调函数，接收 (chunk: str) 参数
    """
    if not self.ai_client:
        _log.warning("AI client not initialized")
        callback("AI 服务未配置，请在 AI 配置页面设置 API Key 和 Base URL。")
        return

    try:
        # 获取流式响应
        for chunk in self.ai_client.chat_completion(
            model=self.ai_model, messages=messages, stream=True
        ):
            # 清理内容
            chunk = chunk.strip()
            if chunk:
                callback(chunk)

    except Exception as e:
        _log.error(f"AI stream error: {e}", exc_info=True)
        callback(f"\n\nAI 服务出错: {str(e)}")
