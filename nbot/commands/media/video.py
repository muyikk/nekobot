"""Media video commands."""
import re

from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.commands.shared.file_sender import handle_generic_file
from nbot.utils.message_sender import send_text


@register_command("/random_video", "/rv", help_text="/random_video 或者 /rv -> 随机二次元视频", category="3")
async def handle_random_video(msg, is_group=True):
    await handle_generic_file(msg, is_group, 'rv', 'video')


@register_command("/dv", help_text="/dv <link> -> 下载视频", category="3")
async def handle_d(msg, is_group=True):
    link = msg.raw_message[len("/dv"):].strip()
    if not link:
        await send_text(msg, "请输入链接喵~", is_group=is_group)
        return

    if re.match(r'^https?://', link):
        await handle_generic_file(msg, is_group, '', 'video', custom_url=link)
    else:
        await send_text(msg, "请输入合法的链接喵~", is_group=is_group)


@register_command("/di", help_text="/di <link> -> 下载图片", category="3")
async def handle_di(msg, is_group=True):
    link = msg.raw_message[len("/di"):].strip()
    if not link:
        await send_text(msg, "请输入链接喵~", is_group=is_group)
        return

    if re.match(r'^https?://', link):
        if is_group:
            await bot.api.post_group_file(group_id=msg.group_id, file=link)
        else:
            await bot.api.upload_private_file(user_id=msg.user_id, file=link, name="download.jpg")
    else:
        await send_text(msg, "请输入合法的链接喵~", is_group=is_group)


@register_command("/df", help_text="/df <link> -> 下载文件", category="3")
async def handle_df(msg, is_group=True):
    link = msg.raw_message[len("/df"):].strip()
    if not link:
        await send_text(msg, "请输入链接喵~", is_group=is_group)
        return

    if re.match(r'^https?://', link):
        await handle_generic_file(msg, is_group, '', 'file', custom_url=link)
    else:
        await send_text(msg, "请输入合法的链接喵~", is_group=is_group)
