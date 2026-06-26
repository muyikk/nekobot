"""Data persistence helpers for the commands package."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

import yaml

from nbot.commands.state import (
    admin,
    black_list_comic,
    running,
    smtp_config,
    user_email,
    user_favorites,
    group_favorites,
    books,
)
from nbot.utils.logger import get_logger

_log = get_logger(__name__)


def normalize_file_path(path: str) -> str:
    """Normalize a file path for cross-platform compatibility.

    Args:
        path: Raw file path.

    Returns:
        Absolute path with forward slashes.
    """
    return os.path.abspath(path).replace("\\", "/")


def load_address() -> str:
    """Return the absolute cache directory path.

    Reads ``resources/config/option.yml`` to determine the PDF output
    directory and returns its parent directory (the cache root).

    Returns:
        Absolute path to the cache directory.
    """
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    # nbot/commands/shared -> nbot -> project_root
    project_root = os.path.dirname(os.path.dirname(current_file_dir))

    config_path = os.path.join(
        project_root, "resources", "config", "option.yml"
    )

    with open(config_path, "r", encoding="utf-8") as f:
        conf = yaml.safe_load(f)
        after_photo_list = conf.get("plugins", {}).get("after_album", [])
        if after_photo_list and isinstance(after_photo_list, list):
            pdf_dir = after_photo_list[0].get("kwargs", {}).get(
                "pdf_dir", "./cache/pdf/"
            )
        else:
            pdf_dir = "./cache/pdf/"

    if not os.path.isabs(pdf_dir):
        pdf_dir = os.path.join(project_root, pdf_dir)

    pdf_dir = os.path.normpath(pdf_dir)
    cache_dir = os.path.dirname(pdf_dir)
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def read_at_all_group() -> None:
    """Load the @all enabled group list from disk."""
    from nbot.commands.state import at_all_group

    try:
        path = os.path.join(load_address(), "at_all_group.txt")
        with open(path, "r", encoding="utf-8") as f:
            group_ids = [line.strip() for line in f.readlines() if line.strip()]
            at_all_group.extend(group_ids)
    except FileNotFoundError:
        write_at_all_group()


def write_at_all_group() -> None:
    """Persist the @all enabled group list to disk."""
    from nbot.commands.state import at_all_group

    path = os.path.join(load_address(), "at_all_group.txt")
    with open(path, "w", encoding="utf-8") as f:
        for group_id in at_all_group:
            f.write(group_id + "\n")


def write_admin() -> None:
    """Persist the admin list to ``admin.txt``."""
    try:
        with open("admin.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(admin) + "\n")
    except Exception as e:
        _log.error(f"写入管理员文件失败: {e}")


def load_admin() -> None:
    """Load extra admin IDs from ``admin.txt``."""
    from nbot.web.utils.config_loader import load_config

    _, admin_id = load_config()
    root_admin = str(admin_id)
    try:
        with open("admin.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and line != root_admin:
                    admin.append(line)
    except FileNotFoundError:
        write_admin()


def load_favorites() -> None:
    """Load user and group favorites from JSON."""
    cache_dir = os.path.join(load_address(), "list")
    os.makedirs(cache_dir, exist_ok=True)

    user_file = os.path.join(cache_dir, "user_favorites.json")
    if os.path.exists(user_file):
        with open(user_file, "r", encoding="utf-8") as f:
            user_favorites.update(json.load(f))

    group_file = os.path.join(cache_dir, "group_favorites.json")
    if os.path.exists(group_file):
        with open(group_file, "r", encoding="utf-8") as f:
            group_favorites.update(json.load(f))


def save_favorites() -> None:
    """Persist user and group favorites to JSON."""
    cache_dir = os.path.join(load_address(), "list")
    os.makedirs(cache_dir, exist_ok=True)

    with open(
        os.path.join(cache_dir, "user_favorites.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(user_favorites, f, ensure_ascii=False, indent=2)

    with open(
        os.path.join(cache_dir, "group_favorites.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(group_favorites, f, ensure_ascii=False, indent=2)


def load_smtp_config() -> None:
    """Load SMTP configuration from ``smtp_config.json``."""
    global smtp_config
    try:
        with open("smtp_config.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "host" in data:
                smtp_config = {"global": data}
            else:
                smtp_config = data
    except FileNotFoundError:
        smtp_config = {}


def save_smtp_config() -> None:
    """Persist SMTP configuration to ``smtp_config.json``."""
    with open("smtp_config.json", "w", encoding="utf-8") as f:
        json.dump(smtp_config, f, ensure_ascii=False, indent=2)


def load_email_config() -> None:
    """Load user email mapping from ``email_config.json``."""
    global user_email
    try:
        with open("email_config.json", "r", encoding="utf-8") as f:
            user_email = json.load(f)
    except FileNotFoundError:
        user_email = {}


def save_email_config() -> None:
    """Persist user email mapping to ``email_config.json``."""
    with open("email_config.json", "w", encoding="utf-8") as f:
        json.dump(user_email, f, ensure_ascii=False, indent=2)


def write_blak_list() -> None:
    """Persist the comic blacklist to disk."""
    cache_dir = os.path.join(load_address(), "black_list")
    os.makedirs(cache_dir, exist_ok=True)
    try:
        with open(
            os.path.join(cache_dir, "blak_list.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(black_list_comic, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _log.error(f"写入黑名单文件失败: {e}")


def load_blak_list() -> None:
    """Load the comic blacklist from disk."""
    cache_dir = os.path.join(load_address(), "black_list")
    os.makedirs(cache_dir, exist_ok=True)
    try:
        with open(
            os.path.join(cache_dir, "blak_list.json"), "r", encoding="utf-8"
        ) as f:
            black_list_comic.update(json.load(f))
    except FileNotFoundError:
        write_blak_list()


def normalize_timestamp(ts: Any) -> float:
    """Normalize a timestamp to seconds.

    Handles millisecond timestamps by dividing by 1000.

    Args:
        ts: Raw timestamp value.

    Returns:
        Timestamp in seconds.
    """
    try:
        value = float(ts)
    except Exception:
        return 0.0
    if value > 1e11:
        return value / 1000.0
    return value


def write_running() -> None:
    """Persist the running chat state to disk."""
    cache_dir = os.path.join(load_address(), "running")
    os.makedirs(cache_dir, exist_ok=True)
    try:
        with open(
            os.path.join(cache_dir, "running.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(running, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _log.error(f"写入定时聊天开关文件失败: {e}")


def load_running() -> None:
    """Load the running chat state from disk."""
    cache_dir = os.path.join(load_address(), "running")
    os.makedirs(cache_dir, exist_ok=True)
    try:
        with open(
            os.path.join(cache_dir, "running.json"), "r", encoding="utf-8"
        ) as f:
            data = json.load(f)
            for uid, info in data.items():
                if isinstance(info, dict) and "last_time" in info:
                    info["last_time"] = normalize_timestamp(info["last_time"])
            running.update(data)
    except FileNotFoundError:
        write_running()


def load_novel_data() -> None:
    """Load the novel metadata cache into memory."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "resources", "config", "novel_details2.json"
    )
    with open(path, "r", encoding="utf-8") as f:
        books.update(json.load(f))
