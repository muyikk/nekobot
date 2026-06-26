"""
工作区管理子包

提供：
- WorkspaceManager: 工作区管理器单例
- _resolve_within / _normalize_edit_block / _replace_content_block: 工具函数
"""

from nbot.core.workspace.utils import (
    _resolve_within,
    _normalize_edit_block,
    _replace_content_block,
)
from nbot.core.workspace.manager import (
    WorkspaceManager,
    workspace_manager,
)

__all__ = [
    "WorkspaceManager",
    "workspace_manager",
    "_resolve_within",
    "_normalize_edit_block",
    "_replace_content_block",
]
