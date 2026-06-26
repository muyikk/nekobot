"""
管理员命令处理器

注册 set_prompt、del_prompt、get_prompt、new_session、character_switch、
model_switch、resume_session、push_session 等命令。
"""

import os
import json
from datetime import datetime

from nbot.commands.ai.handlers_admin_helpers import register_admin_helpers


def register_admin_handlers(reg, deps):
    """注册所有管理员/session 命令处理器。

    Args:
        reg: register_command 函数
        deps: 依赖字典
    """
    bot = deps["bot"]
    log = deps["log"]
    admin = deps["admin"]
    project_root = deps["project_root"]
    read_secure_json = deps["read_secure_json"]
    write_secure_json = deps["write_secure_json"]
    workspace_available = deps["workspace_available"]
    switch = deps["switch"]
    normalize_file_path = deps["normalize_file_path"]
    load_address = deps["load_address"]
    group_messages = deps["group_messages"]
    user_messages = deps["user_messages"]
    delete_session_workspace = deps["delete_session_workspace"]
    get_qq_session_id = deps["get_qq_session_id"]

    h = register_admin_helpers(deps)

    # === 命令注册 ===

    @reg(
        "/set_prompt",
        "/sp",
        help_text="/set_prompt 或 /sp <提示词> -> 设定当前会话提示词(群聊仅admin)",
        category="2",
    )
    async def handle_set_prompt(msg, is_group=True):
        if (str(msg.user_id) not in admin) and is_group:
            await msg.reply(text="你没有权限喔~")
            return

        raw = getattr(msg, "raw_message", "") or ""
        if raw.startswith("/set_prompt"):
            prompt_content = raw[len("/set_prompt"):].strip()
        else:
            prompt_content = raw[len("/sp"):].strip()

        id_str = str(msg.group_id if is_group else msg.user_id)
        prefix = "group" if is_group else "user"
        os.makedirs(f"resources/prompts/{prefix}", exist_ok=True)
        with open(f"resources/prompts/{prefix}/{prefix}_{id_str}.txt", "w", encoding="utf-8") as file:
            file.write(prompt_content)

        messages = group_messages if is_group else user_messages
        messages[id_str] = [{"role": "system", "content": prompt_content}]
        h["save_qq_histories"]()

        reply_text = "群组提示词已更新，对话记录已清除喔~" if is_group else "个人提示词已更新，对话记录已清除喔~"
        await h["reply_current_channel"](msg, is_group, reply_text)

    @reg(
        "/del_prompt",
        "/dp",
        help_text="/del_prompt 或 /dp -> 删除当前会话提示词(群聊仅admin)",
        category="2",
    )
    async def handle_del_prompt(msg, is_group=True):
        if (str(msg.user_id) not in admin) and is_group:
            await msg.reply(text="你没有权限喔~")
            return

        id_str = str(msg.group_id if is_group else msg.user_id)
        prefix = "group" if is_group else "user"
        messages = group_messages if is_group else user_messages
        prompt_path = f"resources/prompts/{prefix}/{prefix}_{id_str}.txt"

        messages.pop(id_str, None)
        try:
            os.remove(prompt_path)
        except FileNotFoundError:
            await h["reply_current_channel"](msg, is_group, "没有可以删除的提示词喔~")
            return

        try:
            from nbot.core.prompt import prompt_manager

            kwargs = {"group_id": id_str} if is_group else {"user_id": id_str}
            prompt = prompt_manager.load_base_prompt(**kwargs)
            messages[id_str] = [{"role": "system", "content": prompt}]
            h["save_qq_histories"]()
        except Exception as e:
            log.warning(f"Reload base prompt failed: {e}")

        await h["reply_current_channel"](msg, is_group, "提示词已删除喔~")

    @reg(
        "/get_prompt",
        "/gp",
        help_text="/get_prompt 或 /gp -> 获取当前会话提示词(群聊仅admin)",
        category="2",
    )
    async def handle_get_prompt(msg, is_group=True):
        if (str(msg.user_id) not in admin) and is_group:
            await msg.reply(text="你没有权限喔~")
            return

        id_str = str(msg.group_id if is_group else msg.user_id)
        prefix = "group" if is_group else "user"
        try:
            with open(f"resources/prompts/{prefix}/{prefix}_{id_str}.txt", "r", encoding="utf-8") as file:
                prompt = file.read()
        except FileNotFoundError:
            prompt = "没有找到提示词喔~"
        await h["reply_current_channel"](msg, is_group, prompt)

    @reg("/new", help_text="/new -> 创建新的对话会话 (清空当前对话历史)(admin)", category="2", admin_show=True)
    async def handle_new_session(msg, is_group=True):
        if (str(msg.user_id) not in admin) and is_group:
            await msg.reply(text="你没有权限喔~")
            return

        if is_group:
            group_id = getattr(msg, "group_id", None)
            chat_id = getattr(msg, "chat_id", None)
            if group_id:
                gid = str(group_id)
                group_messages.pop(gid, None)
                h["save_qq_histories"]()
                delete_session_workspace(group_id=gid, group_user_id=str(msg.user_id))
            elif chat_id:
                session_id = getattr(msg, "session_id", None)
                server = getattr(msg, "server", None)
                if session_id and server and hasattr(server, "sessions"):
                    from nbot.core.session_store import WebSessionStore

                    session_store = WebSessionStore(
                        server.sessions,
                        save_callback=lambda: server._save_data("sessions"),
                    )
                    session = session_store.get_session(session_id)
                    if session:
                        system_msg = next(
                            (m for m in session.get("messages", []) if m.get("role") == "system"),
                            None,
                        )
                        session_store.replace_messages(session_id, [system_msg] if system_msg else [])
                        session["updated_at"] = datetime.now().isoformat()
                    delete_session_workspace(user_id=str(msg.user_id))
                else:
                    await msg.reply(text="当前平台不支持会话重置喔~")
                    return
            else:
                await msg.reply(text="当前平台不支持会话重置喔~")
                return
            await msg.reply(text="已创建新会话喔，之前的对话历史已清空")
            return

        user_id = str(msg.user_id)
        user_messages.pop(user_id, None)
        h["save_qq_histories"]()
        delete_session_workspace(user_id=user_id)
        await bot.api.post_private_msg(msg.user_id, text="已创建新会话喔，之前的对话历史已清空")

    @reg(
        "/character",
        "/char",
        help_text="/character -> 查看/切换角色(admin)\n/character list -> 列出角色\n/character <编号|id|名称> -> 切换角色",
        category="2",
        admin_show=True,
    )
    async def handle_character_switch(msg, is_group=True):
        if (str(msg.user_id) not in admin) and is_group:
            await msg.reply(text="你没有权限喔~")
            return

        raw = (getattr(msg, "raw_message", "") or "").strip()
        parts = raw.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""

        characters = h["load_character_options"]()
        session_scope, session_target_id = h["resolve_character_session"](msg, is_group)
        active = h["find_session_character"](characters, session_scope, session_target_id, msg)
        active_id = str(active.get("id") or active.get("name") or "")
        active_name = str(active.get("name") or active_id or "未设置")

        if not characters:
            await h["reply_current_channel"](msg, is_group, "还没有可切换的角色。请先在 Web 角色卡里创建或导入角色。")
            return

        if not arg or arg.lower() == "list":
            lines = [f"当前角色：{active_name}", "", "可用角色："]
            for i, character in enumerate(characters, 1):
                name = character.get("name") or character.get("id") or "未命名"
                character_id = character.get("id") or name
                marker = "（当前）" if str(character_id) == active_id or str(name) == active_name else ""
                desc = str(character.get("description") or "").strip()
                suffix = f" - {desc[:40]}" if desc else ""
                lines.append(f"{i}. {name} [{character_id}]{marker}{suffix}")
            lines.append("")
            lines.append("用法：/character <编号|id|名称>")
            await h["reply_current_channel"](msg, is_group, "\n".join(lines))
            return

        target = h["find_character"](characters, arg)
        if not target:
            await h["reply_current_channel"](msg, is_group, f"没有找到角色：{arg}\n发送 /character list 查看可用角色。")
            return

        try:
            h["set_current_session_character"](msg, is_group, target)
        except Exception as e:
            log.error(f"Switch character failed: {e}", exc_info=True)
            await h["reply_current_channel"](msg, is_group, f"切换角色失败：{e}")
            return

        name = target.get("name") or target.get("id") or arg
        await h["reply_current_channel"](
            msg,
            is_group,
            f"已切换当前会话角色：{name}\n当前会话历史已清空，提示词已更新。",
        )

    @reg(
        "/model",
        help_text="/model -> 查看当前模型(admin)\n/model <编号> -> 切换到指定模型\n/model list -> 列出所有可用模型",
        category="2",
        admin_show=True,
    )
    async def handle_model_switch(msg, is_group=True):
        if str(msg.user_id) not in admin:
            await h["reply_current_channel"](msg, is_group, "你没有权限使用该命令喔~")
            return

        data_dir = os.path.join("data", "web")
        models_file = os.path.join(data_dir, "ai_models.json")

        if not os.path.exists(models_file):
            await h["reply_current_channel"](msg, is_group, "暂无可用模型配置，请先在 Web 控制台添加模型喔~")
            return

        try:
            models_data, was_plaintext = read_secure_json(models_file, data_dir, {})
            if was_plaintext:
                write_secure_json(models_file, data_dir, models_data)
            if not isinstance(models_data, dict):
                models_data = {}
        except Exception:
            await h["reply_current_channel"](msg, is_group, "读取模型配置失败喔~")
            return

        all_models = models_data.get("models", [])
        active_id = models_data.get("active_model_id")
        chat_models = [
            m for m in all_models
            if m.get("purpose", "chat") == "chat" and m.get("enabled", True)
        ]

        if not chat_models:
            await h["reply_current_channel"](msg, is_group, "暂无启用的对话模型，请先在 Web 控制台启用一个对话模型喔~")
            return

        raw = getattr(msg, "raw_message", "").strip()
        parts = raw.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""

        if arg == "" or arg == "list":
            lines = ["可用对话模型"]
            for i, model in enumerate(chat_models, 1):
                marker = " (当前)" if model.get("id") == active_id else ""
                name = model.get("name", "未命名")
                model_name = model.get("model", "?")
                lines.append(f"{i}. {name} - `{model_name}`{marker}")
            lines.append("")
            lines.append("输入 /model <编号> 切换模型")
            await h["reply_current_channel"](msg, is_group, "\n".join(lines))
            return

        try:
            idx = int(arg)
        except ValueError:
            idx = 0

        if 1 <= idx <= len(chat_models):
            target = chat_models[idx - 1]
            models_data["active_model_id"] = target.get("id")
            write_secure_json(models_file, data_dir, models_data)
            from nbot.services.ai import refresh_runtime_ai_config

            refresh_runtime_ai_config()
            await h["reply_current_channel"](
                msg,
                is_group,
                f"已切换到模型: {target.get('name', '未命名')} (`{target.get('model', '?')}`)",
            )
            return

        current = next((m for m in chat_models if m.get("id") == active_id), None)
        if current:
            reply = (
                f"当前模型: {current.get('name', '未命名')}\n"
                f"模型: `{current.get('model', '?')}`\n"
                f"厂商: {current.get('provider', '?')}\n"
                f"上下文: {current.get('max_context_length', 100000):,} tokens\n\n"
                "输入 /model list 查看所有可用模型"
            )
        else:
            reply = "未找到当前模型信息喔~"
        await h["reply_current_channel"](msg, is_group, reply)

    @reg(
        "/resume",
        help_text="/resume [编号|会话ID|名称] -> 从当前角色的 Web 会话载入到当前频道(admin)",
        category="2",
        admin_show=True,
    )
    async def handle_resume_session(msg, is_group=True):
        if str(msg.user_id) not in admin:
            await h["reply_current_channel"](msg, is_group, "你没有权限使用该命令喔~")
            return

        raw = (getattr(msg, "raw_message", "") or "").strip()
        parts = raw.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""
        active = h["current_character"](msg, is_group)
        candidates = h["candidate_resume_sessions"](msg, is_group)

        if not arg:
            await h["reply_current_channel"](
                msg,
                is_group,
                h["format_resume_session_list"](candidates, active),
            )
            return

        selected = h["find_resume_session"](candidates, arg)
        if not selected:
            await h["reply_current_channel"](
                msg,
                is_group,
                "没有找到匹配的 Web 会话。发送 /resume 查看当前角色可载入的会话。",
            )
            return

        web_session_id, web_session, _ = selected
        info = h["current_qq_session_info"](msg, is_group)
        messages = h["copy_chat_messages"](web_session.get("messages", []))
        system_prompt = h["session_system_prompt"](web_session, messages)
        if system_prompt and not any(m.get("role") == "system" for m in messages):
            messages.insert(0, {"role": "system", "content": system_prompt})

        info["store"][info["history_key"]] = messages
        h["save_qq_histories"]()

        bindings = h["load_resume_bindings"]()
        bindings[info["session_id"]] = {
            "web_session_id": web_session_id,
            "web_session_name": web_session.get("name") or "",
            "loaded_at": datetime.now().isoformat(),
            "channel": info["label"],
            "character_id": web_session.get("character_id") or web_session.get("sender_name") or "",
        }
        h["save_resume_bindings"](bindings)

        try:
            delete_session_workspace(
                user_id=info["user_id"],
                group_id=info["group_id"],
                group_user_id=info["group_user_id"],
            )
        except Exception:
            pass

        await h["reply_current_channel"](
            msg,
            is_group,
            f"已从 Web 会话「{web_session.get('name') or web_session_id[:8]}」载入 {len(messages)} 条消息到当前频道。\n之后 /push 会回写到该 Web 会话。",
        )

    @reg(
        "/push",
        help_text="/push -> 将当前频道会话上传到 /resume 绑定的 Web 会话(admin)",
        category="2",
        admin_show=True,
    )
    async def handle_push_session(msg, is_group=True):
        if str(msg.user_id) not in admin:
            await h["reply_current_channel"](msg, is_group, "你没有权限使用该命令喔~")
            return

        info = h["current_qq_session_info"](msg, is_group)
        bindings = h["load_resume_bindings"]()
        binding = bindings.get(info["session_id"])
        if not binding:
            await h["reply_current_channel"](
                msg,
                is_group,
                "当前频道还没有绑定 Web 会话。请先发送 /resume 选择一个会话。",
            )
            return

        web_session_id = binding.get("web_session_id")
        sessions = h["load_web_sessions"]()
        web_session = sessions.get(web_session_id)
        if not isinstance(web_session, dict):
            await h["reply_current_channel"](
                msg,
                is_group,
                "绑定的 Web 会话不存在了。请重新发送 /resume 选择会话。",
            )
            return

        current_messages = h["copy_chat_messages"](info["store"].get(info["history_key"], []))
        if not current_messages:
            await h["reply_current_channel"](msg, is_group, "当前频道没有可上传的会话内容。")
            return

        system_prompt = h["session_system_prompt"](web_session, current_messages)
        if system_prompt and not any(m.get("role") == "system" for m in current_messages):
            current_messages.insert(0, {"role": "system", "content": system_prompt})

        web_session["messages"] = current_messages
        web_session["system_prompt"] = h["session_system_prompt"](web_session, current_messages)
        web_session["updated_at"] = datetime.now().isoformat()
        web_session["last_message"] = next(
            (
                str(m.get("content") or "")[:100]
                for m in reversed(current_messages)
                if isinstance(m, dict) and m.get("role") != "system"
            ),
            "",
        )
        sessions[web_session_id] = web_session
        h["save_web_sessions"](sessions)

        binding["pushed_at"] = web_session["updated_at"]
        bindings[info["session_id"]] = binding
        h["save_resume_bindings"](bindings)

        await h["reply_current_channel"](
            msg,
            is_group,
            f"已上传当前频道的 {len(current_messages)} 条消息到 Web 会话「{web_session.get('name') or web_session_id[:8]}」。",
        )
