"""Chat translate command."""
from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.services.ai import ai_client


@register_command("/translate", "/tr", help_text="/translate <文本> -> 将文本翻译为中文/英文", category="3")
async def handle_translate(msg, is_group=True):
    text = msg.raw_message[len("/translate"):].strip() if msg.raw_message.startswith("/translate") else msg.raw_message[len("/tr"):].strip()
    if not text:
        reply = "请输入要翻译的文本喵~"
        if is_group: await msg.reply(text=reply)
        else: await bot.api.post_private_msg(msg.user_id, text=reply)
        return

    try:
        response = ai_client.chat_completion(
            model=None,
            messages=[
                {"role": "system", "content": "你是一个专业的翻译官。如果输入是中文，请翻译成英文；如果输入是其他语言，请翻译成中文。只返回翻译结果，不要有任何多余的解释。"},
                {"role": "user", "content": text}
            ]
        )
        result = response.choices[0].message.content.strip()
        reply = f"翻译结果如下喵：\n{result}"
        if is_group: await msg.reply(text=reply)
        else: await bot.api.post_private_msg(msg.user_id, text=reply)
    except Exception as e:
        reply = f"翻译出错喵：{e}"
        if is_group: await msg.reply(text=reply)
        else: await bot.api.post_private_msg(msg.user_id, text=reply)
