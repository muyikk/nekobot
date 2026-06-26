"""Web 服务器自定义任务调度相关方法。

提供自定义定时任务的初始化、调度、执行与状态管理能力，
以 mixin 形式组合到 WebChatServer。
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from nbot.utils.logger import get_logger
from nbot.web.server_utils import _resolve_web_adapter

_log = get_logger(__name__)

# 尝试导入 APScheduler
try:
    from apscheduler.triggers.cron import CronTrigger

    _APSCHEDULER_AVAILABLE = True
except ImportError:
    _APSCHEDULER_AVAILABLE = False
    CronTrigger = None  # type: ignore[misc,assignment]


class TaskMixin:
    """自定义任务调度相关方法 mixin。"""

    def _init_custom_task_scheduler(self):
        """初始化自定义任务调度器。"""
        if not self.scheduler:
            _log.warning("APScheduler not available, custom task scheduling disabled")
            return

        for task in self.scheduled_tasks:
            if task.get("enabled"):
                self._schedule_custom_task(task)

    def _build_custom_task_trigger(self, task: Dict[str, Any]):
        """构建自定义任务触发器参数。"""
        config = task.get("config") or {}
        trigger_type = task.get("trigger", "interval")

        if trigger_type == "interval":
            return {
                "trigger": "interval",
                "minutes": max(1, int(config.get("interval_minutes", 60) or 60)),
            }

        if trigger_type == "date":
            run_at = config.get("run_at")
            if not run_at:
                raise ValueError("run_at is required for date tasks")
            return {"trigger": "date", "run_date": datetime.fromisoformat(run_at)}

        cron_expr = (config.get("cron") or "0 8 * * *").strip()
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError("cron expression must contain 5 parts")

        minute, hour, day, month, day_of_week = parts
        return {
            "trigger": CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
            )
        }

    def _validate_custom_task(self, task: Dict[str, Any]):
        """验证自定义任务配置。"""
        if not (task.get("name") or "").strip():
            raise ValueError("Task name is required")
        if not (task.get("prompt") or "").strip():
            raise ValueError("Task prompt is required")
        session_id = task.get("target_session_id")
        if not session_id or not self.session_store.get_session(session_id):
            raise ValueError("Target session is required or does not exist")
        self._build_custom_task_trigger(task)

    def _mark_task_status(
        self,
        task: Dict[str, Any],
        status: str,
        *,
        error: str = None,
        save: bool = True,
    ):
        """标记自定义任务状态。"""
        now = datetime.now().isoformat()
        task["status"] = status
        if status == "running":
            task["started_at"] = now
            task["last_error"] = None
        elif status == "success":
            task["last_run"] = now
            task["finished_at"] = now
            task["last_error"] = None
        elif status == "failed":
            task["failed_at"] = now
            task["finished_at"] = now
            task["last_error"] = error or "Unknown task error"
        if save:
            self._save_data("scheduled_tasks")

    def _schedule_custom_task(self, task: Dict[str, Any]):
        """调度一个自定义任务。"""
        if not self.scheduler:
            task["next_run"] = None
            task["last_error"] = "Scheduler is not available"
            return

        task_id = task.get("id")
        if not task_id:
            return

        self._unschedule_custom_task(task_id)

        try:
            trigger_kwargs = self._build_custom_task_trigger(task)
            job = self.scheduler.add_job(
                func=self._execute_custom_task,
                id=f"custom_task_{task_id}",
                args=[task_id],
                replace_existing=True,
                **trigger_kwargs,
            )
            self.scheduled_task_jobs[task_id] = job
            task["next_run"] = (
                job.next_run_time.isoformat() if job.next_run_time else None
            )
        except Exception as e:
            task["next_run"] = None
            task["last_error"] = str(e)
            _log.error(f"Failed to schedule custom task {task_id}: {e}")

    def _unschedule_custom_task(self, task_id: str):
        """取消自定义任务的定时调度。"""
        if not self.scheduler:
            return

        try:
            self.scheduler.remove_job(f"custom_task_{task_id}")
        except Exception:
            pass

        self.scheduled_task_jobs.pop(task_id, None)
        task = self._get_custom_task(task_id)
        if task:
            task["next_run"] = None

    def _get_custom_task(self, task_id: str):
        """根据 ID 获取自定义任务。"""
        for task in self.scheduled_tasks:
            if task.get("id") == task_id:
                return task
        return None

    def _execute_custom_task(self, task_id: str):
        """执行自定义任务。"""
        task = self._get_custom_task(task_id)
        if not task or not task.get("enabled"):
            return
        if task_id in self.running_task_ids:
            _log.warning(f"Skip custom task {task_id}: already running")
            return

        prompt = (task.get("prompt") or "").strip()
        session_id = task.get("target_session_id")
        if not prompt or not session_id:
            _log.warning(f"Skip custom task {task_id}: missing prompt or target session")
            self._mark_task_status(task, "failed", error="Missing prompt or target session")
            return

        session = self.session_store.get_session(session_id)
        if not session:
            _log.warning(
                f"Skip custom task {task_id}: target session {session_id} not found"
            )
            self._mark_task_status(task, "failed", error=f"Target session {session_id} not found")
            return

        self.running_task_ids.add(task_id)
        self._mark_task_status(task, "running")
        session_type = session.get("type", "web")

        if session_type in ["qq_private", "qq_group"]:
            try:
                from nbot.services.chat_service import chat as run_qq_chat

                qq_id = session.get("qq_id")
                response_text = run_qq_chat(
                    prompt,
                    user_id=qq_id if session_type == "qq_private" else None,
                    group_id=qq_id if session_type == "qq_group" else None,
                    group_user_id=None,
                    image=False,
                    url=None,
                    video=None,
                )

                if response_text and self.qq_bot and qq_id:
                    def send_qq_task_message():
                        try:
                            async def _send():
                                if session_type == "qq_group":
                                    await self.qq_bot.api.post_group_msg(group_id=qq_id, text=response_text)
                                else:
                                    await self.qq_bot.api.post_private_msg(user_id=qq_id, text=response_text)

                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(_send())
                            loop.close()
                        except Exception as send_error:
                            _log.error(f"Failed to send scheduled QQ task message: {send_error}", exc_info=True)

                    threading.Thread(target=send_qq_task_message, daemon=True).start()

                task["last_run"] = datetime.now().isoformat()
                job = self.scheduled_task_jobs.get(task_id)
                task["next_run"] = (
                    job.next_run_time.isoformat() if job and job.next_run_time else None
                )

                if task.get("trigger") == "date":
                    task["enabled"] = False
                    self._unschedule_custom_task(task_id)

                self._mark_task_status(task, "success", save=False)
                self._save_data("scheduled_tasks")
                return
            except Exception as e:
                _log.error(f"Failed to execute QQ custom task {task_id}: {e}", exc_info=True)
                self._mark_task_status(task, "failed", error=str(e), save=False)
                return
            finally:
                self.running_task_ids.discard(task_id)

        adapter = _resolve_web_adapter(self.web_channel_adapter)
        user_message = adapter.build_message(
            role="user",
            content=prompt,
            sender="scheduler",
            conversation_id=session_id,
            source="task_center",
            metadata={
                "scheduled_task_id": task_id,
                "scheduled_task_name": task.get("name", "定时任务"),
            },
        )
        self.session_store.append_message(session_id, user_message)
        self.socketio.emit("new_message", user_message, room=session_id)

        try:
            self._trigger_ai_response(
                session_id=session_id,
                user_content=prompt,
                sender="scheduler",
            )
        except Exception as e:
            _log.error(f"Failed to execute custom task {task_id}: {e}", exc_info=True)
            self._mark_task_status(task, "failed", error=str(e), save=False)
        else:
            self._mark_task_status(task, "success", save=False)
        finally:
            self.running_task_ids.discard(task_id)

        job = self.scheduled_task_jobs.get(task_id)
        task["next_run"] = (
            job.next_run_time.isoformat() if job and job.next_run_time else None
        )

        if task.get("trigger") == "date":
            task["enabled"] = False
            self._unschedule_custom_task(task_id)

        self._save_data("scheduled_tasks")

    def get_task_center_items(self):
        """获取任务中心所有项目列表。"""
        items = [
            {
                "id": "heartbeat",
                "kind": "heartbeat",
                "name": "Heartbeat 定时任务",
                "description": "系统级定时提示和心跳执行",
                "enabled": self.heartbeat_config.get("enabled", False),
                "trigger": "interval",
                "trigger_label": f"每 {self.heartbeat_config.get('interval_minutes', 60)} 分钟",
                "target_session_id": self.heartbeat_config.get("target_session_id", ""),
                "last_run": self.heartbeat_config.get("last_run"),
                "next_run": self.heartbeat_config.get("next_run"),
                "editable": True,
                "deletable": False,
            }
        ]

        for workflow in self.workflows:
            config = workflow.get("config") or {}
            trigger = workflow.get("trigger", "manual")
            trigger_label = "手动触发"
            if trigger == "cron":
                trigger_label = config.get("cron", "0 8 * * *")
            elif trigger == "message":
                trigger_label = "消息触发"
            next_run = workflow.get("next_run")
            if self.scheduler and trigger == "cron":
                try:
                    job = self.scheduler.get_job(f"workflow_{workflow.get('id')}")
                    next_run = (
                        job.next_run_time.isoformat()
                        if job and job.next_run_time
                        else next_run
                    )
                except Exception:
                    pass

            items.append(
                {
                    "id": workflow.get("id"),
                    "kind": "workflow",
                    "name": workflow.get("name", "工作流"),
                    "description": workflow.get("description", ""),
                    "enabled": workflow.get("enabled", True),
                    "trigger": trigger,
                    "trigger_label": trigger_label,
                    "target_session_id": workflow.get("session_id", ""),
                    "last_run": workflow.get("last_run"),
                    "next_run": next_run,
                    "status": workflow.get("status", "idle"),
                    "last_error": workflow.get("last_error"),
                    "editable": True,
                    "deletable": False,
                }
            )

        for task in self.scheduled_tasks:
            config = task.get("config") or {}
            trigger = task.get("trigger", "interval")
            if trigger == "interval":
                trigger_label = f"每 {config.get('interval_minutes', 60)} 分钟"
            elif trigger == "date":
                trigger_label = config.get("run_at") or "单次执行"
            else:
                trigger_label = config.get("cron") or "0 8 * * *"

            items.append(
                {
                    "id": task.get("id"),
                    "kind": "custom",
                    "name": task.get("name", "定时任务"),
                    "description": task.get("description", ""),
                    "enabled": task.get("enabled", True),
                    "trigger": trigger,
                    "trigger_label": trigger_label,
                    "target_session_id": task.get("target_session_id", ""),
                    "last_run": task.get("last_run"),
                    "next_run": task.get("next_run"),
                    "status": task.get("status", "idle"),
                    "last_error": task.get("last_error"),
                    "editable": True,
                    "deletable": True,
                    "prompt": task.get("prompt", ""),
                    "config": config,
                }
            )

        return items
