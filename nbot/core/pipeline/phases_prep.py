"""
管道准备阶段混入类

提供 AI 管道各准备阶段的处理方法：附件解析、知识库检索、上下文准备、
角色运行时（before_turn / after_turn）、自动记忆等。
作为 AIPipeline 的混入基类使用。
"""

import copy
from typing import Any, Dict, List, Optional

from nbot.utils.logger import get_logger

_log = get_logger(__name__)


class PipelinePrepPhasesMixin:
    """管道准备阶段处理混入类。

    所有方法使用 self 和管道上下文完成各阶段的处理。
    包含附件解析、知识库检索、上下文准备、角色运行时和记忆旁路。
    """

    # ------------------------------------------------------------------
    # Phase 1: 附件解析
    # ------------------------------------------------------------------

    def _phase_attachments(
        self,
        ctx: "PipelineContext",
        callbacks: "PipelineCallbacks",
        progress: "ProgressReporter",
    ) -> None:
        """处理请求中的附件。"""
        attachments = ctx.chat_request.attachments
        if not attachments:
            return

        progress.on_attachment_start(ctx, len(attachments))

        for att in attachments:
            att_type = str(att.get("type", "")).lower()
            att_name = str(att.get("name", att.get("filename", "")))
            resolved = callbacks.resolve_attachment_data(ctx, att)

            if att_type.startswith("image/") or self._looks_like_image(att):
                self._handle_image_attachment(ctx, progress, att, resolved)
            elif self._is_text_type(att_type, att_name):
                self._handle_text_attachment(ctx, progress, att, resolved)
            elif self._is_document_type(att_type, att_name):
                self._handle_document_attachment(ctx, progress, att, resolved)

        progress.on_attachments_done(ctx)

    # ------------------------------------------------------------------
    # Phase 2: 知识库检索
    # ------------------------------------------------------------------

    def _phase_knowledge(
        self,
        ctx: "PipelineContext",
        callbacks: "PipelineCallbacks",
        progress: "ProgressReporter",
    ) -> None:
        """检索知识库。"""
        progress.on_knowledge_start(ctx)
        ctx.knowledge_text = callbacks.search_knowledge(
            ctx, ctx.chat_request.content
        )
        ctx.knowledge_retrieved = bool(ctx.knowledge_text)
        progress.on_knowledge_done(ctx, ctx.knowledge_retrieved)

    # ------------------------------------------------------------------
    # Phase 3: 上下文准备
    # ------------------------------------------------------------------

    def _phase_prepare_context(
        self,
        ctx: "PipelineContext",
        callbacks: "PipelineCallbacks",
        tools: Optional[List[Dict[str, Any]]],
        max_context_chars: int,
    ) -> None:
        """准备 AI 对话上下文：加载历史、注入附件、知识库、角色提示。"""
        from nbot.core.agent_service import prepare_chat_context
        from nbot.character.prompt_stack import split_system_prompt

        # 加载消息历史
        messages_raw = callbacks.load_messages(ctx)
        messages_for_ai = copy.deepcopy(messages_raw)

        # 追加当前用户消息（如果 load_messages 未包含）
        user_content = ctx.chat_request.content
        if not messages_for_ai or messages_for_ai[-1].get("role") != "user" or messages_for_ai[-1].get("content") != user_content:
            messages_for_ai.append({"role": "user", "content": user_content})

        # 注入附件内容
        if ctx.file_contents:
            enhanced_content = user_content
            for fc in ctx.file_contents:
                if fc:
                    enhanced_content += "\n\n" + fc
            for msg in reversed(messages_for_ai):
                if msg.get("role") == "user":
                    msg["content"] = enhanced_content
                    break

        # 图片 URL 注入
        if ctx.image_urls:
            for msg in reversed(messages_for_ai):
                if msg.get("role") == "user":
                    msg["content"] = (
                        f"[附图片 {len(ctx.image_urls)} 张，已通过视觉模型识别]\n"
                        + msg.get("content", "")
                    )
                    break

        # 分离原有 system prompt 和历史消息
        base_prompt, history_messages = split_system_prompt(messages_for_ai)

        # 知识库注入 → PromptStack
        if ctx.knowledge_text:
            ctx.prompt_stack.add(
                "knowledge.rag",
                ctx.knowledge_text,
                priority=70,
            )

        # 跨会话角色记忆注入 → PromptStack
        try:
            from nbot.core.auto_memory import (
                build_memory_context,
                load_character_memories,
            )

            memory_context = build_memory_context(ctx, callbacks)
            memory_text = load_character_memories(
                memory_context.get("character_name", ""),
                memory_context.get("target_id", ""),
            )
            if memory_text:
                ctx.prompt_stack.add(
                    "character.memories_legacy",
                    memory_text,
                    priority=60,
                )
        except Exception:
            pass

        # 角色运行时 before_turn hook
        self._phase_character_runtime_before_turn(ctx, callbacks)
        if ctx.character_turn and getattr(ctx.character_turn, "memories", None):
            ctx.prompt_stack.remove("character.memories_legacy")

        # PromptStack 合成最终 system prompt
        composed_system = ctx.prompt_stack.render(base_prompt)
        messages_for_ai = [
            {"role": "system", "content": composed_system},
            *history_messages,
        ]

        # 将合成后的 system prompt 存入 metadata，供 on_response_complete 回写
        ctx.metadata["composed_system_prompt"] = composed_system
        ctx.metadata["prompt_stack_debug"] = ctx.prompt_stack.render_debug()

        _log.debug(
            "[PromptStack] 本轮注入 keys: %s",
            ctx.prompt_stack.keys,
        )

        # 调用现有的上下文准备
        prepared = prepare_chat_context(
            messages_for_ai,
            user_content,
            knowledge_text="",
            max_total_chars=max_context_chars,
        )
        ctx.messages = prepared.messages
        ctx.tool_call_history = prepared.tool_call_history

    # ------------------------------------------------------------------
    # 角色运行时 hooks
    # ------------------------------------------------------------------

    def _phase_character_runtime_before_turn(
        self,
        ctx: "PipelineContext",
        callbacks: "PipelineCallbacks",
    ) -> None:
        """角色运行时 before_turn：读取状态、生成 ReactionPlan、注册 PromptStack 注入项。"""
        runtime = callbacks.get_character_runtime(ctx)
        identity = callbacks.get_character_context(ctx)

        if not runtime:
            _log.debug("[CharacterRuntime] before_turn skipped: runtime is None")
            return
        if not identity:
            _log.debug("[CharacterRuntime] before_turn skipped: identity is None")
            return

        try:
            turn = runtime.before_turn(ctx.chat_request, identity)
            ctx.character_turn = turn

            from nbot.character.prompt_builder import build_character_injections

            build_character_injections(
                ctx.prompt_stack,
                profile=turn.profile,
                state=turn.state,
                relationship=turn.relationship,
                memories=turn.memories,
                plan=turn.plan,
            )

            _log.debug(
                "[CharacterRuntime] before_turn executed: character=%s target=%s "
                "rel(affection=%s trust=%s familiarity=%s dependency=%s security=%s)",
                identity.character_id,
                identity.target_id,
                turn.relationship.affection if turn.relationship else "N/A",
                turn.relationship.trust if turn.relationship else "N/A",
                turn.relationship.familiarity if turn.relationship else "N/A",
                turn.relationship.dependency if turn.relationship else "N/A",
                turn.relationship.security if turn.relationship else "N/A",
            )
        except Exception as exc:
            _log.warning(
                "[CharacterRuntime] before_turn 异常: %s", exc, exc_info=True
            )

    def _phase_character_runtime_after_turn(
        self,
        ctx: "PipelineContext",
        callbacks: "PipelineCallbacks",
        result: "PipelineResult",
    ) -> None:
        """角色运行时 after_turn：更新情绪、关系、写入事件、抽取记忆。"""
        runtime = callbacks.get_character_runtime(ctx)
        identity = callbacks.get_character_context(ctx)

        if not runtime:
            _log.debug("[CharacterRuntime] after_turn skipped: runtime is None")
            return
        if not identity:
            _log.debug("[CharacterRuntime] after_turn skipped: identity is None")
            return
        if not ctx.character_turn:
            _log.debug("[CharacterRuntime] after_turn skipped: ctx.character_turn is None")
            return

        try:
            runtime.after_turn(
                chat_request=ctx.chat_request,
                result=result,
                turn_context=ctx.character_turn,
            )
            _log.debug(
                "[CharacterRuntime] after_turn executed: character=%s scope=%s",
                identity.character_id,
                identity.scope_id,
            )
        except Exception as exc:
            _log.warning(
                "[CharacterRuntime] after_turn 异常: %s", exc, exc_info=True
            )

    def _phase_auto_memory(
        self,
        ctx: "PipelineContext",
        callbacks: "PipelineCallbacks",
        result: "PipelineResult",
    ) -> None:
        """主回复完成后，旁路抽取并保存记忆。"""
        try:
            from nbot.core.auto_memory import extract_and_save_turn_memories

            saved_count = extract_and_save_turn_memories(ctx, callbacks, result)
            if saved_count:
                result.metadata["auto_memory_saved"] = saved_count
        except Exception as exc:
            _log.warning("[AutoMemory] 记忆中间件异常: %s", exc, exc_info=True)
