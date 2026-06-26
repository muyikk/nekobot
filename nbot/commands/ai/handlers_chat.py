"""
聊天相关命令处理器

注册 summary_recent、summary_today、summary_auto、auto_reply、
active_chat、show_chat 等命令。
"""

import os
import time
from datetime import datetime


def register_chat_handlers(reg, deps):
    """注册所有聊天相关命令处理器。

    Args:
        reg: register_command 函数
        deps: 依赖字典，包含 bot/log/admin/switch 等
    """
    bot = deps["bot"]
    log = deps["log"]
    admin = deps["admin"]
    switch = deps["switch"]
    running = deps["running"]
    write_running = deps["write_running"]
    normalize_timestamp = deps["normalize_timestamp"]
    heartbeat_core = deps["heartbeat_core"]
    normalize_file_path = deps["normalize_file_path"]
    load_address = deps["load_address"]
    get_group_history_items = deps["get_group_history_items"]
    _history_items_to_text = deps["_history_items_to_text"]
    summarize_group_text = deps["summarize_group_text"]
    generate_today_summary = deps["generate_today_summary"]
    group_messages = deps["group_messages"]
    user_messages = deps["user_messages"]

    async def reply_current_channel(msg, is_group, text):
        if is_group:
            await msg.reply(text=text)
        else:
            await bot.api.post_private_msg(msg.user_id, text=text)

    def save_qq_histories():
        os.makedirs("saved_message", exist_ok=True)
        with open("saved_message/user_messages.json", "w", encoding="utf-8") as f:
            json.dump(user_messages, f, ensure_ascii=False, indent=4)
        with open("saved_message/group_messages.json", "w", encoding="utf-8") as f:
            json.dump(group_messages, f, ensure_ascii=False, indent=4)

    import json

    async def _get_group_today_summary_text(group_id):
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

    @reg(
        "/summary_recent",
        "/sr",
        help_text="/summary_recent [数量] 或 /sr [数量] -> 总结最近若干条群聊消息",
        category="2",
    )
    async def handle_summary_recent(msg, is_group=True):
        if not is_group:
            await bot.api.post_private_msg(msg.user_id, text="请在群聊中使用该命令喔~")
            return

        raw = getattr(msg, "raw_message", "") or ""
        prefix = "/summary_recent" if raw.startswith("/summary_recent") else "/sr"
        arg = raw[len(prefix):].strip()
        try:
            count = int(arg) if arg else 100
        except ValueError:
            await msg.reply(text="格式错误喔，请输入 /summary_recent [数量] 或 /sr [数量]")
            return
        count = max(1, min(count, 500))

        try:
            items = await get_group_history_items(msg.group_id, count, bot)
        except Exception as e:
            await msg.reply(text=f"获取群聊历史失败喔：{e}")
            return
        if not items:
            await msg.reply(text="没有获取到群聊历史消息喔~")
            return
        await msg.reply(text=summarize_group_text(_history_items_to_text(items)))

    @reg(
        "/summary_today",
        help_text="/summary_today -> 总结今天与机器人的聊天内容",
        category="2",
    )
    async def handle_summary_today(msg, is_group=True):
        if is_group:
            summary = await _get_group_today_summary_text(msg.group_id)
            if summary:
                await msg.reply(text=summary)
        else:
            summary = generate_today_summary(user_id=msg.user_id)
            await bot.api.post_private_msg(msg.user_id, text=summary)

    @reg(
        "/summary_auto",
        help_text="/summary_auto -> 开启或关闭每日自动总结群聊记录(admin)",
        category="2",
        admin_show=True,
    )
    async def handle_summary_auto(msg, is_group=True):
        if not is_group:
            await bot.api.post_private_msg(msg.user_id, text="请在群聊中使用该命令喔~")
            return
        if str(msg.user_id) not in admin:
            await msg.reply(text="你没有权限开启自动总结喔~")
            return

        state = switch.toggle_switch("summary_auto", group_id=str(msg.group_id))
        text = "已开启每日自动总结喔（将在每天23:55发送）" if state else "已关闭每日自动总结喔"
        await msg.reply(text=text)
        switch.save_switches()

    @reg(
        "/auto_reply",
        help_text="/auto_reply [on|off|话痨程度0-1] -> 开启/关闭或设置群聊智能自动回复(admin)",
        category="2",
        admin_show=True,
    )
    async def handle_auto_reply(msg, is_group=True):
        if not is_group:
            await bot.api.post_private_msg(msg.user_id, text="请在群聊中使用该命令喔~")
            return
        if str(msg.user_id) not in admin:
            await msg.reply(text="你没有权限开启智能自动回复喔~")
            return
        group_id_str = str(msg.group_id)
        raw = (getattr(msg, "raw_message", "") or "")[len("/auto_reply"):].strip()
        level = None

        if not raw:
            state = switch.toggle_switch("auto_reply", group_id=group_id_str)
        else:
            parts = raw.split()
            action = parts[0].lower()
            desired_state = True
            level_text = parts[0]

            if action in {"on", "enable", "start", "开启", "打开"}:
                desired_state = True
                level_text = parts[1] if len(parts) > 1 else None
            elif action in {"off", "disable", "stop", "关闭", "关掉"}:
                desired_state = False
                level_text = parts[1] if len(parts) > 1 else None

            if level_text:
                try:
                    level = max(0.0, min(float(level_text), 1.0))
                except ValueError:
                    await msg.reply(text="格式错误喔，请输入 on/off，或 0~1 之间的小数，例如 0.3 或 0.8")
                    return
                switch.group_switches.setdefault(group_id_str, {})["auto_reply_level"] = level

            switch.set_switch_state("auto_reply", desired_state, group_id=group_id_str)
            state = desired_state

        if level is None:
            try:
                level = float(switch.group_switches.get(group_id_str, {}).get("auto_reply_level", 0.5))
            except Exception:
                level = 0.5
        text = ("已开启群聊智能自动回复喔~" if state else "已关闭群聊智能自动回复喔~") + f" 当前话痨程度：{level:.2f}"
        await msg.reply(text=text)
        switch.save_switches()

    @reg(
        "/主动聊天",
        help_text="/主动聊天 [是否开启(1/0)] -> 开启/关闭主动聊天（AI将自行决定聊天频率）",
        category="2",
    )
    async def handle_active_chat(msg, is_group=True):
        if is_group:
            await msg.reply(text="只能私聊设置喔~")
            return

        try:
            raw = (getattr(msg, "raw_message", "") or "")[len("/主动聊天"):].strip()
            parts = raw.split() if raw else []
            user_id = str(msg.user_id)
            current = running.get(user_id, {})
            interval = float(current.get("interval", 1.0))
            active = bool(current.get("active", False))

            if not parts:
                active = not active
            elif len(parts) == 1:
                if parts[0] in ("0", "1"):
                    active = bool(int(parts[0]))
                else:
                    interval = float(parts[0])
                    active = True
            elif len(parts) >= 2:
                interval = float(parts[0])
                if parts[1] in ("0", "1"):
                    active = bool(int(parts[1]))

            running.setdefault(user_id, {})
            running[user_id]["interval"] = interval
            running[user_id]["active"] = active
            running[user_id]["state"] = False
            switch.set_switch_state("active_chat", active, user_id=user_id)

            if active:
                try:
                    recent = await bot.api.get_recent_contact(100)
                    for contact in recent.get("data", []):
                        latest = contact.get("lastestMsg", {})
                        if str(latest.get("user_id")) == user_id:
                            running[user_id]["last_time"] = normalize_timestamp(latest.get("time", 0))
                            break
                    running[user_id].setdefault("last_time", time.time())
                except Exception as e:
                    log.error(f"获取最近联系人失败: {e}")
                    running[user_id]["last_time"] = time.time()

            write_running()
            reply = f"设置成功喔，{'AI现在会自行决定什么时候找你聊天喔~' if active else '已关闭主动聊天喔~'}"
            await bot.api.post_private_msg(user_id, text=reply)
        except ValueError:
            await bot.api.post_private_msg(msg.user_id, text="格式错误喔，请输入 /主动聊天 [1/0]")

    @reg(
        "/show_chat",
        "/sc",
        help_text="/show_chat 或 /sc -> 发送完整聊天记录(仅群admin)",
        category="2",
    )
    async def handle_show_chat(msg, is_group=True):
        if (str(msg.user_id) not in admin) and is_group:
            await msg.reply(text="你没有权限发送聊天记录喔~")
            return

        cache_dir = normalize_file_path(os.path.join(load_address(), "聊天记录.txt"))
        is_web = hasattr(msg, "send_file") and not hasattr(msg, "message_type")

        if is_group and not is_web:
            try:
                text = str(group_messages[str(msg.group_id)])
            except KeyError:
                text = "该群没有聊天记录喔~"
            with open(cache_dir, "w", encoding="utf-8") as f:
                f.write(text)
            await bot.api.post_group_file(msg.group_id, file=cache_dir)
        else:
            try:
                text = str(user_messages[str(msg.user_id)])
            except KeyError:
                text = "你没有聊天记录喔~"
            with open(cache_dir, "w", encoding="utf-8") as f:
                f.write(text)
            if is_web and hasattr(msg, "send_file"):
                await msg.send_file(cache_dir, "聊天记录.txt")
            else:
                await bot.api.upload_private_file(msg.user_id, file=cache_dir, name="聊天记录.txt")

        try:
            os.remove(cache_dir)
        except OSError:
            pass
