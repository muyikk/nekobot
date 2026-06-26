"""Task scheduling utilities."""

import asyncio
from datetime import datetime
from typing import Any, Callable

from nbot.utils.logger import get_logger
from nbot.commands.state import schedule_tasks

_log = get_logger(__name__)


async def schedule_task(
    delay_hours: float, task_func: Callable, *args: Any, **kwargs: Any
) -> None:
    """Execute a coroutine after a delay.

    Args:
        delay_hours: Hours to wait before execution.
        task_func: Async callable to invoke.
        *args: Positional arguments for ``task_func``.
        **kwargs: Keyword arguments for ``task_func``.
    """
    await asyncio.sleep(delay_hours * 3600)
    await task_func(*args, **kwargs)


async def schedule_task_by_date(
    target_time: datetime, task_func: Callable, *args: Any, **kwargs: Any
) -> None:
    """Execute a coroutine at an exact datetime.

    Args:
        target_time: Target datetime (must be in the future).
        task_func: Async callable to invoke.
        *args: Positional arguments for ``task_func``.
        **kwargs: Keyword arguments for ``task_func``.

    Raises:
        ValueError: If ``target_time`` is in the past.
    """
    now = datetime.now()
    if target_time < now:
        raise ValueError("目标时间不能是过去时间喵~")
    delay_seconds = (target_time - now).total_seconds()
    await asyncio.sleep(delay_seconds)
    await task_func(*args, **kwargs)


async def schedule_job_task(
    delay_hours: float,
    loop: bool,
    name: str,
    task_func: Callable,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Execute a coroutine after a delay, optionally looping.

    Args:
        delay_hours: Hours to wait between executions.
        loop: If True, repeat indefinitely.
        name: Human-readable task name.
        task_func: Async callable to invoke.
        *args: Positional arguments for ``task_func``.
        **kwargs: Keyword arguments for ``task_func``.
    """
    if loop:
        while True:
            await asyncio.sleep(delay_hours * 3600)
            await task_func(*args, **kwargs)
            _log.info(f"任务 {name} 执行完成")
    else:
        await asyncio.sleep(delay_hours * 3600)
        await task_func(*args, **kwargs)
        _log.info(f"任务 {name} 执行完成")
        schedule_tasks.pop(name, None)
