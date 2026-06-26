"""Chat remind commands."""
import asyncio
import re
from datetime import datetime

from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.commands.shared.scheduler import schedule_task, schedule_task_by_date
from nbot.utils.message_sender import send_text


@register_command("/remind", help_text="/remind <多少小时后> <内容> -> 定时提醒", category="7")
async def handle_remind(msg, is_group=True):
    match = re.match(r'^/remind\s+(\d+\.?\d*)\s+(.+)$', msg.raw_message)
    if match:
        hours = float(match.group(1))
        content = match.group(2)
    else:
        if is_group:
            await msg.reply(text="格式错误喵~ 请输入 /remind 时间(小时) 内容")
            return
        else:
            await bot.api.post_private_msg(msg.user_id, text="格式错误喵~ 请输入 /remind 时间(小时) 内容")
            return
    if is_group:
        await msg.reply(text=f"已设置提醒喵~{hours}小时后会提醒你：{content}")
        asyncio.create_task(schedule_task(hours, msg.reply, content))
    else:
        await bot.api.post_private_msg(msg.user_id, text=f"已设置提醒喵~{hours}小时后会提醒你：{content}")
        asyncio.create_task(schedule_task(hours, bot.api.post_private_msg, msg.user_id, content))


@register_command("/premind", help_text="/premind <MM-DD> <HH:MM> <内容> -> 精确时间提醒", category="7")
async def handle_precise_remind(msg, is_group=True):
    try:
        parts = msg.raw_message.split(maxsplit=3)

        if len(parts) < 3:
            raise ValueError

        now = datetime.now()
        year = str(now.year)

        date_str = f"{year}-" + parts[1]
        time_str = parts[2]
        content = parts[3] if len(parts) > 3 else "提醒时间到了喵~"

        target_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        if target_time < now:
            await send_text(msg, "时间已经过去喵~", is_group=is_group)
            return

        reply = f"已设置精确提醒喵~将在 {target_time} 提醒: {content}"
        if is_group:
            await msg.reply(text=reply)
            asyncio.create_task(schedule_task_by_date(target_time, msg.reply, content))
        else:
            await bot.api.post_private_msg(msg.user_id, text=reply)
            asyncio.create_task(schedule_task_by_date(target_time, bot.api.post_private_msg, msg.user_id, content))

    except ValueError:
        error_msg = "格式错误喵~ 使用: /precise_remind MM-DD HH:MM 提醒内容"
        await send_text(msg, error_msg, is_group=is_group)
