"""
管道回调接口

ProgressReporter、PipelineCallbacks 等抽象基类，供各频道实现。
"""

import copy
import json
import logging
import threading
from abc import ABC
from typing import Any, Callable, Dict, List, Optional

from nbot.core.chat_models import ChatRequest, ChatResponse

_log = logging.getLogger(__name__)


class ProgressReporter(ABC):
    """抽象的进度报告接口。

    Web 频道通过 WebProgressReporter 实现，
    其他频道使用 NoOpProgressReporter。
    """

    def on_attachment_start(self, ctx: "PipelineContext", count: int) -> None:
        pass

    def on_attachment_item(
        self, ctx: "PipelineContext", name: str, item_type: str
    ) -> None:
        pass

    def on_attachment_item_done(
        self,
        ctx: "PipelineContext",
        name: str,
        success: bool,
        result_preview: str = "",
    ) -> None:
        pass

    def on_attachments_done(self, ctx: "PipelineContext") -> None:
        pass

    def on_knowledge_start(self, ctx: "PipelineContext") -> None:
        pass

    def on_knowledge_done(self, ctx: "PipelineContext", retrieved: bool) -> None:
        pass

    def on_thinking_start(self, ctx: "PipelineContext") -> None:
        pass

    def on_thinking_content(self, ctx: "PipelineContext", content: str) -> None:
        pass

    def on_tool_start(
        self,
        ctx: "PipelineContext",
        tool_name: str,
        arguments: Dict[str, Any],
        thinking: str,
    ) -> None:
        pass

    def on_tool_done(
        self,
        ctx: "PipelineContext",
        tool_name: str,
        result: Dict[str, Any],
        thinking: str,
    ) -> None:
        pass

    def on_tool_iteration(self, ctx: "PipelineContext", iteration: int) -> None:
        pass

    def on_todo_updated(
        self, ctx: "PipelineContext", tool_name: str, tool_result: Dict[str, Any]
    ) -> None:
        pass

    def on_send_message(self, ctx: "PipelineContext", content: str) -> None:
        pass

    def on_send_file(
        self, ctx: "PipelineContext", file_path: str, filename: str
    ) -> None:
        pass

    def on_done(self, ctx: "PipelineContext") -> None:
        pass

    def on_waiting_confirmation(
        self, ctx: "PipelineContext", command: str, request_id: str
    ) -> None:
        pass


class NoOpProgressReporter(ProgressReporter):
    """默认空实现，用于不支持进度的频道。"""
    pass


class PipelineCallbacks(ABC):
    """频道需实现的回调基类。

    所有方法都有默认实现，简单频道（Telegram、飞书）只需覆写约 2-4 个方法。
    """

    # ---- 会话 / 消息 I/O ----

    def load_messages(self, ctx: "PipelineContext") -> List[Dict[str, Any]]:
        """返回会话的完整消息列表（包含 system prompt）。

        默认：用 get_system_prompt + 当前用户消息构建。
        """
        system = self.get_system_prompt(ctx)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": ctx.chat_request.content})
        return messages

    def get_system_prompt(self, ctx: "PipelineContext") -> str:
        """返回此会话的系统提示词。"""
        return ""

    def save_assistant_message(
        self, ctx: "PipelineContext", message: Dict[str, Any]
    ) -> None:
        """持久化助手消息到会话存储。"""
        pass

    # ---- AI 模型交互 ----

    def build_model_call(
        self, ctx: "PipelineContext", tools: List[Dict[str, Any]]
    ) -> Callable[..., Dict[str, Any]]:
        """返回 model_call 函数。

        默认实现使用全局 ai_client 和运行时配置。
        """
        from nbot.services.ai import ai_client, refresh_runtime_ai_config
        from nbot.core.model_adapter import (
            build_chat_completion_payload,
            normalize_chat_completion_data,
            response_json_utf8,
            resolve_chat_completion_url,
        )
        import requests

        def model_call(messages, stop_event=None):
            if stop_event and stop_event.is_set():
                raise StopIteration("User stopped")

            runtime_ai = refresh_runtime_ai_config()
            base_url = runtime_ai.get("base_url") or ""
            model = runtime_ai.get("model") or ai_client.model
            provider_type = runtime_ai.get("provider_type") or "openai_compatible"
            api_key = runtime_ai.get("api_key") or ""

            url = resolve_chat_completion_url(base_url, model=model, provider_type=provider_type)
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = build_chat_completion_payload(
                model,
                messages,
                base_url=base_url,
                provider_type=provider_type,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                stream=False,
            )
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            normalized = normalize_chat_completion_data(
                response_json_utf8(resp),
                base_url=base_url,
                model=model,
                provider_type=provider_type,
            )
            return normalized.to_dict()

        return model_call

    def build_model_call_streaming(
        self, ctx: "PipelineContext", tools: List[Dict[str, Any]]
    ) -> Optional[Callable]:
        """返回流式 model_call 或 None（不支持流式）。"""
        return None

    # ---- 输出 / 回复 ----

    def send_response(
        self, ctx: "PipelineContext", message: Dict[str, Any]
    ) -> None:
        """发送最终助手消息给用户。必须覆写。"""
        raise NotImplementedError(
            "send_response must be implemented by the channel"
        )

    def on_stream_start(
        self, ctx: "PipelineContext", message: Dict[str, Any]
    ) -> None:
        pass

    def on_stream_chunk(
        self, ctx: "PipelineContext", chunk: str, message_id: str
    ) -> None:
        pass

    def on_stream_end(self, ctx: "PipelineContext", message_id: str) -> None:
        pass

    # ---- 进度报告 ----

    def get_progress_reporter(self, ctx: "PipelineContext") -> ProgressReporter:
        """返回 ProgressReporter 实例。默认返回空实现。"""
        return NoOpProgressReporter()

    # ---- 工具确认 ----

    def on_confirmation_required(
        self, ctx: "PipelineContext", request_id: str, command: str
    ) -> None:
        """工具需要用户确认时调用。"""
        pass

    def check_confirmation(
        self, ctx: "PipelineContext", user_input: str
    ) -> Optional[str]:
        """检查用户输入是否为确认/拒绝。返回 'confirm', 'reject', 或 None。"""
        return None

    # ---- 知识库 ----

    def search_knowledge(self, ctx: "PipelineContext", query: str) -> str:
        """搜索知识库并返回格式化文本。默认不检索。"""
        return ""

    # ---- 工作区 ----

    def ensure_workspace(self, ctx: "PipelineContext") -> str:
        """确保会话工作区存在。返回工作区路径。"""
        return ""

    def get_workspace_context(self, ctx: "PipelineContext") -> Dict[str, Any]:
        """返回工作区上下文字典（供工具使用）。"""
        return {}

    def get_memory_context(self, ctx: "PipelineContext") -> Dict[str, Any]:
        """返回自动记忆需要的频道上下文。"""
        return self.get_workspace_context(ctx)

    # ---- 附件解析 ----

    def resolve_attachment_data(
        self, ctx: "PipelineContext", attachment: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """解析单个附件，返回 {type, name, data, path, text_content, error} 或 None。"""
        return None

    # ---- 后处理 ----

    def on_response_complete(
        self, ctx: "PipelineContext", result: "PipelineResult"
    ) -> None:
        """AI 响应完成后的回调。"""
        pass

    # ---- 角色运行时 ----

    def get_character_context(self, ctx: "PipelineContext"):
        """返回角色身份标识 (CharacterIdentity)，默认 None 表示不启用角色运行时。"""
        return None

    def get_character_runtime(self, ctx: "PipelineContext"):
        """返回 CharacterRuntime 实例，默认 None。"""
        return None
