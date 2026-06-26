"""Media dice and RPS commands."""
from nbot.commands import bot
from nbot.commands.registry import register_command


@register_command("/random_dice", "/rd", help_text="/random_dice 或者 /rd -> 发送随机骰子", category="3")
async def handle_random_dice(msg, is_group=True):
    if is_group:
        await bot.api.post_group_msg(msg.group_id, dice=True)
    else:
        await bot.api.post_private_msg(msg.user_id, dice=True)


@register_command("/random_rps", "/rps", help_text="/random_rps 或者 /rps -> 发送随机石头剪刀布", category="3")
async def handle_random_rps(msg, is_group=True):
    if is_group:
        await bot.api.post_group_msg(msg.group_id, rps=True)
    else:
        await bot.api.post_private_msg(msg.user_id, rps=True)
