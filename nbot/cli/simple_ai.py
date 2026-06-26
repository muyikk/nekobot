"""
NekoBot CLI - 简化版 AI 调用
从 SimpleCLI 提取的 _call_ai_with_tools 方法。
"""

import json
import requests
from typing import Dict, Any, List


def call_ai_with_tools(cli, messages: List[Dict]) -> Dict[str, Any]:
    """调用AI，支持工具调用和多轮思考"""
    model = cli._get_current_model()
    if not model:
        return {
            "content": "错误：没有可用的AI模型。请先配置模型。",
            "thinking": "",
            "tool_calls": [],
        }

    try:
        api_key = model.get("api_key", "")
        base_url = model.get("base_url", "")
        model_name = model.get("model", "")
        supports_tools = model.get("supports_tools", True)

        if not api_key or not base_url:
            return {
                "content": "错误：模型配置不完整（缺少API密钥或基础URL）",
                "thinking": "",
                "tool_calls": [],
            }

        # 处理URL
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

        # 获取工具定义
        tools = cli._get_tool_definitions() if supports_tools else []

        # 准备消息
        tool_messages = cli._expand_messages_for_ai(messages)
        initial_message_count = len(tool_messages)
        all_thinking = []
        all_tool_calls = []

        # 多轮工具调用循环
        for iteration in range(cli.max_tool_iterations):
            payload = {
                "model": model_name,
                "messages": tool_messages,
                "temperature": model.get("temperature", 0.7),
                "max_tokens": model.get("max_tokens", 2000),
                "stream": False,
            }

            # 添加工具支持
            if tools and supports_tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            response = requests.post(url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()

            # 解析响应
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})

            # 提取思考内容（如果支持）
            thinking = message.get("reasoning_content", "") or message.get("thinking", "")
            if thinking:
                all_thinking.append(f"第{iteration + 1}轮: {thinking}")

            # 检查是否有工具调用
            if message.get("tool_calls") and supports_tools:
                tool_calls = message["tool_calls"]
                all_tool_calls.extend(tool_calls)

                # 添加AI回复到消息历史
                tool_messages.append(
                    {
                        "role": "assistant",
                        "content": message.get("content", ""),
                        "tool_calls": [
                            {
                                "id": tc.get("id"),
                                "type": "function",
                                "function": {
                                    "name": tc.get("function", {}).get("name"),
                                    "arguments": tc.get("function", {}).get("arguments"),
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                )

                # 执行工具调用
                for tool_call in tool_calls:
                    tool_name = tool_call.get("function", {}).get("name")
                    try:
                        arguments = json.loads(
                            tool_call.get("function", {}).get("arguments", "{}")
                        )
                    except Exception:
                        arguments = {}

                    # 显示工具调用
                    cli._render_tool_call(tool_name, arguments)

                    # 执行工具
                    result = cli._execute_tool(tool_name, arguments)

                    # 显示工具结果
                    cli._render_tool_result(result)

                    # 添加工具结果到消息历史
                    tool_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.get("id"),
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )

            else:
                # 没有工具调用，得到最终回复
                final_content = message.get("content", "")

                # 处理不同格式的响应
                if not final_content and "base_resp" in data:
                    final_content = data.get("reply", "")

                return {
                    "content": final_content,
                    "thinking": "\n\n".join(all_thinking),
                    "tool_calls": all_tool_calls,
                    "tool_call_history": cli._extract_turn_tool_history(
                        tool_messages, initial_message_count
                    ),
                    "iterations": iteration + 1,
                }

        # 超过最大迭代次数
        return {
            "content": "工具调用次数过多，已停止。请简化您的请求。",
            "thinking": "\n\n".join(all_thinking),
            "tool_calls": all_tool_calls,
            "tool_call_history": cli._extract_turn_tool_history(
                tool_messages, initial_message_count
            ),
            "iterations": cli.max_tool_iterations,
        }

    except requests.exceptions.RequestException as e:
        return {"content": f"网络错误：{str(e)}", "thinking": "", "tool_calls": []}
    except Exception as e:
        return {"content": f"调用AI出错：{str(e)}", "thinking": "", "tool_calls": []}
