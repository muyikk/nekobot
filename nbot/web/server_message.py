"""Web 服务器消息构建与会话名称生成相关方法。

提供会话名称 AI 生成能力，以 mixin 形式组合到 WebChatServer。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from nbot.utils.logger import get_logger

_log = get_logger(__name__)

# 尝试导入进度卡片管理器
try:
    from nbot.core.progress_card import progress_card_manager

    _PROGRESS_CARD_AVAILABLE = True
except ImportError:
    _PROGRESS_CARD_AVAILABLE = False
    progress_card_manager = None  # type: ignore[misc,assignment]


class MessageMixin:
    """消息构建与会话名称生成相关方法 mixin。"""

    def _generate_session_name(
        self,
        messages: List[Dict],
        session_id: str = None,
        parent_message_id: str = None,
    ) -> Optional[str]:
        """根据对话内容生成会话名称。

        Args:
            messages: 对话消息列表。
            session_id: 会话 ID（用于进度卡片）。
            parent_message_id: 父消息 ID（用于进度卡片）。

        Returns:
            生成的会话名称，失败时返回 None。
        """
        if not self.ai_client:
            return None

        progress_card = None

        try:
            if (
                session_id
                and parent_message_id
                and _PROGRESS_CARD_AVAILABLE
                and progress_card_manager
                and self.socketio
            ):
                progress_card = progress_card_manager.create_card(
                    session_id=session_id, parent_message_id=parent_message_id
                )
                if progress_card:
                    from nbot.core.progress_card import StepType

                    progress_card.update(StepType.THINKING, "📝 正在生成会话名称...")

            personality_name = self.personality.get("name", "")
            personality_desc = self.personality.get("description", "")

            conversation_text = ""
            for msg in messages[-12:]:
                role = "用户" if msg.get("role") == "user" else "角色"
                content = str(msg.get("content", ""))[:200]
                conversation_text += f"{role}: {content}\n"

            msg_count = len(messages)
            is_update = msg_count > 6

            role_context = ""
            if personality_name:
                role_context = f"当前角色是'{personality_name}'（{personality_desc}）。"

            update_hint = ""
            if is_update:
                update_hint = "对话已经进行了较长时间，请根据最新的主要话题重新命名，忽略早期已结束的话题。\n"

            prompt_messages = [
                {
                    "role": "system",
                    "content": (
                        f"你是一个会话命名助手。{role_context}请根据对话内容生成一个简短、有辨识度、贴合当前话题的标题。\n\n"
                        f"{update_hint}"
                        "要求：\n"
                        "- 2-15个字\n"
                        "- 概括当前主要话题或最新亮点\n"
                        "- 自然口语化，像聊天记录名称\n"
                        "- 有趣或有诗意更好\n"
                        "- 直接返回标题，不要引号、标点或解释"
                    ),
                },
                {
                    "role": "user",
                    "content": f"请为以下对话生成标题：\n\n{conversation_text.strip()}",
                },
            ]

            response = self.ai_client.chat_completion(
                model=self.ai_model, messages=prompt_messages, stream=False
            )

            name = response.choices[0].message.content.strip()
            name = name.strip("\"'「」『』【】()（）")

            if name and len(name) <= 20:
                if progress_card:
                    from nbot.core.progress_card import StepType

                    progress_card.update(StepType.DONE, f"✅ 会话名称: {name}", True)
                    progress_card.complete()
                return name

            if progress_card:
                from nbot.core.progress_card import StepType

                progress_card.update(StepType.DONE, "❌ 名称生成失败", False)
                progress_card.complete()
            return None

        except Exception as e:
            _log.error(f"生成会话名失败: {e}")
            if progress_card:
                from nbot.core.progress_card import StepType

                progress_card.update(StepType.DONE, f"❌ 错误: {str(e)}", False)
                progress_card.complete()
            return None
