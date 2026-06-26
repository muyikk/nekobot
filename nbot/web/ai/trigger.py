"""Web AI 流式响应——provider 级流式推送与模拟流式发送。"""

import time
from typing import Dict, List

from nbot.utils.logger import get_logger

_log = get_logger(__name__)


def stream_provider_response_to_web(
    server,
    messages: List[Dict],
    session_id: str,
    message: Dict,
    thinking_content: str = None,
) -> str:
    """Stream provider chunks directly to the web chat bubble."""
    if not server.ai_client:
        raise RuntimeError("AI client not initialized")

    stream_iter = server.ai_client.chat_completion(
        model=server.ai_model,
        messages=messages,
        stream=True,
    )

    message["content"] = ""
    server.socketio.emit(
        "ai_stream_start",
        {
            "session_id": session_id,
            "message": message,
            "thinking_content": thinking_content,
        },
        room=session_id,
    )

    content_parts = []
    pending_parts = []
    last_emit_at = time.monotonic()

    def normalize_provider_chunk(raw_chunk: str) -> str:
        chunk_text = str(raw_chunk or "")
        if not chunk_text:
            return ""
        existing = "".join(content_parts)
        if not existing:
            return chunk_text
        if chunk_text.startswith(existing):
            return chunk_text[len(existing):]
        if existing.endswith(chunk_text):
            return ""

        max_overlap = min(len(existing), len(chunk_text), 32)
        for overlap in range(max_overlap, 2, -1):
            if existing.endswith(chunk_text[:overlap]):
                return chunk_text[overlap:]
        return chunk_text

    def emit_pending(force: bool = False):
        nonlocal last_emit_at
        if not pending_parts:
            return
        pending_text = "".join(pending_parts)
        if not force and len(pending_text) < 4 and time.monotonic() - last_emit_at < 0.02:
            return
        pending_parts.clear()
        server.socketio.emit(
            "ai_stream_chunk",
            {
                "session_id": session_id,
                "message_id": message["id"],
                "chunk": pending_text,
                "is_end": False,
            },
            room=session_id,
        )
        last_emit_at = time.monotonic()
        server.socketio.sleep(0)

    try:
        for chunk in stream_iter:
            if chunk is None:
                continue
            chunk = normalize_provider_chunk(chunk)
            if not chunk:
                continue
            content_parts.append(chunk)
            pending_parts.append(chunk)
            emit_pending()
    except Exception as e:
        _log.error(f"Provider stream error: {e}", exc_info=True)
        if not content_parts:
            raise
        error_chunk = f"\n\n[stream interrupted: {e}]"
        content_parts.append(error_chunk)
        pending_parts.append(error_chunk)
        emit_pending(force=True)
    else:
        emit_pending(force=True)
    finally:
        server.socketio.emit(
            "ai_stream_end",
            {"session_id": session_id, "message_id": message["id"], "is_end": True},
            room=session_id,
        )

    final_content = "".join(content_parts)
    message["content"] = final_content
    return final_content


def stream_send_response(
    server, session_id: str, message: Dict, thinking_content: str = None
):
    """通过 WebSocket 发送流式响应

    Args:
        session_id: 会话 ID
        message: 消息对象（包含完整的 content）
        thinking_content: AI 思考内容
    """
    try:
        content = message.get("content", "")
        _log.info(
            f"[Stream] 开始流式发送, session={session_id[:8]}, content长度={len(content)}"
        )

        # 发送开始事件
        server.socketio.emit(
            "ai_stream_start",
            {
                "session_id": session_id,
                "message": message,
                "thinking_content": thinking_content,
            },
            room=session_id,
        )
        _log.info("[Stream] 已发送 ai_stream_start")

        # 清理并分割内容
        content = content.strip()

        # 发送内容片段（每10个字符一段）
        chunk_size = 10
        chunk_count = 0
        for i in range(0, len(content), chunk_size):
            chunk = content[i : i + chunk_size]
            server.socketio.emit(
                "ai_stream_chunk",
                {
                    "session_id": session_id,
                    "message_id": message["id"],
                    "chunk": chunk,
                    "is_end": False,
                },
                room=session_id,
            )
            chunk_count += 1

        _log.info(f"[Stream] 已发送 {chunk_count} 个 chunk")

        # 发送结束事件
        server.socketio.emit(
            "ai_stream_end",
            {"session_id": session_id, "message_id": message["id"], "is_end": True},
            room=session_id,
        )
        _log.info("[Stream] 流式发送完成")

    except Exception as e:
        _log.error(f"Stream send error: {e}", exc_info=True)
        # 降级为普通发送
        server.socketio.emit(
            "ai_response",
            {"session_id": session_id, "message": message},
            room=session_id,
        )
