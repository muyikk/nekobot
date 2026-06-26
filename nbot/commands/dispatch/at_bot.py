"""@bot detection and QQ ID normalization helpers."""

from __future__ import annotations

import re
from typing import Any, Optional, Set

from nbot.commands.state import at_all_group
from nbot.config import get_config
from nbot.utils.logger import get_logger

_log = get_logger(__name__)

# Bot UIN loaded lazily to avoid circular imports at module load time.
_BOT_UIN: Optional[str] = None
_BOT_ID: Optional[str] = None


def _ensure_bot_uin() -> None:
    """Load BOT_UIN and bot_id from config on first use."""
    global _BOT_UIN, _BOT_ID
    if _BOT_UIN is None:
        _BOT_UIN = get_config().get("BOT__UIN", "").strip()
    if _BOT_ID is None:
        _BOT_ID = get_config().get("ROOT", "").strip()


def _normalize_qq_id(value: Any) -> str:
    """Normalize a QQ ID value to a clean string."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def _get_value(source: Any, *keys: str) -> Any:
    """Safely get a value from a dict or object by multiple candidate keys."""
    for key in keys:
        if isinstance(source, dict) and key in source:
            return source.get(key)
        if hasattr(source, key):
            return getattr(source, key)
    return None


def _bot_uin_candidates(msg: Any = None) -> Set[str]:
    """Collect all possible bot UIN candidates."""
    _ensure_bot_uin()
    candidates: Set[str] = set()
    for value in (_BOT_UIN, _BOT_ID):
        qq_id = _normalize_qq_id(value)
        if qq_id:
            candidates.add(qq_id)

    if msg is not None:
        for attr in ("self_id", "bot_id", "bot_uin", "login_uin"):
            qq_id = _normalize_qq_id(getattr(msg, attr, None))
            if qq_id:
                candidates.add(qq_id)

        for attr in ("sender", "self", "login_info"):
            nested = getattr(msg, attr, None)
            qq_id = _normalize_qq_id(
                _get_value(nested, "self_id", "bot_id", "user_id", "uin", "qq", "id")
            )
            if qq_id:
                candidates.add(qq_id)

    return candidates


def _iter_mention_ids(value: Any) -> Any:
    """Yield normalized QQ IDs from a mention structure."""
    if value is None:
        return

    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_mention_ids(item)
        return

    data = _get_value(value, "data")
    if data is not None and data is not value:
        for key in ("qq", "user_id", "uin", "id", "target", "target_id"):
            qq_id = _normalize_qq_id(_get_value(data, key))
            if qq_id:
                yield qq_id

    for key in ("qq", "user_id", "uin", "id", "target", "target_id"):
        qq_id = _normalize_qq_id(_get_value(value, key))
        if qq_id:
            yield qq_id

    if isinstance(value, (str, int, float)):
        qq_id = _normalize_qq_id(value)
        if qq_id:
            yield qq_id


def _iter_message_segments(msg: Any) -> Any:
    """Yield message segments from various message attributes."""
    for attr in ("message", "message_chain", "message_array"):
        segments = getattr(msg, attr, None)
        if not segments:
            continue
        if isinstance(segments, (str, bytes)):
            continue
        for segment in segments:
            yield segment


def _is_at_all_enabled(msg: Any, mention_id: str) -> bool:
    """Check whether @all is enabled for the message's group."""
    if mention_id.lower() != "all" and mention_id != "全体成员":
        return False
    group_id = _normalize_qq_id(getattr(msg, "group_id", None))
    return bool(group_id and group_id in at_all_group)


def is_at_bot(msg: Any) -> bool:
    """Return True if the message mentions the bot."""
    bot_uins = _bot_uin_candidates(msg)
    raw_message = str(getattr(msg, "raw_message", "") or "")

    for attr in ("is_at_me", "at_me", "to_me"):
        if getattr(msg, attr, False):
            return True

    for mention_id in re.findall(
        r"\[CQ:at[^\]]*(?:qq|id|target)=([^,\]\s]+)", raw_message
    ):
        mention_id = _normalize_qq_id(mention_id)
        if mention_id in bot_uins or _is_at_all_enabled(msg, mention_id):
            return True

    for attr in ("at_list", "at", "mentions", "mention_list"):
        for mention_id in _iter_mention_ids(getattr(msg, attr, None)):
            if mention_id in bot_uins or _is_at_all_enabled(msg, mention_id):
                return True

    for segment in _iter_message_segments(msg):
        segment_type = str(_get_value(segment, "type", "msg_type") or "").lower()
        if segment_type not in ("at", "mention"):
            continue
        for mention_id in _iter_mention_ids(segment):
            if mention_id in bot_uins or _is_at_all_enabled(msg, mention_id):
                return True

    for bot_uin in bot_uins:
        if bot_uin and bot_uin in raw_message:
            return True

    return False
