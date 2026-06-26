"""会话 CRUD 核心路由（创建、读取、更新、删除、消息管理、聊天触发、停止生成）。"""

import uuid
from datetime import datetime

from flask import jsonify, request

from nbot.core import WebSessionStore
from nbot.core.prompt_format import format_skills_prompt
from nbot.web.persistence import is_web_visible_session
from nbot.web.sessions_db import get_session as get_session_from_db
from nbot.utils.logger import get_logger
from nbot.web.routes.chat.sessions_utils import (
    _get_base_dir,
    _normalize_tags,
    _skills_prompt_injection_enabled,
)

_log = get_logger(__name__)


def register_session_routes(app, server):
    session_store = WebSessionStore(
        server.sessions, save_callback=lambda: server._save_data("sessions")
    )

    def _get_web_session(session_id):
        session = session_store.get_session(session_id)
        if not session:
            session = get_session_from_db(server.data_dir, session_id)
        if not session or not is_web_visible_session(session_id, session):
            return None
        return session

    def _find_message_index(messages, message_id):
        if not message_id:
            return -1
        return next(
            (idx for idx, msg in enumerate(messages) if str(msg.get("id")) == str(message_id)),
            -1,
        )

    def _ensure_mutable_session(session_id, session):
        if not session_store.get_session(session_id):
            session_store.set_session(session_id, session)
        return session

    @app.route("/api/sessions")
    def get_sessions():
        # 导入公开会话管理模块
        from nbot.web.routes.public_sessions import _public_sessions, _generate_public_id

        current_time = server.time.time() if hasattr(server, "time") else None
        if current_time is None:
            import time

            current_time = time.time()
        if not hasattr(server, "_sessions_cache"):
            server._sessions_cache = []
            server._sessions_cache_time = 0

        sessions_data = dict(server.sessions)

        sessions = []
        for sid, session in sessions_data.items():
            if not is_web_visible_session(sid, session):
                continue
            archived = bool(session.get("archived"))
            # 检查会话是否已公开
            public_id = _generate_public_id(sid)
            is_public = public_id in _public_sessions

            sessions.append(
                {
                    "id": sid,
                    "name": session.get("name", f"会话 {sid[:8]}"),
                    "type": session.get("type", "web"),
                    "user_id": session.get("user_id"),
                    "qq_id": session.get("qq_id"),
                    "channel_id": session.get("channel_id"),
                    "created_at": session.get("created_at"),
                    "archived": archived,
                    "archived_at": session.get("archived_at") if archived else None,
                    "is_archive": bool(session.get("is_archive")),
                    "read_only": bool(session.get("read_only")),
                    "archive_session_id": session.get("archive_session_id"),
                    "source_session_id": session.get("source_session_id"),
                    "message_count": len(session.get("messages", [])),
                    "system_prompt": session.get("system_prompt", ""),
                    "character_id": session.get("character_id", ""),
                    "sender_name": session.get("sender_name", ""),
                    "sender_avatar": session.get("sender_avatar", ""),
                    "sender_portrait": session.get("sender_portrait", ""),
                    "scenario": session.get("scenario", ""),
                    "tags": _normalize_tags(session.get("tags", [])),
                    "favorite": bool(session.get("favorite")),
                    "pinned": bool(session.get("pinned")),
                    "is_public": is_public,
                    "character_runtime_timeline": session.get("character_runtime_timeline", []),
                }
            )

        server._sessions_cache = sessions
        server._sessions_cache_time = current_time
        return jsonify(sessions)

    @app.route("/api/sessions", methods=["POST"])
    def create_session():
        data = request.json
        session_id = str(uuid.uuid4())

        # 使用人格提示词作为默认系统提示词
        system_prompt = data.get(
            "system_prompt", server.personality.get("systemPrompt", "")
        )

        # 替换模板变量 {{user}} -> 当前用户名, {{char}} -> 角色名称
        user_id = data.get("user_id", "")
        # 优先使用请求中传入的角色名称（从角色卡创建时），否则使用当前角色的名称
        char_name = data.get("sender_name") or server.personality.get("name", "")
        if user_id:
            system_prompt = system_prompt.replace('{{user}}', user_id)
        if char_name:
            system_prompt = system_prompt.replace('{{char}}', char_name)

        # 获取角色信息
        sender_name = data.get("sender_name") or server.personality.get("name", "AI")
        character_id = data.get("character_id") or sender_name

        if any(key in data for key in ("state", "initial_state", "initialState", "relationship", "initialRelationship")):
            try:
                from nbot.character.models import CharacterProfile
                from nbot.character.repository import ProfileRepository

                profile_data = dict(getattr(server, "personality", {}) or {})
                profile_data.update(data)
                profile = CharacterProfile.from_personality_dict(profile_data)
                profile.id = str(character_id)
                if not profile.name:
                    profile.name = sender_name
                ProfileRepository(_get_base_dir(server)).save(profile)
            except Exception as exc:
                _log.warning(
                    "[CharacterRuntime] failed to sync session character profile %s: %s",
                    character_id,
                    exc,
                    exc_info=True,
                )

        # 记忆由 ai_pipeline.py 中的 PromptStack 动态注入，不在此处重复添加

        # 添加 Skills 到系统提示词
        if _skills_prompt_injection_enabled(server.settings):
            system_prompt += format_skills_prompt(server.skills_config)
            _log.info(f"已添加 {len([s for s in server.skills_config if s.get('enabled', True)])} 个技能到会话 {session_id[:8]}")
        else:
            _log.info(f"Skills prompt injection disabled for session {session_id[:8]}")

        # 获取角色其他信息（sender_name 已在前面定义）
        sender_avatar = data.get("sender_avatar") or server.personality.get("avatar", "")
        sender_portrait = data.get("sender_portrait") or server.personality.get("portrait", "")

        session = {
            "id": session_id,
            "name": data.get("name", f"新会话 {session_id[:8]}"),
            "type": data.get("type", "web"),
            "user_id": data.get("user_id"),
            "created_at": datetime.now().isoformat(),
            "archived": False,
            "archived_at": None,
            "messages": [{"role": "system", "content": system_prompt}],
            "system_prompt": system_prompt,
            "character_id": character_id,
            "sender_name": sender_name,
            "sender_avatar": sender_avatar,
            "sender_portrait": sender_portrait,
            "tags": _normalize_tags(data.get("tags", [])),
            "favorite": bool(data.get("favorite")),
            "pinned": bool(data.get("pinned")),
            "is_public": bool(data.get("is_public")),
            "character_runtime_timeline": [],
        }

        # 如果有开场白，添加为第一条 assistant 消息
        # 优先使用请求中指定的 first_message，否则使用当前角色的开场白
        first_message = data.get("first_message") or server.personality.get("firstMessage", "")
        if first_message:
            if user_id:
                first_message = first_message.replace('{{user}}', user_id)
            if char_name:
                first_message = first_message.replace('{{char}}', char_name)
            session["messages"].append({
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": first_message,
                "sender": sender_name,
                "timestamp": datetime.now().isoformat(),
            })

        # 获取背景设定，存储在会话中用于前端展示
        # 优先使用请求中传入的 scenario（从角色卡创建时），否则使用当前角色的 scenario
        scenario = data.get("scenario") or server.personality.get("scenario", "")
        if scenario:
            # 替换模板变量 {{user}} -> 当前用户名, {{char}} -> 角色名称
            if user_id:
                scenario = scenario.replace('{{user}}', user_id)
            if char_name:
                scenario = scenario.replace('{{char}}', char_name)
            session["scenario"] = scenario
        if not is_web_visible_session(session_id, session):
            return jsonify({"error": "Invalid session type"}), 400

        session_store.set_session(session_id, session)

        # 创建对应的工作区
        if server.WORKSPACE_AVAILABLE:
            server.workspace_manager.get_or_create(
                session_id, session.get("type", "web"), session.get("name", "")
            )

        return jsonify({"id": session_id, "session": session})

    @app.route("/api/sessions/<session_id>")
    def get_session(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        session["message_count"] = len(session.get("messages", []))
        return jsonify(session)

    @app.route("/api/sessions/<session_id>/debug")
    def debug_session(session_id):
        """调试 API：查看会话详细信息"""
        raw_session = session_store.get_session(session_id)
        db_session = get_session_from_db(server.data_dir, session_id)

        result = {
            "session_id": session_id,
            "in_memory": raw_session is not None,
            "in_db": db_session is not None,
            "is_visible": False,
        }

        if raw_session:
            result["memory_session"] = {
                "type": raw_session.get("type"),
                "channel_id": raw_session.get("channel_id"),
                "message_count": len(raw_session.get("messages", [])),
                "first_message_source": raw_session.get("messages", [{}])[0].get("source") if raw_session.get("messages") else None,
            }
            result["is_visible"] = is_web_visible_session(session_id, raw_session)

        if db_session:
            result["db_session"] = {
                "type": db_session.get("type"),
                "channel_id": db_session.get("channel_id"),
            }

        return jsonify(result)

    @app.route("/api/sessions/<session_id>", methods=["PUT"])
    def update_session(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        data = request.json
        session["name"] = data.get("name", session["name"])
        if "tags" in data:
            session["tags"] = _normalize_tags(data.get("tags"))
        if "favorite" in data:
            session["favorite"] = bool(data.get("favorite"))
        if "pinned" in data:
            session["pinned"] = bool(data.get("pinned"))

        new_prompt = data.get("system_prompt", session.get("system_prompt", ""))
        if new_prompt != session.get("system_prompt", ""):
            session["system_prompt"] = new_prompt
            if session["messages"] and session["messages"][0].get("role") == "system":
                session["messages"][0]["content"] = new_prompt
            else:
                session["messages"].insert(0, {"role": "system", "content": new_prompt})

        session_store.set_session(session_id, session)
        return jsonify({"success": True, "session": session})

    @app.route("/api/sessions/<session_id>", methods=["DELETE"])
    def delete_session(session_id):
        _log.info(f"[DeleteSession] 尝试删除会话: {session_id}")
        _log.info(f"[DeleteSession] 删除前会话列表: {list(server.sessions.keys())}")
        if not _get_web_session(session_id):
            _log.warning(f"[DeleteSession] 会话不存在或不可见: {session_id}")
            return jsonify({"error": "Session not found"}), 404
        if session_store.delete_session(session_id):
            _log.info(f"[DeleteSession] 会话已删除: {session_id}")
            _log.info(f"[DeleteSession] 删除后会话列表: {list(server.sessions.keys())}")
            if server.WORKSPACE_AVAILABLE and server.workspace_manager:
                server.workspace_manager.delete_workspace(session_id)
            server.log_message("info", f"删除了会话 {session_id[:8]}...", important=True)
            return jsonify({"success": True})
        _log.warning(f"[DeleteSession] 删除会话失败: {session_id}")
        return jsonify({"error": "Session not found"}), 404

    @app.route("/api/sessions/<session_id>/messages", methods=["GET"])
    def get_messages(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        messages = session.get("messages", [])
        display_messages = [m for m in messages if m.get("role") != "system"]
        return jsonify(display_messages)

    @app.route("/api/sessions/<session_id>/messages", methods=["POST"])
    def add_message(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        data = request.json
        message = {
            "id": str(uuid.uuid4()),
            "role": data.get("role", "user"),
            "content": data.get("content", ""),
            "timestamp": datetime.now().isoformat(),
            "sender": data.get("sender", "web_user"),
        }

        session_store.append_message(session_id, message)
        return jsonify(message)

    @app.route("/api/sessions/<session_id>/messages/<message_id>", methods=["PUT"])
    def update_message(session_id, message_id):
        """更新单条消息的内容，支持截断后续消息（用于用户编辑重发等场景）"""
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        data = request.json
        messages = session.get("messages", [])

        target_idx = None
        for idx, msg in enumerate(messages):
            if str(msg.get("id", "")) == str(message_id):
                target_idx = idx
                break

        if target_idx is None:
            return jsonify({"error": "Message not found"}), 404

        if "content" in data:
            messages[target_idx]["content"] = data["content"]

        # 截断该消息之后的所有消息
        if data.get("truncate_after"):
            messages[:] = messages[: target_idx + 1]

        session_store.set_session(session_id, session)
        return jsonify({"success": True, "message": messages[target_idx]})

    @app.route("/api/sessions/<session_id>/messages", methods=["DELETE"])
    def clear_messages(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        system_msg = None
        if session["messages"] and session["messages"][0].get("role") == "system":
            system_msg = session["messages"][0]

        session_store.replace_messages(session_id, [system_msg] if system_msg else [])
        server.log_message("info", f"清空了会话 {session_id[:8]} 的消息", important=True)
        return jsonify({"success": True})

    @app.route("/api/sessions/<session_id>/chat", methods=["POST"])
    def chat_with_ai(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        data = request.json or {}
        user_content = (data.get("content") or "").strip()
        if not user_content:
            return jsonify({"error": "Content is required"}), 400

        user_message = {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": user_content,
            "timestamp": datetime.now().isoformat(),
            "sender": data.get("sender", "web_user"),
            "source": "web",
            "session_id": session_id,
        }

        session_store.append_message(session_id, user_message)

        server._trigger_ai_response(
            session_id,
            user_content,
            user_message["sender"],
            data.get("attachments", []),
            user_message["id"],
        )

        return jsonify({"success": True, "user_message": user_message})

    @app.route("/api/stop", methods=["POST"])
    def stop_generation():
        data = request.json or {}
        session_id = data.get("session_id")
        adapter = getattr(server, "web_channel_adapter", None)
        capabilities = adapter.get_capabilities() if adapter else None

        if not session_id:
            return jsonify({"error": "session_id is required"}), 400

        if capabilities is not None and not capabilities.supports_stop:
            return jsonify({"success": False, "error": "Stop is not supported for this channel"}), 400

        if session_id in server.stop_events:
            server.stop_events[session_id].set()
            _log.info(f"[Stop] stop requested for session: {session_id}")
            return jsonify({"success": True, "message": "已请求停止生成"})

        return jsonify(
            {"success": False, "error": "No active generation for this session"}
        ), 404

    # 注册子路由组
    from nbot.web.routes.chat.sessions_archive import register_archive_routes
    from nbot.web.routes.chat.sessions_import_export import register_import_export_routes

    register_archive_routes(app, server, session_store, _get_web_session)
    register_import_export_routes(app, server, session_store, _get_web_session, _find_message_index, _ensure_mutable_session)
