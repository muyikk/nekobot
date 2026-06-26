"""Web AI 图片处理——多模态图片理解。"""

from typing import Dict, List

from nbot.utils.logger import get_logger
from nbot.core import resolve_chat_completion_url, response_json_utf8
from nbot.web.utils.config_loader import get_vision_model_config

_log = get_logger(__name__)


def get_ai_response_with_images(
    server, messages: List[Dict], image_urls: List[str], user_question: str = None
) -> str:
    """获取带图片的 AI 回复（多模态）"""
    try:
        # 获取图片理解模型配置（新架构）
        vision_config = get_vision_model_config()
        api_key = None
        base_url = ""
        model = "zai-org/GLM-4.6V"
        provider_type = "openai_compatible"
        system_prompt = "请详细描述这张图片的内容。"

        if vision_config and vision_config.get("api_key"):
            # 使用新架构的配置
            api_key = vision_config.get("api_key")
            base_url = vision_config.get("base_url", "")
            model = vision_config.get("model", "zai-org/GLM-4.6V")
            provider_type = vision_config.get("provider_type", "openai_compatible")
            system_prompt = vision_config.get("system_prompt", "请详细描述这张图片的内容。")
        else:
            # 回退到旧的配置方式
            if not server.ai_client:
                return "AI 服务未配置，请在 AI 配置页面设置 API Key 和 Base URL。"

            api_key = getattr(server.ai_client, "api_key", None)
            base_url = getattr(server.ai_client, "base_url", None)
            model = getattr(server.ai_client, "pic_model", None) or "zai-org/GLM-4.6V"
            provider_type = getattr(server.ai_client, "provider_type", "openai_compatible")
            system_prompt = "请详细描述这张图片的内容。"

            # 尝试从config.ini获取silicon_api_key
            if not api_key:
                try:
                    import configparser
                    config = configparser.ConfigParser()
                    config.read("config.ini", encoding="utf-8")
                    api_key = config.get("ApiKey", "silicon_api_key", fallback="") or config.get("ApiKey", "api_key", fallback="")
                    base_url = "https://api.siliconflow.cn/v1"
                    model = config.get("pic", "model", fallback="zai-org/GLM-4.6V")
                except Exception:
                    pass

        if not api_key:
            _log.warning("API key not configured for image processing")
            return "图片处理服务未配置 API Key，请在 AI 配置中心配置图片理解模型。"

        # 构建多模态消息 - 简化版本，只包含当前图片，不包含历史记录
        multimodal_messages = []

        # 添加系统提示
        multimodal_messages.append({
            "role": "system",
            "content": "你是一个专业的图片分析助手。请详细描述图片中的内容，包括场景、人物、物体、颜色、氛围等细节。如果用户有具体问题，请结合图片内容回答。"
        })

        # 构建用户内容（图片 + 文本）
        user_content = []
        for img_url in image_urls:
            user_content.append(
                {"type": "image_url", "image_url": {"url": img_url}}
            )

        # 添加用户的原始问题或默认提示
        if user_question:
            user_text = user_question
        else:
            user_text = system_prompt
        user_content.append({"type": "text", "text": user_text})

        multimodal_messages.append({"role": "user", "content": user_content})

        # 调用多模态模型
        import requests

        # 构建请求URL
        if provider_type == "siliconflow" or "siliconflow" in base_url:
            url = "https://api.siliconflow.cn/v1/chat/completions"
        else:
            url = resolve_chat_completion_url(base_url, model=model, provider_type=provider_type)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": multimodal_messages,
            "stream": False,
        }

        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        data = response_json_utf8(response)

        if not data.get("choices"):
            return "图片处理返回结果为空。"

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content.strip() if content else "图片处理完成，但未返回内容。"

    except ImportError:
        return "图片处理失败：缺少 requests 库。"
    except Exception as e:
        # 回退到普通响应
        if user_question:
            temp_messages = messages.copy()
            temp_messages.append({"role": "user", "content": user_question})
            return server._get_ai_response(temp_messages)
        return f"处理图片时出错: {str(e)}"
