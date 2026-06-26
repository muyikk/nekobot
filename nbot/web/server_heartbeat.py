"""Web 服务器心跳调度相关方法。

提供 Heartbeat 定时任务的初始化、执行与发送能力，
以 mixin 形式组合到 WebChatServer。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional

from nbot.utils.logger import get_logger
from nbot.web.server_utils import (
    _build_heartbeat_assistant_message,
    _build_heartbeat_user_message,
    _resolve_web_adapter,
)

_log = get_logger(__name__)


class HeartbeatMixin:
    """心跳调度相关方法 mixin。"""

    def _init_heartbeat_scheduler(self):
        """初始化 Heartbeat 调度器。"""
        if not self.heartbeat_config.get("enabled"):
            _log.info("Heartbeat is disabled")
            return

        interval = self.heartbeat_config.get("interval_minutes", 60)
        self._start_heartbeat_job(interval)

    def _start_heartbeat_job(self, interval_minutes: int):
        """启动 Heartbeat 定时任务。"""
        if not self.scheduler:
            _log.warning("Scheduler not available for heartbeat")
            return

        if self.heartbeat_job:
            try:
                self.scheduler.remove_job("heartbeat")
            except Exception:
                pass

        try:
            def run_heartbeat_sync():
                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                    asyncio.create_task(self._execute_heartbeat())
                except RuntimeError:
                    asyncio.run(self._execute_heartbeat())

            job = self.scheduler.add_job(
                func=run_heartbeat_sync,
                trigger="interval",
                minutes=interval_minutes,
                id="heartbeat",
                replace_existing=True,
            )
            self.heartbeat_job = job
            self.heartbeat_config["next_run"] = (
                job.next_run_time.isoformat() if job.next_run_time else None
            )
            _log.info(f"Heartbeat scheduled every {interval_minutes} minutes")
        except Exception as e:
            _log.error(f"Failed to start heartbeat job: {e}")

    def _stop_heartbeat_job(self):
        """停止 Heartbeat 定时任务。"""
        if self.scheduler and self.heartbeat_job:
            try:
                self.scheduler.remove_job("heartbeat")
                self.heartbeat_job = None
                _log.info("Heartbeat job stopped")
            except Exception:
                pass

    async def _execute_heartbeat(self, force: bool = False):
        """执行 Heartbeat 任务。

        Args:
            force: 是否强制执行，跳过 enabled 检查。
        """
        if not force and not self.heartbeat_config.get("enabled"):
            _log.info("Heartbeat is disabled, skipping execution")
            return

        config = self.heartbeat_config
        content_file = config.get("content_file", "heartbeat.md")
        targets = config.get("targets", [])
        target_session_id = config.get("target_session_id")

        _log.info(
            f"[Heartbeat] 配置: targets={targets}, target_session_id={target_session_id}"
        )

        content = self._load_heartbeat_content(content_file)
        if not content:
            _log.warning(f"Heartbeat content file '{content_file}' not found or empty")
            return

        _log.info(f"Executing heartbeat with content from {content_file}")

        context_target = None
        session = None
        session_id = None

        if target_session_id and self.session_store.get_session(target_session_id):
            session_id = target_session_id
            session = self.session_store.get_session(session_id)
            context_target = f"web:{target_session_id}"
        else:
            for target in targets:
                if not isinstance(target, str):
                    continue
                if target.startswith("web:"):
                    candidate_session_id = target.split(":", 1)[1]
                    candidate_session = self.session_store.get_session(candidate_session_id)
                    if candidate_session:
                        session_id = candidate_session_id
                        session = candidate_session
                        context_target = target
                        break
                elif target.startswith("qq_private:") or target.startswith("qq_user:"):
                    qq_user_id = target.split(":", 1)[1]
                    candidate_session_id = self.sync_qq_messages(
                        user_id=qq_user_id, create_if_not_exists=True
                    )
                    candidate_session = (
                        self.session_store.get_session(candidate_session_id)
                        if candidate_session_id
                        else None
                    )
                    if candidate_session:
                        session_id = candidate_session_id
                        session = candidate_session
                        context_target = f"qq_private:{qq_user_id}"
                        break
                elif target.startswith("qq_group:"):
                    qq_group_id = target.split(":", 1)[1]
                    candidate_session_id = self.sync_qq_messages(
                        user_id=None, group_id=qq_group_id, create_if_not_exists=True
                    )
                    candidate_session = (
                        self.session_store.get_session(candidate_session_id)
                        if candidate_session_id
                        else None
                    )
                    if candidate_session:
                        session_id = candidate_session_id
                        session = candidate_session
                        context_target = f"qq_group:{qq_group_id}"
                        break

        is_appended_session = bool(session_id and session)
        heartbeat_adapter = _resolve_web_adapter(self.web_channel_adapter)

        if is_appended_session:
            hb_user_message = _build_heartbeat_user_message(
                heartbeat_adapter, session_id, content
            )
            self.session_store.append_message(session_id, hb_user_message)
            _log.info(f"Heartbeat: 追加到会话 {session_id}")
        else:
            session_id = f"heartbeat_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            session = {
                "id": session_id,
                "name": f"Heartbeat {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "type": "heartbeat",
                "user_id": "heartbeat",
                "created_at": datetime.now().isoformat(),
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个智能助手，请根据以下任务描述执行相关操作。",
                    },
                    {"role": "user", "content": f"【Heartbeat 任务】\n\n{content}"},
                ],
                "system_prompt": "你是一个智能助手，请根据任务描述执行相关操作。",
            }
            if heartbeat_adapter:
                session["messages"][1] = _build_heartbeat_user_message(
                    heartbeat_adapter, session_id, content
                )
            self.session_store.set_session(session_id, session)
            _log.info(f"Heartbeat: 创建新会话 {session_id}")

        try:
            heartbeat_session = self.session_store.get_session(session_id) or session or {}
            heartbeat_messages = []
            for msg in heartbeat_session.get("messages", [])[-12:]:
                role = msg.get("role")
                if role in ["system", "user", "assistant"]:
                    heartbeat_messages.append(
                        {
                            "role": role,
                            "content": msg.get("content", ""),
                        }
                    )

            if not heartbeat_messages:
                heartbeat_messages = [
                    {
                        "role": "system",
                        "content": heartbeat_session.get(
                            "system_prompt",
                            "你是一个智能助手，请根据任务描述执行相关操作。",
                        ),
                    },
                    {"role": "user", "content": content},
                ]

            response_text = self._get_ai_response(heartbeat_messages)

            if response_text:
                _log.info(f"Heartbeat AI response: {response_text[:200]}...")

                hb_assistant_message = _build_heartbeat_assistant_message(
                    heartbeat_adapter, session_id, response_text
                )
                self.session_store.append_message(session_id, hb_assistant_message)

                append_target_key = (
                    context_target
                    if is_appended_session
                    and isinstance(context_target, str)
                    and context_target.startswith("web:")
                    else None
                )
                for target in targets:
                    if append_target_key and target == append_target_key:
                        _log.info(
                            f"Skip duplicated heartbeat target {target} because it is already appended to session {target_session_id}"
                        )
                        continue
                    try:
                        await self._send_heartbeat_to_target(target, response_text)
                    except Exception as send_error:
                        _log.error(
                            f"Failed to send heartbeat to {target}: {send_error}",
                            exc_info=True,
                        )
            else:
                _log.warning("Heartbeat AI returned empty response")
        except Exception as e:
            _log.error(f"Error executing heartbeat: {e}", exc_info=True)

        if is_appended_session and self.socketio:
            self.socketio.emit(
                "session_updated",
                {"session_id": session_id, "action": "heartbeat_completed"},
                room=session_id,
            )
            _log.info(f"Heartbeat: 已通知前端刷新会话 {session_id}")

        if (not is_appended_session) and self.socketio:
            heartbeat_session = self.session_store.get_session(session_id) or {}
            self.socketio.emit(
                "session_updated",
                {
                    "session_id": session_id,
                    "action": "heartbeat_created",
                    "session": {
                        "id": session_id,
                        "name": heartbeat_session.get(
                            "name", f"Heartbeat {session_id[-8:]}"
                        ),
                        "type": heartbeat_session.get("type", "heartbeat"),
                        "user_id": heartbeat_session.get("user_id"),
                        "created_at": heartbeat_session.get("created_at"),
                        "message_count": len(heartbeat_session.get("messages", [])),
                        "system_prompt": heartbeat_session.get("system_prompt", ""),
                    },
                },
            )
            _log.info(f"Heartbeat: 已通知前端新会话 {session_id}")

        self.heartbeat_config["last_run"] = datetime.now().isoformat()
        self._save_data("heartbeat")

    def _load_heartbeat_content(self, filename: str) -> str:
        """加载 heartbeat.md 文件内容。"""
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "..", "..", "resources", filename),
            os.path.join(os.getcwd(), "resources", filename),
            os.path.join(os.path.dirname(__file__), "..", "..", filename),
            os.path.join(os.getcwd(), filename),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read().strip()
                except Exception as e:
                    _log.error(f"Failed to read heartbeat file {path}: {e}")

        return ""

    async def _send_heartbeat_to_target(self, target: str, content: str):
        """发送 heartbeat 结果到指定目标。"""
        try:
            if target.startswith("qq_group:"):
                group_id = target.split(":", 1)[1]
                if self.qq_bot:
                    await self.qq_bot.api.post_group_msg(
                        group_id=group_id, text=content
                    )
                    _log.info(f"Heartbeat sent to group {group_id}")
            elif target.startswith("qq_user:") or target.startswith("qq_private:"):
                user_id = target.split(":", 1)[1]
                if self.qq_bot:
                    await self.qq_bot.api.post_private_msg(
                        user_id=user_id, text=content
                    )
                    _log.info(f"Heartbeat sent to user {user_id}")
            elif target.startswith("web:"):
                session_id = target.split(":", 1)[1]
                if self.socketio:
                    self.socketio.emit(
                        "new_message",
                        {
                            "session_id": session_id,
                            "content": content,
                            "role": "assistant",
                            "timestamp": datetime.now().isoformat(),
                            "sender": "AI",
                            "source": "heartbeat",
                            "is_heartbeat": True,
                        },
                        room=session_id,
                    )
                    _log.info(f"Heartbeat sent to web session {session_id}")
            elif target == "web":
                if self.socketio:
                    self.socketio.emit(
                        "heartbeat",
                        {"content": content, "timestamp": datetime.now().isoformat()},
                    )
                    _log.info("Heartbeat broadcast to all web clients")
        except Exception as e:
            _log.error(f"Failed to send heartbeat to {target}: {e}")
