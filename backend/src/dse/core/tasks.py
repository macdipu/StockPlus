"""Task helpers for process lifecycle code."""

import asyncio


async def cancel_and_wait(task: "asyncio.Task[object]", *, retry_s: float = 1.0) -> None:
    """Cancel `task` and wait until it is really finished.

    A single `cancel()` can be lost: on Python 3.11 a cancellation that lands while a library is inside
    `asyncio.wait_for` may be swallowed, leaving the task running and shutdown hung forever. Re-issuing the
    request until the task is done makes shutdown deterministic.
    """
    while not task.done():
        task.cancel()
        await asyncio.wait({task}, timeout=retry_s)
    if not task.cancelled() and (exc := task.exception()) is not None:
        raise exc
