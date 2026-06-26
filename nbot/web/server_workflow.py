"""Web 服务器工作流调度相关方法。

提供工作流的初始化、调度、执行与结果发送能力，
以 mixin 形式组合到 WebChatServer。
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from nbot.utils.logger import get_logger
from nbot.web.server_utils import (
    CORE_INSTRUCTIONS,
    _build_web_manager_payload,
    _build_workflow_assistant_message,
    _build_workflow_user_message,
    _resolve_web_adapter,
)

_log = get_logger(__name__)

# 尝试导入 APScheduler
try:
    from apscheduler.triggers.cron import CronTrigger

    _APSCHEDULER_AVAILABLE = True
except ImportError:
    _APSCHEDULER_AVAILABLE = False
    CronTrigger = None  # type: ignore[misc,assignment]

# 尝试导入消息模块
try:
    from nbot.core import create_message, message_manager

    _MESSAGE_MODULE_AVAILABLE = True
except ImportError:
    _MESSAGE_MODULE_AVAILABLE = False
    create_message = None  # type: ignore[misc,assignment]
    message_manager = None  # type: ignore[misc,assignment]

# 尝试导入工作区管理器
try:
    from nbot.core.workspace import workspace_manager

    _WORKSPACE_AVAILABLE = True
except ImportError:
    _WORKSPACE_AVAILABLE = False
    workspace_manager = None  # type: ignore[misc,assignment]


class WorkflowMixin:
    """工作流调度相关方法 mixin。"""

    def _init_workflow_scheduler(self):
        """初始化工作流调度器。"""
        if not self.scheduler:
            _log.warning("APScheduler not available, workflow scheduling disabled")
            return

        for workflow in self.workflows:
            if workflow.get("enabled") and workflow.get("trigger") == "cron":
                self._schedule_workflow(workflow)

    def _schedule_workflow(self, workflow: Dict):
        """调度一个工作流任务。"""
        if not self.scheduler:
            workflow["next_run"] = None
            workflow["last_error"] = "Scheduler is not available"
            return

        workflow_id = workflow["id"]
        config = workflow.get("config", {})
        cron_expr = config.get("cron", "0 8 * * *")

        try:
            parts = cron_expr.split()
            if len(parts) == 5:
                minute, hour, day, month, day_of_week = parts
                trigger = CronTrigger(
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week,
                )

                job_id = f"workflow_{workflow_id}"
                try:
                    self.scheduler.remove_job(job_id)
                except Exception:
                    pass

                job = self.scheduler.add_job(
                    func=self._execute_workflow,
                    trigger=trigger,
                    id=job_id,
                    args=[workflow_id],
                    replace_existing=True,
                )
                workflow["next_run"] = (
                    job.next_run_time.isoformat() if job.next_run_time else None
                )
                _log.info(
                    f"Scheduled workflow '{workflow['name']}' with cron: {cron_expr}"
                )
        except Exception as e:
            workflow["next_run"] = None
            workflow["last_error"] = str(e)
            _log.error(f"Failed to schedule workflow {workflow_id}: {e}")

    def _unschedule_workflow(self, workflow_id: str):
        """取消工作流的定时任务。"""
        if self.scheduler:
            try:
                self.scheduler.remove_job(f"workflow_{workflow_id}")
            except Exception:
                pass
        for workflow in self.workflows:
            if workflow.get("id") == workflow_id:
                workflow["next_run"] = None
                break

    def _validate_workflow(self, workflow: Dict[str, Any]):
        """验证工作流配置。"""
        if not (workflow.get("name") or "").strip():
            raise ValueError("Workflow name is required")
        if not (workflow.get("description") or "").strip():
            raise ValueError("Workflow description is required")
        trigger = workflow.get("trigger", "manual")
        if trigger not in {"manual", "cron"}:
            raise ValueError(f"Unsupported workflow trigger: {trigger}")
        if trigger == "cron":
            cron_expr = ((workflow.get("config") or {}).get("cron") or "").strip()
            if len(cron_expr.split()) != 5:
                raise ValueError("Workflow cron expression must contain 5 parts")

    def _mark_workflow_status(
        self,
        workflow: Dict[str, Any],
        status: str,
        *,
        error: str = None,
        save: bool = True,
    ):
        """标记工作流状态。"""
        now = datetime.now().isoformat()
        workflow["status"] = status
        if status == "running":
            workflow["started_at"] = now
            workflow["last_error"] = None
        elif status == "success":
            workflow["last_run"] = now
            workflow["finished_at"] = now
            workflow["last_error"] = None
        elif status == "failed":
            workflow["failed_at"] = now
            workflow["finished_at"] = now
            workflow["last_error"] = error or "Unknown workflow error"
        if save:
            self._save_data("workflows")

    def _execute_workflow(self, workflow_id: str, trigger_data: Dict = None):
        """执行工作流 - 支持多轮工具调用。"""
        workflow = None
        workflow_adapter = _resolve_web_adapter(self.web_channel_adapter)
        for w in self.workflows:
            if w["id"] == workflow_id:
                workflow = w
                break

        if not workflow or not workflow.get("enabled"):
            return
        if workflow_id in self.running_workflow_ids:
            _log.warning(f"Skip workflow {workflow_id}: already running")
            return

        _log.info(f"Executing workflow: {workflow['name']}")
        self.running_workflow_ids.add(workflow_id)
        self._mark_workflow_status(workflow, "running")

        session_id = workflow.get("session_id")
        if not session_id or not self.session_store.get_session(session_id):
            session_id = self._create_workflow_session(workflow)
            workflow["session_id"] = session_id
            self._save_data("workflows")

        system_prompt = workflow.get(
            "description", "你是一个工作流助手，请按照工作流配置执行任务。"
        )

        messages = [
            {"role": "system", "content": f"{system_prompt}\n\n{CORE_INSTRUCTIONS}"}
        ]

        session = self.session_store.get_session(session_id) or {}
        history = session.get("messages", [])
        for msg in history:
            if msg.get("role") in ["user", "assistant"]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        if trigger_data:
            trigger_content = trigger_data.get("content", "")
            trigger_source = trigger_data.get("source", "manual")
            trigger_time = trigger_data.get("time", datetime.now().isoformat())

            if trigger_content:
                trigger_msg = (
                    f"[工作流触发 - {trigger_source}] 任务内容：{trigger_content}"
                )
            else:
                trigger_msg = f"[工作流触发 - {trigger_source}] 请根据工作流描述执行任务。触发时间：{trigger_time}"

            messages.append({"role": "user", "content": trigger_msg})

            user_message = _build_workflow_user_message(
                workflow_adapter, session_id, trigger_msg, workflow_id
            )
            if self.session_store.get_session(session_id):
                self.session_store.append_message(session_id, user_message)
                if _MESSAGE_MODULE_AVAILABLE and message_manager:
                    manager_payload = _build_web_manager_payload(
                        workflow_adapter,
                        user_message,
                        default_role="user",
                        default_content=trigger_msg,
                        default_sender="user",
                        default_conversation_id=session_id,
                        metadata={"workflow_id": workflow_id},
                    )
                    message_manager.add_web_message(
                        session_id,
                        create_message(**manager_payload),
                    )
        else:
            messages.append({"role": "user", "content": "[定时触发] 请执行工作流任务"})

        def run_workflow_with_tools():
            try:
                from nbot.services.tools import get_all_tool_definitions, execute_tool

                all_tools = get_all_tool_definitions(include_workspace=True)
                tool_context = {"session_id": session_id, "session_type": "workflow"}

                max_iterations = 50
                final_response = None

                for iteration in range(max_iterations):
                    _log.info(f"Workflow iteration {iteration + 1}")

                    response = self._get_ai_response_with_tools(messages, all_tools)

                    if "tool_calls" in response and response["tool_calls"]:
                        tool_calls = response["tool_calls"]

                        messages.append(
                            {
                                "role": "assistant",
                                "content": response.get("content", ""),
                                "tool_calls": [
                                    {
                                        "id": tc.get("id", str(uuid.uuid4())),
                                        "type": "function",
                                        "function": {
                                            "name": tc["name"],
                                            "arguments": json.dumps(tc["arguments"]),
                                        },
                                    }
                                    for tc in tool_calls
                                ],
                            }
                        )

                        for tool_call in tool_calls:
                            tool_name = tool_call["name"]
                            arguments = tool_call["arguments"]

                            _log.info(
                                f"Executing tool: {tool_name} with args: {arguments}"
                            )

                            tool_result = execute_tool(
                                tool_name, arguments, context=tool_context
                            )

                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.get("id", ""),
                                    "content": json.dumps(
                                        tool_result, ensure_ascii=False
                                    ),
                                }
                            )

                            _log.info(f"Tool result: {tool_result}")

                    else:
                        final_response = response.get("content", "")
                        break

                if not final_response:
                    final_response = messages[-1].get("content", "工作流执行完成")

                assistant_message = _build_workflow_assistant_message(
                    workflow_adapter, session_id, final_response, workflow_id
                )

                if self.session_store.get_session(session_id):
                    self.session_store.append_message(session_id, assistant_message)
                    if _MESSAGE_MODULE_AVAILABLE and message_manager:
                        manager_payload = _build_web_manager_payload(
                            workflow_adapter,
                            assistant_message,
                            default_role="assistant",
                            default_content=final_response,
                            default_sender="AI",
                            default_conversation_id=session_id,
                            metadata={"workflow_id": workflow_id},
                        )
                        message_manager.add_web_message(
                            session_id,
                            create_message(**manager_payload),
                        )

                self._send_workflow_result(workflow, final_response)

                self.socketio.emit(
                    "workflow_executed",
                    {
                        "workflow_id": workflow_id,
                        "workflow_name": workflow["name"],
                        "result": final_response,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
                workflow["last_run"] = datetime.now().isoformat()
                if self.scheduler and workflow.get("trigger") == "cron":
                    try:
                        job = self.scheduler.get_job(f"workflow_{workflow_id}")
                        workflow["next_run"] = (
                            job.next_run_time.isoformat()
                            if job and job.next_run_time
                            else None
                        )
                    except Exception:
                        workflow["next_run"] = None
                self._mark_workflow_status(workflow, "success", save=False)
                self._save_data("workflows")

            except Exception as e:
                _log.error(f"Workflow execution error: {e}", exc_info=True)
                self._mark_workflow_status(workflow, "failed", error=str(e), save=True)
            finally:
                self.running_workflow_ids.discard(workflow_id)

        self.socketio.start_background_task(run_workflow_with_tools)

    def _create_workflow_session(self, workflow: Dict) -> str:
        """为工作流创建专属会话。"""
        session_id = str(uuid.uuid4())
        session = {
            "id": session_id,
            "name": f"[工作流] {workflow['name']}",
            "type": "workflow",
            "workflow_id": workflow["id"],
            "created_at": datetime.now().isoformat(),
            "messages": [
                {"role": "system", "content": workflow.get("description", "")}
            ],
            "system_prompt": workflow.get("description", ""),
        }
        self.session_store.set_session(session_id, session)

        if _WORKSPACE_AVAILABLE and workspace_manager:
            workspace_manager.get_or_create(
                session_id, "workflow", f"[工作流] {workflow['name']}"
            )

        return session_id

    def _send_workflow_result(self, workflow: Dict, result: str):
        """发送工作流结果到指定目标。"""
        config = workflow.get("config", {})
        target_type = config.get("target_type", "none")
        target_id = config.get("target_id", "")

        if target_type == "none" or not target_id:
            return

        try:
            if target_type in ["qq_group", "qq_private"] and self.qq_bot:
                import asyncio

                async def send_qq_message():
                    try:
                        if target_type == "qq_group":
                            await self.qq_bot.api.post_group_msg(
                                group_id=target_id, text=result
                            )
                        else:
                            await self.qq_bot.api.post_private_msg(
                                user_id=target_id, text=result
                            )
                        _log.info(
                            f"Workflow result sent to QQ {target_type}: {target_id}"
                        )
                    except Exception as e:
                        _log.error(f"Failed to send workflow result: {e}")

                def run_async_task():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(send_qq_message())
                        loop.close()
                    except Exception as e:
                        _log.error(f"Failed to run async task: {e}")

                threading.Thread(target=run_async_task, daemon=True).start()

            elif target_type == "session":
                if self.session_store.get_session(target_id):
                    message = {
                        "id": str(uuid.uuid4()),
                        "role": "assistant",
                        "content": f"[工作流: {workflow['name']}]\n{result}",
                        "timestamp": datetime.now().isoformat(),
                        "sender": "Workflow",
                        "workflow_id": workflow["id"],
                    }
                    self.session_store.append_message(target_id, message)
                    self.socketio.emit("new_message", message, room=target_id)
                    _log.info(f"Workflow result sent to session: {target_id}")

        except Exception as e:
            _log.error(f"Failed to send workflow result: {e}")

    def trigger_workflow_by_message(
        self, workflow_id: str, message_content: str, source: str = "qq"
    ):
        """由消息触发工作流。"""
        for workflow in self.workflows:
            if workflow["id"] == workflow_id and workflow.get("enabled"):
                trigger_data = {
                    "source": source,
                    "content": message_content,
                    "time": datetime.now().isoformat(),
                }
                self._execute_workflow(workflow_id, trigger_data)
                return True
        return False
