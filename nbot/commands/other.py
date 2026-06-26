"""Other miscellaneous commands."""
import re

from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.utils.message_sender import send_text


@register_command("/generate_photo", "/gf", help_text="/generate_photo 或 /gf <图片描述(不能有空格)> <大小> -> 生成图片", category="3")
async def handle_gf(msg, is_group=True):
    text = re.sub(r'\[CQ:[^\]]*\]', '', msg.raw_message).strip()
    prefix = "/generate_photo" if text.startswith("/generate_photo") else "/gf"
    default_size = "2k"
    try:
        args = text[len(prefix):].strip().split()
        if not args:
            raise ValueError
        if len(args) == 1:
            prompt = args[0]
            size = default_size
        else:
            size = args[-1]
            prompt = ' '.join(args[:-1])

        if ('x' not in size) and ('k' not in size):
            size = default_size
    except Exception:
        error_msg = f"请输入图片描述喵~ 格式: {prefix} <描述> [大小，默认{default_size}]"
        await (msg.reply(text=error_msg) if is_group else bot.api.post_private_msg(msg.user_id, text=error_msg))
        return

    if is_group:
        await msg.reply(text="正在绘制喵……")
    else:
        await bot.api.post_private_msg(msg.user_id, text="正在绘制喵……")

    if msg.message[0]["type"] == "reply":
        id = msg.message[0]["data"]["id"]
        msg_obj = await bot.api.get_msg(message_id=id)
        if msg_obj.get("data").get("message")[0].get("type") == "image":
            image = msg_obj.get("data").get("message")[0].get("data").get("url")
    else:
        image = None

    from nbot.config import get_config
    api_key = get_config().get('gf', 'api_key')

    url = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

    payload = {
        "model": "doubao-seedream-4-0-250828",
        "prompt": prompt,
        "sequential_image_generation": "disabled",
        "response_format": "url",
        "size": size,
        "stream": False,
        "watermark": True
    }
    if image:
        payload["image"] = image

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    from nbot.utils.http_client import post_sync
    response = post_sync(url, json=payload, headers=headers)

    try:
        url = response.json().get("data")[0].get("url")
    except Exception as e:
        reply = f"绘制失败喵~,{e}\n{response.json()}"
        await send_text(msg, reply, is_group=is_group)
        return
    if is_group:
        await msg.reply(text="绘制完成喵~")
        await bot.api.post_group_file(msg.group_id, image=url)
    else:
        await bot.api.post_private_msg(msg.user_id, text="绘制完成喵~")
        await bot.api.post_private_file(msg.user_id, image=url)


@register_command("/识别人物", help_text="/识别人物 -> 识别图片中的二次元人物", category="3")
async def handle_rec(msg, is_group=True):
    if is_group:
        await msg.reply(text="请先发送图片，再回复图片，加上@我，/识别人物")
    else:
        await bot.api.post_private_msg(msg.user_id, text="请先发送图片，再回复图片，加上/识别人物")
    return
