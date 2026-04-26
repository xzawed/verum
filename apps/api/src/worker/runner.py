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

import src.config as cfg
import src.db.models  # noqa: F401 — ensures User+Repo register with SQLAlchemy mapper before any query
from src.db.enums import JobStatus
from src.db.session import AsyncSessionLocal, get_db_for_user
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

MAX_ATTEMPTS = cfg.JOB_MAX_ATTEMPTS
STALE_AFTER_MINUTES = cfg.JOB_STALE_AFTER_MINUTES
HEARTBEAT_INTERVAL = cfg.HEARTBEAT_INTERVAL_SECS
EXPERIMENT_INTERVAL: int = int(os.environ.get("VERUM_EXPERIMENT_INTERVAL_SECONDS", "300"))
if EXPERIMENT_INTERVAL <= 0:
    raise RuntimeError(
        f"VERUM_EXPERIMENT_INTERVAL_SECONDS must be a positive integer, got {EXPERIMENT_INTERVAL}"
    )
STALE_RESET_INTERVAL: int = int(os.environ.get("VERUM_STALE_RESET_INTERVAL_SECONDS", "300"))

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
    """On startup and periodically, reset jobs and sources stuck from a previous crash."""
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

    # Reset harvest_sources stuck in CRAWLING (worker killed between mark_crawling and mark_done).
    # Uses created_at as proxy because the model has no updated_at column.
    src_result = await db.execute(
        text(
            "UPDATE harvest_sources SET status = 'error',"
            " error = 'reset: worker restart detected'"
            " WHERE status = 'crawling' AND created_at < :cutoff"
            " RETURNING id"
        ),
        {"cutoff": cutoff},
    )
    src_ids = src_result.fetchall()
    if src_ids:
        logger.info("Reset %d stale harvest_sources to error", len(src_ids))

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
    next_status = JobStatus.FAILED if attempts >= MAX_ATTEMPTS else JobStatus.QUEUED
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


_heartbeat_failures: int = 0
MAX_HEARTBEAT_FAILURES: int = int(os.environ.get("VERUM_MAX_HEARTBEAT_FAILURES", "5"))


async def _heartbeat_loop() -> None:
    """Update heartbeat row every HEARTBEAT_INTERVAL seconds.

    Exits the process after MAX_HEARTBEAT_FAILURES consecutive failures so the
    container restarts instead of running as a silent zombie.
    """
    global _heartbeat_failures
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await _update_heartbeat(db)
            _heartbeat_failures = 0
        except Exception as exc:
            _heartbeat_failures += 1
            logger.warning(
                "Heartbeat update failed (%d/%d): %s",
                _heartbeat_failures, MAX_HEARTBEAT_FAILURES, exc,
            )
            if _heartbeat_failures >= MAX_HEARTBEAT_FAILURES:
                logger.critical(
                    "Heartbeat max failures reached (%d) — shutting down worker",
                    MAX_HEARTBEAT_FAILURES,
                )
                os._exit(1)
        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def _stale_reset_loop() -> None:
    """Periodically reset stuck running jobs back to queued (every STALE_RESET_INTERVAL seconds).

    Complements the one-time reset at startup: handles cases where a peer worker
    crashed after the current worker started and no restart is imminent.
    """
    while True:
        await asyncio.sleep(STALE_RESET_INTERVAL)
        try:
            async with AsyncSessionLocal() as db:
                await _reset_stale(db)
        except Exception as exc:
            logger.warning("Periodic stale reset failed: %s", exc)


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
                            # Resolve owner_user_id before INSERT to catch NULL and
                            # raise explicitly rather than silently drop the evolve job.
                            owner_row = (
                                await db.execute(
                                    text(
                                        "SELECT r.owner_user_id FROM repos r"
                                        " JOIN inferences inf ON inf.repo_id = r.id"
                                        " JOIN generations gen ON gen.inference_id = inf.id"
                                        " JOIN deployments dep ON dep.generation_id = gen.id"
                                        " WHERE dep.id = :did LIMIT 1"
                                    ),
                                    {"did": str(deployment_id)},
                                )
                            ).mappings().first()
                            if owner_row is None or owner_row["owner_user_id"] is None:
                                raise RuntimeError(
                                    f"Cannot enqueue EVOLVE for experiment {exp['id']}: "
                                    f"deployment {deployment_id} has no resolvable owner_user_id"
                                )
                            evolve_owner_user_id = owner_row["owner_user_id"]
                            await db.execute(
                                text(
                                    "INSERT INTO verum_jobs (kind, payload, status, owner_user_id)"
                                    " VALUES ("
                                    "   'evolve',"
                                    "   jsonb_build_object("
                                    "     'experiment_id', :eid::text,"
                                    "     'deployment_id', :did::text,"
                                    "     'winner_variant', :wv::text,"
                                    "     'confidence', :conf::double precision,"
                                    "     'current_challenger', :cv::text"
                                    "   ),"
                                    "   'queued',"
                                    "   :owner_uid::uuid"
                                    " )"
                                    " ON CONFLICT ((payload->>'experiment_id'))"
                                    " WHERE kind = 'evolve' AND status IN ('queued', 'running')"
                                    " DO NOTHING"
                                ),
                                {
                                    "eid": str(exp["id"]),
                                    "did": str(deployment_id),
                                    "wv": result.winner_variant,
                                    "conf": result.confidence,
                                    "cv": exp["challenger_variant"],
                                    "owner_uid": str(evolve_owner_user_id),
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
        # RLS context: app.current_user_id set for the handler's session so
        # that once FORCE ROW LEVEL SECURITY is active (migration 0022) the
        # worker only sees rows owned by owner_user_id.
        async with get_db_for_user(str(owner_user_id)) as db:
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
    for _coro in (_heartbeat_loop(), _stale_reset_loop(), _experiment_loop()):
        _t = asyncio.create_task(_coro)
        _bg_tasks.add(_t)
        _t.add_done_callback(_bg_tasks.discard)
    logger.info(
        "Background loops started — experiment=%ds stale_reset=%ds heartbeat=%ds",
        EXPERIMENT_INTERVAL, STALE_RESET_INTERVAL, HEARTBEAT_INTERVAL,
    )

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
                    await asyncio.wait_for(_wake_event.wait(), timeout=cfg.WORKER_POLL_TIMEOUT_SECS)
                except asyncio.TimeoutError:
                    pass
                _wake_event.clear()
                continue

            await _dispatch_job(job)

        except Exception as exc:
            logger.exception("Unexpected runner error: %s", exc)
            await asyncio.sleep(5)
