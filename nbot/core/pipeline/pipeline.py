"""
AI 处理管道主模块

PipelineContext、PipelineResult 和 AIPipeline 主类。
AIPipeline 通过混入继承获得附件处理和阶段执行能力。
"""

import threading
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from nbot.core.chat_models import ChatRequest, ChatResponse
from nbot.core.pipeline.attachments import PipelineAttachmentMixin
from nbot.core.pipeline.phases import PipelinePhasesMixin
from nbot.core.pipeline.phases_prep import PipelinePrepPhasesMixin

_log = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """贯穿 AI 管道的上下文，承载输入 → 中间状态 → 输出。"""

    # === 输入（由调用方设置） ===
    chat_request: ChatRequest
    adapter: Any = None  # BaseChannelAdapter

    # === 会话 / 消息准备 ===
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_call_history: Optional[List[Dict[str, Any]]] = None

    # === 知识库 ===
    knowledge_text: str = ""
    knowledge_retrieved: bool = False

    # === 附件处理 ===
    image_urls: List[str] = field(default_factory=list)
    file_contents: List[str] = field(default_factory=list)

    # === 工具上下文 ===
    tool_context: Dict[str, Any] = field(default_factory=dict)

    # === 停止控制 ===
    stop_event: Optional[threading.Event] = None

    # === 流式状态 ===
    streamed_message: Optional[Dict[str, Any]] = None

    # === 角色运行时 ===
    character_turn: Any = None

    # === 结果 ===
    final_content: str = ""
    stopped_prematurely: bool = False
    tool_trace: List[Dict[str, Any]] = field(default_factory=list)
    consecutive_errors: int = 0
    round_file_changes: List[Dict[str, Any]] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """延迟初始化 PromptStack，避免循环导入。"""
        if not hasattr(self, '_prompt_stack'):
            from nbot.character.prompt_stack import PromptStack
            self._prompt_stack = PromptStack()

    @property
    def prompt_stack(self):
        if not hasattr(self, '_prompt_stack'):
            from nbot.character.prompt_stack import PromptStack
            self._prompt_stack = PromptStack()
        return self._prompt_stack


@dataclass
class PipelineResult:
    """管道处理结果。"""

    final_content: str = ""
    assistant_message: Optional[Dict[str, Any]] = None
    tool_trace: List[Dict[str, Any]] = field(default_factory=list)
    can_continue: bool = False
    stopped_prematurely: bool = False
    usage: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_chat_response(self) -> ChatResponse:
        """转换为 ChatResponse。"""
        return ChatResponse(
            final_content=self.final_content,
            assistant_message=self.assistant_message,
            tool_trace=self.tool_trace,
            can_continue=self.can_continue,
            usage=self.usage,
            error=self.error,
            metadata=self.metadata,
        )


class AIPipeline(PipelineAttachmentMixin, PipelinePrepPhasesMixin, PipelinePhasesMixin):
    """统一 AI 处理管道。所有频道的单一入口点。"""

    # MIME 类型分类
    TEXT_MIME_TYPES = {
        "text/plain", "text/markdown", "text/csv", "text/html",
        "text/css", "text/javascript", "text/xml", "text/x-python",
        "text/x-shellscript", "text/x-sh", "text/x-bash", "text/x-c",
        "text/x-c++", "application/json", "application/xml",
        "application/javascript", "application/x-python",
        "application/x-shellscript",
    }

    TEXT_EXTENSIONS = {
        ".txt", ".md", ".csv", ".json", ".xml", ".html", ".css", ".js",
        ".py", ".sh", ".bash", ".c", ".h", ".cpp", ".hpp", ".java",
        ".go", ".rs", ".ts", ".tsx", ".jsx", ".yaml", ".yml", ".toml",
        ".ini", ".cfg", ".conf", ".log", ".sql", ".rb", ".php", ".pl",
        ".r", ".swift", ".kt", ".scala", ".lua", ".vim", ".tex",
    }

    DOCUMENT_MIME_TYPES = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }

    def process(
        self,
        ctx: PipelineContext,
        callbacks: "PipelineCallbacks",
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tool_iterations: int = 50,
        max_context_chars: int = 100000,
    ) -> PipelineResult:
        """执行完整的 AI 处理管道。

        Args:
            ctx: 管道上下文（含 ChatRequest 和 adapter）
            callbacks: 频道回调实现
            tools: 可用工具定义列表（None = 不启用工具）
            max_tool_iterations: 工具循环最大迭代次数
            max_context_chars: 上下文最大字符数

        Returns:
            PipelineResult 可转为 ChatResponse
        """
        # === 通用消息预处理（附件下载 + 媒体描述） ===
        self._ensure_middleware_initialized()
        from nbot.core.message_middleware import MessagePreprocessor
        MessagePreprocessor.process(ctx.chat_request)

        progress = callbacks.get_progress_reporter(ctx)

        # Phase 1: 附件解析
        self._phase_attachments(ctx, callbacks, progress)

        # Phase 2: 知识库检索
        self._phase_knowledge(ctx, callbacks, progress)

        # Phase 3: 上下文准备
        self._phase_prepare_context(ctx, callbacks, tools, max_context_chars)

        # Phase 4: AI 响应（工具循环 或 直接补全 或 流式）
        self._phase_ai_response(ctx, callbacks, tools, max_tool_iterations, progress)

        # Phase 5: 结果组装
        result = self._phase_assemble_result(ctx, callbacks)

        # Phase 5.5: 角色运行时 after_turn
        self._phase_character_runtime_after_turn(ctx, callbacks, result)

        self._phase_auto_memory(ctx, callbacks, result)
        callbacks.on_response_complete(ctx, result)

        return result


# 全局单例
ai_pipeline = AIPipeline()
