"""
CLI 工作区工具执行 - CCStyleCLI 的工作区工具实现
包含所有 workspace_* 工具的执行逻辑。
"""

import os
import sys
import mimetypes
from typing import Dict


def execute_workspace_tool(tool_name: str, arguments: Dict) -> Dict:
    """在CLI中执行工作区工具，使用当前目录作为工作区根目录"""
    workspace_root = os.getcwd()
    filename = arguments.get("filename") or arguments.get("file_path", "")

    try:
        if tool_name == "workspace_create_file":
            if not filename:
                return {"success": False, "error": "缺少文件名参数"}
            if "content" not in arguments:
                return {"success": False, "error": "缺少 content 参数"}

            file_path = os.path.join(workspace_root, filename)
            parent_dir = os.path.dirname(file_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(arguments["content"])

            return {
                "success": True,
                "filename": os.path.basename(filename),
                "path": file_path,
                "size": len(arguments["content"].encode("utf-8")),
                "message": f"文件已创建: {filename}",
            }

        elif tool_name == "workspace_read_file":
            if not filename:
                return {"success": False, "error": "缺少文件名参数"}

            file_path = os.path.join(workspace_root, filename)
            if not os.path.exists(file_path):
                return {"success": False, "error": f"文件不存在: {filename}"}

            if os.path.isdir(file_path):
                return {"success": False, "error": f"这是一个目录，不是文件: {filename}"}

            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                start_line = arguments.get("start_line")
                end_line = arguments.get("end_line")
                if start_line is not None or end_line is not None:
                    lines = content.split("\n")
                    start = (start_line - 1) if start_line else 0
                    end = end_line if end_line else len(lines)
                    content = "\n".join(lines[start:end])

                char_count = arguments.get("char_count")
                start_char = arguments.get("start_char")
                if char_count is not None or start_char is not None:
                    start = start_char if start_char else 0
                    end = start + char_count if char_count else len(content)
                    content = content[start:end]

                return {
                    "success": True,
                    "filename": filename,
                    "content": content,
                    "size": os.path.getsize(file_path),
                }
            except Exception as e:
                return {"success": False, "error": f"读取文件失败: {str(e)}"}

        elif tool_name == "workspace_edit_file":
            if not filename:
                return {"success": False, "error": "缺少文件名参数"}

            file_path = os.path.join(workspace_root, filename)
            if not os.path.exists(file_path):
                return {"success": False, "error": f"文件不存在: {filename}"}

            old_content = arguments.get("old_content", "")
            new_content = arguments.get("new_content", "")

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                if old_content not in content:
                    return {"success": False, "error": "未找到要替换的内容"}

                new_file_content = content.replace(old_content, new_content, 1)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_file_content)

                return {
                    "success": True,
                    "filename": filename,
                    "message": f"文件已修改: {filename}",
                }
            except Exception as e:
                return {"success": False, "error": f"修改文件失败: {str(e)}"}

        elif tool_name == "workspace_delete_file":
            if not filename:
                return {"success": False, "error": "缺少文件名参数"}

            file_path = os.path.join(workspace_root, filename)
            if not os.path.exists(file_path):
                return {"success": False, "error": f"文件不存在: {filename}"}

            try:
                if os.path.isdir(file_path):
                    import shutil

                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)

                return {
                    "success": True,
                    "filename": filename,
                    "message": f"已删除: {filename}",
                }
            except Exception as e:
                return {"success": False, "error": f"删除失败: {str(e)}"}

        elif tool_name == "workspace_list_files":
            path = arguments.get("path", "")
            recursive = arguments.get("recursive", False)

            target_path = os.path.join(workspace_root, path) if path else workspace_root

            if not os.path.exists(target_path) or not os.path.isdir(target_path):
                return {"success": False, "error": f"目录不存在: {path}"}

            files = []

            if recursive:
                for root, dirs, filenames in os.walk(target_path):
                    for name in filenames:
                        full_path = os.path.join(root, name)
                        rel_path = os.path.relpath(full_path, workspace_root)
                        mime_type, _ = mimetypes.guess_type(full_path)
                        files.append(
                            {
                                "name": name,
                                "type": "file",
                                "size": os.path.getsize(full_path),
                                "mime_type": mime_type or "application/octet-stream",
                                "path": rel_path.replace("\\", "/"),
                            }
                        )
                    for name in dirs:
                        full_path = os.path.join(root, name)
                        rel_path = os.path.relpath(full_path, workspace_root)
                        files.append(
                            {
                                "name": name,
                                "type": "directory",
                                "size": 0,
                                "path": rel_path.replace("\\", "/"),
                            }
                        )
            else:
                for name in os.listdir(target_path):
                    full_path = os.path.join(target_path, name)
                    rel_path = os.path.relpath(full_path, workspace_root)
                    if os.path.isdir(full_path):
                        files.append(
                            {
                                "name": name,
                                "type": "directory",
                                "size": 0,
                                "path": rel_path.replace("\\", "/"),
                            }
                        )
                    else:
                        mime_type, _ = mimetypes.guess_type(full_path)
                        files.append(
                            {
                                "name": name,
                                "type": "file",
                                "size": os.path.getsize(full_path),
                                "mime_type": mime_type or "application/octet-stream",
                                "path": rel_path.replace("\\", "/"),
                            }
                        )

            return {
                "success": True,
                "path": path or ".",
                "recursive": recursive,
                "files": files,
                "count": len(files),
                "message": f"工作区 '{workspace_root}' 包含 {len(files)} 个文件/文件夹",
            }

        elif tool_name == "workspace_send_file":
            if not filename:
                return {"success": False, "error": "缺少文件名参数"}

            file_path = os.path.join(workspace_root, filename)
            if not os.path.exists(file_path):
                return {"success": False, "error": f"文件不存在: {filename}"}

            file_size = os.path.getsize(file_path)
            mime_type, _ = mimetypes.guess_type(file_path)

            abs_path = os.path.abspath(file_path)
            if sys.platform == "win32":
                file_url = "file:///" + abs_path.replace("\\", "/")
            else:
                file_url = "file://" + abs_path

            if file_size < 1024:
                size_str = f"{file_size} B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"

            return {
                "success": True,
                "filename": filename,
                "path": file_path,
                "file_url": file_url,
                "size": file_size,
                "size_str": size_str,
                "mime_type": mime_type or "application/octet-stream",
                "message": f"📄 [{filename}]({file_url}) ({size_str})",
            }

        elif tool_name == "workspace_parse_file":
            if not filename:
                return {"success": False, "error": "缺少文件名参数"}

            file_path = os.path.join(workspace_root, filename)
            if not os.path.exists(file_path):
                return {"success": False, "error": f"文件不存在: {filename}"}

            try:
                from nbot.core.file_parser import file_parser

                max_chars = arguments.get("max_chars", 50000)
                result = file_parser.parse_file(file_path, filename, max_chars)
                return result
            except Exception as e:
                return {"success": False, "error": f"解析文件失败: {str(e)}"}

        elif tool_name == "workspace_file_info":
            if not filename:
                return {"success": False, "error": "缺少文件名参数"}

            file_path = os.path.join(workspace_root, filename)
            if not os.path.exists(file_path):
                return {"success": False, "error": f"文件不存在: {filename}"}

            try:
                from nbot.core.file_parser import file_parser

                result = file_parser.get_file_metadata(file_path, filename)
                return result
            except Exception as e:
                return {"success": False, "error": f"获取文件信息失败: {str(e)}"}

        else:
            return {"success": False, "error": f"未知的工作区工具: {tool_name}"}

    except Exception as e:
        return {"success": False, "error": f"执行工作区工具失败: {str(e)}"}
