"""
管道响应阶段混入类

提供 AI 管道各响应阶段的处理方法：AI 响应（工具循环/流式/简单调用）、结果组装。
作为 AIPipeline 的混入基类使用。
"""

import json
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

from nbot.core.chat_models import ChatResponse

_log = logging.getLogger(__name__)


class PipelinePhasesMixin:
    """管道响应阶段处理混入类。

    所有方法使用 self 和管道上下文完成各阶段的处理。
    包含 AI 响应选择、工具循环、流式输出和结果组装。
    """

    # ------------------------------------------------------------------
    # Phase 4: AI 响应
    # ------------------------------------------------------------------

    def _phase_ai_response(
        self,
        ctx: "PipelineContext",
        callbacks: "PipelineCallbacks",
        tools: Optional[List[Dict[str, Any]]],
        max_tool_iterations: int,
        progress: "ProgressReporter",
    ) -> None:
        """选择并执行 AI 响应路径（流式/工具循环/简单调用）。"""
        progress.on_thinking_start(ctx)

        # 尝试流式
        if tools is None:
            streamer = callbacks.build_model_call_streaming(ctx, tools or [])
            if streamer is not None:
                self._run_streaming(ctx, callbacks, streamer, progress)
                progress.on_done(ctx)
                return

        # 尝试工具循环
        if tools:
            self._run_tool_loop(ctx, callbacks, tools, max_tool_iterations, progress)
            progress.on_done(ctx)
            return

        # 简单路径：单次模型调用
        self._run_simple(ctx, callbacks)
        progress.on_done(ctx)

    def _run_simple(
        self,
        ctx: "PipelineContext",
        callbacks: "PipelineCallbacks",
    ) -> None:
        """简单的单次模型调用（无工具、无流式）。"""
        model_call = callbacks.build_model_call(ctx, [])
        try:
            response = model_call(ctx.messages, stop_event=ctx.stop_event)
        except StopIteration:
            ctx.stopped_prematurely = True
            ctx.final_content = "【生成已停止】"
            return
        except Exception as e:
            _log.error(f"Simple model call failed: {e}")
            ctx.error = str(e)
            ctx.final_content = f"AI 调用失败: {e}"
            return

        ctx.final_content = response.get("content", "")
        ctx.usage = response.get("usage", {})

    def _run_tool_loop(
        self,
        ctx: "PipelineContext",
        callbacks: "PipelineCallbacks",
        tools: List[Dict[str, Any]],
        max_tool_iterations: int,
        progress: "ProgressReporter",
    ) -> None:
        """运行工具调用循环。"""
        from nbot.core.agent_service import (
            ToolLoopSession,
            ToolLoopHooks,
            run_tool_loop_session,
            ToolLoopExit,
            resolve_loop_final_content,
            build_continue_chat_response,
            extract_tool_call_history,
        )
        from nbot.services.tools import execute_tool

        model_call = callbacks.build_model_call(ctx, tools)
        ctx.tool_context = callbacks.get_workspace_context(ctx)

        # 工具执行器
        def tool_executor(tool_call, thinking_content, iteration, tool_messages):
            name = tool_call.get("name", "")
            args = tool_call.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}

            result = execute_tool(name, args, ctx.tool_context)

            # 处理确认请求
            if result.get("require_confirmation"):
                request_id = result.get("request_id", "")
                command = result.get("command", "")
                callbacks.on_confirmation_required(ctx, request_id, command)
                progress.on_waiting_confirmation(ctx, command, request_id)
                raise ToolLoopExit(
                    result.get(
                        "message",
                        f"⚠️ 命令需要确认: {command}\n"
                        f"[请求ID: {request_id}]\n"
                        f"请回复「确认」执行，或「取消」放弃。",
                    )
                )

            return result

        # 工具循环钩子 → 进度报告
        def on_iteration_start(iteration, messages):
            progress.on_tool_iteration(ctx, iteration)

        def on_tool_start(tool_call, thinking, iteration, messages):
            name = tool_call.get("name", "")
            args = tool_call.get("arguments", {})
            progress.on_tool_start(ctx, name, args, thinking)

        def on_tool_result(tool_call, result, thinking, iteration, messages):
            name = tool_call.get("name", "")
            progress.on_tool_done(ctx, name, result, thinking)
            if result.get("_send_message"):
                progress.on_send_message(ctx, result.get("_send_message", ""))
            if result.get("_file_path"):
                progress.on_send_file(
                    ctx,
                    result.get("_file_path", ""),
                    result.get("_file_name", ""),
                )
            return None

        hooks = ToolLoopHooks(
            on_iteration_start=on_iteration_start,
            on_tool_start=on_tool_start,
            on_tool_result=on_tool_result,
        )

        session = ToolLoopSession(
            initial_messages=ctx.messages,
            model_call=model_call,
            tool_executor=tool_executor,
            tool_call_history=ctx.tool_call_history,
            max_iterations=max_tool_iterations,
            stop_event=ctx.stop_event,
            hooks=hooks,
        )

        try:
            execution_result = run_tool_loop_session(session)
        except Exception as e:
            error_str = str(e)
            _log.error(f"Tool loop failed: {e}")
            # 400：模型不支持工具调用 → 去掉工具回退到普通对话
            if "400" in error_str and ("Bad Request" in error_str or "chat/completions" in error_str):
                _log.warning("模型返回400错误，跳过工具调用，回退到普通对话")
                progress.on_thinking_start(ctx)
                self._run_simple(ctx, callbacks)
                progress.on_done(ctx)
                return
            # 5xx / timeout / connection：服务端临时故障 → 去掉工具重试一次普通对话
            if any(x in error_str for x in ("502", "503", "504", "520", "timeout", "Timeout", "Connection")):
                _log.warning(f"服务端错误({error_str[:80]})，跳过工具调用，回退到普通对话")
                try:
                    progress.on_thinking_start(ctx)
                    self._run_simple(ctx, callbacks)
                    progress.on_done(ctx)
                    return
                except Exception as retry_err:
                    _log.error(f"回退普通对话也失败: {retry_err}")
                    error_str = str(retry_err)
            ctx.error = error_str
            ctx.final_content = f"工具循环执行失败: {error_str}"
            return

        loop_result = execution_result.loop_result

        if loop_result.stopped:
            ctx.stopped_prematurely = True
            ctx.tool_trace = extract_tool_call_history(loop_result.tool_messages)
            ctx.final_content = "【生成已停止 - 工具调用记录已保存，回复「继续」可继续执行】"
            return

        ctx.final_content = resolve_loop_final_content(loop_result)

    def _run_streaming(
        self,
        ctx: "PipelineContext",
        callbacks: "PipelineCallbacks",
        streamer: Callable,
        progress: "ProgressReporter",
    ) -> None:
        """运行流式模型调用。"""
        message_id = str(uuid.uuid4())
        full_content = ""

        try:
            for event in streamer(ctx.messages, stop_event=ctx.stop_event):
                if ctx.stop_event and ctx.stop_event.is_set():
                    break

                chunk = event.get("content", "") if isinstance(event, dict) else str(event)
                if not chunk:
                    continue

                if not full_content:
                    msg = {"role": "assistant", "content": "", "id": message_id}
                    callbacks.on_stream_start(ctx, msg)
                    ctx.streamed_message = msg

                full_content += chunk
                callbacks.on_stream_chunk(ctx, chunk, message_id)
        except Exception as e:
            _log.error(f"Streaming failed: {e}")
            ctx.error = str(e)
            full_content = full_content or f"流式输出失败: {e}"

        ctx.final_content = full_content
        if ctx.streamed_message:
            ctx.metadata["streamed"] = True
            ctx.metadata["stream_end_pending"] = True
            ctx.metadata["stream_message_id"] = message_id
        else:
            ctx.metadata.pop("streamed", None)
            ctx.metadata.pop("stream_end_pending", None)
            ctx.metadata.pop("stream_message_id", None)

    # ------------------------------------------------------------------
    # Phase 5: 结果组装
    # ------------------------------------------------------------------

    def _phase_assemble_result(
        self,
        ctx: "PipelineContext",
        callbacks: "PipelineCallbacks",
    ) -> "PipelineResult":
        """组装最终管道结果。"""
        from nbot.core.agent_service import extract_tool_call_history
        from nbot.core.pipeline.pipeline import PipelineResult

        # 流式消息在管道结果组装前已可见。
        # 在发出 stream_end 之前持久化，防止消息列表刷新丢失临时气泡。
        if ctx.metadata.get("streamed") and ctx.streamed_message:
            ctx.streamed_message["content"] = ctx.final_content
            callbacks.save_assistant_message(ctx, ctx.streamed_message)
            result = PipelineResult(
                final_content=ctx.final_content,
                assistant_message=ctx.streamed_message,
                tool_trace=ctx.tool_trace,
                can_continue=bool(ctx.tool_trace),
                stopped_prematurely=ctx.stopped_prematurely,
                usage=ctx.usage,
                error=ctx.error,
                metadata=ctx.metadata,
            )
            if ctx.metadata.pop("stream_end_pending", False):
                callbacks.on_stream_end(
                    ctx,
                    ctx.metadata.get("stream_message_id") or ctx.streamed_message.get("id", ""),
                )
            callbacks.on_response_complete(ctx, result)
            return result

        if ctx.error:
            result = PipelineResult(
                final_content=ctx.final_content or ctx.error,
                error=ctx.error,
                metadata=ctx.metadata,
            )
            return result

        # 非流式：通过适配器构建 assistant_message
        if ctx.adapter and hasattr(ctx.adapter, "build_assistant_message"):
            temp_response = ChatResponse(
                final_content=ctx.final_content,
                tool_trace=ctx.tool_trace,
                usage=ctx.usage,
            )
            assistant_message = ctx.adapter.build_assistant_message(
                temp_response,
                conversation_id=ctx.chat_request.conversation_id,
            )
        else:
            assistant_message = {
                "role": "assistant",
                "content": ctx.final_content,
            }

        # 添加工具调用历史（用于"继续"功能）
        if ctx.tool_trace:
            assistant_message["tool_call_history"] = ctx.tool_trace
            assistant_message["can_continue"] = True

        # 保存历史
        callbacks.save_assistant_message(ctx, assistant_message)

        # 发送回复
        callbacks.send_response(ctx, assistant_message)

        result = PipelineResult(
            final_content=ctx.final_content,
            assistant_message=assistant_message,
            tool_trace=ctx.tool_trace,
            can_continue=bool(ctx.tool_trace),
            stopped_prematurely=ctx.stopped_prematurely,
            usage=ctx.usage,
            error=ctx.error,
            metadata=ctx.metadata,
        )
        return result
