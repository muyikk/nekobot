"""Admin commands."""
from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.commands.shared.data_persistence import write_admin
from nbot.utils.message_sender import send_text
from nbot.commands.state import admin
from nbot.config import get_config


_ADMIN_ID: str | None = None


def _get_admin_id() -> str:
    """Return the configured root admin ID, loading it lazily."""
    global _ADMIN_ID
    if _ADMIN_ID is None:
        _ADMIN_ID = get_config().get("ROOT", "").strip()
    return _ADMIN_ID


@register_command("/set_admin", "/sa", help_text="/set_admin <qq号> 或者 /sa <qq号> -> 设置管理员(root)", category="4", admin_show=True)
async def handle_set_admin(msg, is_group=True):
    if is_group:
        await msg.reply(text="只能私聊设置喵~")
        return
    if str(msg.user_id) != _get_admin_id():
        await bot.api.post_private_msg(msg.user_id, text="你没有权限设置管理员喵~")
        return

    if msg.raw_message.startswith("/set_admin"):
        id = msg.raw_message[len("/set_admin"):].strip()
    else:
        id = msg.raw_message[len("/sa"):].strip()

    if id in admin:
        await bot.api.post_private_msg(msg.user_id, text="已经是管理员了喵~")
        return

    admin.append(id)
    write_admin()
    await bot.api.post_private_msg(msg.user_id, text="设置成功喵~，现在"+id+"是管理员喵~")


@register_command("/del_admin", "/da", help_text="/del_admin <qq号> 或者 /da <qq号> -> 删除管理员(root)", category="4", admin_show=True)
async def handle_del_admin(msg, is_group=True):
    if is_group:
        await msg.reply(text="只能私聊设置喵~")
        return
    if str(msg.user_id) != _get_admin_id():
        await bot.api.post_private_msg(msg.user_id, text="你没有权限删除管理员喵~")
        return

    if msg.raw_message.startswith("/del_admin"):
        id = msg.raw_message[len("/del_admin"):].strip()
    else:
        id = msg.raw_message[len("/da"):].strip()

    if id in admin:
        admin.remove(id)
        write_admin()
        await bot.api.post_private_msg(msg.user_id, text="删除成功喵~，现在"+id+"不是管理员喵~")
    else:
        await bot.api.post_private_msg(msg.user_id, text="没有这个管理员喵~")


@register_command("/get_admin", "/ga", help_text="/get_admin 或者 /ga -> 获取管理员", category="4")
async def handle_get_admin(msg, is_group=True):
    await send_text(msg, "管理员列表："+str(admin), is_group=is_group)


@register_command("/set_ids", help_text="/set_ids <昵称> <个性签名> <性别> -> 设置账号信息(管理员)", category="4", admin_show=True)
async def handle_set(msg, is_group=True):
    """
            nickname: 昵称
            personal_note: 个性签名
            sex: 性别
            :return: 设置账号信息
    """
    if is_group:
        await msg.reply(text="只能私聊设置喵~")
        return
    if str(msg.user_id) not in admin:
        await bot.api.post_private_msg(msg.user_id, text="你没有权限设置账号信息喵~")
        return
    msgs = msg.raw_message[len("/set_ids"):].split(" ")
    if len(msgs) < 3:
        text = "格式错误喵~ 请输入 /set 昵称 个性签名 性别"
        await send_text(msg, text, is_group=is_group)
        return
    try:
        nickname = msgs[0]
        personal_note = msgs[1]
        sex = msgs[2]
        await bot.api.set_qq_profile(nickname=nickname, personal_note=personal_note, sex=sex)
        text = "设置成功喵~"
        await send_text(msg, text, is_group=is_group)
    except Exception:
        text = "设置失败喵~"
        await send_text(msg, text, is_group=is_group)


@register_command("/set_online_status", help_text="/set_online_status <在线状态> -> 设置在线状态(管理员)", category="4", admin_show=True)
async def handle_set_online_status(msg, is_group=True):
    if is_group:
        await msg.reply(text="只能私聊设置喵~")
        return
    if str(msg.user_id) not in admin:
        await bot.api.post_private_msg(msg.user_id, text="你没有权限设置在线状态喵~")
        return
    msgs = msg.raw_message[len("/set_online_status"):].split(" ")[0]
    await bot.api.set_online_status(msgs)
    text = "设置成功喵~"
    await send_text(msg, text, is_group=is_group)


@register_command("/get_friends", help_text="/get_friends -> 获取好友列表（管理员）", category="4", admin_show=True)
async def handle_get_friends(msg, is_group=True):
    if is_group:
        await msg.reply(text="只能私聊获取喵~")
        return
    if str(msg.user_id) not in admin:
        await bot.api.post_private_msg(msg.user_id, text="你没有权限获取好友列表喵~")
        return
    friends = await bot.api.get_friend_list(False)
    await send_text(msg, friends, is_group=is_group)


@register_command("/set_qq_avatar", help_text="/set_qq_avatar <地址> -> 更改头像（管理员）", category="4", admin_show=True)
async def handle_set_qq_avatar(msg, is_group=True):
    if is_group:
        await msg.reply(text="只能私聊设置喵~")
        return

    if str(msg.user_id) not in admin:
        await bot.api.post_private_msg(msg.user_id, text="你没有权限设置头像喵~")
        return

    msgs = msg.raw_message[len("/set_qq_avatar"):]
    await bot.api.set_qq_avatar(msgs)
    text = "设置成功喵~"
    await send_text(msg, text, is_group=is_group)


@register_command("/send_like", help_text="/send_like <目标QQ号> <次数> -> 发送点赞(admin)", category="4", admin_show=True)
async def handle_send_like(msg, is_group=True):
    if str(msg.user_id) not in admin:
        await send_text(msg, "你没有权限发送点赞喵~", is_group=is_group)
        return

    msgs = msg.raw_message[len("/send_like"):].split(" ")
    if len(msgs) < 2:
        text = "格式错误喵~ 请输入 /send_like 目标QQ号 次数"
        await send_text(msg, text, is_group=is_group)
        return

    target_qq = msgs[0]
    times = msgs[1]
    await bot.api.send_like(target_qq, times)
    text = "发送成功喵~"
    await send_text(msg, text, is_group=is_group)


@register_command("/set_group_admin", help_text="/set_group_admin <目标QQ号> -> 设置群管理员(admin)", category="4", admin_show=True)
async def handle_set_group_admin(msg, is_group=True):
    if not is_group:
        await bot.api.post_private_msg(msg.user_id, text="只能在群聊中设置群管理员喵~")
        return

    if str(msg.user_id) not in admin:
        await msg.reply(text="你没有权限设置群管理员喵~")
        return

    msgs = msg.raw_message[len("/set_group_admin"):].split(" ")[0]
    await bot.api.set_group_admin(msg.group_id, msgs, True)
    await msg.reply(text="设置成功喵~")


@register_command("/del_group_admin", help_text="/del_group_admin <目标QQ号> -> 取消群管理员(admin)", category="4", admin_show=True)
async def handle_del_group_admin(msg, is_group=True):
    if not is_group:
        await bot.api.post_private_msg(msg.user_id, text="只能在群聊中取消群管理员喵~")
        return

    if str(msg.user_id) not in admin:
        await msg.reply(text="你没有权限设置群管理员喵~")
        return

    msgs = msg.raw_message[len("/del_group_admin"):].split(" ")[0]
    await bot.api.set_group_admin(msg.group_id, msgs, False)
    await msg.reply(text="取消成功喵~")
