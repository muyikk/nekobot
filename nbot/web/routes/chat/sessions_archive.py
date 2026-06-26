"""会话归档、恢复、上下文压缩与 AI 总结路由。"""

import time as _time_module
from datetime import datetime

from flask import jsonify, request

from nbot.utils.logger import get_logger

_log = get_logger(__name__)


def register_archive_routes(app, server, session_store, _get_web_session):
    """注册归档、恢复、压缩与 AI 总结相关的路由。"""

    def _get_or_create_archive_session(source_session_id, source_session):
        archive_id = source_session.get("archive_session_id")
        if archive_id:
            archive = session_store.get_session(archive_id)
            if archive:
                return archive
        import uuid

        now = datetime.now().isoformat()
        base_name = source_session.get("name", f"会话 {source_session_id[:8]}")
        archive_id = str(uuid.uuid4())
        sender_name = source_session.get("sender_name", "")
        archive = {
            "id": archive_id,
            "name": f"📦 {base_name} - 归档",
            "type": "web",
            "created_at": now,
            "archived": True,
            "archived_at": now,
            "is_archive": True,
            "read_only": True,
            "source_session_id": source_session_id,
            "messages": [],
            "system_prompt": "",
            "character_id": source_session.get("character_id") or sender_name,
            "sender_name": sender_name,
            "sender_avatar": source_session.get("sender_avatar", ""),
            "sender_portrait": source_session.get("sender_portrait", ""),
            "scenario": source_session.get("scenario", ""),
        }
        session_store.set_session(archive_id, archive)
        source_session["archive_session_id"] = archive_id
        session_store.set_session(source_session_id, source_session)
        return archive

    def _append_to_archive(archive_session, messages_to_add, label=""):
        existing = archive_session.get("messages", [])
        if label:
            existing.append({
                "id": f"archive_divider_{int(_time_module.time())}",
                "role": "system",
                "content": f"━━━ {label} ━━━",
                "timestamp": datetime.now().isoformat(),
            })
        for msg in messages_to_add:
            if msg.get("role") == "system" and msg.get("id", "").startswith("summary_"):
                continue
            existing.append(msg)
        archive_session["messages"] = existing
        session_store.set_session(archive_session["id"], archive_session)

    @app.route("/api/sessions/<session_id>/archive", methods=["POST"])
    def archive_session(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        messages = session.get("messages", [])
        non_system_msgs = [m for m in messages if m.get("role") != "system"]
        if non_system_msgs:
            archive = _get_or_create_archive_session(session_id, session)
            archive_label = f"完整归档于 {datetime.now().strftime('%Y-%m-%d %H:%M')} ({len(non_system_msgs)} 条消息)"
            _append_to_archive(archive, non_system_msgs, label=archive_label)

        session["archived"] = True
        session["archived_at"] = datetime.now().isoformat()
        session_store.set_session(session_id, session)

        archive_id = session.get("archive_session_id")
        return jsonify({
            "success": True,
            "session": session,
            "archive_session_id": archive_id,
        })

    @app.route("/api/sessions/<session_id>/restore", methods=["POST"])
    def restore_session(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        session["archived"] = False
        session["archived_at"] = None
        session_store.set_session(session_id, session)
        return jsonify({"success": True, "session": session})

    @app.route("/api/sessions/<session_id>/compress", methods=["POST"])
    def compress_context(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        messages = session.get("messages", [])
        # 已经压缩过的会话允许更少消息即可再次压缩，确保归档可以持续追加
        has_been_compressed = any(
            m.get("role") == "system" and m.get("id", "").startswith("summary_")
            for m in messages
        )
        min_messages = 5 if has_been_compressed else 10
        if len(messages) < min_messages:
            return jsonify({"success": False, "error": "消息数量不足，无需压缩"}), 400

        system_msg = None
        if messages and messages[0].get("role") == "system":
            system_msg = messages[0]

        keep_count = min(3 if has_been_compressed else 5, len(messages) - 2)
        recent_messages = messages[-keep_count:] if messages else []

        compress_start = 1 if system_msg else 0
        compress_end = len(messages) - keep_count

        if compress_end <= compress_start:
            return jsonify(
                {"success": False, "error": "没有足够的早期消息需要压缩"}
            ), 400

        messages_to_compress = messages[compress_start:compress_end]
        if not messages_to_compress:
            return jsonify({"success": False, "error": "没有消息需要压缩"}), 400

        conversation_text = "\n".join(
            [
                f"[{msg.get('role', 'user')}]: {msg.get('content', '')[:500]}"
                for msg in messages_to_compress
                if msg.get("content")
            ]
        )

        summary_prompt = f"""请简洁地总结以下对话的主要内容，保留关键信息和结论：

{conversation_text}

请用50-100字总结："""

        try:
            if not server.ai_client:
                return jsonify(
                    {"success": False, "error": "AI服务不可用，请先配置AI"}
                ), 503

            _log.info(f"[Compress] 开始压缩会话 {session_id[:8]}... 的上下文")

            response = server.ai_client.chat_completion(
                model=server.ai_model,
                messages=[{"role": "user", "content": summary_prompt}],
                stream=False,
            )

            summary = response.choices[0].message.content.strip()

            archive = _get_or_create_archive_session(session_id, session)
            compress_label = f"压缩于 {datetime.now().strftime('%Y-%m-%d %H:%M')} ({len(messages_to_compress)} 条消息)"
            _append_to_archive(archive, messages_to_compress, label=compress_label)

            new_messages = [system_msg] if system_msg else []
            summary_msg = {
                "id": f"summary_{int(_time_module.time())}",
                "role": "system",
                "content": f"【对话总结】{summary}",
                "timestamp": _time_module.time(),
            }
            new_messages.append(summary_msg)
            new_messages.extend(recent_messages)

            session_store.replace_messages(session_id, new_messages)

            _log.info(
                f"[Compress] 上下文压缩完成: {session_id[:8]}... ({len(messages_to_compress)} 条消息被压缩，已归档到 {archive['id'][:8]}...)"
            )

            return jsonify(
                {
                    "success": True,
                    "compressed_count": len(messages_to_compress),
                    "summary": summary[:200],
                    "archive_session_id": archive["id"],
                }
            )
        except Exception as e:
            _log.error(f"[Compress] 压缩上下文失败: {e}", exc_info=True)
            return jsonify({"success": False, "error": f"压缩失败: {str(e)}"}), 500

    @app.route("/api/sessions/<session_id>/ai-summary", methods=["POST"])
    def ai_summary_session(session_id):
        session = _get_web_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404

        messages = session.get("messages", [])
        non_system = [m for m in messages if m.get("role") != "system"]
        if not non_system:
            return jsonify({"success": False, "error": "没有可总结的对话内容"}), 400

        character_name = session.get("character_id") or session.get("sender_name", "")
        user_name = session.get("user_id", "")

        conversation_text = "\n".join(
            [
                f"[{msg.get('role', 'user')}]: {msg.get('content', '')[:800]}"
                for msg in non_system
                if msg.get("content")
            ]
        )

        summary_prompt = f"""请对以下完整对话进行深度总结，提取出值得长期记住的关键信息。

角色名: {character_name or '未知'}
用户名: {user_name or '用户'}

对话内容:
{conversation_text}

请按以下格式输出总结：

## 对话总结
（用2-3段话概括对话的主要内容和走向）

## 关键信息
（列出3-5条最值得记住的关键事实、关系变化、重要决定等）

## 角色记忆
（提取2-3条与角色"{character_name}"直接相关的、值得保存为长期记忆的信息，每条包含标题和内容）"""

        try:
            if not server.ai_client:
                return jsonify({"success": False, "error": "AI服务不可用"}), 503

            _log.info(f"[AISummary] 开始总结会话 {session_id[:8]}...")

            response = server.ai_client.chat_completion(
                model=server.ai_model,
                messages=[{"role": "user", "content": summary_prompt}],
                stream=False,
            )

            summary_text = response.choices[0].message.content.strip()

            saved_memories = 0
            if character_name and server.PROMPT_MANAGER_AVAILABLE and server.prompt_manager:
                memory_prompt = f"""从以下对话总结中，提取与角色"{character_name}"直接相关的、值得长期保存的记忆。
每条记忆必须与角色"{character_name}"有关，不要提取通用信息。
返回JSON数组，每项包含 title、content、type("long"/"short") 字段。如果没有值得保存的记忆，返回[]。

对话总结:
{summary_text}"""
                try:
                    mem_response = server.ai_client.chat_completion(
                        model=server.ai_model,
                        messages=[{"role": "user", "content": memory_prompt}],
                        stream=False,
                    )
                    import json

                    mem_text = mem_response.choices[0].message.content.strip()
                    json_start = mem_text.find("[")
                    json_end = mem_text.rfind("]") + 1
                    if json_start >= 0 and json_end > json_start:
                        mem_items = json.loads(mem_text[json_start:json_end])
                        for item in mem_items[:3]:
                            title = str(item.get("title", "")).strip()
                            content = str(item.get("content", "")).strip()
                            if not title or not content:
                                continue
                            if server.prompt_manager.add_memory(
                                title, content,
                                session_id,
                                None,
                                item.get("type", "long"),
                                7,
                                character_name,
                            ):
                                saved_memories += 1
                        if saved_memories:
                            server.memories = server.prompt_manager.get_memories()
                            server._save_data("memories")
                except Exception as mem_exc:
                    _log.warning(f"[AISummary] 保存记忆失败: {mem_exc}")

            _log.info(f"[AISummary] 总结完成: {session_id[:8]}... (保存了 {saved_memories} 条记忆)")

            return jsonify({
                "success": True,
                "summary": summary_text,
                "saved_memories": saved_memories,
            })
        except Exception as e:
            _log.error(f"[AISummary] 总结失败: {e}", exc_info=True)
            return jsonify({"success": False, "error": f"总结失败: {str(e)}"}), 500
