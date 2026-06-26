"""
管理员命令辅助函数

从 handlers_admin.py 提取出的辅助函数，供命令处理器使用。
"""

import os
import json
from datetime import datetime


def register_admin_helpers(deps):
    """注册所有管理员/session 命令所需的辅助函数。

    Args:
        deps: 依赖字典

    Returns:
        dict[str, callable]: 辅助函数名到函数的映射
    """
    log = deps["log"]
    project_root = deps["project_root"]
    user_messages = deps["user_messages"]
    group_messages = deps["group_messages"]
    delete_session_workspace = deps["delete_session_workspace"]
    get_qq_session_id = deps["get_qq_session_id"]
    workspace_available = deps["workspace_available"]
    bot = deps["bot"]

    def load_character_options():
        characters = []
        seen = set()

        def add_character(data):
            if not isinstance(data, dict):
                return
            name = str(data.get("name") or "").strip()
            character_id = str(data.get("id") or name).strip()
            if not name and not character_id:
                return
            key = character_id or name
            if key in seen:
                return
            seen.add(key)
            item = dict(data)
            item["id"] = character_id or name
            item["name"] = name or character_id
            characters.append(item)

        base_dir = project_root()

        try:
            from nbot.character.repository import ProfileRepository

            for profile in ProfileRepository(base_dir).list_all():
                add_character(profile.to_personality_dict())
        except Exception as e:
            log.warning(f"Load character profiles failed: {e}")

        for file_path in (
            os.path.join(base_dir, "resources", "prompts", "personality.json"),
            os.path.join(base_dir, "data", "web", "custom_personality_presets.json"),
        ):
            try:
                if not os.path.exists(file_path):
                    continue
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        add_character(item)
                elif isinstance(data, dict):
                    add_character(data)
            except Exception as e:
                log.warning(f"Load character file failed: {file_path}, {e}")

        return characters

    def compile_character_prompt(character):
        if character.get("systemPrompt"):
            return str(character.get("systemPrompt") or "")
        from nbot.character.compiler import compile_personality_prompt
        return compile_personality_prompt(character)

    def resolve_character_session(msg, is_group):
        if is_group and getattr(msg, "group_id", None):
            return "group", str(msg.group_id)
        if not is_group and getattr(msg, "user_id", None):
            return "user", str(msg.user_id)

        session_id = (
            getattr(msg, "session_id", None)
            or getattr(msg, "chat_id", None)
            or getattr(msg, "conversation_id", None)
        )
        if session_id:
            return "channel", str(session_id)

        if getattr(msg, "user_id", None):
            return "user", str(msg.user_id)
        return "", ""

    def get_session_prompt(scope, target_id, msg=None):
        if scope == "channel":
            session_id = getattr(msg, "session_id", None) or target_id
            server = getattr(msg, "server", None)
            session = None
            if server and hasattr(server, "sessions"):
                session = server.sessions.get(str(session_id))
            if session:
                prompt = session.get("system_prompt") or session.get("prompt") or ""
                if prompt:
                    return str(prompt)
                for item in session.get("messages", []):
                    if item.get("role") == "system":
                        return str(item.get("content") or "")

        prefix = "group" if scope == "group" else "user" if scope == "user" else "channel"
        prompt_file = os.path.join(
            project_root(),
            "resources",
            "prompts",
            prefix,
            f"{prefix}_{target_id}.txt",
        )
        try:
            if os.path.exists(prompt_file):
                with open(prompt_file, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            log.warning(f"Load session prompt failed: {e}")
        return ""

    def get_active_character():
        personality_file = os.path.join(project_root(), "resources", "prompts", "personality.json")
        try:
            if os.path.exists(personality_file):
                with open(personality_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            log.warning(f"Load active character failed: {e}")
        return {}

    def find_session_character(characters, scope, target_id, msg=None):
        current_prompt = get_session_prompt(scope, target_id, msg).strip()
        if current_prompt:
            for character in characters:
                try:
                    if compile_character_prompt(character).strip() == current_prompt:
                        return character
                except Exception:
                    continue
        return get_active_character()

    def find_character(characters, arg):
        if not arg:
            return None
        try:
            index = int(arg)
            if 1 <= index <= len(characters):
                return characters[index - 1]
        except ValueError:
            pass

        needle = arg.casefold()
        for character in characters:
            if needle in {
                str(character.get("id") or "").casefold(),
                str(character.get("name") or "").casefold(),
            }:
                return character

        matches = [
            c for c in characters
            if needle in str(c.get("id") or "").casefold()
            or needle in str(c.get("name") or "").casefold()
        ]
        return matches[0] if len(matches) == 1 else None

    def save_qq_histories():
        os.makedirs("saved_message", exist_ok=True)
        with open("saved_message/user_messages.json", "w", encoding="utf-8") as f:
            json.dump(user_messages, f, ensure_ascii=False, indent=4)
        with open("saved_message/group_messages.json", "w", encoding="utf-8") as f:
            json.dump(group_messages, f, ensure_ascii=False, indent=4)

    def web_data_dir():
        return os.path.join(project_root(), "data", "web")

    def resume_bindings_path():
        return os.path.join(web_data_dir(), "qq_web_session_bindings.json")

    def load_resume_bindings():
        path = resume_bindings_path()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            log.warning(f"Load resume bindings failed: {e}")
        return {}

    def save_resume_bindings(bindings):
        os.makedirs(web_data_dir(), exist_ok=True)
        with open(resume_bindings_path(), "w", encoding="utf-8") as f:
            json.dump(bindings, f, ensure_ascii=False, indent=2)

    async def reply_current_channel(msg, is_group, text):
        if is_group:
            await msg.reply(text=text)
        else:
            await bot.api.post_private_msg(msg.user_id, text=text)

    def set_current_session_character(msg, is_group, character):
        base_dir = project_root()
        prompt = compile_character_prompt(dict(character))
        scope, target_id = resolve_character_session(msg, is_group)
        if not scope or not target_id:
            raise ValueError("无法识别当前会话")

        prefix = "group" if scope == "group" else "user" if scope == "user" else "channel"
        prompt_dir = os.path.join(base_dir, "resources", "prompts", prefix)
        prompt_file = os.path.join(prompt_dir, f"{prefix}_{target_id}.txt")

        os.makedirs(prompt_dir, exist_ok=True)
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)

        if scope in {"group", "user"}:
            messages = group_messages if scope == "group" else user_messages
            messages[target_id] = [{"role": "system", "content": prompt}]
            save_qq_histories()

            if scope == "group":
                delete_session_workspace(
                    group_id=target_id,
                    group_user_id=str(getattr(msg, "user_id", "")),
                )
            else:
                delete_session_workspace(user_id=target_id)
        else:
            server = getattr(msg, "server", None)
            session_id = getattr(msg, "session_id", None) or target_id
            if server and hasattr(server, "sessions"):
                from nbot.core.session_store import WebSessionStore

                session_store = WebSessionStore(
                    server.sessions,
                    save_callback=lambda: server._save_data("sessions"),
                )
                session = session_store.get_session(str(session_id))
                if session is not None:
                    system_msg = {"role": "system", "content": prompt}
                    session["system_prompt"] = prompt
                    session["character_id"] = character.get("id") or character.get("name") or ""
                    session["sender_name"] = character.get("name") or "AI"
                    session["sender_avatar"] = character.get("avatar", "")
                    session["sender_portrait"] = character.get("portrait", "")
                    session_store.replace_messages(str(session_id), [system_msg])
                    session_store.set_session(str(session_id), session)
            if workspace_available:
                try:
                    from nbot.core.workspace import workspace_manager

                    workspace_manager.delete_workspace(str(session_id))
                except Exception as e:
                    log.debug(f"Delete channel workspace skipped: {e}")

        try:
            from nbot.core.prompt import prompt_manager

            prompt_manager._prompt_cache = {}
        except Exception:
            pass

    def current_qq_session_info(msg, is_group):
        if is_group:
            group_id = str(getattr(msg, "group_id", "") or "")
            user_id = str(getattr(msg, "user_id", "") or "")
            history_key = f"{group_id}_{user_id}" if group_id and user_id else group_id
            session_id = get_qq_session_id(group_id=group_id, group_user_id=user_id)
            return {
                "store": group_messages,
                "history_key": history_key,
                "session_id": session_id,
                "user_id": None,
                "group_id": group_id,
                "group_user_id": user_id,
                "label": f"群 {group_id} / 用户 {user_id}" if user_id else f"群 {group_id}",
            }

        user_id = str(getattr(msg, "user_id", "") or "")
        return {
            "store": user_messages,
            "history_key": user_id,
            "session_id": get_qq_session_id(user_id=user_id),
            "user_id": user_id,
            "group_id": None,
            "group_user_id": None,
            "label": f"私聊 {user_id}",
        }

    def copy_chat_messages(messages):
        return [dict(message) for message in messages or [] if isinstance(message, dict)]

    def session_system_prompt(session, messages):
        prompt = str((session or {}).get("system_prompt") or "")
        if prompt:
            return prompt
        for message in messages or []:
            if isinstance(message, dict) and message.get("role") == "system":
                return str(message.get("content") or "")
        return ""

    def session_matches_character(session, active):
        active_ids = {
            str((active or {}).get("id") or "").strip().casefold(),
            str((active or {}).get("name") or "").strip().casefold(),
        }
        active_ids.discard("")
        if not active_ids:
            return True
        session_ids = {
            str((session or {}).get("character_id") or "").strip().casefold(),
            str((session or {}).get("sender_name") or "").strip().casefold(),
        }
        session_ids.discard("")
        return bool(active_ids & session_ids)

    def load_web_sessions():
        from nbot.web.sessions_db import load_sessions as load_sessions_from_db

        sessions = load_sessions_from_db(web_data_dir())
        return sessions if isinstance(sessions, dict) else {}

    def save_web_sessions(sessions):
        from nbot.web.sessions_db import save_sessions as save_sessions_to_db

        save_sessions_to_db(web_data_dir(), sessions)

    def current_character(msg, is_group):
        characters = load_character_options()
        scope, target_id = resolve_character_session(msg, is_group)
        return find_session_character(characters, scope, target_id, msg)

    def candidate_resume_sessions(msg, is_group):
        active = current_character(msg, is_group)
        sessions = load_web_sessions()
        candidates = []
        for session_id, session in sessions.items():
            if not isinstance(session, dict):
                continue
            session_type = str(session.get("type") or "web").lower()
            if session_type.startswith("qq_") or session_type == "cli":
                continue
            if session.get("archived"):
                continue
            if not session_matches_character(session, active):
                continue
            messages = session.get("messages") if isinstance(session.get("messages"), list) else []
            candidates.append((session_id, session, len(messages)))

        candidates.sort(
            key=lambda item: str(item[1].get("updated_at") or item[1].get("created_at") or ""),
            reverse=True,
        )
        return candidates

    def find_resume_session(candidates, arg):
        arg = (arg or "").strip()
        if not arg:
            return None
        try:
            index = int(arg)
            if 1 <= index <= len(candidates):
                return candidates[index - 1]
        except ValueError:
            pass

        needle = arg.casefold()
        matches = []
        for item in candidates:
            session_id, session, _ = item
            name = str(session.get("name") or "")
            if needle == str(session_id).casefold() or needle == name.casefold():
                return item
            if needle in str(session_id).casefold() or needle in name.casefold():
                matches.append(item)
        return matches[0] if len(matches) == 1 else None

    def format_resume_session_list(candidates, active):
        active_name = (active or {}).get("name") or (active or {}).get("id") or "当前角色"
        lines = [f"可载入的 Web 会话（角色：{active_name}）："]
        if not candidates:
            lines.append("没有找到匹配当前角色的 Web 会话。")
            return "\n".join(lines)
        for index, (session_id, session, message_count) in enumerate(candidates[:20], 1):
            name = session.get("name") or session_id[:8]
            updated = session.get("updated_at") or session.get("created_at") or ""
            suffix = f" - {updated[:16]}" if updated else ""
            lines.append(f"{index}. {name} [{session_id[:8]}] {message_count} 条{suffix}")
        lines.append("")
        lines.append("用法：/resume <编号|会话ID|名称>")
        return "\n".join(lines)

    return {
        "load_character_options": load_character_options,
        "compile_character_prompt": compile_character_prompt,
        "resolve_character_session": resolve_character_session,
        "get_session_prompt": get_session_prompt,
        "get_active_character": get_active_character,
        "find_session_character": find_session_character,
        "find_character": find_character,
        "save_qq_histories": save_qq_histories,
        "web_data_dir": web_data_dir,
        "resume_bindings_path": resume_bindings_path,
        "load_resume_bindings": load_resume_bindings,
        "save_resume_bindings": save_resume_bindings,
        "reply_current_channel": reply_current_channel,
        "set_current_session_character": set_current_session_character,
        "current_qq_session_info": current_qq_session_info,
        "copy_chat_messages": copy_chat_messages,
        "session_system_prompt": session_system_prompt,
        "session_matches_character": session_matches_character,
        "load_web_sessions": load_web_sessions,
        "save_web_sessions": save_web_sessions,
        "current_character": current_character,
        "candidate_resume_sessions": candidate_resume_sessions,
        "find_resume_session": find_resume_session,
        "format_resume_session_list": format_resume_session_list,
    }
