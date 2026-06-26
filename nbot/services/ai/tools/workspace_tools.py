"""工作区工具 - 工作区文件操作与变更追踪."""
import os
import difflib
import mimetypes
from typing import Dict, Any, Optional

from nbot.utils.logger import get_logger

_log = get_logger(__name__)

# Web 配置数据目录
WEB_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'web')


def _truncate_text_preview(text: str, limit: int = 1200) -> str:
    text = (text or "").replace("\r\n", "\n")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...<truncated>"


def _read_text_preview(path: str, limit: int = 1200) -> Optional[str]:
    if not path or not os.path.exists(path) or os.path.isdir(path):
        return None
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type and not (
        mime_type.startswith("text/")
        or mime_type
        in {
            "application/json",
            "application/xml",
            "application/yaml",
            "application/javascript",
            "application/x-python",
        }
    ):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return _truncate_text_preview(f.read(), limit=limit)
    except Exception:
        return None


def _build_diff_preview(before_text: str, after_text: str, max_lines: int = 80) -> str:
    before_lines = (before_text or "").replace("\r\n", "\n").splitlines()
    after_lines = (after_text or "").replace("\r\n", "\n").splitlines()
    diff_lines = list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )
    if len(diff_lines) > max_lines:
        diff_lines = diff_lines[:max_lines] + ["...<diff truncated>"]
    return "\n".join(diff_lines)


