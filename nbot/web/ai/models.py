"""Web 频道 AI 模型调用辅助——非流式与流式请求。"""

import json
from typing import Dict, List

from nbot.utils.logger import get_logger
from nbot.core import (
    build_chat_completion_payload,
    normalize_chat_completion_data,
    repair_mojibake_text,
    resolve_chat_completion_url,
    response_json_utf8,
)

_log = get_logger(__name__)


def _call_web_ai(server, messages: List[Dict], tools: list, stop_event=None) -> Dict:
    """Web 频道的 model_call 实现。"""
    import requests
    from nbot.services.ai import refresh_runtime_ai_config

    if stop_event and stop_event.is_set():
        raise StopIteration("User stopped")

    runtime_ai = refresh_runtime_ai_config()
    base_url = runtime_ai.get("base_url") or ""
    model = runtime_ai.get("model") or ""
    provider_type = runtime_ai.get("provider_type") or "openai_compatible"
    api_key = runtime_ai.get("api_key") or ""

    url = resolve_chat_completion_url(base_url, model=model, provider_type=provider_type)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = build_chat_completion_payload(
        model, messages,
        base_url=base_url, provider_type=provider_type,
        tools=tools if tools else None,
        tool_choice="auto" if tools else None,
        stream=False,
    )
    resp = requests.post(url, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    normalized = normalize_chat_completion_data(
        response_json_utf8(resp),
        base_url=base_url, model=model, provider_type=provider_type,
    )
    return normalized.to_dict()


def _stream_to_web(server, messages: List[Dict], tools: list, session_id: str, stop_event=None):
    """Web 频道的 provider 级流式实现，含 chunk 去重。"""
    import requests
    from nbot.services.ai import refresh_runtime_ai_config

    runtime_ai = refresh_runtime_ai_config()
    base_url = runtime_ai.get("base_url") or ""
    model = runtime_ai.get("model") or ""
    provider_type = runtime_ai.get("provider_type") or "openai_compatible"
    api_key = runtime_ai.get("api_key") or ""

    url = resolve_chat_completion_url(base_url, model=model, provider_type=provider_type)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = build_chat_completion_payload(
        model, messages,
        base_url=base_url, provider_type=provider_type,
        tools=tools if tools else None,
        tool_choice="auto" if tools else None,
        stream=True,
    )
    resp = requests.post(url, json=payload, headers=headers, stream=True, timeout=120)
    resp.raise_for_status()

    # chunk 去重：部分提供商返回累积文本而非增量
    content_parts: List[str] = []

    def normalize_chunk(raw: str) -> str:
        """从累积文本中提取新增部分。"""
        if not raw:
            return ""
        existing = "".join(content_parts)
        if not existing:
            return raw
        if raw.startswith(existing):
            return raw[len(existing):]
        if existing.endswith(raw):
            return ""
        max_overlap = min(len(existing), len(raw), 32)
        for overlap in range(max_overlap, 2, -1):
            if existing.endswith(raw[:overlap]):
                return raw[overlap:]
        return raw

    for raw_line in resp.iter_lines(decode_unicode=False):
        if stop_event and stop_event.is_set():
            break
        line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
        if line and line.startswith("data: "):
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                break
            try:
                data = json.loads(data_str)
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                raw_content = delta.get("content", "")
                if raw_content is None:
                    raw_content = ""
                if not isinstance(raw_content, str):
                    raw_content = str(raw_content)
                raw = repair_mojibake_text(raw_content)
                if raw:
                    chunk = normalize_chunk(raw)
                    if chunk:
                        content_parts.append(chunk)
                        yield {"content": chunk}
            except json.JSONDecodeError:
                continue
