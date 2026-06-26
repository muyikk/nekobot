"""Message dispatch package."""

from nbot.commands.dispatch.at_bot import (
    is_at_bot,
    _bot_uin_candidates,
    _get_value,
    _is_at_all_enabled,
    _iter_mention_ids,
    _iter_message_segments,
    _normalize_qq_id,
)
from nbot.commands.dispatch.workspace import (
    _get_project_root,
    _save_incoming_files_to_workspace,
)
from nbot.commands.dispatch.dispatch import (
    dispatch_message,
    handle_group_message,
    handle_private_message,
)

__all__ = [
    "dispatch_message",
    "handle_group_message",
    "handle_private_message",
    "is_at_bot",
    "_normalize_qq_id",
    "_get_value",
    "_bot_uin_candidates",
    "_iter_mention_ids",
    "_iter_message_segments",
    "_is_at_all_enabled",
    "_save_incoming_files_to_workspace",
    "_get_project_root",
]
