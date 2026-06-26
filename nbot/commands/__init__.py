"""Commands package — backward-compatible exports.

All infrastructure previously living in ``nbot/commands.py`` has been
moved into this package.  Business command handlers remain in
``nbot/commands.py`` for now (Phase 5 will migrate them).
"""

# Shared state (centralised to avoid circular imports)
from nbot.commands.state import (
    command_handlers,
    admin,
    black_list_comic,
    running,
    tasks,
    user_favorites,
    group_favorites,
    comic_cache,
    api_book,
    schedule_tasks,
    smtp_config,
    user_email,
    at_all_group,
    books,
    if_tts,
)

# Registry
from nbot.commands.registry import register_command, get_all_help_text_for_prompt

# Dispatch
from nbot.commands.dispatch import (
    dispatch_message,
    handle_group_message,
    handle_private_message,
    is_at_bot,
    _normalize_qq_id,
    _get_value,
    _bot_uin_candidates,
    _iter_mention_ids,
    _iter_message_segments,
    _is_at_all_enabled,
    _save_incoming_files_to_workspace,
    _get_project_root,
)

# Shared helpers
from nbot.commands.shared.data_persistence import (
    load_address,
    load_favorites,
    save_favorites,
    load_admin,
    write_admin,
    load_blak_list,
    write_blak_list,
    load_running,
    write_running,
    load_smtp_config,
    save_smtp_config,
    load_email_config,
    save_email_config,
    read_at_all_group,
    write_at_all_group,
    normalize_file_path,
    normalize_timestamp,
    load_novel_data,
)
from nbot.commands.shared.scheduler import (
    schedule_task,
    schedule_task_by_date,
    schedule_job_task,
)
from nbot.commands.shared.chatter import (
    chatter,
    chat_loop,
    update_user_active_chat_time,
    update_running,
)
from nbot.commands.shared.message_patches import apply_message_patches
from nbot.commands.shared.file_sender import async_send_file, handle_generic_file
from nbot.commands.shared.email import send_comic_email, _send_comic_email_sync

# Individual command handlers migrated out of commands.py
from nbot.commands.help import handle_help
from nbot.commands.bot_api import handle_api, parse_command_string
from nbot.commands.at_all import handle_at_all_group

# Re-export bot/switch so submodules can import them from here lazily.
# These are populated by nbot/commands.py after it imports this package.
bot = None  # type: ignore
switch = None  # type: ignore

__all__ = [
    # state
    "command_handlers",
    "admin",
    "black_list_comic",
    "running",
    "tasks",
    "user_favorites",
    "group_favorites",
    "comic_cache",
    "api_book",
    "schedule_tasks",
    "smtp_config",
    "user_email",
    "at_all_group",
    "books",
    "if_tts",
    # registry
    "register_command",
    "get_all_help_text_for_prompt",
    # dispatch
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
    # shared data
    "load_address",
    "load_favorites",
    "save_favorites",
    "load_admin",
    "write_admin",
    "load_blak_list",
    "write_blak_list",
    "load_running",
    "write_running",
    "load_smtp_config",
    "save_smtp_config",
    "load_email_config",
    "save_email_config",
    "read_at_all_group",
    "write_at_all_group",
    "normalize_file_path",
    "normalize_timestamp",
    "load_novel_data",
    # scheduler
    "schedule_task",
    "schedule_task_by_date",
    "schedule_job_task",
    # chatter
    "chatter",
    "chat_loop",
    "update_user_active_chat_time",
    "update_running",
    # patches
    "apply_message_patches",
    # file sender
    "async_send_file",
    "handle_generic_file",
    # email
    "send_comic_email",
    "_send_comic_email_sync",
    # handlers
    "handle_help",
    "handle_api",
    "parse_command_string",
    "handle_at_all_group",
    # populated by commands.py
    "bot",
    "switch",
]
