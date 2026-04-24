"""Polling helpers for integration tests."""
from __future__ import annotations
import asyncio
from typing import Callable, Any


async def wait_until(
    pred: Callable[[], Any],
    *,
    timeout: float = 60.0,
    interval: float = 1.0,
    min_interval: float = 0.1,
    label: str = "condition",
) -> Any:
    """Poll pred() until truthy or timeout. Returns the truthy value.

    Uses exponential backoff from min_interval up to interval to reduce
    unnecessary DB/HTTP round-trips during fast operations while still
    polling slowly for long-running jobs.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    first_exc: Exception | None = None
    last_exc: Exception | None = None
    current_interval = min_interval
    while loop.time() < deadline:
        try:
            result = await pred() if asyncio.iscoroutinefunction(pred) else pred()
            if result:
                return result
        except Exception as exc:
            if first_exc is None:
                first_exc = exc
            last_exc = exc
        await asyncio.sleep(min(current_interval, interval))
        current_interval = min(current_interval * 2, interval)
    msg = f"Timed out waiting for {label!r} after {timeout}s."
    if first_exc:
        msg += f" First error: {first_exc}"
    if last_exc and last_exc is not first_exc:
        msg += f" Last error: {last_exc}"
    raise TimeoutError(msg)
