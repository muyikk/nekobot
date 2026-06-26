"""Minecraft server status commands."""
import os

from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.utils.message_sender import send_text

mc = {}


@register_command("/mc", help_text="/mc <服务器地址> -> 发送mc服务器状态", category="3")
async def handle_mc(msg, is_group=True):
    if os.path.exists("mc.txt"):
        with open("mc.txt", "r") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) >= 2:
                    id = parts[0]
                    server = ":".join(parts[1:])
                    mc[id] = server
    else:
        with open("mc.txt", "w") as f:
            pass
    server = msg.raw_message[len("/mc"):].strip()
    if not server:
        if str(msg.user_id) in mc:
            server = mc[str(msg.user_id)]
        else:
            reply = "请输入服务器地址或使用/mc_bind进行绑定喵~"
            await send_text(msg, reply, is_group=is_group)
            return

    try:
        import mcstatus
        server = mcstatus.JavaServer.lookup(server)
        status = server.status()
        reply = f"服务器状态如下喵~\n服务器描述：{status.description}\n版本: {status.version.name}\n在线人数: {status.players.online}\n最大人数: {status.players.max}\n延迟: {int(status.latency)}ms"
        await send_text(msg, reply, is_group=is_group)
    except ImportError:
        reply = "未安装mcstatus库喵~请使用pip install mcstatus进行安装喵~"
        await send_text(msg, reply, is_group=is_group)
    except Exception:
        reply = "获取服务器状态失败喵~"
        await send_text(msg, reply, is_group=is_group)


@register_command("/mc_bind", help_text="/mc_bind <服务器地址> -> 绑定mc服务器", category="3")
async def handle_mc_bind(msg, is_group=True):
    server = msg.raw_message[len("/mc_bind"):].strip()
    if not server:
        reply = "请输入服务器地址喵~"
        await send_text(msg, reply, is_group=is_group)
        return
    mc[str(msg.user_id)] = server
    with open("mc.txt", "a") as f:
        f.write(f"{msg.user_id}:{server}\n")
    reply = "绑定成功喵~"
    await send_text(msg, reply, is_group=is_group)


@register_command("/mc_unbind", help_text="/mc_unbind -> 解绑mc服务器", category="3")
async def handle_mc_unbind(msg, is_group=True):
    if str(msg.user_id) in mc:
        del mc[str(msg.user_id)]
        with open("mc.txt", "r") as f:
            lines = f.readlines()
        with open("mc.txt", "w") as f:
            for line in lines:
                if line.split(":")[0] != str(msg.user_id):
                    f.write(line)
        reply = "解绑成功喵~"
        await send_text(msg, reply, is_group=is_group)
    else:
        reply = "你没有绑定过mc服务器喵~"
        await send_text(msg, reply, is_group=is_group)


@register_command("/mc_show", help_text="/mc_show -> 查看绑定的mc服务器", category="3")
async def handle_mc_show(msg, is_group=True):
    if str(msg.user_id) in mc:
        reply = f"你绑定的mc服务器是：{mc[str(msg.user_id)]}"
        await send_text(msg, reply, is_group=is_group)
    else:
        reply = "你没有绑定过mc服务器喵~"
        await send_text(msg, reply, is_group=is_group)
