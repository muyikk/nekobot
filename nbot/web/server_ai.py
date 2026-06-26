"""Web 服务器 AI 客户端相关方法。

提供 AI 配置加载、多模型管理、AIClient 初始化等能力，
以 mixin 形式组合到 WebChatServer。
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from nbot.utils.logger import get_logger

_log = get_logger(__name__)

# 尝试导入配置加载器（可选）
try:
    from nbot.web.utils.config_loader import (
        get_api_config,
        get_pic_config,
        get_search_config,
        resolve_runtime_api_key,
        get_video_config,
    )

    _CONFIG_LOADER_AVAILABLE = True
except ImportError:
    _CONFIG_LOADER_AVAILABLE = False
    get_api_config = None  # type: ignore[misc,assignment]
    get_pic_config = None  # type: ignore[misc,assignment]
    get_search_config = None  # type: ignore[misc,assignment]
    resolve_runtime_api_key = None  # type: ignore[misc,assignment]
    get_video_config = None  # type: ignore[misc,assignment]

# 尝试导入知识库配置（可选）
try:
    from nbot.core.knowledge import configure_knowledge_embedding

    _KNOWLEDGE_EMBEDDING_AVAILABLE = True
except ImportError:
    _KNOWLEDGE_EMBEDDING_AVAILABLE = False
    configure_knowledge_embedding = None  # type: ignore[misc,assignment]

# 尝试导入 nbot.config（替代 config.ini）
try:
    from nbot.config import get_config

    _NBOT_CONFIG_AVAILABLE = True
except ImportError:
    _NBOT_CONFIG_AVAILABLE = False
    get_config = None  # type: ignore[misc,assignment]


class AIMixin:
    """AI 客户端相关方法 mixin。"""

    def _initialize_ai_client(
        self,
        *,
        provider_type: str = None,
        supports_tools: Optional[bool] = None,
        supports_reasoning: Optional[bool] = None,
        supports_stream: Optional[bool] = None,
    ) -> bool:
        """初始化 AI 客户端。

        Args:
            provider_type: 提供商类型。
            supports_tools: 是否支持工具调用。
            supports_reasoning: 是否支持推理。
            supports_stream: 是否支持流式输出。

        Returns:
            初始化成功返回 True。
        """
        resolved_provider_type = provider_type or self.ai_config.get(
            "provider_type", self.ai_config.get("provider", "openai_compatible")
        )
        if resolve_runtime_api_key:
            self.ai_api_key = resolve_runtime_api_key(
                self.ai_api_key or "",
                resolved_provider_type,
            )

        if not self.ai_api_key or not self.ai_base_url:
            self.ai_client = None
            return False

        try:
            if _CONFIG_LOADER_AVAILABLE and get_pic_config:
                pic_config = get_pic_config() if get_pic_config else {}
                search_config = get_search_config() if get_search_config else {}
                video_config = get_video_config() if get_video_config else {}
                api_config = get_api_config() if get_api_config else {}
            else:
                pic_config, search_config, video_config, api_config = self._fallback_ai_configs()

            from nbot.services.ai import AIClient

            resolved_supports_tools = (
                self.ai_config.get("supports_tools", True)
                if supports_tools is None
                else supports_tools
            )
            resolved_supports_reasoning = (
                self.ai_config.get("supports_reasoning", True)
                if supports_reasoning is None
                else supports_reasoning
            )
            resolved_supports_stream = (
                self.ai_config.get("supports_stream", True)
                if supports_stream is None
                else supports_stream
            )

            self.ai_client = AIClient(
                api_key=self.ai_api_key,
                base_url=self.ai_base_url,
                model=self.ai_model,
                pic_model=pic_config.get("model", ""),
                search_api_key=search_config.get("api_key", ""),
                search_api_url=search_config.get("api_url", ""),
                video_api=video_config.get("api_key", ""),
                silicon_api_key=api_config.get("silicon_api_key", ""),
                provider_type=resolved_provider_type,
                supports_tools=resolved_supports_tools,
                supports_reasoning=resolved_supports_reasoning,
                supports_stream=resolved_supports_stream,
            )
            return True
        except Exception as e:
            _log.error(f"Failed to initialize AI client: {e}")
            self.ai_client = None
            return False

    def _fallback_ai_configs(self) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """当配置加载器不可用时，回退到 nbot.config 或 config.ini。"""
        pic_config: Dict[str, Any] = {}
        search_config: Dict[str, Any] = {}
        video_config: Dict[str, Any] = {}
        api_config: Dict[str, Any] = {}

        if _NBOT_CONFIG_AVAILABLE and get_config:
            cfg = get_config()
            pic_config = {"model": cfg.get("PIC__MODEL", "")}
            search_config = {
                "api_key": cfg.get("SEARCH__API_KEY", ""),
                "api_url": cfg.get("SEARCH__API_URL", ""),
            }
            video_config = {"api_key": cfg.get("VIDEO__API_KEY", "")}
            api_config = {"silicon_api_key": cfg.get("APIKEY__SILICON_API_KEY", "")}
        else:
            import configparser

            config = configparser.ConfigParser()
            config.read("config.ini", encoding="utf-8")
            pic_config = {"model": config.get("pic", "model", fallback="")}
            search_config = {
                "api_key": config.get("search", "api_key", fallback=""),
                "api_url": config.get("search", "api_url", fallback=""),
            }
            video_config = {"api_key": config.get("video", "api_key", fallback="")}
            api_config = {
                "silicon_api_key": config.get("ApiKey", "silicon_api_key", fallback="")
            }

        return pic_config, search_config, video_config, api_config

    def _load_ai_config(self):
        """从配置文件加载 AI 配置（支持 .env 环境变量）。"""
        try:
            if _CONFIG_LOADER_AVAILABLE and get_api_config:
                api_config = get_api_config()
                self.ai_api_key = api_config.get("api_key", "")
                self.ai_base_url = api_config.get("base_url", "")
                self.ai_model = api_config.get("model", "MiniMax-M2.7")
                self.ai_config["provider_type"] = api_config.get(
                    "provider_type",
                    self.ai_config.get("provider_type", "openai_compatible"),
                )
            elif _NBOT_CONFIG_AVAILABLE and get_config:
                cfg = get_config()
                self.ai_api_key = cfg.get("APIKEY__API_KEY", "")
                self.ai_base_url = cfg.get("APIKEY__BASE_URL", "")
                self.ai_model = cfg.get("APIKEY__MODEL", "MiniMax-M2.7")
                self.ai_config["provider_type"] = cfg.get(
                    "APIKEY__PROVIDER_TYPE",
                    self.ai_config.get("provider_type", "openai_compatible"),
                )
            else:
                import configparser

                config = configparser.ConfigParser()
                config.read("config.ini", encoding="utf-8")
                self.ai_api_key = config.get("ApiKey", "api_key", fallback="")
                self.ai_base_url = config.get("ApiKey", "base_url", fallback="")
                self.ai_model = config.get("ApiKey", "model", fallback="MiniMax-M2.7")

            _log.info(
                f"[Config] 加载 AI 配置: model={self.ai_model}, "
                f"base_url={self.ai_base_url[:30] if self.ai_base_url else 'None'}..."
            )

            if self.ai_api_key and self.ai_base_url:
                _log.info("[Config] AI client initialization deferred to background startup")
                return
            else:
                _log.warning("[Config] AI 配置不完整，api_key 或 base_url 为空")
        except Exception as e:
            _log.error(f"Failed to load AI config: {e}")

    def _load_ai_models(self):
        """加载多模型配置。"""
        try:
            from nbot.web.secure_store import read_secure_json, write_secure_json

            models_file = os.path.join(self.data_dir, "ai_models.json")
            if os.path.exists(models_file):
                data, was_plaintext = read_secure_json(models_file, self.data_dir, {})
                if was_plaintext:
                    write_secure_json(models_file, self.data_dir, data)
                if isinstance(data, dict):
                    self.ai_models = data.get("models", [])
                    self.active_model_id = data.get("active_model_id")
                    self.active_models_by_purpose = data.get("active_models_by_purpose", {})

            if not self.ai_models and self.ai_api_key:
                default_model = {
                    "id": str(uuid.uuid4()),
                    "name": "默认配置",
                    "provider": "custom",
                    "provider_type": "openai_compatible",
                    "api_key": self.ai_api_key,
                    "base_url": self.ai_base_url,
                    "model": self.ai_model,
                    "enabled": True,
                    "is_default": True,
                    "supports_tools": True,
                    "supports_reasoning": True,
                    "supports_stream": True,
                    "temperature": 0.7,
                    "max_tokens": 2000,
                    "top_p": 0.9,
                    "created_at": datetime.now().isoformat(),
                }
                self.ai_models.append(default_model)
                self.active_model_id = default_model["id"]
                self._save_data("ai_models")
        except Exception as e:
            _log.error(f"Failed to load AI models: {e}")

    def _apply_ai_model(self, model_id: str, purpose: str = None) -> bool:
        """应用指定的 AI 模型配置。

        Args:
            model_id: 模型配置 ID。
            purpose: 模型用途 (chat, vision, video, tts, stt, embedding)。

        Returns:
            应用成功返回 True。
        """
        try:
            model = None
            for m in self.ai_models:
                if m["id"] == model_id:
                    model = m
                    break

            if not model or not model.get("enabled", True):
                return False

            model_purpose = purpose or model.get("purpose", "chat")
            self.active_models_by_purpose[model_purpose] = model_id

            if model_purpose == "chat":
                self.active_model_id = model_id

                model_provider_type = model.get(
                    "provider_type", model.get("provider", "openai_compatible")
                )
                if resolve_runtime_api_key:
                    self.ai_api_key = resolve_runtime_api_key(
                        model.get("api_key", ""),
                        model_provider_type,
                    )
                else:
                    self.ai_api_key = model.get("api_key", "")
                self.ai_base_url = model.get("base_url", "")
                self.ai_model = model.get("model", "")

                self.ai_config.update(
                    {
                        "provider": model.get("provider", "custom"),
                        "provider_type": model.get(
                            "provider_type", model.get("provider", "openai_compatible")
                        ),
                        "api_key": self.ai_api_key,
                        "base_url": self.ai_base_url,
                        "model": self.ai_model,
                        "temperature": model.get("temperature", 0.7),
                        "max_tokens": model.get("max_tokens", 2000),
                        "top_p": model.get("top_p", 0.9),
                        "frequency_penalty": model.get("frequency_penalty", 0),
                        "presence_penalty": model.get("presence_penalty", 0),
                        "system_prompt": model.get("system_prompt", ""),
                        "timeout": model.get("timeout", 60),
                        "retry_count": model.get("retry_count", 3),
                        "stream": model.get("stream", True),
                        "enable_memory": model.get("enable_memory", True),
                        "image_model": model.get("image_model", ""),
                        "search_api_key": model.get("search_api_key", ""),
                        "embedding_model": model.get("embedding_model", ""),
                        "max_context_length": model.get("max_context_length", 100000),
                        "supports_tools": model.get("supports_tools", True),
                        "supports_reasoning": model.get("supports_reasoning", True),
                        "supports_stream": model.get("supports_stream", True),
                    }
                )
                self._save_data("ai_config")

                if self.ai_api_key and self.ai_base_url:
                    self._initialize_ai_client(
                        provider_type=model_provider_type,
                        supports_tools=model.get("supports_tools", True),
                        supports_reasoning=model.get("supports_reasoning", True),
                        supports_stream=model.get("supports_stream", True),
                    )

                embedding_model = model.get("embedding_model", "")
                if configure_knowledge_embedding and embedding_model:
                    try:
                        configure_knowledge_embedding(
                            api_key=self.ai_api_key,
                            base_url=self.ai_base_url,
                            model=embedding_model
                        )
                    except Exception as e:
                        _log.warning(f"Failed to configure knowledge embedding: {e}")

            self._save_data("ai_models")
            _log.info(f"Applied model {model_id} for purpose {model_purpose}")
            return True
        except Exception as e:
            _log.error(f"Failed to apply AI model: {e}")
            return False
