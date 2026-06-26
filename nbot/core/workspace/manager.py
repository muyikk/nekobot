"""
工作区管理器核心

每个会话（QQ私聊/群聊、Web会话）对应一个独立的工作区文件夹。
用户上传的文件存入工作区，AI 也可以在工作区中创建、读取、修改、删除文件。
删除会话时同步删除对应的工作区文件夹。

环境变量:
    NBOT_WORKSPACE_DIR: 自定义工作区根目录路径（可选）
                        如果不设置，默认使用项目目录下的 data/workspaces
"""

import os
import json
import shutil
import logging
import hashlib
import tempfile
from datetime import datetime
from typing import Optional, Dict, Any, List

from .file_ops import WorkspaceFileOpsMixin
from .references import WorkspaceReferenceMixin
from .shared_ops import WorkspaceSharedOpsMixin
from .upload import WorkspaceUploadMixin

_log = logging.getLogger(__name__)


class WorkspaceManager(WorkspaceFileOpsMixin, WorkspaceUploadMixin, WorkspaceReferenceMixin, WorkspaceSharedOpsMixin):
    """工作区管理器（单例模式）。

    继承 WorkspaceFileOpsMixin、WorkspaceReferenceMixin 和 WorkspaceSharedOpsMixin，
    提供完整的文件操作、引用管理和共享工作区功能。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 优先从环境变量获取工作区目录
        workspace_env = os.environ.get('NBOT_WORKSPACE_DIR')

        if workspace_env:
            self.workspaces_dir = os.path.normpath(workspace_env)
            _log.info(f"使用环境变量指定的工作区目录: {self.workspaces_dir}")
        else:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.workspaces_dir = os.path.join(self.base_dir, 'data', 'workspaces')
            _log.info(f"使用默认工作区目录: {self.workspaces_dir}")

        self.meta_file = os.path.join(self.workspaces_dir, '_meta.json')

        # 确保工作区目录存在
        try:
            os.makedirs(self.workspaces_dir, exist_ok=True)
            _log.info(f"工作区目录已就绪: {self.workspaces_dir}")
        except Exception as e:
            _log.error(f"创建工作区目录失败: {e}")
            self.workspaces_dir = os.path.join(tempfile.gettempdir(), 'nbot_workspaces')
            self.meta_file = os.path.join(self.workspaces_dir, '_meta.json')
            os.makedirs(self.workspaces_dir, exist_ok=True)
            _log.warning(f"使用临时目录作为工作区: {self.workspaces_dir}")

        # session_id -> workspace_path 的映射
        self._meta: Dict[str, Dict[str, Any]] = {}
        self._load_meta()

        # 共享工作区（所有会话共用）
        self.shared_workspace_dir = os.path.join(self.workspaces_dir, '_shared')
        try:
            os.makedirs(self.shared_workspace_dir, exist_ok=True)
            _log.info(f"共享工作区目录已就绪: {self.shared_workspace_dir}")
        except Exception as e:
            _log.error(f"创建共享工作区目录失败: {e}")

    # ========== 共享工作区获取 ==========

    def get_shared_workspace(self) -> str:
        """获取共享工作区路径（所有会话共用）。"""
        return self.shared_workspace_dir

    # ========== 工作区生命周期 ==========

    def get_or_create(self, session_id: str, session_type: str = "unknown",
                      session_name: str = "") -> str:
        """获取或创建会话对应的工作区目录。

        Args:
            session_id: 会话唯一标识
            session_type: 会话类型 (qq_private, qq_group, web, workflow)
            session_name: 会话名称（用于元数据记录）

        Returns:
            工作区绝对路径
        """
        if session_id in self._meta:
            ws_path = self._meta[session_id]['path']
            if os.path.isdir(ws_path):
                return ws_path
            os.makedirs(ws_path, exist_ok=True)
            return ws_path

        # 创建新工作区
        if session_type.startswith('qq_'):
            parts = session_id.split('_')
            if len(parts) >= 3:
                qq_id = parts[-1]
                folder_name = f"{session_type}_{qq_id}"
            else:
                short_hash = hashlib.md5(session_id.encode()).hexdigest()[:8]
                folder_name = f"{session_type}_{short_hash}"
        else:
            short_id = session_id.replace('-', '')[:8]
            folder_name = f"{session_type}_{short_id}"

        # 清理文件夹名中的非法字符
        folder_name = folder_name.replace(':', '_').replace('/', '_').replace('\\', '_')

        ws_path = os.path.join(self.workspaces_dir, folder_name)
        os.makedirs(ws_path, exist_ok=True)

        self._meta[session_id] = {
            'path': ws_path,
            'folder': folder_name,
            'type': session_type,
            'name': session_name,
            'created_at': datetime.now().isoformat()
        }
        self._save_meta()

        _log.info(f"创建工作区: {folder_name} (session={session_id[:8]}...)")
        return ws_path

    def get_workspace(self, session_id: str) -> Optional[str]:
        """获取会话对应的工作区路径（不自动创建）。

        Returns:
            工作区路径，不存在则返回 None
        """
        info = self._meta.get(session_id)
        if info and os.path.isdir(info['path']):
            return info['path']
        return None

    def delete_workspace(self, session_id: str) -> bool:
        """删除会话对应的工作区。

        Returns:
            是否成功删除
        """
        info = self._meta.get(session_id)
        if not info:
            return False

        ws_path = info['path']
        try:
            if os.path.isdir(ws_path):
                shutil.rmtree(ws_path)
                _log.info(f"删除工作区: {info['folder']} (session={session_id[:8]}...)")
        except Exception as e:
            _log.error(f"删除工作区失败: {ws_path}, {e}")
            return False

        del self._meta[session_id]
        self._save_meta()
        return True

    # ========== 元数据管理 ==========

    def _load_meta(self):
        """加载工作区元数据，并修复跨平台路径问题。"""
        if os.path.exists(self.meta_file):
            try:
                with open(self.meta_file, 'r', encoding='utf-8') as f:
                    loaded_meta = json.load(f)

                self._meta = {}
                for session_id, info in loaded_meta.items():
                    old_path = info.get('path', '')
                    folder = info.get('folder', '')

                    if folder:
                        new_path = os.path.join(self.workspaces_dir, folder)
                    else:
                        new_path = os.path.join(self.workspaces_dir, session_id)

                    new_path = os.path.normpath(new_path)

                    if old_path != new_path:
                        _log.info(f"修复工作区路径: {old_path} -> {new_path}")

                    info['path'] = new_path
                    self._meta[session_id] = info

            except Exception as e:
                _log.error(f"加载工作区元数据失败: {e}")
                self._meta = {}

    def _save_meta(self):
        """保存工作区元数据。"""
        try:
            with open(self.meta_file, 'w', encoding='utf-8') as f:
                json.dump(self._meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            _log.error(f"保存工作区元数据失败: {e}")

    def get_all_workspaces(self) -> List[Dict[str, Any]]:
        """获取所有工作区信息。"""
        result = []
        for session_id, info in self._meta.items():
            ws_path = info['path']
            file_count = 0
            total_size = 0
            if os.path.isdir(ws_path):
                for root, dirs, files in os.walk(ws_path):
                    file_count += len(files)
                    for f in files:
                        total_size += os.path.getsize(os.path.join(root, f))
            result.append({
                'session_id': session_id,
                'folder': info.get('folder', ''),
                'type': info.get('type', 'unknown'),
                'name': info.get('name', ''),
                'created_at': info.get('created_at', ''),
                'file_count': file_count,
                'total_size': total_size
            })
        return result

    # ========== 工具方法 ==========

    @staticmethod
    def _safe_filename(filename: str) -> str:
        """清理文件名，移除危险字符。"""
        parts = filename.replace('\\', '/').split('/')
        safe_parts = []
        for part in parts:
            if part in ('.', '..', ''):
                continue
            safe = ''.join(c for c in part if c.isalnum() or c in '._- ()')
            if safe:
                safe_parts.append(safe)
        return '/'.join(safe_parts) if safe_parts else 'unnamed_file'


# 全局单例
workspace_manager = WorkspaceManager()
