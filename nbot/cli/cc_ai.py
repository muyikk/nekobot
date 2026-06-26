"""
CLI AI 调用 - CCStyleCLI 的 AI 调用、流式响应处理和工具循环
"""

import json
from typing import Dict, Any, List

from rich.console import Console
from rich.text import Text
from rich.live import Live
from nbot.cli.markdown import render_markdown_to_text


def process_stream_response(console: Console, response, supports_tools: bool, cli) -> Dict:
    """处理流式响应，实时渲染 Markdown
    返回: {"content": str, "thinking": str, "tool_calls": list, "interrupted": bool}
    """
    display_text = Text("🐱 ", style="cyan")

    content_parts = []
    thinking_parts = []
    tool_calls = []

    with Live(
        display_text, console=console, refresh_per_second=10, transient=False
    ) as live:
        for line in response.iter_lines():
            if cli.interrupt_requested:
                return {
                    "content": "".join(content_parts),
                    "thinking": "".join(thinking_parts),
                    "tool_calls": tool_calls,
                    "interrupted": True,
                }

            if not line:
                continue

            line_str = line.decode("utf-8")

            if line_str.startswith("data: "):
                data_str = line_str[6:]

                if data_str.strip() == "[DONE]":
                    break

                try:
                    data = json.loads(data_str)
                    choice = data.get("choices", [{}])[0]
                    delta = choice.get("delta", {})

                    thinking = delta.get("reasoning_content", "") or delta.get(
                        "thinking", ""
                    )
                    if thinking:
                        thinking_parts.append(thinking)

                    content = delta.get("content", "")
                    if content:
                        content_parts.append(content)
                        current_content = "".join(content_parts)
                        live.update(render_markdown_to_text(current_content))

                    if supports_tools and delta.get("tool_calls"):
                        for tc_delta in delta["tool_calls"]:
                            index = tc_delta.get("index", 0)

                            while len(tool_calls) <= index:
                                tool_calls.append(
                                    {
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }
                                )

                            if tc_delta.get("id"):
                                tool_calls[index]["id"] = tc_delta["id"]
                            if tc_delta.get("function", {}).get("name"):
                                tool_calls[index]["function"]["name"] = tc_delta[
                                    "function"
                                ]["name"]
                            if tc_delta.get("function", {}).get("arguments"):
                                tool_calls[index]["function"]["arguments"] += tc_delta[
                                    "function"
                                ]["arguments"]

                except json.JSONDecodeError:
                    continue

    return {
        "content": "".join(content_parts),
        "thinking": "".join(thinking_parts),
        "tool_calls": tool_calls if tool_calls else [],
        "interrupted": False,
    }


