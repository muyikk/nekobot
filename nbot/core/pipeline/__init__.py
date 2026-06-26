"""
AI 处理管道子包

提供统一的 AI 处理管道：
- AIPipeline: 管道主类
- PipelineContext / PipelineResult: 上下文与结果数据类
- PipelineCallbacks / ProgressReporter / NoOpProgressReporter: 频道回调接口
- handle_tool_confirmation: 工具确认处理
"""

from nbot.core.pipeline.pipeline import (
    AIPipeline,
    PipelineContext,
    PipelineResult,
    ai_pipeline,
)
from nbot.core.pipeline.callbacks import (
    PipelineCallbacks,
    ProgressReporter,
    NoOpProgressReporter,
)
from nbot.core.pipeline.tools import handle_tool_confirmation

__all__ = [
    "AIPipeline",
    "PipelineContext",
    "PipelineResult",
    "PipelineCallbacks",
    "ProgressReporter",
    "NoOpProgressReporter",
    "ai_pipeline",
    "handle_tool_confirmation",
]
