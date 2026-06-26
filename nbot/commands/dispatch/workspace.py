"""Persist incoming files from QQ messages to the workspace."""

from __future__ import annotations

import os
import re
from typing import Any

from nbot.utils.logger import get_logger

_log = get_logger(__name__)


def _get_project_root() -> str:
    """Return the project root directory (two levels above this file)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _save_incoming_files_to_workspace(msg: Any, is_group: bool) -> None:
    """Detect files in a message and persist them to the workspace."""
    from nbot.services.chat_service import (
        WORKSPACE_AVAILABLE,
        get_qq_session_id,
    )

    if not WORKSPACE_AVAILABLE:
        _log.debug("[文件保存] 工作区不可用")
        return

    from nbot.core.workspace import workspace_manager

    if is_group:
        session_id = get_qq_session_id(
            group_id=str(msg.group_id), group_user_id=str(msg.user_id)
        )
        session_type = "qq_group"
    else:
        session_id = get_qq_session_id(user_id=str(msg.user_id))
        session_type = "qq_private"

    _log.info(
        f"[文件保存] 开始检查消息，session_id={session_id}, type={session_type}"
    )

    # Method 1: inspect msg.message elements
    if hasattr(msg, "message") and msg.message:
        _log.info(f"[文件保存] 消息元素数量: {len(msg.message)}")
        for elem in msg.message:
            if not hasattr(elem, "type"):
                _log.debug(f"[文件保存] 元素没有type属性: {elem}")
                continue
            _log.info(f"[文件保存] 检查元素类型: {elem.type}")
            if elem.type == "file":
                file_url = (
                    elem.data.get("url", "")
                    if hasattr(elem, "data")
                    else ""
                )
                file_name = (
                    elem.data.get("name", "unknown_file")
                    if hasattr(elem, "data")
                    else "unknown_file"
                )
                _log.info(
                    f"[文件保存] 发现文件: {file_name}, "
                    f"URL: {file_url[:50] if file_url else '空'}..."
                )
                if file_url:
                    try:
                        from nbot.utils.http_client import get_sync
                        resp = get_sync(file_url, timeout=30)
                        _log.info(f"[文件保存] 下载响应: {resp.status_code}")
                        if resp.status_code == 200:
                            result = workspace_manager.save_uploaded_file(
                                session_id, resp.content, file_name, session_type
                            )
                            _log.info(f"[文件保存] 保存成功: {result}")
                        else:
                            _log.warning(
                                f"[文件保存] 下载失败，状态码: {resp.status_code}"
                            )
                    except Exception as e:
                        _log.warning(
                            f"[文件保存] 保存失败: {file_name}, {e}", exc_info=True
                        )
            else:
                _log.debug(f"[文件保存] 非文件类型元素: {elem.type}")

    # Method 2: parse CQ code for files
    if hasattr(msg, "raw_message") and msg.raw_message:
        raw_msg = msg.raw_message
        _log.info(f"[文件保存] 检查 raw_message: {raw_msg[:100]}...")
        file_cq_pattern = (
            r"\[CQ:file[^,]*,file=([^,\]]+)"
            r"(?:[^,]*,file_id=([^,\]+))?"
            r"(?:[^,]*,url=([^,\]+))?[^\]*\]"
        )
        file_matches = re.findall(file_cq_pattern, raw_msg)
        if file_matches:
            _log.info(f"[文件保存] 从 CQ 码发现 {len(file_matches)} 个文件")
            for match in file_matches:
                file_name = match[0] if match[0] else "unknown_file"
                file_id = match[1] if len(match) > 1 and match[1] else None
                file_url = match[2] if len(match) > 2 and match[2] else None
                _log.info(
                    f"[文件保存] CQ码文件: {file_name}, "
                    f"file_id={file_id}, "
                    f"url={file_url[:50] if file_url else '无'}..."
                )
                if not file_url and file_id:
                    try:
                        api_url = "http://127.0.0.1:3000"
                        if is_group:
                            endpoint = f"{api_url}/get_group_file_url"
                            params = {"group_id": msg.group_id, "file_id": file_id}
                        else:
                            endpoint = f"{api_url}/get_private_file_url"
                            params = {"user_id": msg.user_id, "file_id": file_id}
                        _log.info(f"[文件保存] 尝试获取文件URL: {endpoint}")
                        # Lazy import bot to avoid circular import
                        from nbot.commands import bot
                        request_method = getattr(
                            bot.api, "_request", getattr(bot.api, "request", None)
                        )
                        if request_method:
                            file_info = request_method(endpoint, params=params)
                            if (
                                file_info
                                and "data" in file_info
                                and "url" in file_info["data"]
                            ):
                                file_url = file_info["data"]["url"]
                                _log.info(
                                    f"[文件保存] 通过API获取到文件URL: "
                                    f"{file_url[:50]}..."
                                )
                    except Exception as e:
                        _log.warning(f"[文件保存] 获取文件下载链接失败: {e}")
                    if not file_url:
                        try:
                            from nbot.services.ai import base_url
                            if base_url:
                                possible_urls = [
                                    f"{base_url}/download_file?file_id={file_id}",
                                    f"{base_url}/get_file?file_id={file_id}",
                                ]
                                for url in possible_urls:
                                    try:
                                        from nbot.utils.http_client import head_sync
                                        resp = head_sync(url, timeout=5)
                                        if resp.status_code == 200:
                                            file_url = url
                                            _log.info(
                                                f"[文件保存] 找到可用下载链接: "
                                                f"{file_url[:50]}..."
                                            )
                                            break
                                    except Exception:
                                        continue
                        except Exception as e:
                            _log.debug(f"[文件保存] 尝试直接下载失败: {e}")
                if file_url:
                    try:
                        from nbot.utils.http_client import get_sync
                        resp = get_sync(file_url, timeout=30)
                        _log.info(f"[文件保存] 下载响应: {resp.status_code}")
                        if resp.status_code == 200:
                            result = workspace_manager.save_uploaded_file(
                                session_id, resp.content, file_name, session_type
                            )
                            _log.info(f"[文件保存] 保存成功: {result}")
                        else:
                            _log.warning(
                                f"[文件保存] 下载失败，状态码: {resp.status_code}"
                            )
                    except Exception as e:
                        _log.warning(
                            f"[文件保存] 保存失败: {file_name}, {e}", exc_info=True
                        )
                else:
                    _log.warning(f"[文件保存] 无法获取文件下载链接: {file_name}")
        else:
            _log.debug("[文件保存] raw_message 中没有 CQ:file 码")