def _build_workspace_change(
    *,
    action: str,
    filename: str,
    scope: str,
    before_text: Optional[str] = None,
    after_text: Optional[str] = None,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    max_preview_chars = 4000
    preview_too_large = (
        len(before_text or "") > max_preview_chars
        or len(after_text or "") > max_preview_chars
    )
    before_preview = (
        _truncate_text_preview(before_text or "") if before_text is not None and not preview_too_large else None
    )
    after_preview = (
        _truncate_text_preview(after_text or "") if after_text is not None and not preview_too_large else None
    )
    change = {
        "action": action,
        "path": filename,
        "scope": scope,
        "preview_too_large": preview_too_large,
    }
    if path:
        change["absolute_path"] = path
    if before_preview is not None:
        change["before_preview"] = before_preview
    if after_preview is not None:
        change["after_preview"] = after_preview
    if (before_text is not None or after_text is not None) and not preview_too_large:
        change["diff_preview"] = _build_diff_preview(before_text or "", after_text or "")
    return change


def _append_workspace_change(result: Dict[str, Any], change: Dict[str, Any]) -> Dict[str, Any]:
    file_changes = list(result.get("file_changes") or [])
    file_changes.append(change)
    result["file_changes"] = file_changes
    result["change_summary"] = {
        "created": sum(1 for item in file_changes if item.get("action") == "created"),
        "modified": sum(1 for item in file_changes if item.get("action") == "modified"),
        "deleted": sum(1 for item in file_changes if item.get("action") == "deleted"),
    }
    return result


def _execute_workspace_tool(tool_name: str, arguments: Dict[str, Any],
                            context: Dict = None) -> Dict[str, Any]:
    """执行工作区相关工具."""
    try:
        from nbot.core.workspace import workspace_manager
    except ImportError:
        return {"success": False, "error": "工作区模块不可用"}

    if not context or not context.get('session_id'):
        return {"success": False, "error": "缺少会话信息，无法操作工作区"}

    session_id = context['session_id']
    session_type = context.get('session_type', 'unknown')

    try:
        # 兼容 file_path 和 filename 两种参数名
        filename = arguments.get('filename') or arguments.get('file_path')

        # 获取 scope 参数，默认 'private'
        scope = arguments.get('scope', 'private')
        is_shared = (scope == 'shared')
        if is_shared:
            target_path = os.path.normpath(
                os.path.join(workspace_manager.get_shared_workspace(), filename or "")
            )
        else:
            workspace_root = workspace_manager.get_or_create(session_id, session_type)
            target_path = os.path.normpath(os.path.join(workspace_root, filename or ""))
        target_exists_before = os.path.exists(target_path) if filename else False
        target_preview_before = _read_text_preview(target_path) if target_exists_before else None

        if tool_name == "workspace_create_file":
            if not filename:
                return {"success": False, "error": "缺少文件名参数 (filename 或 file_path)"}
            if 'content' not in arguments:
                return {"success": False, "error": "缺少 content 参数"}

            if is_shared:
                result = workspace_manager.create_shared_file(filename, arguments['content'])
            else:
                result = workspace_manager.create_file(
                    session_id, filename, arguments['content'], session_type)
            result['scope'] = scope
            if result.get('success'):
                _append_workspace_change(
                    result,
                    _build_workspace_change(
                        action='modified' if target_exists_before else 'created',
                        filename=result.get('filename', filename),
                        scope=scope,
                        before_text=target_preview_before,
                        after_text=arguments.get('content', ''),
                        path=result.get('path', target_path),
                    ),
                )
            return result

        elif tool_name == "workspace_read_file":
            if not filename:
                return {"success": False, "error": "缺少文件名参数 (filename 或 file_path)"}

            if is_shared:
                result = workspace_manager.read_shared_file(
                    filename,
                    start_line=arguments.get('start_line'),
                    end_line=arguments.get('end_line'),
                    char_count=arguments.get('char_count'),
                    start_char=arguments.get('start_char')
                )
            else:
                result = workspace_manager.read_file(
                    session_id,
                    filename,
                    start_line=arguments.get('start_line'),
                    end_line=arguments.get('end_line'),
                    char_count=arguments.get('char_count'),
                    start_char=arguments.get('start_char')
                )
            result['scope'] = scope
            return result

        elif tool_name == "workspace_edit_file":
            if not filename:
                return {"success": False, "error": "缺少文件名参数 (filename 或 file_path)"}

            if is_shared:
                result = workspace_manager.edit_shared_file(
                    filename,
                    arguments['old_content'], arguments['new_content'])
            else:
                result = workspace_manager.edit_file(
                    session_id, filename,
                    arguments['old_content'], arguments['new_content'])
            result['scope'] = scope
            if result.get('success'):
                _append_workspace_change(
                    result,
                    _build_workspace_change(
                        action='modified',
                        filename=result.get('filename', filename),
                        scope=scope,
                        before_text=arguments.get('old_content', ''),
                        after_text=arguments.get('new_content', ''),
                        path=result.get('path', target_path),
                    ),
                )
            return result

        elif tool_name == "workspace_delete_file":
            if not filename:
                return {"success": False, "error": "缺少文件名参数 (filename 或 file_path)"}

            if is_shared:
                result = workspace_manager.delete_shared_file(filename)
            else:
                result = workspace_manager.delete_file(session_id, filename)
            result['scope'] = scope
            if result.get('success'):
                _append_workspace_change(
                    result,
                    _build_workspace_change(
                        action='deleted',
                        filename=result.get('filename', filename),
                        scope=scope,
                        before_text=target_preview_before,
                        after_text=None,
                        path=target_path,
                    ),
                )
            return result

        elif tool_name == "workspace_list_files":
            list_scope = arguments.get('scope', 'all')
            path = arguments.get('path', '')
            recursive = arguments.get('recursive', False)

            if list_scope == 'private':
                if recursive:
                    private_result = workspace_manager.list_files_recursive(session_id, path)
                else:
                    private_result = workspace_manager.list_files(session_id, path)
                files = []
                if private_result.get('success') and private_result.get('files'):
                    for f in private_result['files']:
                        f['scope'] = 'private'
                        files.append(f)
                return {
                    'success': True,
                    'scope': 'private',
                    'path': path,
                    'recursive': recursive,
                    'files': files,
                    'count': len(files),
                    'message': f'私有工作区 {f"/{path}" if path else ""} {"(递归)" if recursive else ""} 包含 {len(files)} 个文件/文件夹'
                }
            elif list_scope == 'shared':
                if recursive:
                    shared_result = workspace_manager.list_shared_files_recursive(path)
                else:
                    shared_result = workspace_manager.list_shared_files(path)
                files = []
                if shared_result.get('success') and shared_result.get('files'):
                    for f in shared_result['files']:
                        f['scope'] = 'shared'
                        files.append(f)
                return {
                    'success': True,
                    'scope': 'shared',
                    'path': path,
                    'recursive': recursive,
                    'files': files,
                    'count': len(files),
                    'message': f'共享工作区 {f"/{path}" if path else ""} {"(递归)" if recursive else ""} 包含 {len(files)} 个文件/文件夹'
                }
            else:
                # 返回所有
                if recursive:
                    private_result = workspace_manager.list_files_recursive(session_id, path)
                    shared_result = workspace_manager.list_shared_files_recursive(path)
                else:
                    private_result = workspace_manager.list_files(session_id, path)
                    shared_result = workspace_manager.list_shared_files(path)

                all_files = []
                private_count = 0
                shared_count = 0

                if private_result.get('success') and private_result.get('files'):
                    for f in private_result['files']:
                        f['scope'] = 'private'
                        all_files.append(f)
                        private_count += 1

                if shared_result.get('success') and shared_result.get('files'):
                    for f in shared_result['files']:
                        f['scope'] = 'shared'
                        all_files.append(f)
                        shared_count += 1

                path_info = f"/{path}" if path else ""
                return {
                    'success': True,
                    'scope': 'all',
                    'path': path,
                    'recursive': recursive,
                    'private_workspace': f'当前会话私有工作区 {path_info} {"(递归)" if recursive else ""} ({private_count} 个文件)',
                    'shared_workspace': f'所有会话共享的工作区 {path_info} {"(递归)" if recursive else ""} ({shared_count} 个文件)',
                    'files': all_files,
                    'count': len(all_files),
                    'message': f'工作区 {path_info} 包含 {private_count} 个私有文件和 {shared_count} 个共享文件。使用 scope 和 path 参数指定要操作的工作区和目录。'
                }

        elif tool_name == "workspace_send_file":
            if not filename:
                return {"success": False, "error": "缺少文件名参数 (filename 或 file_path)"}

            if is_shared:
                shared_path = workspace_manager.get_shared_workspace()
                file_path = os.path.join(shared_path, filename)
            else:
                file_path = workspace_manager.get_file_path(session_id, filename)

            if file_path and os.path.exists(file_path):
                return {
                    "success": True,
                    "action": "send_file",
                    "filename": filename,
                    "scope": scope,
                    "path": file_path,
                    "size": os.path.getsize(file_path),
                    "message": f"文件 '{filename}' ({'共享工作区' if is_shared else '私有工作区'}) 已发送给用户，无需再次提及文件路径或内容。"
                }
            return {"success": False, "error": f"文件不存在: {filename}"}

        elif tool_name == "workspace_parse_file":
            if not filename:
                return {"success": False, "error": "缺少文件名参数 (filename)"}

            if is_shared:
                shared_path = workspace_manager.get_shared_workspace()
                file_path = os.path.join(shared_path, filename)
                if not os.path.exists(file_path):
                    return {"success": False, "error": f"共享文件不存在: {filename}"}
            else:
                file_path = workspace_manager.get_file_path(session_id, filename)
                if not file_path:
                    return {"success": False, "error": f"私有文件不存在: {filename}"}

            try:
                from nbot.core.file_parser import file_parser
                max_chars = arguments.get('max_chars', 50000)
                result = file_parser.parse_file(file_path, filename, max_chars)
                result['scope'] = scope
                return result
            except Exception as e:
                _log.error(f"解析文件失败: {filename}, {e}")
                return {"success": False, "error": f"解析文件失败: {str(e)}"}

        elif tool_name == "workspace_file_info":
            if not filename:
                return {"success": False, "error": "缺少文件名参数 (filename)"}

            if is_shared:
                shared_path = workspace_manager.get_shared_workspace()
                file_path = os.path.join(shared_path, filename)
                if not os.path.exists(file_path):
                    return {"success": False, "error": f"共享文件不存在: {filename}"}
            else:
                file_path = workspace_manager.get_file_path(session_id, filename)
                if not file_path:
                    return {"success": False, "error": f"私有文件不存在: {filename}"}

            try:
                from nbot.core.file_parser import file_parser
                result = file_parser.get_file_metadata(file_path, filename)
                result['scope'] = scope
                return result
            except Exception as e:
                _log.error(f"获取文件元数据失败: {filename}, {e}")
                return {"success": False, "error": f"获取文件元数据失败: {str(e)}"}

        elif tool_name == "workspace_skill_copy":
            skill_id = arguments.get('skill_id')
            if not skill_id:
                return {"success": False, "error": "缺少 skill_id 参数"}

            filename = arguments.get('filename')
            skill_scope = arguments.get('scope', 'private')
            is_skill_shared = skill_scope == 'shared'

            # 从配置文件读取 skills 找到 skill 的 name
            import json
            skills_file = os.path.join(WEB_DATA_DIR, 'skills.json')
            skill_config = None
            skill_name = skill_id

            if os.path.exists(skills_file):
                try:
                    with open(skills_file, 'r', encoding='utf-8') as f:
                        skills_list = json.load(f)
                        for s in skills_list:
                            if s.get('id') == skill_id or s.get('name') == skill_id:
                                skill_config = s
                                skill_name = s.get('name', skill_id)
                                break
                except Exception as e:
                    _log.warning(f"读取 skills 配置文件失败: {e}")

            if not skill_config:
                return {"success": False, "error": f"Skill '{skill_id}' 不存在"}

            # 找到 skill 的实际目录
            from nbot.core.skills_manager import SKILLS_ROOT, SkillStorage
            skill_source_dir = os.path.join(SKILLS_ROOT, skill_name)

            # 确定目标路径
            if is_skill_shared:
                shared_path = workspace_manager.get_shared_workspace()
                target_dir = shared_path
            else:
                target_dir = workspace_manager.get_workspace(session_id)
                if not target_dir:
                    target_dir = workspace_manager.create_workspace(session_id)

            if not target_dir:
                return {"success": False, "error": "无法创建工作区"}

            # 如果 skill 源目录存在，复制整个目录
            if os.path.exists(skill_source_dir) and os.path.isdir(skill_source_dir):
                import shutil
                target_skill_dir = os.path.join(target_dir, 'skills', skill_name)
                os.makedirs(os.path.dirname(target_skill_dir), exist_ok=True)
                try:
                    shutil.copytree(skill_source_dir, target_skill_dir, dirs_exist_ok=True)
                    return {
                        "success": True,
                        "message": f"已复制 Skill '{skill_name}' 到工作区: {target_skill_dir}",
                        "path": target_skill_dir,
                        "scope": skill_scope
                    }
                except Exception as e:
                    return {"success": False, "error": f"复制 Skill 目录失败: {str(e)}"}

            # 如果指定了文件名，在配置中查找
            if filename:
                # 在 scripts 中查找
                scripts = skill_config.get('scripts', [])
                if filename in scripts:
                    target_path = os.path.join(target_dir, filename)
                    os.makedirs(os.path.dirname(target_path), exist_ok=True) if os.path.dirname(target_path) else None
                    try:
                        # 尝试从 SkillStorage 读取脚本
                        storage = SkillStorage(skill_name)
                        script_content = storage.get_script(filename)
                        if script_content:
                            with open(target_path, 'w', encoding='utf-8') as f:
                                f.write(script_content)
                            return {
                                "success": True,
                                "message": f"已复制脚本 '{filename}' 到工作区: {target_path}",
                                "path": target_path
                            }
                    except Exception as e:
                        return {"success": False, "error": f"复制脚本失败: {str(e)}"}

            # 如果以上都不行，至少复制 JSON 配置
            skills_dir = os.path.join(target_dir, 'skills')
            os.makedirs(skills_dir, exist_ok=True)
            target_file = os.path.join(skills_dir, f"{skill_name}.json")
            try:
                content = json.dumps(skill_config, ensure_ascii=False, indent=2)
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                return {
                    "success": True,
                    "message": f"已复制 Skill 配置 '{skill_name}' 到工作区: {target_file}",
                    "path": target_file,
                    "scope": skill_scope
                }
            except Exception as e:
                return {"success": False, "error": f"复制 Skill 配置失败: {str(e)}"}

        else:
            return {"success": False, "error": f"未知的工作区工具: {tool_name}"}

    except Exception as e:
        _log.error(f"Workspace tool error: {tool_name} - {e}")
        return {"success": False, "error": str(e)}
