"""Main message dispatch logic."""

from __future__ import annotations

import asyncio
import html
import json
import os
import random
import re
from typing import Any, Dict, List, Optional

from nbot.commands.dispatch.at_bot import is_at_bot
from nbot.commands.dispatch.workspace import _save_incoming_files_to_workspace
from nbot.commands.state import command_handlers
from nbot.utils.logger import get_logger

_log = get_logger(__name__)


async def handle_group_message(msg: Any) -> None:
    """Entry point for group messages."""
    await dispatch_message(msg, is_group=True)


async def handle_private_message(msg: Any) -> None:
    """Entry point for private messages."""
    await dispatch_message(msg, is_group=False)


async def dispatch_message(msg: Any, is_group: bool) -> None:
    """Route an incoming message to the correct command handler or AI chat.

    Args:
        msg: The ncatbot message object.
        is_group: Whether the message came from a group.
    """
    raw_msg = msg.raw_message
    if not raw_msg:
        return

    # --- Extract image URL ---
    image_url: Optional[str] = None
    try:
        if hasattr(msg, "message") and msg.message:
            first_elem = msg.message[0]
            if hasattr(first_elem, "type") and first_elem.type == "image":
                image_url = first_elem.data.get("url")
                if image_url:
                    _log.info(
                        f"从 message[0].data.url 获取图片 URL: "
                        f"{image_url[:50]}..."
                    )
                else:
                    _log.warning(
                        f"message[0].type=image 但 data.url 为空"
                    )
            else:
                elem_type = (
                    first_elem.type
                    if hasattr(first_elem, "type")
                    else type(first_elem).__name__
                )
                _log.debug(
                    f"message[0].type={elem_type}, 非图片消息, 不提取图片URL"
                )
        else:
            _log.debug(
                f"msg 无 message 属性或为空"
            )
    except Exception as e:
        _log.warning(f"无法从 message 获取图片 URL: {e}")

    if not image_url:
        image_match = re.search(
            r"\[CQ:image\b.*?url=(https?://[^,\]]+)", raw_msg
        )
        if image_match:
            image_url = image_match.group(1)
            _log.info(f"从 CQ 码解析图片 URL: {image_url[:50]}...")
        else:
            if (
                "CQ:image" in raw_msg
                or "[图片]" in raw_msg
                or "image" in raw_msg.lower()
            ):
                _log.warning(
                    f"消息疑似包含图片但未能提取URL, raw_msg={raw_msg[:200]}"
                )

    if image_url:
        unescaped = html.unescape(image_url)
        if unescaped != image_url:
            _log.info("URL HTML 实体已修复: &amp; → &")
            image_url = unescaped

    # --- Extract video URL ---
    video_url: Optional[str] = None
    video_file_id: Optional[str] = None
    try:
        if hasattr(msg, "message") and msg.message:
            for i, elem in enumerate(msg.message):
                elem_type = elem.type if hasattr(elem, "type") else None
                _log.info(
                    f"  msg.message[{i}].type={elem_type}, "
                    f"has_data={hasattr(elem, 'data')}"
                )
                if elem_type == "video":
                    if hasattr(elem, "data"):
                        data_dict = (
                            dict(elem.data)
                            if hasattr(elem.data, "items")
                            else {}
                        )
                        _log.info(
                            f"  视频元素 data: "
                            f"{json.dumps(data_dict, ensure_ascii=False, default=str)[:500]}"
                        )
                        video_file_id = (
                            data_dict.get("file_id")
                            or data_dict.get("file_unique")
                            or data_dict.get("id")
                        )
                    video_url = (
                        elem.data.get("url")
                        or elem.data.get("file")
                        or elem.data.get("path")
                    )
                    if video_url:
                        _log.info(
                            f"从 message[{i}] 获取视频路径: {video_url[:100]}"
                        )
                    if not video_url and video_file_id:
                        _log.info(
                            f"message[{i}] 视频无本地路径, 但有 file_id={video_file_id}, "
                            f"将通过 API 下载"
                        )
                    break
    except Exception as e:
        _log.warning(f"无法从 message 获取视频数据: {e}")
        import traceback as _tb
        _log.info(_tb.format_exc())

    if not video_url and not video_file_id:
        video_match = re.search(r"\[CQ:video\b.*?url=([^,\]]+)", raw_msg)
        if video_match:
            video_url = video_match.group(1)
            _log.info(f"从 CQ 码 url= 提取到视频路径: {video_url[:100]}")
        else:
            video_match = re.search(r"\[CQ:video\b.*?file=([^,\]]+)", raw_msg)
            if video_match:
                video_url = video_match.group(1)
                _log.info(
                    f"从 CQ 码 file= 提取到视频文件名: {video_url[:100]}（仅有文件名）"
                )

    if video_url and not video_file_id:
        video_url = html.unescape(video_url)
        _log.info(f"[视频] HTML 实体修复后: {video_url[:100]}")
        if video_url.startswith("http://") or video_url.startswith("https://"):
            _log.info("[视频] 远程 URL，直接使用")
        else:
            _log.info("[视频] 检测到本地文件路径，尝试转为 base64...")
            import base64 as _b64
            video_read = None
            try:
                if os.path.exists(video_url):
                    file_size = os.path.getsize(video_url)
                    _log.info(f"[视频] 文件存在, 大小: {file_size // 1024}KB")
                    with open(video_url, "rb") as _f:
                        video_read = _f.read()
                else:
                    _log.warning(
                        f"[视频] 本地文件不存在（可能因 macOS 沙盒限制）: {video_url}"
                    )
            except Exception as e:
                _log.warning(f"[视频] 直接读取失败: {e}")

            if not video_read:
                _log.info("[视频] 尝试通过 NapCat 协议下载文件...")
                try:
                    import base64 as _b64_inner
                    # Lazy import bot
                    from nbot.commands import bot
                    result = await bot.api._http.post("get_file", {"file": video_url})
                    _log.info(
                        f"[视频] NapCat API 响应: "
                        f"{json.dumps(result, ensure_ascii=False)[:300]}"
                    )
                    if result and result.get("status") == "ok":
                        file_data = result.get("data", {})
                        if file_data.get("base64"):
                            video_read = _b64_inner.b64decode(file_data["base64"])
                        elif file_data.get("url"):
                            video_url = file_data["url"]
                            video_read = b"__HTTP_URL__"
                except Exception as e:
                    _log.warning(f"[视频] NapCat API 下载失败: {e}")

            if video_read and video_read != b"__HTTP_URL__":
                _ext = (
                    os.path.splitext(video_url)[1].lower()
                    if "." in video_url
                    else ".mp4"
                )
                _mime_map = {
                    ".mp4": "video/mp4",
                    ".avi": "video/x-msvideo",
                    ".mov": "video/quicktime",
                    ".webm": "video/webm",
                }
                _mime = _mime_map.get(_ext, "video/mp4")
                _video_b64 = _b64.b64encode(video_read).decode("utf-8")
                video_url = f"data:{_mime};base64,{_video_b64}"
                _log.info(
                    f"[视频] 已转 base64 data URL, 大小: {len(_video_b64) // 1024}KB"
                )
            elif video_read == b"__HTTP_URL__":
                _log.info("[视频] 使用 API 返回的 HTTP URL")
            else:
                _log.warning("[视频] 无法获取视频内容，video_url 置空")
                video_url = None

    if video_file_id and not video_url:
        _log.info(f"[视频] 尝试通过 file_id={video_file_id} 下载...")
        try:
            # Lazy import bot
            from nbot.commands import bot
            result = await bot.api._http.post("get_file", {"file_id": video_file_id})
            _log.info(
                f"[视频] NapCat get_file 响应: "
                f"{json.dumps(result, ensure_ascii=False)[:300]}"
            )
            if result and result.get("status") == "ok":
                file_data = result.get("data", {})
                if file_data.get("url"):
                    video_url = file_data["url"]
                    _log.info(f"[视频] 通过 file_id 获取到 URL: {video_url[:100]}")
                elif file_data.get("base64"):
                    import base64 as _b64
                    video_read = _b64.b64decode(file_data["base64"])
                    _video_b64 = _b64.b64encode(video_read).decode("utf-8")
                    video_url = f"data:video/mp4;base64,{_video_b64}"
                    _log.info(
                        f"[视频] 通过 file_id 转 base64, 大小: {len(_video_b64) // 1024}KB"
                    )
        except Exception as e:
            _log.warning(f"[视频] file_id 下载失败: {e}")
    else:
        _log.info(
            f"[视频] 未能提取到视频, video_url={video_url is not None}, "
            f"video_file_id={video_file_id is not None}, "
            f"raw_msg前200={raw_msg[:200]}"
        )

    # --- Save files to workspace ---
    from nbot.services.chat_service import WORKSPACE_AVAILABLE
    if WORKSPACE_AVAILABLE:
        try:
            _save_incoming_files_to_workspace(msg, is_group)
        except Exception as e:
            _log.warning(f"保存文件到工作区失败: {e}")

    # --- Bilibili link detection ---
    try:
        from nbot.plugins.bilibili_parser import on_bilibili_message
        handled = await on_bilibili_message(msg, is_group)
        if handled:
            return
    except Exception as e:
        _log.warning(f"B站链接检测失败: {e}")

    # --- Douyin link detection ---
    try:
        from nbot.plugins.douyin_parser import on_douyin_message
        handled = await on_douyin_message(msg, is_group)
        if handled:
            return
    except Exception as e:
        _log.warning(f"抖音链接检测失败: {e}")

    # --- Command dispatch ---
    for commands, handler in command_handlers.items():
        for cmd in commands:
            if raw_msg.startswith(cmd):
                try:
                    await handler(msg, is_group)
                except Exception as e:
                    _log.error(f"Error handling command {cmd}: {e}")
                return

    # --- AI chat fallback ---
    loop = asyncio.get_event_loop()
    if is_group:
        group_id = str(msg.group_id) if hasattr(msg, "group_id") else None
        user_id = str(msg.user_id) if hasattr(msg, "user_id") else None
        at_bot = is_at_bot(msg)
        auto_reply_enabled = False
        auto_reply_level = 0.3

        if group_id:
            try:
                # Lazy import to avoid circular
                from nbot.commands import switch
                auto_reply_enabled = switch.get_switch_state(
                    "auto_reply", group_id=group_id
                )
                auto_reply_level = float(
                    switch.group_switches.get(group_id, {}).get(
                        "auto_reply_level", 0.5
                    )
                )
                auto_reply_level = max(0.0, min(1.0, auto_reply_level))
            except Exception as e:
                _log.warning(
                    f"Failed to read auto_reply config for group {group_id}: {e}"
                )

        if not at_bot and not auto_reply_enabled:
            _log.debug(f"Group message ignored (not @bot): {raw_msg[:50]}...")
            return

        if not at_bot and random.random() > auto_reply_level:
            _log.debug(
                f"Group auto_reply skipped by level={auto_reply_level:.2f}: "
                f"{raw_msg[:50]}..."
            )
            return

        from nbot.services.chat_service import chat as do_chat
        try:
            content = raw_msg
            atts: List[Dict[str, Any]] = (
                [{"type": "image", "url": image_url, "source": "qq"}]
                if image_url
                else []
            )
            if video_url:
                atts.append({"type": "video", "url": video_url, "source": "qq"})
            trigger = "at bot" if at_bot else f"auto_reply level={auto_reply_level:.2f}"
            _log.info(
                f"Processing group message ({trigger}) from {user_id} in {group_id}: "
                f"{content[:50]}..., image: {bool(image_url)}, video: {bool(video_url)}"
            )

            if not at_bot and auto_reply_enabled and group_id:
                try:
                    from nbot.ai_commands import (
                        get_group_history_items,
                        history_items_to_text,
                    )
                    history_items = await get_group_history_items(int(group_id), 30)
                    if history_items:
                        history_text = history_items_to_text(history_items)
                        user_prefix = f"用户{user_id}说："
                        content = (
                            f"[群聊最近消息上下文]\n{history_text}\n"
                            f"[当前消息]\n{user_prefix}{content}"
                        )
                        _log.info(
                            f"Added group chat context with {len(history_items)} "
                            f"messages for auto_reply"
                        )
                except Exception as ctx_err:
                    _log.warning(f"Failed to get group history for context: {ctx_err}")

            response = await loop.run_in_executor(
                None,
                do_chat,
                content,
                None,
                group_id,
                user_id,
                False,
                None,
                None,
                atts,
            )
            if response:
                _log.info(f"Sending group reply: {response[:50]}...")
                await msg.reply(text=response)
            else:
                _log.warning("No response from chat service")
        except Exception as e:
            _log.error(f"Error in group chat: {e}")
            import traceback
            _log.error(traceback.format_exc())
    else:
        from nbot.services.chat_service import chat as do_chat
        try:
            content = raw_msg
            user_id = str(msg.user_id) if hasattr(msg, "user_id") else None
            atts: List[Dict[str, Any]] = (
                [{"type": "image", "url": image_url, "source": "qq"}]
                if image_url
                else []
            )
            if video_url:
                atts.append({"type": "video", "url": video_url, "source": "qq"})
            _log.info(
                f"Processing private message from {user_id}: "
                f"{content[:50]}..., image: {bool(image_url)}, video: {bool(video_url)}"
            )
            response = await loop.run_in_executor(
                None, do_chat, content, user_id, None, None, False, None, None, atts
            )
            if response:
                _log.info(f"Sending private reply: {response[:50]}...")
                await msg.reply(text=response)
            else:
                _log.warning("No response from chat service")
        except Exception as e:
            _log.error(f"Error in private chat: {e}")
            import traceback
            _log.error(traceback.format_exc())
