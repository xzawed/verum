"""Job runner: claim → dispatch → complete/fail.

Postgres SKIP LOCKED for concurrency-safe job claiming.
LISTEN verum_jobs for instant wakeup on INSERT (avoids tight polling).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import src.db.models  # noqa: F401 — ensures User+Repo register with SQLAlchemy mapper before any query
from src.db.session import AsyncSessionLocal
from src.worker.payloads import (
    AnalyzePayload,
    DeployPayload,
    EvolvePayload,
    GeneratePayload,
    HarvestPayload,
    InferPayload,
    JudgePayload,
    RetrievePayload,
)
from .handlers.analyze import handle_analyze
from .handlers.deploy import handle_deploy
from .handlers.evolve import handle_evolve
from .handlers.generate import handle_generate
from .handlers.harvest import handle_harvest
from .handlers.infer import handle_infer
from .handlers.judge import handle_judge
from .handlers.retrieve import handle_retrieve

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
STALE_AFTER_MINUTES = 10
HEARTBEAT_INTERVAL = 30  # seconds
EXPERIMENT_INTERVAL: int = int(os.environ.get("VERUM_EXPERIMENT_INTERVAL_SECONDS", "300"))
if EXPERIMENT_INTERVAL <= 0:
    raise RuntimeError(
        f"VERUM_EXPERIMENT_INTERVAL_SECONDS must be a positive integer, got {EXPERIMENT_INTERVAL}"
    )

_HANDLERS = {
    "analyze": handle_analyze,
    "infer": handle_infer,
    "harvest": handle_harvest,
    "retrieve": handle_retrieve,
    "generate": handle_generate,
    "deploy": handle_deploy,
    "judge": handle_judge,
    "evolve": handle_evolve,
}

# Pydantic schema for each job kind — validated before dispatch.
_PAYLOAD_SCHEMAS = {
    "analyze": AnalyzePayload,
    "infer": InferPayload,
    "harvest": HarvestPayload,
    "generate": GeneratePayload,
    "deploy": DeployPayload,
    "judge": JudgePayload,
    "evolve": EvolvePayload,
    "retrieve": RetrievePayload,
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


async def _experiment_loop() -> None:
    """Periodic loop: check all running experiments and enqueue EVOLVE jobs on convergence."""
    from src.loop.experiment.engine import check_experiment
    from src.loop.experiment.repository import (
        aggregate_variant_wins,
        get_all_running_experiments,
        update_experiment_stats,
    )

    while True:
        await asyncio.sleep(EXPERIMENT_INTERVAL)
        try:
            async with AsyncSessionLocal() as db:
                experiments = await get_all_running_experiments(db)
                for exp in experiments:
                    try:
                        deployment_id = exp["deployment_id"]
                        b_wins, b_n, c_wins, c_n, _null_count = await aggregate_variant_wins(
                            db,
                            deployment_id,
                            exp["baseline_variant"],
                            exp["challenger_variant"],
                            exp["win_threshold"],
                        )
                        await update_experiment_stats(
                            db, exp["id"], b_wins, b_n, c_wins, c_n
                        )
                        result = check_experiment(
                            {
                                **exp,
                                "baseline_wins": b_wins,
                                "baseline_n": b_n,
                                "challenger_wins": c_wins,
                                "challenger_n": c_n,
                            },
                            max_cost_in_window=1.0,
                        )
                        if result.converged and result.winner_variant:
                            await db.execute(
                                text(
                                    "INSERT INTO verum_jobs (kind, payload, status, owner_user_id)"
                                    " SELECT 'evolve',"
                                    "   jsonb_build_object("
                                    "     'experiment_id', :eid::text,"
                                    "     'deployment_id', :did::text,"
                                    "     'winner_variant', :wv,"
                                    "     'confidence', :conf,"
                                    "     'current_challenger', :cv"
                                    "   ),"
                                    "   'queued',"
                                    "   (SELECT r.owner_user_id FROM repos r"
                                    "    JOIN inferences inf ON inf.repo_id = r.id"
                                    "    JOIN generations gen ON gen.inference_id = inf.id"
                                    "    JOIN deployments dep ON dep.generation_id = gen.id"
                                    "    WHERE dep.id = :did LIMIT 1)"
                                    " WHERE NOT EXISTS ("
                                    "   SELECT 1 FROM verum_jobs"
                                    "   WHERE kind = 'evolve'"
                                    "     AND (payload->>'experiment_id') = :eid::text"
                                    "     AND status IN ('queued', 'running')"
                                    " )"
                                    " ON CONFLICT DO NOTHING"
                                ),
                                {
                                    "eid": str(exp["id"]),
                                    "did": str(deployment_id),
                                    "wv": result.winner_variant,
                                    "conf": result.confidence,
                                    "cv": exp["challenger_variant"],
                                },
                            )
                            await db.commit()
                            logger.info(
                                "EXPERIMENT: enqueued EVOLVE for experiment %s winner=%s",
                                exp["id"],
                                result.winner_variant,
                            )
                    except Exception as exc:
                        logger.warning(
                            "EXPERIMENT: error checking experiment %s: %s",
                            exp.get("id"),
                            exc,
                        )
        except Exception as exc:
            logger.warning("EXPERIMENT loop error: %s", exc)


async def _dispatch_job(job: dict[str, Any]) -> None:
    """Validate and execute one claimed job; mark done or failed."""
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
        return

    schema = _PAYLOAD_SCHEMAS.get(kind)
    if schema is not None:
        try:
            schema(**payload)
        except Exception as exc:
            async with AsyncSessionLocal() as db:
                await _mark_failed(db, job_id, f"invalid payload for {kind}: {exc}", attempts)
            logger.error("Invalid payload for job %s kind=%s: %s", job_id, kind, exc)
            return

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


async def run_loop() -> None:
    logger.info("Worker starting")
    async with AsyncSessionLocal() as db:
        await _reset_stale(db)
    logger.info("Stale job reset complete")

    _bg_tasks: set[asyncio.Task[None]] = set()
    _bg_tasks.add(asyncio.create_task(_heartbeat_loop()))
    _bg_tasks.add(asyncio.create_task(_experiment_loop()))
    logger.info("Experiment loop started (interval=%ds)", EXPERIMENT_INTERVAL)

    from src.worker.listener import get_wake_event, start_listener
    await start_listener()
    logger.info("LISTEN/NOTIFY listener started")
    _wake_event = get_wake_event()

    while True:
        try:
            async with AsyncSessionLocal() as db:
                job = await _claim_one(db)

            if job is None:
                # Wait for NOTIFY wake or fall back to 1s timeout.
                try:
                    await asyncio.wait_for(_wake_event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                _wake_event.clear()
                continue

            await _dispatch_job(job)

        except Exception as exc:
            logger.exception("Unexpected runner error: %s", exc)
            await asyncio.sleep(5)
