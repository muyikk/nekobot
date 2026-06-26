"""Web AI 工具调用——带工具支持的 AI 调用及文本工具解析。"""

import json
import re
import time
from typing import Dict, List

from nbot.utils.logger import get_logger
from nbot.core import (
    build_chat_completion_payload,
    normalize_chat_completion_data,
    resolve_chat_completion_url,
    response_json_utf8,
)

_log = get_logger(__name__)


def get_ai_response_with_tools(
    server,
    messages: List[Dict],
    tools: List[Dict],
    use_silicon: bool = False,
    stop_event=None,
) -> Dict:
    """调用 AI 并支持工具

    Args:
        messages: 消息列表
        tools: 工具定义列表
        use_silicon: 是否使用 Silicon API（默认 False，使用主 API）
        stop_event: 可选的停止事件，用于立即停止
    """
    # 如果传入了 stop_event 且已设置，立即返回
    if stop_event and stop_event.is_set():
        raise StopIteration("用户停止生成")

    def check_stop():
        if stop_event and stop_event.is_set():
            raise StopIteration("用户停止生成")

    try:
        if not server.ai_client:
            return {"content": "AI 服务未配置"}

        import requests

        # 从设置中获取超时时间，默认 120 秒
        timeout = server.settings.get("api_timeout", 120)
        max_retries = server.settings.get("api_retry_count", 3)

        # 使用适当的超时：有工具时至少 60 秒，无工具时至少 30 秒
        # 这样可以更频繁地检查停止事件，同时不会因为太短而频繁超时
        if tools:
            api_timeout = max(timeout, 60)  # 有工具调用时至少 60 秒
        else:
            api_timeout = max(timeout, 30)  # 无工具调用时至少 30 秒

        # 检查是否应该使用 Silicon API
        # 只有在明确指定 use_silicon=True 且有 Silicon API key 时才使用
        if use_silicon:
            silicon_api_key = getattr(server.ai_client, "silicon_api_key", None)
            if not silicon_api_key:
                try:
                    import configparser

                    config = configparser.ConfigParser()
                    config.read("config.ini", encoding="utf-8")
                    silicon_api_key = config.get(
                        "ApiKey", "silicon_api_key", fallback=""
                    )
                except:
                    silicon_api_key = ""

            if not silicon_api_key:
                _log.info("[AI] Silicon API key 未配置，使用主 API")
                use_silicon = False

        if use_silicon:
            # Silicon API 调用
            url = "https://api.siliconflow.cn/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {silicon_api_key}",
                "Content-Type": "application/json",
            }
            # Silicon 支持的工具调用模型
            model = "Qwen/Qwen2.5-72B-Instruct"

            # 检查消息总长度，必要时截断工具结果
            MAX_CONTENT_LENGTH = 12000  # 每个消息内容的最大长度
            processed_messages = []
            for msg in messages:
                msg_copy = msg.copy()
                if "content" in msg_copy and isinstance(msg_copy["content"], str):
                    content_len = len(msg_copy["content"])
                    if content_len > MAX_CONTENT_LENGTH:
                        # 尝试保留 JSON 的完整性
                        truncated = msg_copy["content"][:MAX_CONTENT_LENGTH]
                        # 如果看起来像 JSON，尝试找到最后一个完整的括号
                        if truncated.strip().startswith(
                            "{"
                        ) or truncated.strip().startswith("["):
                            # 找到最后一个完整的 JSON 对象/数组
                            last_brace = max(
                                truncated.rfind("}"), truncated.rfind("]")
                            )
                            if (
                                last_brace > MAX_CONTENT_LENGTH - 500
                            ):  # 如果最后一个括号位置还合理
                                truncated = truncated[: last_brace + 1]
                        msg_copy["content"] = (
                            truncated
                            + f"\n... [内容过长，已截断，原始长度: {content_len} 字符]"
                        )
                processed_messages.append(msg_copy)

            payload = {
                "model": model,
                "messages": processed_messages,
                "tools": tools,
                "tool_choice": "auto",
            }

            # 重试机制
            last_error = None
            for attempt in range(max_retries):
                check_stop()  # 检查是否停止
                try:
                    _log.info(
                        f"[AI] Silicon API 调用 (尝试 {attempt + 1}/{max_retries})"
                    )

                    # 使用线程来执行请求，以便能够响应停止事件
                    import threading

                    result_container = {"data": None, "error": None}

                    def make_request():
                        try:
                            resp = requests.post(
                                url,
                                json=payload,
                                headers=headers,
                                timeout=api_timeout,
                            )
                            resp.raise_for_status()
                            result_container["data"] = response_json_utf8(resp)
                        except Exception as e:
                            result_container["error"] = e

                    request_thread = threading.Thread(target=make_request)
                    request_thread.daemon = True
                    request_thread.start()

                    # 等待请求完成，同时检查停止事件（每0.5秒检查一次）
                    while request_thread.is_alive():
                        check_stop()  # 如果停止事件被设置，这里会抛出 StopIteration
                        request_thread.join(timeout=0.5)

                    # 检查请求结果
                    if result_container["error"]:
                        raise result_container["error"]

                    data = result_container["data"]
                    if data is None:
                        raise Exception("请求未返回数据")

                    break
                except StopIteration:
                    # 用户停止生成，立即抛出
                    _log.info("[AI] 检测到停止信号，中断 Silicon API 请求")
                    raise
                except requests.exceptions.Timeout as e:
                    last_error = e
                    _log.warning(
                        f"[AI] Silicon API 超时 (尝试 {attempt + 1}/{max_retries}): {e}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(min(2**attempt, 2))  # 限制最大等待2秒
                    continue
                except requests.exceptions.RequestException as e:
                    last_error = e
                    _log.error(
                        f"[AI] Silicon API 错误 (尝试 {attempt + 1}/{max_retries}): {e}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(min(2**attempt, 2))
                    continue
            else:
                # 所有重试都失败
                raise last_error or Exception("API 调用失败")
        else:
            # 使用主 API
            url = resolve_chat_completion_url(
                server.ai_base_url,
                model=server.ai_model or "",
                provider_type=server.ai_config.get("provider_type", server.ai_config.get("provider", "openai_compatible")),
            )

            headers = {
                "Authorization": f"Bearer {server.ai_api_key}",
                "Content-Type": "application/json",
            }

            # 检查消息总长度，必要时截断工具结果
            MAX_CONTENT_LENGTH = 12000  # 每个消息内容的最大长度
            MAX_ARGUMENTS_LENGTH = 50000  # tool_calls arguments 的最大长度
            processed_messages = []
            for msg in messages:
                msg_copy = msg.copy()
                if "content" in msg_copy and isinstance(msg_copy["content"], str):
                    content_len = len(msg_copy["content"])
                    if content_len > MAX_CONTENT_LENGTH:
                        # 尝试保留 JSON 的完整性
                        truncated = msg_copy["content"][:MAX_CONTENT_LENGTH]
                        # 如果看起来像 JSON，尝试找到最后一个完整的括号
                        if truncated.strip().startswith(
                            "{"
                        ) or truncated.strip().startswith("["):
                            # 找到最后一个完整的 JSON 对象/数组
                            last_brace = max(
                                truncated.rfind("}"), truncated.rfind("]")
                            )
                            if (
                                last_brace > MAX_CONTENT_LENGTH - 500
                            ):  # 如果最后一个括号位置还合理
                                truncated = truncated[: last_brace + 1]
                        msg_copy["content"] = (
                            truncated
                            + f"\n... [内容过长，已截断，原始长度: {content_len} 字符]"
                        )

                # 检查 tool_calls arguments 长度
                if "tool_calls" in msg_copy and msg_copy["tool_calls"]:
                    for tc in msg_copy["tool_calls"]:
                        if "function" in tc and "arguments" in tc["function"]:
                            args_str = tc["function"]["arguments"]
                            if (
                                isinstance(args_str, str)
                                and len(args_str) > MAX_ARGUMENTS_LENGTH
                            ):
                                tc["function"]["arguments"] = (
                                    args_str[:MAX_ARGUMENTS_LENGTH]
                                    + f"\n... [参数过长已截断，原始长度: {len(args_str)}]"
                                )
                                _log.warning(
                                    f"[AI] 工具 {tc.get('function', {}).get('name')} 的 arguments 过长，已截断"
                                )

                processed_messages.append(msg_copy)

            payload = build_chat_completion_payload(
                server.ai_model,
                processed_messages,
                base_url=server.ai_base_url,
                provider_type=server.ai_config.get("provider_type", server.ai_config.get("provider", "openai_compatible")),
                tools=tools,
                tool_choice="auto",
            )

            # 记录 payload 大小
            import json

            payload_size = len(json.dumps(payload, ensure_ascii=False))
            _log.info(
                f"[AI] 发送请求到 {url}, 模型={server.ai_model}, 工具数={len(tools) if tools else 0}, payload大小={payload_size} bytes"
            )

            if payload_size > 500000:  # 超过 500KB
                _log.warning(
                    f"[AI] Payload 过大 ({payload_size} bytes)，可能导致 API 拒绝"
                )

            # 重试机制
            last_error = None
            for attempt in range(max_retries):
                check_stop()  # 检查是否停止
                try:
                    _log.info(
                        f"[AI] 主 API 调用 (尝试 {attempt + 1}/{max_retries})"
                    )

                    # 使用线程来执行请求，以便能够响应停止事件
                    import threading

                    result_container = {"data": None, "error": None}

                    def make_request():
                        try:
                            resp = requests.post(
                                url,
                                json=payload,
                                headers=headers,
                                timeout=api_timeout,
                            )
                            resp.raise_for_status()
                            result_container["data"] = response_json_utf8(resp)
                        except Exception as e:
                            result_container["error"] = e

                    request_thread = threading.Thread(target=make_request)
                    request_thread.daemon = True
                    request_thread.start()

                    # 等待请求完成，同时检查停止事件（每0.5秒检查一次）
                    while request_thread.is_alive():
                        check_stop()  # 如果停止事件被设置，这里会抛出 StopIteration
                        request_thread.join(timeout=0.5)

                    # 检查请求结果
                    if result_container["error"]:
                        raise result_container["error"]

                    data = result_container["data"]
                    if data is None:
                        raise Exception("请求未返回数据")

                    break
                except StopIteration:
                    # 用户停止生成，立即抛出
                    _log.info("[AI] 检测到停止信号，中断 API 请求")
                    raise
                except requests.exceptions.Timeout as e:
                    last_error = e
                    _log.warning(
                        f"[AI] 主 API 超时 (尝试 {attempt + 1}/{max_retries}): {e}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(min(2**attempt, 2))  # 限制最大等待2秒
                    continue
                except requests.exceptions.RequestException as e:
                    last_error = e
                    _log.error(
                        f"[AI] 主 API 错误 (尝试 {attempt + 1}/{max_retries}): {e}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(min(2**attempt, 2))
                    continue
            else:
                raise last_error or Exception("API 调用失败")

        normalized = normalize_chat_completion_data(
            data,
            base_url=server.ai_base_url or "",
            model=server.ai_model or "",
            provider_type=server.ai_config.get("provider_type", server.ai_config.get("provider", "openai_compatible")),
            fallback_tool_parser=server._parse_tool_call_from_text,
        )
        message = normalized.raw_message
        finish_reason = normalized.finish_reason

        _log.info(
            f"[AI] API 响应: finish_reason={finish_reason}, has_tool_calls={'tool_calls' in message}"
        )
        _log.debug(f"[AI] 工具数量: {len(tools) if tools else 0}")

        # 记录完整响应用于调试
        if "tool_calls" not in message and message.get("content", ""):
            _log.warning(
                f"[AI] 工具未生效，content 前100字符: {message.get('content', '')[:100]}"
            )

        result = normalized.to_dict()

        # 获取AI思考内容（如果API返回了的话）
        supports_reasoning = server.ai_config.get("supports_reasoning", True)
        thinking_content = normalized.thinking_content if supports_reasoning else ""
        if not supports_reasoning and "thinking_content" in result:
            result.pop("thinking_content", None)
        if thinking_content:
            _log.debug(f"[AI] 收到思考内容: {len(thinking_content)} 字符")
        elif normalized.thinking_content and not supports_reasoning:
            _log.info("[AI] 当前模型配置声明不展示 reasoning 字段，已忽略思考内容")
        if result.get("tool_calls") and "[TOOL_CALL]" in result.get("content", ""):
            cleaned = re.sub(
                r"\[TOOL_CALL\]\s*.*?\s*\[/TOOL_CALL\]\s*",
                "",
                result["content"],
                flags=re.DOTALL,
            )
            cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
            result["content"] = cleaned.strip()
            _log.info(f"[AI] 成功解析 {len(result['tool_calls'])} 个工具调用")

        return result

    except StopIteration as e:
        # 用户停止生成
        _log.info(f"[AI] 停止生成: {e}")
        raise  # 重新抛出，让调用者处理

    except Exception as e:
        _log.error(f"AI with tools error: {e}")
        # 回退到普通 AI 调用
        content = server._get_ai_response(messages)
        return {"content": content}


def parse_tool_call_from_text(self, content: str) -> list:
    """解析 [TOOL_CALL] 格式的工具调用

    支持的格式：
    [TOOL_CALL]
    {tool => "exec_command", args => {
    --command ls -la
    --timeout 15
    }}
    [/TOOL_CALL]
    """
    import re

    tool_calls = []

    # 首先查找所有 [TOOL_CALL]...[/TOOL_CALL] 块
    # 使用简单的标记来分割
    pattern = r"\[TOOL_CALL\](.*?)\[/TOOL_CALL\]"
    matches = re.finditer(pattern, content, re.DOTALL)

    for match in matches:
        block = match.group(1).strip()

        # 提取工具名称
        name_match = re.search(r'tool\s*=>\s*["\']([^"\']+)["\']', block)
        if not name_match:
            # 尝试另一种格式: tool_name => "xxx" 或 "tool": "xxx"
            name_match = re.search(r'tool_name\s*=>\s*["\']([^"\']+)["\']', block)
            if not name_match:
                name_match = re.search(r'"tool":\s*"([^"]+)"', block)

        if not name_match:
            continue
        tool_name = name_match.group(1)

        # 提取参数块 { ... }
        # 找到 args => { 开始的位置
        args_start = block.find("args")
        if args_start == -1:
            continue

        # 找到第一个 {
        brace_start = block.find("{", args_start)
        if brace_start == -1:
            continue

        # 计算嵌套的括号，找到匹配的 }
        depth = 0
        args_end = brace_start
        for i in range(brace_start, len(block)):
            if block[i] == "{":
                depth += 1
            elif block[i] == "}":
                depth -= 1
                if depth == 0:
                    args_end = i
                    break

        args_block = block[brace_start + 1 : args_end]

        # 解析参数（--key value 格式）
        arguments = {}
        # 将参数按行分割
        lines = args_block.strip().split("\n")
        current_key = None
        current_value_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否是 --key 开头
            if line.startswith("--"):
                # 保存上一个参数
                if current_key is not None:
                    arguments[current_key] = "\n".join(current_value_lines).strip()

                # 解析新的 key
                parts = line[2:].split(
                    None, 1
                )  # 分割一次，空格前是key，后面是value
                current_key = parts[0] if parts else None
                current_value_lines = [parts[1]] if len(parts) > 1 else []
            elif current_key:
                # continuation of previous value
                current_value_lines.append(line)

        # 保存最后一个参数
        if current_key is not None:
            arguments[current_key] = "\n".join(current_value_lines).strip()

        tool_calls.append(
            {
                "id": f"tool_call_{len(tool_calls) + 1}",
                "name": tool_name,
                "arguments": arguments,
            }
        )

    return tool_calls
