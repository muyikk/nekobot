"""BotAPI message patches for recording assistant messages."""

from ncatbot.core import BotAPI, GroupMessage, PrivateMessage

# Prevent duplicate application of patches
if not hasattr(BotAPI, "_nbot_patched"):
    _original_post_private_msg = BotAPI.post_private_msg
    _original_post_group_msg = BotAPI.post_group_msg
    _original_group_reply = GroupMessage.reply
    _original_private_reply = PrivateMessage.reply
    _pending_group_reply_context: dict = {}

    async def wrapped_post_private_msg(self, user_id, **kwargs):  # noqa: N805
        content = kwargs.get("text", "")
        if content and isinstance(content, str):
            try:
                from chat import record_assistant_message
                record_assistant_message(content, user_id=user_id)
            except Exception:
                pass
        return await _original_post_private_msg(self, user_id, **kwargs)

    async def wrapped_post_group_msg(self, group_id, **kwargs):  # noqa: N805
        content = kwargs.get("text", "")
        if content and isinstance(content, str):
            try:
                from chat import record_assistant_message, log_to_group_full_file
                context_key = (str(group_id), content)
                pending_users = _pending_group_reply_context.get(context_key, [])
                # Lazy import to avoid circular
                from nbot.web.utils.config_loader import load_config
                bot_id, _ = load_config()
                group_user_id = (
                    pending_users.pop(0)
                    if pending_users
                    else kwargs.get("group_user_id")
                )
                if pending_users:
                    _pending_group_reply_context[context_key] = pending_users
                else:
                    _pending_group_reply_context.pop(context_key, None)
                record_assistant_message(
                    content,
                    group_id=group_id,
                    group_user_id=group_user_id,
                )
                log_to_group_full_file(group_id, bot_id, "机器人", content)
            except Exception:
                pass
        return await _original_post_group_msg(self, group_id, **kwargs)

    async def wrapped_group_reply(self, text=None, **kwargs):  # noqa: N805
        content = text if isinstance(text, str) else kwargs.get("text", "")
        if content and isinstance(content, str):
            context_key = (str(self.group_id), content)
            _pending_group_reply_context.setdefault(context_key, []).append(
                str(self.user_id)
            )
        return await _original_group_reply(self, text=text, **kwargs)

    BotAPI.post_private_msg = wrapped_post_private_msg
    BotAPI.post_group_msg = wrapped_post_group_msg
    GroupMessage.reply = wrapped_group_reply
    BotAPI._nbot_patched = True


def apply_message_patches() -> None:
    """No-op; patches are applied at module import time.

    This function exists so callers can explicitly document that
    patches are expected to be active.
    """
    pass
