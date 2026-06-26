"""Chat task commands."""
import asyncio
import re

from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.commands.bot_api import parse_command_string
from nbot.commands.shared.scheduler import schedule_job_task
from nbot.utils.message_sender import send_text
from nbot.commands.state import admin, schedule_tasks


@register_command("/smtp", help_text="/smtp <host> <port> <user> <password> <tls(1/0)> <from> -> 配置当前用户SMTP服务", category="4")
async def handle_smtp_config_command(msg, is_group=True):
    from nbot.commands.state import smtp_config
    from nbot.commands.shared.data_persistence import save_smtp_config
    user_id = str(msg.user_id)
    raw = msg.raw_message[len("/smtp"):].strip()
    parts = raw.split() if raw else []
    if not parts:
        conf = smtp_config.get(user_id) or smtp_config.get("global")
        if conf:
            text = f"当前SMTP已配置喵~ host={conf.get('host')}, port={conf.get('port')}"
        else:
            text = "当前还没有配置SMTP喵~"
        await send_text(msg, text, is_group=is_group)
        return
    if len(parts) < 5:
        text = "格式错误喵~ 应为: /smtp host port user password tls(1/0) [from]"
        await send_text(msg, text, is_group=is_group)
        return
    host = parts[0]
    try:
        port = int(parts[1])
    except ValueError:
        text = "端口必须是数字喵~"
        await send_text(msg, text, is_group=is_group)
        return
    user = parts[2]
    password = parts[3]
    use_tls = parts[4] != "0"
    from_addr = parts[5] if len(parts) > 5 else user
    smtp_config[user_id] = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "use_tls": use_tls,
        "from_addr": from_addr
    }
    save_smtp_config()
    text = "SMTP配置已更新喵~"
    await send_text(msg, text, is_group=is_group)


@register_command("/task", help_text="/task </bot.api.xxxx(参数1=值1...)> <时间(小时)> <是否循环(1/0)> -> 设置定时任务(admin)", category="7", admin_show=True)
async def handle_task(msg, is_group=True):
    if str(msg.user_id) not in admin:
        text = "你没有权限设置定时任务喵~"
        await send_text(msg, text, is_group=is_group)
        return

    match = re.match(r'^/task\s+(.+)\s+(\d+\.?\d*)\s+(\d)$', msg.raw_message)
    if match:
        command_str = match.group(1)
        hours = float(match.group(2))
        loop = int(match.group(3))
    else:
        error_msg = "格式错误喵~ 请输入 /task bot.api.xxxx(参数1=值1...) 时间(小时) 是否循环(1/0)"
        if is_group:
            await msg.reply(text=error_msg)
        else:
            await bot.api.post_private_msg(msg.user_id, text=error_msg)
        return
    if loop not in [0, 1]:
        error_msg = "格式错误喵~ 请输入 /task bot.api.xxxx(参数1=值1...) 时间(小时) 是否循环(1/0)"
        if is_group:
            await msg.reply(text=error_msg)
        else:
            await bot.api.post_private_msg(msg.user_id, text=error_msg)
        return

    dict = parse_command_string(command_str)
    command = dict["func"]
    params = dict["params"]
    try:
        func = getattr(bot.api, command.split('.')[-1])
    except Exception as e:
        error_msg = f"发生错误喵~ 请检查命令是否正确。{e}"
        if is_group:
            await msg.reply(text=error_msg)
        else:
            await bot.api.post_private_msg(msg.user_id, text=error_msg)
        return

    if loop == 0:
        task = asyncio.create_task(schedule_job_task(hours, 0, f"{command_str}_{hours}_{loop}", func, **params))
        schedule_tasks[f"{command_str}_{hours}_{loop}"] = task
        await send_text(msg, f"已设置定时任务喵~{hours}小时后会执行：{command_str}", is_group=is_group)
        return

    else:
        task = asyncio.create_task(schedule_job_task(hours, 1, f"{command_str}_{hours}_{loop}", func, **params))
        schedule_tasks[f"{command_str}_{hours}_{loop}"] = task
        await send_text(msg, f"已设置循环定时任务喵~{hours}小时后会执行：{command_str}", is_group=is_group)
        return


@register_command("/list_tasks", "/lt", help_text="/list_tasks 或者 /lt -> 查看定时任务(admin)", category="7", admin_show=True)
async def handle_list_tasks(msg, is_group=True):
    if str(msg.user_id) not in admin:
        text = "你没有权限查看定时任务喵~"
        await send_text(msg, text, is_group=is_group)
        return
    text = "定时任务列表：\n"
    tot = 0
    for i in schedule_tasks.keys():
        tot += 1
        text += f"{tot}. {i}\n"
    await send_text(msg, text, is_group=is_group)
    return


@register_command("/cancel_tasks", "/ct", help_text="/cancel_tasks 或者 /ct <任务名> -> 取消定时任务(admin)", category="7", admin_show=True)
async def handle_cancel_tasks(msg, is_group=True):
    if str(msg.user_id) not in admin:
        text = "你没有权限取消定时任务喵~"
        await send_text(msg, text, is_group=is_group)
        return
    pre = "/cancel_tasks" if msg.raw_message.startswith("/cancel_tasks") else "/ct"
    name = msg.raw_message[len(pre):].strip()

    if name == "":
        text = "请输入任务名喵~"
        await send_text(msg, text, is_group=is_group)
        return

    if name not in schedule_tasks:
        text = "没有这个任务喵~"
        await send_text(msg, text, is_group=is_group)
        return

    schedule_tasks[name].cancel()
    del schedule_tasks[name]
    text = "取消成功喵~"
    await send_text(msg, text, is_group=is_group)
    return
