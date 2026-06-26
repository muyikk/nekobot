"""Media music commands."""
from ncatbot.core import MessageChain, Music

from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.utils.http_client import get_sync
from nbot.utils.message_sender import send_text


@register_command("/music", help_text="/music <音乐名/id> -> 发送音乐", category="3")
async def handle_music(msg, is_group=True):
    music_name = msg.raw_message[len("/music"):].strip()
    if not music_name:
        await msg.reply(text="请输入音乐名喵~")
        return

    if music_name.isdigit():
        messagechain = MessageChain(
            Music(type="163", id=music_name)
        )
        if is_group:
            await msg.reply(rtf=messagechain)
        else:
            await bot.api.post_private_msg(msg.user_id, rtf=messagechain)
        return

    music_id = None
    url = 'https://music.163.com/api/search/get'
    params = {
        's': music_name,
        'type': 1,
        'limit': 1
    }
    response = get_sync(url, params=params)
    data = response.json()
    if data['code'] == 200 and data['result']['songs']:
        music_id = data['result']['songs'][0]['id']

    messagechain = MessageChain(
        Music(type="163", id=music_id)
    )
    if is_group:
        await bot.api.post_group_msg(msg.group_id, rtf=messagechain)
    else:
        await bot.api.post_private_msg(msg.user_id, rtf=messagechain)


@register_command("/random_music", "/rm", help_text="/random_music 或者 /rm -> 发送随机音乐", category="3")
async def handle_random_music(msg, is_group=True):
    id = get_sync("https://api.mtbbs.top/Music/song/?id=2645495145").json()["data"]["id"]
    messagechain = MessageChain(
        Music(type="163", id=id)
    )
    if is_group:
        await bot.api.post_group_msg(msg.group_id, rtf=messagechain)
    else:
        await bot.api.post_private_msg(msg.user_id, rtf=messagechain)
