"""Postgres LISTEN/NOTIFY listener — wakes the job runner on INSERT."""
from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

_wake_event: asyncio.Event | None = None
_listener_task: asyncio.Task[None] | None = None


def get_wake_event() -> asyncio.Event:
    """Return (or create) the shared wake event."""
    global _wake_event
    if _wake_event is None:
        _wake_event = asyncio.Event()
    return _wake_event


async def _listen_loop(dsn: str) -> None:  # pragma: no cover
    """Maintain a persistent asyncpg connection and set wake_event on NOTIFY."""
    import asyncpg  # type: ignore[import-untyped]

    wake = get_wake_event()
    while True:
        try:
            conn: asyncpg.Connection = await asyncpg.connect(dsn)

            def _on_notify(
                conn: asyncpg.Connection,
                pid: int,
                channel: str,
                payload: str,
            ) -> None:
                wake.set()

            await conn.add_listener("verum_jobs", _on_notify)
            logger.info("LISTEN/NOTIFY: listening on channel 'verum_jobs'")

            # Keep alive; short sleep to detect silent TCP disconnects quickly.
            while not conn.is_closed():
                await asyncio.sleep(5)

            await conn.close()
        except Exception as exc:
            logger.warning("LISTEN/NOTIFY: connection error (%s) — retrying in 5s", exc)
            await asyncio.sleep(5)


async def start_listener() -> None:
    """Start the background LISTEN loop. No-op if DATABASE_URL is not set."""
    global _listener_task
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        logger.warning("LISTEN/NOTIFY: DATABASE_URL not set, skipping listener startup")
        return
    # asyncpg.connect() requires "postgresql://" or "postgres://".
    # SQLAlchemy dialect URLs use "postgresql+asyncpg://" — strip the driver suffix.
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    _listener_task = asyncio.create_task(_listen_loop(dsn))
