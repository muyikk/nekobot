"""
工作区共享操作混入类

提供共享工作区中的文件创建、读取、编辑、删除、列表、移动等操作。
作为 WorkspaceManager 的混入基类使用。
"""

import os
import shutil
import mimetypes
from typing import Dict, Any

from .utils import _resolve_within, _replace_content_block


class WorkspaceSharedOpsMixin:
    """工作区共享操作混入类。

    所有方法依赖 self.shared_workspace_dir 等由 WorkspaceManager 提供的属性。
    """

    # ========== 共享工作区文件列表 ==========

    def list_shared_files(self, path: str = '') -> Dict[str, Any]:
        """列出共享工作区中的文件。"""
        target_path = _resolve_within(self.shared_workspace_dir, path)
        if not target_path:
            return {'success': False, 'error': '路径不合法'}

        if not os.path.exists(target_path) or not os.path.isdir(target_path):
            return {'success': False, 'error': '目录不存在'}

        files = []
        try:
            for name in os.listdir(target_path):
                full_path = os.path.join(target_path, name)
                if os.path.isdir(full_path):
                    files.append({
                        'name': name,
                        'type': 'directory',
                        'size': 0,
                        'path': path + '/' + name if path else name,
                        'scope': 'shared'
                    })
                else:
                    mime_type, _ = mimetypes.guess_type(full_path)
                    files.append({
                        'name': name,
                        'type': 'file',
                        'size': os.path.getsize(full_path),
                        'mime_type': mime_type or 'application/octet-stream',
                        'path': path + '/' + name if path else name,
                        'scope': 'shared'
                    })
        except Exception as e:
            return {'success': False, 'error': str(e)}

        return {'success': True, 'files': files, 'count': len(files), 'scope': 'shared'}

    def list_shared_files_recursive(self, path: str = '') -> Dict[str, Any]:
        """递归列出共享工作区中所有子目录的文件。"""
        target_path = _resolve_within(self.shared_workspace_dir, path)
        if not target_path:
            return {'success': False, 'error': '路径不合法'}

        if not os.path.exists(target_path) or not os.path.isdir(target_path):
            return {'success': False, 'error': '目录不存在'}

        all_items = []

        def scan_directory(current_path: str, relative_prefix: str = ''):
            try:
                for name in os.listdir(current_path):
                    full_path = os.path.join(current_path, name)
                    relative_path = relative_prefix + '/' + name if relative_prefix else name

                    if os.path.isdir(full_path):
                        all_items.append({
                            'name': name,
                            'type': 'directory',
                            'size': 0,
                            'path': relative_path,
                            'scope': 'shared'
                        })
                        scan_directory(full_path, relative_path)
                    else:
                        mime_type, _ = mimetypes.guess_type(full_path)
                        all_items.append({
                            'name': name,
                            'type': 'file',
                            'size': os.path.getsize(full_path),
                            'mime_type': mime_type or 'application/octet-stream',
                            'path': relative_path,
                            'scope': 'shared'
                        })
            except Exception:
                pass

        scan_directory(target_path, path)

        return {
            'success': True,
            'files': all_items,
            'count': len(all_items),
            'scope': 'shared',
            'recursive': True
        }

    # ========== 共享工作区文件读取 ==========

    def read_shared_file(self, filename: str, start_line: int = None, end_line: int = None,
                         char_count: int = None, start_char: int = None) -> Dict[str, Any]:
        """读取共享工作区中的文件。"""
        file_path = os.path.normpath(os.path.join(self.shared_workspace_dir, filename))
        if not file_path.startswith(os.path.normpath(self.shared_workspace_dir)):
            return {'success': False, 'error': '路径不合法'}

        if not os.path.exists(file_path):
            return {'success': False, 'error': f'文件不存在: {filename}'}

        if os.path.isdir(file_path):
            return {'success': False, 'error': f'这是一个文件夹，不是文件: {filename}'}

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if start_line is not None or end_line is not None:
                lines = content.split('\n')
                start = start_line - 1 if start_line else 0
                end = end_line if end_line else len(lines)
                content = '\n'.join(lines[start:end])

            if start_char is not None or char_count is not None:
                start = start_char if start_char else 0
                end = start + char_count if char_count else len(content)
                content = content[start:end]

            return {
                'success': True,
                'filename': filename,
                'content': content,
                'size': len(content),
                'scope': 'shared'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ========== 共享工作区文件创建 ==========

    def create_shared_folder(self, folder_name: str, path: str = '') -> Dict[str, Any]:
        """在共享工作区创建文件夹。"""
        if not folder_name.strip():
            return {'success': False, 'error': '文件夹名称不能为空'}

        import re
        if not re.match(r'^[\w\-\. ]+$', folder_name):
            return {'success': False, 'error': '文件夹名称包含非法字符'}

        if path:
            folder_path = _resolve_within(self.shared_workspace_dir, path, folder_name)
            if not folder_path:
                return {'success': False, 'error': '路径不合法，不能超出共享工作区'}
        else:
            folder_path = _resolve_within(self.shared_workspace_dir, folder_name)
            if not folder_path:
                return {'success': False, 'error': '路径不合法，不能超出共享工作区'}

        try:
            if os.path.exists(folder_path):
                return {'success': False, 'error': '文件夹已存在'}

            os.makedirs(folder_path, exist_ok=True)
            return {'success': True, 'name': folder_name, 'path': path + '/' + folder_name if path else folder_name}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def create_shared_file(self, filename: str, content: str) -> Dict[str, Any]:
        """在共享工作区中创建/覆盖文本文件。

        Args:
            filename: 文件名
            content: 文件内容

        Returns:
            操作结果
        """
        safe_name = self._safe_filename(filename)

        file_path = os.path.normpath(os.path.join(self.shared_workspace_dir, safe_name))
        if not file_path.startswith(os.path.normpath(self.shared_workspace_dir)):
            return {'success': False, 'error': '路径不合法，不能超出共享工作区范围'}

        parent_dir = os.path.dirname(file_path)
        if not parent_dir.startswith(os.path.normpath(self.shared_workspace_dir)):
            return {'success': False, 'error': '路径不合法，不能超出共享工作区范围'}

        try:
            if parent_dir != self.shared_workspace_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {
                'success': True,
                'filename': safe_name,
                'path': file_path,
                'scope': 'shared',
                'size': len(content.encode('utf-8'))
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ========== 共享工作区文件编辑与删除 ==========

    def edit_shared_file(self, filename: str, old_content: str, new_content: str) -> Dict[str, Any]:
        """修改共享工作区中的文件（查找替换方式）。"""
        file_path = os.path.normpath(os.path.join(self.shared_workspace_dir, filename))
        if not file_path.startswith(os.path.normpath(self.shared_workspace_dir)):
            return {'success': False, 'error': '路径不合法'}

        if not os.path.exists(file_path):
            return {'success': False, 'error': f'文件不存在: {filename}'}

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            new_file_content, match_mode = _replace_content_block(
                content, old_content, new_content
            )
            if new_file_content is None:
                return {'success': False, 'error': '未找到要替换的内容'}
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_file_content)

            return {
                'success': True,
                'filename': filename,
                'scope': 'shared',
                'size': len(new_file_content.encode('utf-8')),
                'match_mode': match_mode,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def delete_shared_file(self, filename: str) -> Dict[str, Any]:
        """删除共享工作区中的文件或文件夹。"""
        file_path = os.path.normpath(os.path.join(self.shared_workspace_dir, filename))
        if not file_path.startswith(os.path.normpath(self.shared_workspace_dir)):
            return {'success': False, 'error': '路径不合法'}

        if not os.path.exists(file_path):
            return {'success': False, 'error': f'文件不存在: {filename}'}

        try:
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
            else:
                os.remove(file_path)
            return {'success': True, 'filename': filename}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ========== 共享工作区文件移动 ==========

    def move_shared_file(self, filename: str, target_path: str = '') -> Dict[str, Any]:
        """移动共享工作区中的文件。"""
        src_path = _resolve_within(self.shared_workspace_dir, filename)
        if not src_path:
            return {'success': False, 'error': '路径不合法'}

        if not os.path.exists(src_path):
            return {'success': False, 'error': f'文件不存在: {filename}'}

        if target_path:
            dst_dir = _resolve_within(self.shared_workspace_dir, target_path)
            if not dst_dir:
                return {'success': False, 'error': '目标路径不合法，不能超出共享工作区'}
        else:
            dst_dir = self.shared_workspace_dir

        if not os.path.exists(dst_dir) or not os.path.isdir(dst_dir):
            return {'success': False, 'error': '目标目录不存在'}

        try:
            shutil.move(src_path, dst_dir)
            new_path = os.path.join(target_path, os.path.basename(filename)) if target_path else os.path.basename(filename)
            return {'success': True, 'new_path': new_path.replace('\\', '/')}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def move_to_shared(self, session_id: str, filename: str, target_path: str = '') -> Dict[str, Any]:
        """将私有工作区的文件移动到共享工作区。"""
        src_path = self.get_file_path(session_id, filename)
        if not src_path:
            return {'success': False, 'error': f'文件不存在: {filename}'}

        if not os.path.exists(src_path):
            return {'success': False, 'error': f'文件不存在: {filename}'}

        if target_path:
            dst_dir = os.path.normpath(os.path.join(self.shared_workspace_dir, target_path))
            if not dst_dir.startswith(os.path.normpath(self.shared_workspace_dir)):
                return {'success': False, 'error': '目标路径不合法'}
        else:
            dst_dir = self.shared_workspace_dir

        if not os.path.exists(dst_dir):
            return {'success': False, 'error': '目标目录不存在'}

        try:
            filename_only = os.path.basename(filename)
            dst_path = os.path.join(dst_dir, filename_only)

            if os.path.exists(dst_path):
                name, ext = os.path.splitext(filename_only)
                counter = 1
                while os.path.exists(dst_path):
                    dst_path = os.path.join(dst_dir, f"{name}_{counter}{ext}")
                    counter += 1

            shutil.move(src_path, dst_path)
            new_path = os.path.join(target_path, os.path.basename(dst_path)) if target_path else os.path.basename(dst_path)
            return {
                'success': True,
                'new_path': new_path.replace('\\', '/'),
                'scope': 'shared'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def move_from_shared(self, session_id: str, filename: str, target_path: str = '') -> Dict[str, Any]:
        """将共享工作区的文件移动到私有工作区。"""
        src_path = _resolve_within(self.shared_workspace_dir, filename)
        if not src_path:
            return {'success': False, 'error': '路径不合法'}

        if not os.path.exists(src_path):
            return {'success': False, 'error': f'文件不存在: {filename}'}

        ws_path = self.get_or_create(session_id, 'web')

        if target_path:
            dst_dir = _resolve_within(ws_path, target_path)
            if not dst_dir:
                return {'success': False, 'error': '目标路径不合法'}
        else:
            dst_dir = ws_path

        if not os.path.exists(dst_dir):
            return {'success': False, 'error': '目标目录不存在'}

        try:
            filename_only = os.path.basename(filename)
            dst_path = os.path.join(dst_dir, filename_only)

            if os.path.exists(dst_path):
                name, ext = os.path.splitext(filename_only)
                counter = 1
                while os.path.exists(dst_path):
                    dst_path = os.path.join(dst_dir, f"{name}_{counter}{ext}")
                    counter += 1

            shutil.move(src_path, dst_path)
            new_path = os.path.join(target_path, os.path.basename(dst_path)) if target_path else os.path.basename(dst_path)
            return {
                'success': True,
                'new_path': new_path.replace('\\', '/'),
                'scope': 'private'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
