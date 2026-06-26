"""
AI 命令注册中心

register_ai_commands() 主函数，负责：
- 设置全局依赖（bot 引用、路径、辅助函数）
- 启动后台定时任务（每日自动总结、主动聊天）
- 委托 handlers_chat / handlers_admin 完成命令注册
"""

import asyncio
import json
import os
import time
from datetime import datetime

from nbot.services.chat_service import (
    delete_session_workspace,
    generate_today_summary,
    get_qq_session_id,
    group_messages,
    summarize_group_text,
    user_messages,
)

from nbot.commands.ai.utils import (
    _extract_history_text_item as _top_extract_history_text_item,
    _history_items_to_text,
    get_group_history_items,
    history_items_to_text,
)

# 模块级别的 bot 实例引用，用于群聊历史记录功能
_bot_instance = None


def register_ai_commands(
    *,
    register_command,
    bot,
    log,
    project_root,
    admin,
    read_secure_json,
    write_secure_json,
    workspace_available,
    switch,
    running,
    write_running,
    normalize_timestamp,
    heartbeat_core,
    normalize_file_path,
    load_address,
):
    """注册 AI/session 命令（QQ 和 Web 历史共用）。"""
    global _bot_instance
    _bot_instance = bot

    def web_data_dir():
        return os.path.join(project_root(), "data", "web")

    def resume_bindings_path():
        return os.path.join(web_data_dir(), "qq_web_session_bindings.json")

    def load_resume_bindings():
        path = resume_bindings_path()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            log.warning(f"Load resume bindings failed: {e}")
        return {}

    def save_resume_bindings(bindings):
        os.makedirs(web_data_dir(), exist_ok=True)
        with open(resume_bindings_path(), "w", encoding="utf-8") as f:
            json.dump(bindings, f, ensure_ascii=False, indent=2)

    def save_qq_histories():
        os.makedirs("saved_message", exist_ok=True)
        with open("saved_message/user_messages.json", "w", encoding="utf-8") as f:
            json.dump(user_messages, f, ensure_ascii=False, indent=4)
        with open("saved_message/group_messages.json", "w", encoding="utf-8") as f:
            json.dump(group_messages, f, ensure_ascii=False, indent=4)

    async def reply_current_channel(msg, is_group, text):
        if is_group:
            await msg.reply(text=text)
        else:
            await bot.api.post_private_msg(msg.user_id, text=text)

    # extract_history_text_item — 与顶层版本功能相同但增加消息段处理
    def extract_history_text_item(item):
        def parts_from_segments(segments):
            parts = []
            for seg in segments or []:
                seg_type = getattr(seg, "type", None)
                data = getattr(seg, "data", None)
                if isinstance(seg, dict):
                    seg_type = seg.get("type")
                    data = seg.get("data")
                data = data or {}
                if seg_type == "text":
                    parts.append(str(data.get("text") or ""))
                elif seg_type == "image":
                    parts.append("[图片]")
                elif seg_type:
                    parts.append(f"[{seg_type}]")
            return "".join(parts).strip()

        if isinstance(item, dict):
            message = item.get("message")
            if isinstance(message, list):
                text = parts_from_segments(message)
                if text:
                    return text
            return str(item.get("raw_message") or item.get("message") or item.get("content") or "").strip()

        message = getattr(item, "message", None)
        if isinstance(message, list):
            text = parts_from_segments(message)
            if text:
                return text
        return str(
            getattr(item, "raw_message", None)
            or getattr(item, "content", None)
            or ""
        ).strip()

    async def get_group_today_summary_text(group_id):
        try:
            items = await get_group_history_items(group_id, 500, bot)
        except Exception as e:
            log.error(f"获取群聊历史失败：{e}")
            return None
        if not items:
            return "今天群里还没有记录到消息喔~"

        today = datetime.now().date()
        filtered = []
        for item in items:
            t = item.get("time") if isinstance(item, dict) else getattr(item, "time", None)
            try:
                dt = datetime.fromtimestamp(int(t)) if t is not None else None
            except Exception:
                dt = None
            if dt is not None and dt.date() == today:
                filtered.append(item)
        if not filtered:
            return "今天群里还没有记录到消息喔~"
        return summarize_group_text(_history_items_to_text(filtered))

    # === 定时任务 ===

    async def auto_summary_task():
        log.info("每日自动总结定时任务已启动")
        while True:
            try:
                now = datetime.now()
                if now.hour == 23 and now.minute == 55:
                    for group_id, switches in switch.group_switches.items():
                        if switches.get("summary_auto", False):
                            try:
                                summary = await get_group_today_summary_text(int(group_id))
                                if summary and "还没有记录到消息" not in summary:
                                    await bot.api.post_group_msg(
                                        group_id=int(group_id),
                                        text=f"【每日自动总结】\n{summary}",
                                    )
                            except Exception as e:
                                log.error(f"自动总结群 {group_id} 失败: {e}")
                    await asyncio.sleep(65)
                else:
                    await asyncio.sleep(30)
            except Exception as e:
                log.error(f"每日自动总结任务发生异常: {e}")
                await asyncio.sleep(60)

    async def auto_active_chat_task():
        log.info("主动聊天定时任务已启动")
        while True:
            try:
                now = datetime.now()
                if 8 <= now.hour < 24:
                    current_time = time.time()
                    for user_id, info in list(running.items()):
                        if not info.get("active", False):
                            continue
                        interval = float(info.get("interval", 1.0))
                        last_time = normalize_timestamp(info.get("last_time", 0))
                        if last_time == 0:
                            running[user_id]["last_time"] = current_time
                            write_running()
                            continue
                        if current_time - last_time >= 60 * 60 * interval:
                            try:
                                next_interval = await heartbeat_core.process_user(int(user_id), interval)
                                if next_interval is not None:
                                    running[user_id]["interval"] = next_interval
                                running[user_id]["last_time"] = current_time
                                write_running()
                            except Exception as e:
                                log.error(f"主动聊天用户 {user_id} 发送失败: {e}")
                await asyncio.sleep(60)
            except Exception as e:
                log.error(f"主动聊天定时任务发生异常: {e}")
                await asyncio.sleep(60)

    # 启动后台任务
    asyncio.create_task(auto_summary_task())
    asyncio.create_task(auto_active_chat_task())

    # === 委托命令注册 ===

    chat_deps = {
        "bot": bot,
        "log": log,
        "admin": admin,
        "switch": switch,
        "running": running,
        "write_running": write_running,
        "normalize_timestamp": normalize_timestamp,
        "heartbeat_core": heartbeat_core,
        "normalize_file_path": normalize_file_path,
        "load_address": load_address,
        "get_group_history_items": get_group_history_items,
        "_history_items_to_text": _history_items_to_text,
        "summarize_group_text": summarize_group_text,
        "generate_today_summary": generate_today_summary,
        "group_messages": group_messages,
        "user_messages": user_messages,
    }

    admin_deps = {
        "bot": bot,
        "log": log,
        "admin": admin,
        "project_root": project_root,
        "read_secure_json": read_secure_json,
        "write_secure_json": write_secure_json,
        "workspace_available": workspace_available,
        "switch": switch,
        "normalize_file_path": normalize_file_path,
        "load_address": load_address,
        "group_messages": group_messages,
        "user_messages": user_messages,
        "delete_session_workspace": delete_session_workspace,
        "get_qq_session_id": get_qq_session_id,
    }

    from nbot.commands.ai.handlers_chat import register_chat_handlers
    from nbot.commands.ai.handlers_admin import register_admin_handlers

    register_chat_handlers(register_command, chat_deps)
    register_admin_handlers(register_command, admin_deps)
