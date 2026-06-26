"""角色卡管理子包——编译、平台集成、路由注册。"""
from .compile import compile_personality_prompt
from .personality import allowed_image_file, register_personality_routes
from .platform import (
    _get_preview_token,
    _local_portrait_path,
    _post_card_to_platform,
    _role_card_platform_token,
    _role_card_platform_url,
)

__all__ = [
    "allowed_image_file",
    "compile_personality_prompt",
    "register_personality_routes",
    "_get_preview_token",
    "_local_portrait_path",
    "_post_card_to_platform",
    "_role_card_platform_token",
    "_role_card_platform_url",
]
