"""会话导入/导出、Fork、角色绑定、重新生成与运行时时间线路由。"""

import json
import uuid
from copy import deepcopy
from datetime import datetime

from flask import jsonify, request

from nbot.web.persistence import is_web_visible_session
from nbot.utils.logger import get_logger
from nbot.web.routes.chat.sessions_utils import (
    _copy_character_runtime_state,
    _normalize_runtime_timeline_entry,
    _normalize_tags,
)

_log = get_logger(__name__)


def register_import_export_routes(app, server, session_store, _get_web_session, _find_message_index, _ensure_mutable_session):
    """注册导入/导出、Fork、角色绑定、重新生成与运行时时间线相关路由。"""

    def _export_session_payload(sessions):
        return {
            "version": 1,
            "type": "nbot_session_export",
            "exported_at": datetime.now().isoformat(),
            "total": len(sessions),
            "sessions": sessions,
        }

    def _normalize_imported_session(raw_session):
        if not isinstance(raw_session, dict):
            raise ValueError("session must be an object")
        old_id = str(raw_session.get("id") or "").strip()
        new_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        session = dict(raw_session)
        session["id"] = new_id
        session["name"] = session.get("name") or f"Imported {new_id[:8]}"
        if old_id:
            session["imported_from"] = old_id
        session["imported_at"] = now
        session["type"] = session.get("type") or "web"
        if session["type"] not in {"web", "cli"}:
            session["type"] = "web"
        messages = session.get("messages")
        if not isinstance(messages, list):
            messages = []
        session["messages"] = [m for m in messages if isinstance(m, dict)]
        system_prompt = session.get("system_prompt")
        if not system_prompt:
            system_msg = next((m for m in session["messages"] if m.get("role") == "system"), None)
            system_prompt = (system_msg or {}).get("content", "")
        session["system_prompt"] = system_prompt or ""
        if not session.get("character_id") and session.get("sender_name"):
            session["character_id"] = session["sender_name"]
        if session["system_prompt"] and not any(m.get("role") == "system" for m in session["messages"]):
            session["messages"].insert(0, {"role": "system", "content": session["system_prompt"]})
        session["created_at"] = session.get("created_at") or now
        session["archived"] = bool(session.get("archived"))
        session["archived_at"] = session.get("archived_at") if session["archived"] else None
        if not is_web_visible_session(new_id, session):
            raise ValueError("invalid session type")
        return new_id, session

    @app.route("/api/sessions/<session_id>/runtime-timeline", methods=["GET"])
    def get_runtime_timeline(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        timeline = session.get("character_runtime_timeline", [])
        if not isinstance(timeline, list):
            timeline = []
        return jsonify({"success": True, "timeline": timeline})

    @app.route("/api/sessions/<session_id>/runtime-timeline", methods=["POST"])
    def add_runtime_timeline(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        data = request.json or {}
        snapshot = data.get("snapshot") if isinstance(data, dict) else None
        if not isinstance(snapshot, dict):
            return jsonify({"error": "Invalid runtime snapshot"}), 400

        entry = _normalize_runtime_timeline_entry(snapshot)
        timeline = session.get("character_runtime_timeline", [])
        if not isinstance(timeline, list):
            timeline = []

        last = timeline[-1] if timeline else None
        if isinstance(last, dict):
            last_signature = {k: v for k, v in last.items() if k != "timestamp"}
            entry_signature = {k: v for k, v in entry.items() if k != "timestamp"}
            if last_signature == entry_signature:
                last["timestamp"] = entry["timestamp"]
            else:
                timeline.append(entry)
        else:
            timeline.append(entry)

        session["character_runtime_timeline"] = timeline[-200:]
        session_store.set_session(session_id, session)
        return jsonify({"success": True, "timeline": session["character_runtime_timeline"]})

    @app.route("/api/sessions/<session_id>/export")
    def export_session(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        return jsonify(_export_session_payload([session]))

    @app.route("/api/sessions/export")
    def export_sessions():
        ids = [sid.strip() for sid in request.args.get("ids", "").split(",") if sid.strip()]
        sessions = []
        if ids:
            for sid in ids:
                session = _get_web_session(sid)
                if session:
                    sessions.append(session)
        else:
            for sid, session in (server.sessions or {}).items():
                if is_web_visible_session(sid, session):
                    sessions.append(session)
        return jsonify(_export_session_payload(sessions))

    @app.route("/api/sessions/import", methods=["POST"])
    def import_sessions():
        data = request.get_json(silent=True) or {}
        sessions_payload = data.get("sessions")
        if sessions_payload is None and isinstance(data.get("session"), dict):
            sessions_payload = [data["session"]]
        if sessions_payload is None and isinstance(data, dict) and data.get("type") != "nbot_session_export":
            sessions_payload = [data]
        if not isinstance(sessions_payload, list):
            return jsonify({"success": False, "error": "sessions must be a list"}), 400

        imported = []
        errors = []
        for idx, raw_session in enumerate(sessions_payload):
            try:
                session_id, session = _normalize_imported_session(raw_session)
                session_store.set_session(session_id, session)
                if server.WORKSPACE_AVAILABLE and server.workspace_manager:
                    server.workspace_manager.get_or_create(
                        session_id, session.get("type", "web"), session.get("name", "")
                    )
                imported.append({"id": session_id, "name": session.get("name")})
            except Exception as exc:
                errors.append({"index": idx, "error": str(exc)})

        return jsonify({
            "success": True,
            "imported": len(imported),
            "failed": len(errors),
            "sessions": imported,
            "errors": errors,
        })

    @app.route("/api/sessions/<session_id>/fork", methods=["POST"])
    def fork_session(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        data = request.get_json(silent=True) or {}
        message_id = data.get("message_id")
        messages = session.get("messages", [])
        message_index = _find_message_index(messages, message_id)
        if message_index < 0:
            return jsonify({"success": False, "error": "Message not found"}), 404

        now = datetime.now().isoformat()
        new_id = str(uuid.uuid4())
        base_name = session.get("name") or f"Session {session_id[:8]}"
        forked_messages = deepcopy(messages[: message_index + 1])
        system_prompt = session.get("system_prompt", "")
        if not system_prompt:
            system_msg = next((m for m in forked_messages if m.get("role") == "system"), None)
            system_prompt = (system_msg or {}).get("content", "")
        if system_prompt and not any(m.get("role") == "system" for m in forked_messages):
            forked_messages.insert(0, {"role": "system", "content": system_prompt})

        new_session = {
            "id": new_id,
            "name": f"{base_name} - Fork",
            "type": session.get("type") if session.get("type") in {"web", "cli"} else "web",
            "user_id": session.get("user_id"),
            "qq_id": session.get("qq_id"),
            "created_at": now,
            "archived": False,
            "archived_at": None,
            "messages": forked_messages,
            "system_prompt": system_prompt,
            "character_id": session.get("character_id") or session.get("sender_name", ""),
            "sender_name": session.get("sender_name", ""),
            "sender_avatar": session.get("sender_avatar", ""),
            "sender_portrait": session.get("sender_portrait", ""),
            "scenario": session.get("scenario", ""),
            "character_runtime_snapshot": deepcopy(session.get("character_runtime_snapshot")),
            "forked_from": {
                "session_id": session_id,
                "message_id": message_id,
                "message_index": message_index,
                "created_at": now,
            },
        }
        session_store.set_session(new_id, new_session)
        _copy_character_runtime_state(
            server,
            new_session.get("character_id"),
            session_id,
            new_id,
        )
        if server.WORKSPACE_AVAILABLE and server.workspace_manager:
            server.workspace_manager.get_or_create(
                new_id, new_session.get("type", "web"), new_session.get("name", "")
            )
        return jsonify({"success": True, "id": new_id, "session": new_session})

    @app.route("/api/sessions/<session_id>/bind-character", methods=["PUT"])
    def bind_character_to_session(session_id):
        """为会话绑定角色属性"""
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        data = request.json or {}
        old_name = session.get("sender_name", "")
        sender_name = (data.get("sender_name") or "").strip()
        if not sender_name:
            return jsonify({"error": "角色名称不能为空"}), 400

        session["sender_name"] = sender_name
        session["character_id"] = (data.get("character_id") or sender_name).strip()
        if "sender_avatar" in data:
            session["sender_avatar"] = data.get("sender_avatar") or ""
        if "sender_portrait" in data:
            session["sender_portrait"] = data.get("sender_portrait") or ""
        if "scenario" in data:
            scenario = data.get("scenario") or ""
            user_id = session.get("user_id", "")
            if user_id:
                scenario = scenario.replace("{{user}}", user_id)
            if sender_name:
                scenario = scenario.replace("{{char}}", sender_name)
            session["scenario"] = scenario

        # 更新系统提示词中的角色信息
        system_prompt = session.get("system_prompt", "")
        if system_prompt and sender_name:
            if old_name and old_name != sender_name:
                system_prompt = system_prompt.replace(f'你是角色 "{old_name}"', f'你是角色 "{sender_name}"')
        if "system_prompt" in data:
            system_prompt = data.get("system_prompt") or ""
        session["system_prompt"] = system_prompt

        # 更新 system 消息
        messages = session.get("messages", [])
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = system_prompt

        session_store.set_session(session_id, session)
        return jsonify({"success": True, "session": session})

    @app.route("/api/sessions/<session_id>/regenerate", methods=["POST"])
    def regenerate_message(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        data = request.get_json(silent=True) or {}
        message_id = data.get("message_id")
        messages = session.get("messages", [])
        message_index = _find_message_index(messages, message_id)
        if message_index < 0:
            return jsonify({"success": False, "error": "Message not found"}), 404

        target = messages[message_index]
        if target.get("role") != "assistant":
            return jsonify({"success": False, "error": "Only assistant messages can be regenerated"}), 400

        previous_user = next(
            (msg for msg in reversed(messages[:message_index]) if msg.get("role") == "user"),
            None,
        )
        if not previous_user or not previous_user.get("content"):
            return jsonify({"success": False, "error": "Previous user message not found"}), 400

        _ensure_mutable_session(session_id, session)
        original_messages = deepcopy(messages)
        trimmed_messages = deepcopy(messages[:message_index])
        previous_user_id = previous_user.get("id")
        for retained_msg in reversed(trimmed_messages):
            if str(retained_msg.get("id")) == str(previous_user_id):
                retained_msg.pop("thinking_cards", None)
                retained_msg.pop("todo_cards", None)
                retained_msg.pop("change_cards", None)
                break
        session_store.replace_messages(session_id, trimmed_messages)
        trigger = getattr(server, "_trigger_ai_response", None)
        if not trigger:
            session_store.replace_messages(session_id, original_messages)
            return jsonify({"success": False, "error": "AI trigger is unavailable"}), 500

        try:
            trigger(
                session_id,
                previous_user.get("content", ""),
                previous_user.get("sender", "web_user"),
                previous_user.get("attachments") or [],
                previous_user.get("id"),
            )
        except Exception as exc:
            session_store.replace_messages(session_id, original_messages)
            _log.error("Failed to trigger regenerated response: %s", exc, exc_info=True)
            return jsonify({"success": False, "error": "Failed to trigger AI response"}), 500
        return jsonify({
            "success": True,
            "session_id": session_id,
            "removed_count": len(messages) - message_index,
            "prompt_message_id": previous_user.get("id"),
        })
