"""Web 频道 AI 子包——AI 管道、回调、工具、图片和流式响应。"""

from nbot.web.ai.service import (
    _build_change_card,
    _build_channel_assistant_message,
    _emit_change_card,
    _feature_enabled,
    _get_tool_display_name,
    _looks_like_tool_request,
    _update_web_token_stats,
    get_ai_response,
    stream_ai_response,
    trigger_ai_response,
    trigger_ai_response_for_request,
)
from nbot.web.ai.models import _call_web_ai, _stream_to_web
from nbot.web.ai.callbacks import WebCallbacks
from nbot.web.ai.progress import WebProgressReporter
from nbot.web.ai.tools import get_ai_response_with_tools, parse_tool_call_from_text
from nbot.web.ai.images import get_ai_response_with_images
from nbot.web.ai.trigger import stream_provider_response_to_web, stream_send_response

__all__ = [
    "_build_change_card",
    "_build_channel_assistant_message",
    "_call_web_ai",
    "_emit_change_card",
    "_feature_enabled",
    "_get_tool_display_name",
    "_looks_like_tool_request",
    "_stream_to_web",
    "_update_web_token_stats",
    "get_ai_response",
    "get_ai_response_with_images",
    "get_ai_response_with_tools",
    "parse_tool_call_from_text",
    "stream_ai_response",
    "stream_provider_response_to_web",
    "stream_send_response",
    "trigger_ai_response",
    "trigger_ai_response_for_request",
    "WebCallbacks",
    "WebProgressReporter",
]
