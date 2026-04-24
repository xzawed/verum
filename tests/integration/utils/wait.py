"""Polling helpers for integration tests."""
from __future__ import annotations
import asyncio
from typing import Callable, Any


async def wait_until(
    pred: Callable[[], Any],
    *,
    timeout: float = 60.0,
    interval: float = 1.0,
    label: str = "condition",
) -> Any:
    """Poll pred() until truthy or timeout. Returns the truthy value."""
    deadline = asyncio.get_event_loop().time() + timeout
    last_exc: Exception | None = None
    while asyncio.get_event_loop().time() < deadline:
        try:
            result = await pred() if asyncio.iscoroutinefunction(pred) else pred()
            if result:
                return result
        except Exception as exc:
            last_exc = exc
        await asyncio.sleep(interval)
    raise TimeoutError(
        f"Timed out waiting for {label!r} after {timeout}s."
        + (f" Last error: {last_exc}" if last_exc else "")
    )
