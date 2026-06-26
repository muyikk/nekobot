"""角色卡管理路由——聚合所有子路由注册并暴露公共符号。"""
from nbot.utils.logger import get_logger

_log = get_logger(__name__)

# 允许的图片扩展名（供 io 子模块使用）
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def register_personality_routes(app, server):
    """注册所有角色卡管理路由。"""
    from .personality_crud import register_crud_routes
    from .personality_ai import register_ai_routes
    from .personality_io import register_io_routes

    register_crud_routes(app, server)
    register_ai_routes(app, server)
    register_io_routes(app, server)
