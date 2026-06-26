"""向后兼容 shim——从 nbot.web.routes.persona 子包重新导出所有公共符号。"""
from nbot.web.routes.persona import (
    allowed_image_file,
    compile_personality_prompt,
    register_personality_routes,
)

__all__ = [
    "allowed_image_file",
    "compile_personality_prompt",
    "register_personality_routes",
]
