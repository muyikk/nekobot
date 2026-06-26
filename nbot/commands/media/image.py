"""Media image commands."""
from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.commands.shared.file_sender import handle_generic_file
from nbot.utils.http_client import get_sync
from nbot.utils.message_sender import send_text


@register_command("/random_image", "/ri", help_text="/random_image 或者 /ri -> 随机图片", category="3")
async def handle_random_image(msg, is_group=True):
    await handle_generic_file(msg, is_group, 'ri', 'image')


@register_command("/random_emoticons", help_text="/random_emoticons 或者 /re -> 随机表情包", category="3")
async def handle_random_emoticons(msg, is_group=True):
    await handle_generic_file(msg, is_group, 're', 'image')


@register_command("/st", help_text="/st <标签名> -> 发送随机涩图,标签支持与与(& |)", category="3")
async def handle_st(msg, is_group=True):
    tags = msg.raw_message[len("/st"):].strip()
    res = get_sync(f"https://api.lolicon.app/setu/v2?tag={tags}").json().get("data")[0].get("urls").get("original")
    await handle_generic_file(msg, is_group, "", "image", custom_url=res)


def _parse_loli_params(raw: str):
    """解析 /loli 和 /r18 命令参数

    纯数字 → num，其他字符 → tag（可用 & 组合）
    示例: "初音未来 3" → tag="初音未来", num=3
          "初音未来&和服" → tag="初音未来&和服", num=1
          "5" → tag="", num=5
    """
    tag = ""
    num = 1
    for p in raw.strip().split():
        if p.isdigit():
            num = max(1, min(int(p), 10))
        else:
            if tag:
                tag += " " + p
            else:
                tag = p
    return tag, num


@register_command("/loli", help_text="/loli [标签] [数量] -> 获取安全涩图(r18=0), 标签可用&组合, 如: /loli 初音未来&和服 3", category="3")
async def handle_loli(msg, is_group=True):
    tag, num = _parse_loli_params(msg.raw_message[len("/loli"):])
    try:
        params = {"r18": 0, "num": num, "size": "original"}
        if tag:
            params["tag"] = tag
        data = get_sync("https://api.lolicon.app/setu/v2", params=params, timeout=30).json()
        if data.get("error"):
            await msg.reply(text=f"获取失败: {data['error']}")
            return
        items = data.get("data") or []
        if not items:
            await msg.reply(text="没有找到匹配的图片喵~")
            return
        for item in items:
            img_url = item.get("urls", {}).get("original")
            if img_url:
                await handle_generic_file(msg, is_group, "", "image", custom_url=img_url)
    except Exception as e:
        from nbot.utils.logger import get_logger
        _log = get_logger(__name__)
        _log.error(f"/loli 失败: {e}")
        await msg.reply(text=f"获取失败喵~ {e}")


@register_command("/r18", help_text="/r18 [标签] [数量] -> 获取R18涩图(r18=1), 标签可用&组合, 如: /r18 萝莉 5", category="3")
async def handle_r18(msg, is_group=True):
    tag, num = _parse_loli_params(msg.raw_message[len("/r18"):])
    try:
        params = {"r18": 1, "num": num, "size": "original"}
        if tag:
            params["tag"] = tag
        data = get_sync("https://api.lolicon.app/setu/v2", params=params, timeout=30).json()
        if data.get("error"):
            await msg.reply(text=f"获取失败: {data['error']}")
            return
        items = data.get("data") or []
        if not items:
            await msg.reply(text="没有找到匹配的图片喵~")
            return
        for item in items:
            img_url = item.get("urls", {}).get("original")
            if img_url:
                await handle_generic_file(msg, is_group, "", "image", custom_url=img_url)
    except Exception as e:
        from nbot.utils.logger import get_logger
        _log = get_logger(__name__)
        _log.error(f"/r18 失败: {e}")
        await msg.reply(text=f"获取失败喵~ {e}")
