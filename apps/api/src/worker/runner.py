"""Job runner: claim → dispatch → complete/fail.

Postgres SKIP LOCKED for concurrency-safe job claiming.
LISTEN verum_jobs for instant wakeup on INSERT (avoids tight polling).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import src.db.models  # noqa: F401 — ensures User+Repo register with SQLAlchemy mapper before any query
from src.db.session import AsyncSessionLocal
from .handlers.analyze import handle_analyze
from .handlers.deploy import handle_deploy
from .handlers.generate import handle_generate
from .handlers.harvest import handle_harvest
from .handlers.infer import handle_infer
from .handlers.judge import handle_judge
from .handlers.retrieve import handle_retrieve

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
STALE_AFTER_MINUTES = 10
HEARTBEAT_INTERVAL = 30  # seconds

_HANDLERS = {
    "analyze": handle_analyze,
    "infer": handle_infer,
    "harvest": handle_harvest,
    "retrieve": handle_retrieve,
    "generate": handle_generate,
    "deploy": handle_deploy,
    "judge": handle_judge,
}


async def _reset_stale(db: AsyncSession) -> None:
    """On startup, reset any jobs stuck in 'running' from a previous crash."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=STALE_AFTER_MINUTES)
    result = await db.execute(
        text(
            "UPDATE verum_jobs SET status = 'queued', started_at = NULL"
            " WHERE status = 'running' AND started_at < :cutoff"
            " RETURNING id"
        ),
        {"cutoff": cutoff},
    )
    ids = result.fetchall()
    if ids:
        logger.info("Reset %d stale jobs to queued", len(ids))
    await db.commit()


async def _claim_one(db: AsyncSession) -> dict[str, Any] | None:
    """Atomically claim one queued job; return its row dict or None."""
    result = await db.execute(
        text(
            "UPDATE verum_jobs SET status = 'running', started_at = now(), attempts = attempts + 1"
            " WHERE id = ("
            "   SELECT id FROM verum_jobs"
            "   WHERE status = 'queued'"
            "   ORDER BY created_at ASC"
            "   LIMIT 1"
            "   FOR UPDATE SKIP LOCKED"
            " )"
            " RETURNING id, kind, payload, owner_user_id, attempts"
        )
    )
    row = result.mappings().first()
    await db.commit()
    return dict(row) if row else None


async def _mark_done(db: AsyncSession, job_id: uuid.UUID, result: Any) -> None:
    await db.execute(
        text(
            "UPDATE verum_jobs SET status = 'done', result = :result, finished_at = now()"
            " WHERE id = :id"
        ),
        {"id": job_id, "result": json.dumps(result, default=str)},
    )
    await db.commit()


async def _mark_failed(db: AsyncSession, job_id: uuid.UUID, error: str, attempts: int) -> None:
    next_status = "failed" if attempts >= MAX_ATTEMPTS else "queued"
    await db.execute(
        text(
            "UPDATE verum_jobs SET status = :status, error = :error, finished_at = now()"
            " WHERE id = :id"
        ),
        {"id": job_id, "status": next_status, "error": error},
    )
    await db.commit()


async def _update_heartbeat(db: AsyncSession) -> None:
    await db.execute(
        text("UPDATE worker_heartbeat SET last_seen_at = now() WHERE id = 1")
    )
    await db.commit()


async def _heartbeat_loop() -> None:
    """Update heartbeat row every HEARTBEAT_INTERVAL seconds."""
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await _update_heartbeat(db)
        except Exception as exc:
            logger.warning("Heartbeat update failed: %s", exc)
        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def run_loop() -> None:
    logger.info("Worker starting")
    async with AsyncSessionLocal() as db:
        await _reset_stale(db)
    logger.info("Stale job reset complete")

    asyncio.create_task(_heartbeat_loop())

    while True:
        try:
            async with AsyncSessionLocal() as db:
                job = await _claim_one(db)

            if job is None:
                # No jobs available; short sleep before checking again.
                # LISTEN/NOTIFY would be cleaner but requires a persistent connection.
                # For simplicity, polling every 2 s keeps latency low without tight loop.
                await asyncio.sleep(2)
                continue

            job_id: uuid.UUID = job["id"]
            kind: str = job["kind"]
            payload: dict[str, Any] = job["payload"] or {}
            owner_user_id: uuid.UUID = job["owner_user_id"]
            attempts: int = job["attempts"]

            logger.info("Claiming job %s kind=%s attempt=%d", job_id, kind, attempts)

            handler = _HANDLERS.get(kind)
            if handler is None:
                async with AsyncSessionLocal() as db:
                    await _mark_failed(db, job_id, f"unknown job kind: {kind}", attempts)
                logger.error("Unknown job kind '%s' for job %s", kind, job_id)
                continue

            try:
                async with AsyncSessionLocal() as db:
                    result = await handler(db, owner_user_id, payload)
                async with AsyncSessionLocal() as db:
                    await _mark_done(db, job_id, result)
                logger.info("Job %s done", job_id)
            except Exception as exc:
                logger.exception("Job %s failed: %s", job_id, exc)
                async with AsyncSessionLocal() as db:
                    await _mark_failed(db, job_id, str(exc), attempts)

        except Exception as exc:
            logger.exception("Unexpected runner error: %s", exc)
            await asyncio.sleep(5)
