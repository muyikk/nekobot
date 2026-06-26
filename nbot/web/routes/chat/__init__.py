"""NekoBot Web Chat 路由子包。

提供会话管理的完整 REST API：
- 会话 CRUD（创建、读取、更新、删除）
- 消息管理（添加、删除、清空、重新生成）
- 归档与恢复
- 上下文压缩与 AI 总结
- 导入/导出/Fork
- 角色运行时时间线
"""

from nbot.web.routes.chat.sessions_utils import (
    _copy_character_runtime_state,
    _get_base_dir,
    _normalize_runtime_timeline_entry,
    _normalize_tags,
    _runtime_snapshot_signature,
    _skills_prompt_injection_enabled,
)
from nbot.web.routes.chat.sessions import register_session_routes

__all__ = [
    "_copy_character_runtime_state",
    "_get_base_dir",
    "_normalize_runtime_timeline_entry",
    "_normalize_tags",
    "_runtime_snapshot_signature",
    "_skills_prompt_injection_enabled",
    "register_session_routes",
]
