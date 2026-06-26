"""Web 频道 AI 管道回调——WebCallbacks 实现 PipelineCallbacks 接口。"""

import copy
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional

from nbot.utils.logger import get_logger
from nbot.core.ai_pipeline import PipelineCallbacks, PipelineContext, PipelineResult

from nbot.web.ai.service import (
    _emit_change_card,
    _feature_enabled,
    _get_tool_display_name,
)
from nbot.web.ai.models import _call_web_ai, _stream_to_web

_log = get_logger(__name__)


class WebCallbacks(PipelineCallbacks):
    """Web 频道的管道回调实现。"""

    def __init__(
        self,
        server,
        session_store,
        session_id: str,
        adapter,
        parent_message_id: str = None,
        progress_reporter=None,
    ):
        self.server = server
        self.session_store = session_store
        self.session_id = session_id
        self.adapter = adapter
        self.parent_message_id = parent_message_id
        self._progress = progress_reporter

    # ---- 会话 / 消息 I/O ----

    def load_messages(self, ctx: PipelineContext) -> List[Dict]:
        session = self.session_store.get_session(self.session_id)
        if session:
            return copy.deepcopy(session.get("messages", []))
        return []

    def get_system_prompt(self, ctx: PipelineContext) -> str:
        session = self.session_store.get_session(self.session_id)
        if session and session.get("system_prompt"):
            return str(session.get("system_prompt") or "").strip()
        return str(
            getattr(self.server, "personality", {}).get("systemPrompt") or ""
        ).strip()

    def save_assistant_message(self, ctx: PipelineContext, message: Dict) -> None:
        self.session_store.append_message(self.session_id, message)
        self._try_auto_name_session()

    # ---- AI 模型交互 ----

    def build_model_call(self, ctx, tools):
        """Web 频道使用服务器的 AI 方法。"""
        server = self.server
        return lambda messages, stop_event=None: _call_web_ai(
            server, messages, tools, stop_event
        )

    def build_model_call_streaming(self, ctx, tools):
        """返回 provider 级流式迭代器。"""
        server = self.server
        session_id = self.session_id

        def streamer(messages, stop_event=None):
            return _stream_to_web(server, messages, tools, session_id, stop_event)

        return streamer

    # ---- 输出 / 回复 ----

    def send_response(self, ctx: PipelineContext, message: Dict) -> None:
        if ctx.metadata.get("streamed"):
            # 流式已发送，无需再次发送
            return
        self.server.socketio.emit(
            "ai_response",
            {"session_id": self.session_id, "message": message},
            room=self.session_id,
        )

    def on_stream_start(self, ctx: PipelineContext, message: Dict) -> None:
        self.server.socketio.emit(
            "ai_stream_start",
            {"session_id": self.session_id, "message": message},
            room=self.session_id,
        )

    def on_stream_chunk(self, ctx: PipelineContext, chunk: str, message_id: str) -> None:
        self.server.socketio.emit(
            "ai_stream_chunk",
            {
                "session_id": self.session_id,
                "message_id": message_id,
                "chunk": chunk,
                "is_end": False,
            },
            room=self.session_id,
        )

    def on_stream_end(self, ctx: PipelineContext, message_id: str) -> None:
        self.server.socketio.emit(
            "ai_stream_end",
            {
                "session_id": self.session_id,
                "message_id": message_id,
                "is_end": True,
            },
            room=self.session_id,
        )

    # ---- 进度 ----

    def get_progress_reporter(self, ctx: PipelineContext):
        if self._progress:
            return self._progress
        from nbot.core.ai_pipeline import NoOpProgressReporter
        return NoOpProgressReporter()

    # ---- 工具确认 ----

    def on_confirmation_required(self, ctx: PipelineContext, request_id: str, command: str) -> None:
        self.server.socketio.emit(
            "exec_confirm_request",
            {
                "request_id": request_id,
                "command": command,
                "message": f"命令 `{command}` 需要您的确认",
                "session_id": self.session_id,
            },
            room=self.session_id,
        )

    # ---- 知识库 ----

    def search_knowledge(self, ctx: PipelineContext, query: str) -> str:
        if not _feature_enabled(self.server, "knowledge", True):
            return ""
        try:
            return self.server._retrieve_knowledge(query)
        except Exception:
            return ""

    # ---- 工作区 ----

    def ensure_workspace(self, ctx: PipelineContext) -> str:
        if getattr(self.server, "WORKSPACE_AVAILABLE", False) and self.server.workspace_manager:
            return self.server.workspace_manager.get_or_create(
                self.session_id, "web"
            )
        return ""

    def get_workspace_context(self, ctx: PipelineContext) -> Dict:
        # 从会话中获取角色名
        character_name = ""
        target_id = ""
        session = self.session_store.get_session(self.session_id)
        if session:
            character_name = session.get("character_id") or session.get("sender_name", "")
            target_id = session.get("user_id") or session.get("qq_id") or ""
        # 只有拿不到会话时才回退到全局角色，避免旧会话被当前设置污染。
        if not session and not character_name:
            character_name = getattr(self.server, "personality", {}).get("name", "")

        context = {"session_id": self.session_id, "session_type": "web"}
        if target_id:
            context["target_id"] = str(target_id)
            context["user_id"] = str(target_id)
        if character_name:
            context["character_name"] = character_name
        return context

    # ---- 角色运行时 ----

    def get_character_context(self, ctx):
        """返回当前会话的角色身份标识"""
        from nbot.character.adapters.nekobot import get_web_character_context
        return get_web_character_context(
            self.server, self.session_store, self.session_id
        )

    def get_character_runtime(self, ctx):
        """返回 CharacterRuntime 实例"""
        from nbot.character.adapters.nekobot import get_character_runtime_from_server
        return get_character_runtime_from_server(self.server)

    # ---- 响应完成 ----

    def on_response_complete(self, ctx: PipelineContext, result) -> None:
        """AI 响应完成后的回调，兜底触发自动命名，并回写实时 system_prompt"""
        self._try_auto_name_session()
        self._update_session_system_prompt(ctx)

    def _update_session_system_prompt(self, ctx: PipelineContext):
        """将 PromptStack 合成后的实时 system_prompt 回写到 session，供前端 i 按钮查看"""
        try:
            composed = ctx.metadata.get("composed_system_prompt")
            if not composed:
                return

            session = self.session_store.get_session(self.session_id)
            if not session:
                return

            session["system_prompt"] = composed

            # 同时保存角色运行时调试信息
            prompt_stack_debug = ctx.metadata.get("prompt_stack_debug")
            if prompt_stack_debug:
                session["prompt_stack_debug"] = prompt_stack_debug

            # 保存角色运行时上下文摘要
            if hasattr(ctx, 'character_turn') and ctx.character_turn:
                turn = ctx.character_turn
                snapshot = {
                    "mood": turn.state.mood,
                    "mood_intensity": turn.state.mood_intensity,
                    "energy": turn.state.energy,
                    "affection": turn.relationship.affection,
                    "trust": turn.relationship.trust,
                    "familiarity": turn.relationship.familiarity,
                    "dependency": turn.relationship.dependency,
                    "security": turn.relationship.security,
                    "jealousy": turn.relationship.jealousy,
                    "plan_tone": turn.plan.tone,
                    "visible_emotion": turn.plan.visible_emotion,
                    "hidden_emotion": turn.plan.hidden_emotion,
                }
                session["character_runtime_snapshot"] = snapshot

                timeline = session.get("character_runtime_timeline", [])
                if not isinstance(timeline, list):
                    timeline = []
                entry = {
                    **{
                        key: snapshot.get(key)
                        for key in (
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
                    },
                    "timestamp": datetime.now().isoformat(),
                }
                last = timeline[-1] if timeline else None
                if isinstance(last, dict) and {
                    k: v for k, v in last.items() if k != "timestamp"
                } == {k: v for k, v in entry.items() if k != "timestamp"}:
                    last["timestamp"] = entry["timestamp"]
                else:
                    timeline.append(entry)
                session["character_runtime_timeline"] = timeline[-200:]

            self.session_store.set_session(self.session_id, session)
        except Exception:
            pass

    def _try_auto_name_session(self):
        """会话名称自动更新：首次命名 + 每隔一段对话更新"""
        try:
            session = self.session_store.get_session(self.session_id)
            if not session:
                return

            messages = session.get("messages", [])
            user_assistant_msgs = [m for m in messages if m.get("role") in ("user", "assistant")]
            total_count = len(user_assistant_msgs)
            if total_count < 2:
                return

            name = session.get("name", "")
            is_default_name = (
                not name
                or name.startswith("Web 会话")
                or name.startswith("新会话")
                or name.startswith("新对话")
            )

            # 首次命名：默认名称 + 至少一轮对话
            # 后续更新：每 10 条消息（约 5 轮对话）更新一次
            last_rename_count = session.get("_last_rename_count", 0)
            should_rename = is_default_name or (total_count - last_rename_count >= 10)

            if not should_rename:
                return

            # 防止并发重复生成
            if getattr(self, "_naming_in_progress", False):
                return
            self._naming_in_progress = True

            _log.info(f"开始为会话 {self.session_id[:8]} 自动生成名称 (当前: {name}, 消息数: {total_count})")

            # 取最近对话作为上下文
            recent_msgs = copy.deepcopy(user_assistant_msgs[-10:])

            def generate_and_update():
                try:
                    new_name = self.server._generate_session_name(recent_msgs)
                    if new_name:
                        session["name"] = new_name
                        session["_last_rename_count"] = total_count
                        self.session_store.set_session(self.session_id, session)
                        self.server.socketio.emit(
                            "session_renamed",
                            {"session_id": self.session_id, "name": new_name},
                            room=self.session_id,
                        )
                        _log.info(f"会话自动命名成功: {self.session_id[:8]} -> {new_name}")
                except Exception as e:
                    _log.error(f"自动命名失败: {e}")
                finally:
                    self._naming_in_progress = False

            threading.Thread(target=generate_and_update, daemon=True).start()
        except Exception as e:
            _log.error(f"自动命名检查失败: {e}")

    # ---- 附件解析 ----

    def resolve_attachment_data(self, ctx: PipelineContext, attachment: Dict) -> Optional[Dict]:
        """Web 频道附件解析：静态文件 / 工作区文件 / 数据 URL。"""
        att_path = attachment.get("path", "")
        att_url = attachment.get("url", "")
        att_data = attachment.get("data", "")
        att_name = attachment.get("name", "unknown")

        result = {"type": attachment.get("type", ""), "name": att_name}

        # 数据 URL 直接返回
        if att_data:
            result["data"] = att_data
            return result

        path_to_use = att_path or att_url
        if not path_to_use:
            return None

        try:
            file_path = None
            if path_to_use.startswith("/static/"):
                file_path = os.path.join(
                    self.server.static_folder,
                    path_to_use.replace("/static/", ""),
                )
            elif "/workspace/files/" in path_to_use:
                filename = path_to_use.split("/workspace/files/")[-1]
                if self.server.workspace_manager:
                    file_path = self.server.workspace_manager.get_file_path(
                        self.session_id, filename
                    )
                    if not file_path:
                        ws_path = self.server.workspace_manager.get_workspace(
                            self.session_id
                        )
                        if ws_path:
                            file_path = os.path.join(ws_path, filename)

            if file_path and os.path.isfile(file_path):
                result["path"] = file_path
                # 读取文本文件内容
                att_type = attachment.get("type", "")
                ext = os.path.splitext(att_name)[1].lower()
                from nbot.core.ai_pipeline import AIPipeline
                if att_type in AIPipeline.TEXT_MIME_TYPES or ext in AIPipeline.TEXT_EXTENSIONS:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        result["text_content"] = f.read()
                return result
        except Exception:
            pass

        return None

    # ---- 后处理 ----

    def on_response_complete_post(self, ctx: PipelineContext, result: PipelineResult) -> None:
        # 自动重命名会话
        self._auto_rename_session(ctx)
        self._update_session_system_prompt(ctx)
        # 文件变更卡片
        if ctx.round_file_changes:
            _emit_change_card(
                self.server,
                self.session_store,
                session_id=self.session_id,
                parent_message_id=self.parent_message_id,
                file_changes=ctx.round_file_changes,
            )

    def _auto_rename_session(self, ctx: PipelineContext) -> None:
        """自动重命名会话（基于对话内容）。"""
        try:
            session = self.session_store.get_session(self.session_id)
            if not session:
                return
            name = session.get("name", "")
            if name and name != "新对话":
                return
            messages = session.get("messages", [])
            user_count = sum(1 for m in messages if m.get("role") == "user")
            if user_count < 2:
                return
            # 简化：取第一条用户消息的前30字作为会话名
            first_user_msg = ""
            for m in messages:
                if m.get("role") == "user":
                    content = m.get("content", "").strip()
                    if content and len(content) > 3:
                        first_user_msg = content
                        break
            if first_user_msg:
                new_name = first_user_msg[:30] + ("..." if len(first_user_msg) > 30 else "")
                session["name"] = new_name
                self.session_store.set_session(self.session_id, session)
        except Exception:
            pass
