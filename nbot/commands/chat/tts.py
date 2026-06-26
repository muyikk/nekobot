"""Chat TTS command."""
from nbot.commands import switch
from nbot.commands.registry import register_command
from nbot.utils.message_sender import send_text
from nbot.commands.state import admin, if_tts


@register_command("/tts", help_text="/tts -> 开启或关闭TTS(admin)", admin_show=True, category="4")
async def handle_tts(msg, is_group=True):
    if str(msg.user_id) not in admin:
        await send_text(msg, "你没有权限使用此命令喵~", is_group=is_group)
        return
    if_tts = switch.toggle_switch('tts', group_id=str(msg.group_id) if is_group else None, user_id=str(msg.user_id) if not is_group else None)

    text = "已开启TTS喵~" if if_tts else "已关闭TTS喵~"
    await send_text(msg, text, is_group=is_group)
    switch.save_switches()
