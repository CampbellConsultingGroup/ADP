"""Background tasks that are not awaited by the request that starts them (ADP-blp.24).

``asyncio.create_task`` only keeps a weak reference to the task it returns. A task nobody holds
can be garbage-collected before it finishes, and an exception inside it surfaces only as "Task
exception was never retrieved" at some later point. The tasks started this way here write audit
and provenance records (reasoning logs, accepted/rejected recommendations), which must not
silently go missing.

``spawn`` keeps a strong reference until the task is done and logs any failure with the task's
name. ``drain`` waits for what is still running, for application shutdown.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

_logger = logging.getLogger("adp.background")

_tasks: set[asyncio.Task[Any]] = set()


def _finished(task: asyncio.Task[Any]) -> None:
    _tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        _logger.error("background task %s failed: %s", task.get_name(), exc, exc_info=exc)


def spawn(coro: Coroutine[Any, Any, Any], *, name: str | None = None) -> asyncio.Task[Any]:
    """Start ``coro`` in the background. Raises RuntimeError when no event loop is running,
    exactly as asyncio.create_task does."""
    task = asyncio.create_task(coro, name=name)
    _tasks.add(task)
    task.add_done_callback(_finished)
    return task


def pending() -> int:
    return len(_tasks)


async def drain(timeout: float = 10.0) -> None:
    """Wait for the current loop's background tasks to finish; cancel what is left."""
    loop = asyncio.get_running_loop()
    mine = [t for t in _tasks if t.get_loop() is loop]
    if not mine:
        return
    _done, still_running = await asyncio.wait(mine, timeout=timeout)
    for task in still_running:
        _logger.warning("background task %s did not finish before shutdown", task.get_name())
        task.cancel()
