"""会话相关的工具函数（标签规范化、角色运行时状态复制等）。"""

import logging
import os
from copy import deepcopy
from datetime import datetime

from nbot.utils.logger import get_logger

_log = get_logger(__name__)


def _normalize_tags(tags):
    if isinstance(tags, str):
        tags = [part.strip() for part in tags.replace("，", ",").split(",")]
    if not isinstance(tags, list):
        return []
    normalized = []
    seen = set()
    for tag in tags:
        tag = str(tag or "").strip()
        if not tag:
            continue
        tag = tag[:24]
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(tag)
        if len(normalized) >= 20:
            break
    return normalized


def _runtime_snapshot_signature(snapshot):
    if not isinstance(snapshot, dict):
        return {}
    keys = (
        "mood",
        "mood_intensity",
        "energy",
        "affection",
        "trust",
        "security",
        "familiarity",
        "dependency",
        "jealousy",
        "visible_emotion",
        "hidden_emotion",
    )
    return {key: snapshot.get(key) for key in keys if key in snapshot}


def _normalize_runtime_timeline_entry(snapshot, timestamp=None):
    entry = _runtime_snapshot_signature(snapshot)
    entry["timestamp"] = timestamp or datetime.now().isoformat()
    return entry


def _skills_prompt_injection_enabled(settings):
    features = (settings or {}).get("features") or {}
    return bool(features.get("skills_prompt_injection", False))


def _get_base_dir(server):
    return getattr(server, "base_dir", os.getcwd())


def _copy_character_runtime_state(server, character_id, source_session_id, target_session_id):
    if not character_id or not source_session_id or not target_session_id:
        return

    try:
        from nbot.character.repository import (
            CharacterStateRepository,
            RelationshipRepository,
        )

        base_dir = _get_base_dir(server)
        source_scope = f"web:{source_session_id}"
        target_scope = f"web:{target_session_id}"

        state_repo = CharacterStateRepository(base_dir)
        state = state_repo.get(character_id, source_scope)
        if state:
            state.scope_id = target_scope
            state_repo.save(state)

        relationship_repo = RelationshipRepository(base_dir)
        source_session = getattr(server, "sessions", {}).get(source_session_id, {}) or {}
        source_targets = [
            source_scope,
            source_session.get("user_id"),
            source_session.get("qq_id"),
            source_session_id,
        ]
        relationship = None
        for source_target in source_targets:
            if not source_target:
                continue
            relationship = relationship_repo.get(character_id, str(source_target))
            if relationship:
                break
        if relationship:
            relationship.target_id = target_scope
            relationship_repo.save(relationship)
    except Exception as exc:
        _log.warning(
            "[CharacterRuntime] failed to copy fork runtime state %s -> %s: %s",
            source_session_id,
            target_session_id,
            exc,
            exc_info=True,
        )
