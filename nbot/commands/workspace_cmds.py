"""Workspace commands."""
import os

from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.commands.shared.data_persistence import normalize_file_path
from nbot.services.chat_service import get_qq_session_id, WORKSPACE_AVAILABLE
from nbot.utils.message_sender import send_text, send_file


@register_command("/workspace", "/ws", help_text="/workspace 或 /ws -> 查看当前会话工作区文件列表", category="3")
async def handle_workspace(msg, is_group=True):
    """查看当前会话的工作区文件列表"""
    if not WORKSPACE_AVAILABLE:
        reply = "工作区功能不可用喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    from nbot.core.workspace import workspace_manager

    if is_group:
        session_id = get_qq_session_id(group_id=str(msg.group_id), group_user_id=str(msg.user_id))
    else:
        session_id = get_qq_session_id(user_id=str(msg.user_id))

    result = workspace_manager.list_files(session_id)
    files = result.get('files', [])

    if not files:
        reply = "当前工作区没有文件喵~"
    else:
        reply = f"工作区文件列表 ({len(files)} 个文件)：\n"
        for f in files:
            size_kb = f['size'] / 1024
            if size_kb < 1:
                size_str = f"{f['size']} B"
            elif size_kb < 1024:
                size_str = f"{size_kb:.1f} KB"
            else:
                size_str = f"{size_kb/1024:.2f} MB"
            reply += f"  {f['name']} ({size_str})\n"

    await send_text(msg, reply, is_group=is_group)


@register_command("/ws_send", help_text="/ws_send <文件名> -> 发送工作区中的文件", category="3")
async def handle_ws_send(msg, is_group=True):
    """发送工作区中的文件给用户"""
    if not WORKSPACE_AVAILABLE:
        reply = "工作区功能不可用喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    from nbot.core.workspace import workspace_manager

    raw = msg.raw_message
    filename = raw[len("/ws_send"):].strip()
    if not filename:
        reply = "请指定文件名喵~ 用法: /ws_send 文件名"
        await send_text(msg, reply, is_group=is_group)
        return

    if is_group:
        session_id = get_qq_session_id(group_id=str(msg.group_id), group_user_id=str(msg.user_id))
    else:
        session_id = get_qq_session_id(user_id=str(msg.user_id))

    file_path = workspace_manager.get_file_path(session_id, filename)
    if not file_path:
        reply = f"文件不存在喵~: {filename}"
        await send_text(msg, reply, is_group=is_group)
        return

    file_path = normalize_file_path(file_path)
    try:
        await send_file(msg, file_path, is_group=is_group, filename=os.path.basename(file_path))
    except Exception as e:
        reply = f"发送文件失败喵~: {e}"
        await send_text(msg, reply, is_group=is_group)
