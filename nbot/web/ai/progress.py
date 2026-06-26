"""Web 频道进度报告器——封装 ProgressCard 和 TodoCard。"""

import json
from typing import Dict, Optional

from nbot.utils.logger import get_logger

_log = get_logger(__name__)


class WebProgressReporter:
    """Web 频道的进度报告实现，封装 ProgressCard 和 TodoCard。"""

    def __init__(self, server, session_id: str, parent_message_id: str, session_store):
        self.server = server
        self.session_id = session_id
        self.parent_message_id = parent_message_id
        self.session_store = session_store
        self.progress_card: Optional[object] = None
        self.todo_card: Optional[object] = None
        self._init_cards()

    def _init_cards(self):
        if (
            self.server.PROGRESS_CARD_AVAILABLE
            and self.server.progress_card_manager
            and self.server.socketio
        ):
            self.progress_card = self.server.progress_card_manager.create_card(
                session_id=self.session_id,
                parent_message_id=self.parent_message_id,
                max_iterations=50,
            )

        if (
            self.server.TODO_CARD_AVAILABLE
            and self.server.todo_card_manager
            and self.server.socketio
        ):
            self.todo_card = self.server.todo_card_manager.create_card(
                session_id=self.session_id,
                parent_message_id=self.parent_message_id,
            )

    def on_thinking_start(self, ctx) -> None:
        if self.progress_card:
            from nbot.core.progress_card import StepType
            self.progress_card.update(StepType.THINKING, "AI 正在思考...")

    def on_knowledge_start(self, ctx) -> None:
        pass

    def on_knowledge_done(self, ctx, retrieved: bool) -> None:
        if self.progress_card and retrieved:
            from nbot.core.progress_card import StepType
            self.progress_card.update(StepType.KNOWLEDGE_DONE, "知识库检索完成")

    def on_tool_start(self, ctx, tool_name: str, arguments: dict, thinking: str) -> None:
        if self.progress_card:
            from nbot.core.progress_card import StepType
            from nbot.web.ai.service import _get_tool_display_name
            display_name = _get_tool_display_name(tool_name)
            self.progress_card.update(
                StepType.TOOL,
                display_name,
                json.dumps(arguments, ensure_ascii=False)[:100],
                step_arguments=arguments,
                thinking_content=thinking,
            )

    def on_tool_done(self, ctx, tool_name: str, result: dict, thinking: str) -> None:
        if self.progress_card:
            from nbot.core.progress_card import StepType
            from nbot.web.ai.service import _get_tool_display_name
            result_preview = json.dumps(result, ensure_ascii=False)[:200]
            self.progress_card.update(
                StepType.TOOL_DONE,
                _get_tool_display_name(tool_name),
                result_preview,
                thinking_content=thinking,
            )
        if self.todo_card:
            try:
                # 更新 Todo 卡片
                self.server.todo_card_manager.update_from_tool_result(
                    self.todo_card, tool_name, result
                )
            except Exception:
                pass

    def on_tool_iteration(self, ctx, iteration: int) -> None:
        pass

    def on_attachment_start(self, ctx, count: int) -> None:
        if self.progress_card:
            from nbot.core.progress_card import StepType
            self.progress_card.update(StepType.UPLOAD, f"正在处理 {count} 个附件...")

    def on_attachment_item(self, ctx, name: str, item_type: str) -> None:
        pass

    def on_attachment_item_done(self, ctx, name: str, success: bool, result_preview: str = "") -> None:
        pass

    def on_attachments_done(self, ctx) -> None:
        pass

    def on_done(self, ctx) -> None:
        if self.progress_card:
            from nbot.core.progress_card import StepType
            self.progress_card.complete("✅ 处理完成")

    def on_waiting_confirmation(self, ctx, command: str, request_id: str) -> None:
        pass

    def dispose(self):
        """清理卡片资源。"""
        self.progress_card = None
        self.todo_card = None