def call_ai(console: Console, cli, messages: List[Dict]) -> Dict[str, Any]:
    """调用AI，支持工具调用和多轮思考"""
    import requests

    model = cli._get_current_model()
    if not model:
        return {
            "content": "error: no model available",
            "thinking": "",
            "tool_calls": [],
            "tool_call_history": [],
        }

    try:
        api_key = model.get("api_key", "")
        base_url = model.get("base_url", "")
        model_name = model.get("model", "")
        supports_tools = model.get("supports_tools", True)

        if not api_key or not base_url:
            return {
                "content": "error: model not configured",
                "thinking": "",
                "tool_calls": [],
                "tool_call_history": [],
            }

        url = base_url.rstrip("/")
        if "minimaxi.com" in url:
            pass
        elif "siliconflow.cn" in url:
            url += "/chat/completions"
        elif "/v1" not in url:
            url += "/v1/chat/completions"
        else:
            url += "/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        tools = cli._get_tool_definitions() if supports_tools else []
        tool_messages = cli._expand_messages_for_ai(messages)
        initial_message_count = len(tool_messages)
        all_thinking = []
        all_tool_calls = []

        for iteration in range(cli.max_tool_iterations):
            if cli.interrupt_requested:
                return {
                    "content": "[interrupted by user]",
                    "thinking": "\n\n".join(all_thinking),
                    "tool_calls": all_tool_calls,
                    "tool_call_history": cli._extract_turn_tool_history(
                        tool_messages, initial_message_count
                    ),
                    "iterations": iteration + 1,
                    "interrupted": True,
                }

            payload = {
                "model": model_name,
                "messages": tool_messages,
                "temperature": model.get("temperature", 0.7),
                "stream": True,
            }

            max_tokens = model.get("max_tokens")
            if max_tokens:
                payload["max_tokens"] = max_tokens

            if tools and supports_tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            response = requests.post(
                url, headers=headers, json=payload, timeout=120, stream=True
            )
            response.raise_for_status()

            result = process_stream_response(console, response, supports_tools, cli)

            if result.get("interrupted"):
                result.setdefault(
                    "tool_call_history",
                    cli._extract_turn_tool_history(tool_messages, initial_message_count),
                )
                return result

            thinking = result.get("thinking", "")
            if thinking:
                all_thinking.append(f"Round {iteration + 1}: {thinking}")
                cli._render_inline_thinking(thinking)

            if result.get("tool_calls") and supports_tools:
                tool_calls = result["tool_calls"]
                all_tool_calls.extend(tool_calls)

                tool_call_info = "\n".join(
                    [
                        f"调用工具: {tc.get('function', {}).get('name')}({tc.get('function', {}).get('arguments', '{}')})"
                        for tc in tool_calls
                    ]
                )
                assistant_msg = result.get("content", "")
                if assistant_msg:
                    assistant_msg += "\n\n"
                assistant_msg += f"[工具调用]\n{tool_call_info}"
                tool_messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_msg,
                    }
                )

                for tool_call in tool_calls:
                    if cli.interrupt_requested:
                        return {
                            "content": "[interrupted by user]",
                            "thinking": "\n\n".join(all_thinking),
                            "tool_calls": all_tool_calls,
                            "tool_call_history": cli._extract_turn_tool_history(
                                tool_messages, initial_message_count
                            ),
                            "iterations": iteration + 1,
                            "interrupted": True,
                        }

                    tool_name = tool_call.get("function", {}).get("name")
                    try:
                        arguments = json.loads(
                            tool_call.get("function", {}).get("arguments", "{}")
                        )
                    except Exception:
                        arguments = {}

                    exec_result = cli._execute_tool(tool_name, arguments)
                    success = exec_result.get("success", False)

                    cli._render_tool_call_and_result(
                        tool_name, arguments, exec_result, success
                    )

                    tool_result_msg = f"工具 {tool_name} 执行结果：\n{json.dumps(exec_result, ensure_ascii=False, indent=2)}"
                    tool_messages.append(
                        {
                            "role": "user",
                            "content": tool_result_msg,
                        }
                    )

                continue
            else:
                final_content = result.get("content", "")

                if not final_content:
                    if all_tool_calls:
                        final_content = "工具执行完成。"
                    elif all_thinking:
                        final_content = "[思考完成]"
                    else:
                        final_content = "[无回复内容]"

                return {
                    "content": final_content,
                    "thinking": "\n\n".join(all_thinking),
                    "tool_calls": all_tool_calls,
                    "tool_call_history": cli._extract_turn_tool_history(
                        tool_messages, initial_message_count
                    ),
                    "iterations": iteration + 1,
                    "interrupted": False,
                }

        return {
            "content": "tool iterations exceeded limit",
            "thinking": "\n\n".join(all_thinking),
            "tool_calls": all_tool_calls,
            "tool_call_history": cli._extract_turn_tool_history(
                tool_messages, initial_message_count
            ),
            "iterations": cli.max_tool_iterations,
            "interrupted": False,
        }

    except Exception as e:
        return {
            "content": f"error: {str(e)}",
            "thinking": "",
            "tool_calls": [],
            "tool_call_history": [],
            "interrupted": False,
        }
