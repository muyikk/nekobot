"""Chat fortune command."""
import random
from datetime import datetime

from nbot.commands import bot
from nbot.commands.registry import register_command


@register_command("/fortune", "/jrrp", help_text="/fortune -> 查看今日运势", category="3")
async def handle_fortune(msg, is_group=True):
    user_id = str(msg.user_id)
    today = datetime.now().strftime("%Y%m%d")
    seed = int(user_id) + int(today)
    random.seed(seed)

    luck_score = random.randint(1, 100)

    fortunes = [
        "大吉：万事如意，心想事成喵！",
        "中吉：今天会有好事发生喵~",
        "小吉：平平安安就是福喵~",
        "末吉：虽然平淡，但也是充实的一天喵。",
        "凶：出门记得带伞，注意安全喵……",
        "大凶：建议今天宅在家里看漫画喵QAQ"
    ]

    if luck_score >= 90: fortune = fortunes[0]
    elif luck_score >= 70: fortune = fortunes[1]
    elif luck_score >= 50: fortune = fortunes[2]
    elif luck_score >= 30: fortune = fortunes[3]
    elif luck_score >= 10: fortune = fortunes[4]
    else: fortune = fortunes[5]

    random.seed()

    reply = f"今日运势：{luck_score}点\n评价：{fortune}"
    if is_group: await msg.reply(text=reply)
    else: await bot.api.post_private_msg(msg.user_id, text=reply)
