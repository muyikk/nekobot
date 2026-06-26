"""
工作区文件引用管理混入类

提供外部文件引用的注册、查询、删除功能。
作为 WorkspaceManager 的混入基类使用。
"""

import os
import mimetypes
from datetime import datetime
from typing import Optional, Dict, Any, List

from .utils import _resolve_within
from nbot.utils.logger import get_logger

_log = get_logger(__name__)


class WorkspaceReferenceMixin:
    """工作区文件引用管理混入类。

    所有方法依赖 self._meta / self._save_meta / self.get_or_create /
    self._safe_filename 等由 WorkspaceManager 提供的属性。
    """

    # ========== 文件引用管理 ==========

    def _get_file_references(self, session_id: str) -> List[Dict[str, Any]]:
        """获取会话的文件引用列表（内部方法）。"""
        info = self._meta.get(session_id)
        if not info:
            return []
        refs = info.get("file_references")
        if isinstance(refs, list):
            return refs
        info["file_references"] = []
        return info["file_references"]

    def register_file_reference(
        self,
        session_id: str,
        source_path: str,
        display_name: str,
        *,
        session_type: str = "web",
        relative_path: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """注册一个外部文件引用到工作区。

        Args:
            session_id: 会话ID
            source_path: 源文件绝对路径
            display_name: 显示名称
            session_type: 会话类型
            relative_path: 相对路径
            metadata: 附加元数据

        Returns:
            操作结果
        """
        ws_path = self.get_or_create(session_id, session_type)
        if not ws_path:
            return {"success": False, "error": "Workspace not found"}

        normalized_source = os.path.normpath(source_path)
        if not os.path.exists(normalized_source):
            return {"success": False, "error": "Source file not found"}

        safe_name = self._safe_filename(display_name)
        safe_relative = self._safe_filename(relative_path) if relative_path else ""
        reference_path = f"{safe_relative}/{safe_name}" if safe_relative else safe_name

        refs = self._get_file_references(session_id)
        refs[:] = [ref for ref in refs if ref.get("path") != reference_path]

        mime_type, _ = mimetypes.guess_type(normalized_source)
        reference = {
            "name": safe_name,
            "path": reference_path,
            "source_path": normalized_source,
            "size": os.path.getsize(normalized_source),
            "mime_type": mime_type or "application/octet-stream",
            "reference": True,
            "reference_kind": "external",
            "created_at": datetime.now().isoformat(),
        }
        if metadata:
            reference["metadata"] = metadata

        refs.append(reference)
        self._save_meta()
        return {"success": True, "reference": reference}

    def get_file_reference(
        self, session_id: str, filename: str
    ) -> Optional[Dict[str, Any]]:
        """获取文件引用信息。"""
        normalized_name = filename.replace("\\", "/")
        for ref in self._get_file_references(session_id):
            if ref.get("path") == normalized_name:
                source_path = ref.get("source_path")
                if source_path and os.path.exists(source_path):
                    return ref
        return None

    def delete_file_reference(self, session_id: str, filename: str) -> Dict[str, Any]:
        """删除文件引用。"""
        refs = self._get_file_references(session_id)
        normalized_name = filename.replace("\\", "/")
        original_count = len(refs)
        refs[:] = [ref for ref in refs if ref.get("path") != normalized_name]
        if len(refs) == original_count:
            return {"success": False, "error": "File not found"}
        self._save_meta()
        return {"success": True, "filename": normalized_name, "reference": True}
