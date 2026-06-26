"""JM comic settings and get_fav commands."""
import hashlib
import os
import re
import time

from jmcomic import JmOption

from nbot.commands import bot, switch
from nbot.commands.registry import register_command
from nbot.commands.shared.data_persistence import load_address
from nbot.commands.jmcomic.html_builder import (
    build_jm_grid_html,
    append_jm_card,
    close_jm_grid_html,
)
from nbot.utils.message_sender import send_text, send_file
from nbot.commands.state import admin, comic_cache, user_email
from nbot.commands.shared.data_persistence import (
    save_email_config,
    load_email_config,
)


@register_command("/jm_clear", help_text="/jm_clear -> 清除缓存", category="1")
async def handle_jm_clear(msg, is_group=True):
    comic_cache.clear()
    await send_text(msg, "缓存已清除喵~", is_group=is_group)


@register_command("/jm_send_user", help_text="/jm_send_user <on|off> -> 开启/关闭群聊用户私信发送漫画(admin)", category="1", admin_show=True)
async def handle_jm_send_user(msg, is_group=True):
    if str(msg.user_id) not in admin:
        await msg.reply(text="只有管理员才能使用该命令喵~")
        return

    state = msg.raw_message[len("/jm_send_user"):].strip().lower()
    if state not in ['on', 'off']:
        reply = "请输入 on 或 off 喵~"
    else:
        switch.set_switch_state('jm_send_user', state == 'on', group_id=str(msg.group_id) if is_group else None, user_id=str(msg.user_id) if not is_group else None)
        reply = f"用户私信发送漫画已 {'开启' if state == 'on' else '关闭'} 喵~"
    await send_text(msg, reply, is_group=is_group)
    switch.save_switches()


@register_command("/jm_send", help_text="/jm_send <on|off> -> 开启/关闭发送漫画(admin)", category="1", admin_show=True)
async def handle_jm_send(msg, is_group=True):
    if str(msg.user_id) not in admin:
        await msg.reply(text="只有管理员才能使用该命令喵~")
        return
    state = msg.raw_message[len("/jm_send"):].strip().lower()
    if state not in ['on', 'off']:
        reply = "请输入 on 或 off 喵~"
    else:
        switch.set_switch_state('jm_send', state == 'on', group_id=str(msg.group_id) if is_group else None, user_id=str(msg.user_id) if not is_group else None)
        reply = f"{'群组' if is_group else '用户'}发送漫画已 {'开启' if state == 'on' else '关闭'} 喵~"
    await send_text(msg, reply, is_group=is_group)
    switch.save_switches()


@register_command("/jm_pwd", help_text="/jm_pwd <on|off> -> 开启/关闭密码加密(admin)，密码为漫画id", category="1", admin_show=True)
async def handle_jm_pwd(msg, is_group=True):
    if str(msg.user_id) not in admin:
        await msg.reply(text="只有管理员才能使用该命令喵~")
        return
    state = msg.raw_message[len("/jm_pwd"):].strip().lower()
    if state not in ['on', 'off']:
        reply = "请输入 on 或 off 喵~"
    else:
        switch.set_switch_state('pdf_password', state == 'on', group_id=str(msg.group_id) if is_group else None, user_id=str(msg.user_id) if not is_group else None)
        reply = f"{'群组' if is_group else '用户'}密码加密已 {'开启' if state == 'on' else '关闭'} 喵~，密码为漫画id"
    await send_text(msg, reply, is_group=is_group)


@register_command("/jm_email", help_text="/jm_email <邮箱> <on|off> -> 配置邮箱并开启或关闭发送漫画到邮箱", category="1")
async def handle_jm_email(msg, is_group=True):
    user_id = str(msg.user_id)
    raw = msg.raw_message[len("/jm_email"):].strip()
    parts = raw.split() if raw else []
    email = None
    state = None
    if not parts:
        current_email = user_email.get(user_id)
        enabled = switch.get_switch_state('jm_send_email', user_id=user_id)
        text = f"当前邮箱：{current_email or '未设置'}，状态：{'开启' if enabled else '关闭'}"
        await send_text(msg, text, is_group=is_group)
        return
    if len(parts) == 1:
        if parts[0].lower() in ("on", "off"):
            state = parts[0].lower() == "on"
        else:
            email = parts[0]
            state = True
    else:
        email = parts[0]
        if parts[1].lower() in ("on", "off"):
            state = parts[1].lower() == "on"
        else:
            text = "第二个参数请输入 on 或 off 喵~"
            await send_text(msg, text, is_group=is_group)
            return
    if email:
        if "@" not in email:
            text = "请输入正确的邮箱地址喵~"
            await send_text(msg, text, is_group=is_group)
            return
        user_email[user_id] = email
        save_email_config()
    if state is not None:
        switch.set_switch_state('jm_send_email', state, user_id=user_id)
        switch.save_switches()
    text = "邮箱配置已更新喵~"
    if state is not None:
        text = f"邮箱配置已更新喵~，发送到邮箱已{'开启' if state else '关闭'}"
    await send_text(msg, text, is_group=is_group)


@register_command("/get_fav", help_text="/get_fav <用户名> <密码> -> 获取收藏夹(群聊请私聊)", category="1")
async def handle_get_fav(msg, is_group=True):
    match = re.match(r'^/get_fav\s+(\S+)\s+(\S+)$', msg.raw_message)
    if not match:
        error_msg = "格式错误喵~ 请输入 /get_fav 用户名 密码"
        await send_text(msg, error_msg, is_group=is_group)
        return

    username = match.group(1)
    password = match.group(2)

    await send_text(msg, "正在获取收藏夹喵~", is_group=is_group)

    cache_dir = os.path.join(load_address(), "fav")
    os.makedirs(cache_dir, exist_ok=True)

    file_token = hashlib.md5(f"fav_{username}_{time.time()}".encode("utf-8")).hexdigest()[:8]
    filename = f"{file_token}_{username}.html"
    filepath = os.path.join(cache_dir, filename)
    comic_cache.clear()

    option = JmOption.default()
    cl = option.new_jm_client()
    try:
        cl.login(username, password)
    except Exception as e:
        await send_text(msg, f"登录失败喵~：{e}", is_group=is_group)
        return

    build_jm_grid_html(f"{__import__('html').escape(username)} · JM 收藏夹", filepath)

    tot = 0
    for page in cl.favorite_folder_gen():
        for aid, atitle in page.iter_id_title():
            tot += 1
            append_jm_card(filepath, aid, atitle, tot, client=cl)
            comic_cache.append(aid)
        if tot >= 50:
            break

    close_jm_grid_html(filepath)

    await send_file(msg, filepath, is_group=is_group, filename=filename)
