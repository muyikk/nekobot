"""
工作区文件上传混入类

提供用户文件上传到工作区的方法。
作为 WorkspaceManager 的混入基类使用。
"""

import os
import logging
import shutil
import mimetypes
from typing import Dict, Any

_log = logging.getLogger(__name__)


class WorkspaceUploadMixin:
    """工作区文件上传混入类。"""

    def save_uploaded_file(self, session_id: str, file_data: bytes,
                           filename: str, session_type: str = "unknown") -> Dict[str, Any]:
        """保存用户上传的文件到工作区。

        Args:
            session_id: 会话ID
            file_data: 文件二进制内容
            filename: 原始文件名
            session_type: 会话类型

        Returns:
            文件信息字典
        """
        ws_path = self.get_or_create(session_id, session_type)
        safe_name = self._safe_filename(filename)
        file_path = os.path.join(ws_path, safe_name)

        # 同名文件自动加序号
        if os.path.exists(file_path):
            base, ext = os.path.splitext(safe_name)
            i = 1
            while os.path.exists(file_path):
                file_path = os.path.join(ws_path, f"{base}_{i}{ext}")
                i += 1

        with open(file_path, 'wb') as f:
            f.write(file_data)

        actual_name = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)

        _log.info(f"文件已保存到工作区: {actual_name} (session={session_id[:8]}...)")
        return {
            'success': True,
            'filename': actual_name,
            'path': file_path,
            'size': len(file_data),
            'mime_type': mime_type or 'application/octet-stream'
        }

    def save_uploaded_file_from_path(self, session_id: str, src_path: str,
                                      filename: str = None,
                                      session_type: str = "unknown") -> Dict[str, Any]:
        """从本地路径复制文件到工作区。

        Args:
            session_id: 会话ID
            src_path: 源文件路径
            filename: 目标文件名（默认使用源文件名）
            session_type: 会话类型

        Returns:
            文件信息字典
        """
        if not os.path.exists(src_path):
            return {'success': False, 'error': f'源文件不存在: {src_path}'}

        ws_path = self.get_or_create(session_id, session_type)
        if not filename:
            filename = os.path.basename(src_path)
        safe_name = self._safe_filename(filename)
        dest_path = os.path.join(ws_path, safe_name)

        # 同名文件自动加序号
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(safe_name)
            i = 1
            while os.path.exists(dest_path):
                dest_path = os.path.join(ws_path, f"{base}_{i}{ext}")
                i += 1

        shutil.copy2(src_path, dest_path)
        actual_name = os.path.basename(dest_path)
        mime_type, _ = mimetypes.guess_type(dest_path)

        return {
            'success': True,
            'filename': actual_name,
            'path': dest_path,
            'size': os.path.getsize(dest_path),
            'mime_type': mime_type or 'application/octet-stream'
        }
