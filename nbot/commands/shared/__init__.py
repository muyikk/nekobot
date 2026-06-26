"""Shared sub-package init."""

from nbot.commands.shared.data_persistence import (
    normalize_file_path,
    read_at_all_group,
    write_at_all_group,
    write_admin,
    load_admin,
    load_address,
    load_favorites,
    load_smtp_config,
    save_smtp_config,
    load_email_config,
    save_email_config,
    save_favorites,
    write_blak_list,
    load_blak_list,
    write_running,
    normalize_timestamp,
    load_running,
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

__all__ = [
    "normalize_file_path",
    "read_at_all_group",
    "write_at_all_group",
    "write_admin",
    "load_admin",
    "load_address",
    "load_favorites",
    "load_smtp_config",
    "save_smtp_config",
    "load_email_config",
    "save_email_config",
    "save_favorites",
    "write_blak_list",
    "load_blak_list",
    "write_running",
    "normalize_timestamp",
    "load_running",
    "load_novel_data",
    "schedule_task",
    "schedule_task_by_date",
    "schedule_job_task",
    "chatter",
    "chat_loop",
    "update_user_active_chat_time",
    "update_running",
    "apply_message_patches",
    "async_send_file",
    "handle_generic_file",
    "send_comic_email",
    "_send_comic_email_sync",
]
