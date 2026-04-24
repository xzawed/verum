"""HARVEST job handler.

Payload schema:
  inference_id: str (UUID)
  source_ids: list of [source_id_str, url_str] pairs
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.email import send_quota_warning_email
from src.loop.generate.repository import create_pending_generation
from src.loop.harvest.pipeline import harvest_source
from src.loop.quota import FREE_LIMITS, QuotaExceededError, get_or_create_quota, increment_quota
from src.worker.chain import enqueue_next

logger = logging.getLogger(__name__)


async def handle_harvest(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    inference_id = uuid.UUID(payload["inference_id"])
    source_pairs: list[list[str]] = payload["source_ids"]  # [[source_id, url], ...]
    chunking_strategy: str = payload.get("chunking_strategy", "recursive")
    use_playwright: bool = bool(payload.get("use_playwright", False))

    sem = asyncio.Semaphore(3)

    async def _harvest_one(source_id_str: str, url: str) -> dict[str, Any]:
        source_id = uuid.UUID(source_id_str)
        async with sem:
            try:
                count = await harvest_source(
                    db, source_id, url, inference_id,
                    chunking_strategy=chunking_strategy,
                    use_playwright=use_playwright,
                )
                return {"source_id": source_id_str, "chunks": count, "status": "done"}
            except Exception as exc:
                return {"source_id": source_id_str, "error": str(exc), "status": "error"}

    results: list[dict[str, Any]] = list(await asyncio.gather(
        *[_harvest_one(sid, url) for sid, url in source_pairs],
        return_exceptions=False,
    ))
    total_chunks = sum(r.get("chunks", 0) for r in results)

    successful_sources = sum(1 for r in results if r["status"] == "done")
    if successful_sources == 0 or total_chunks == 0:
        raise RuntimeError(
            f"HARVEST produced no usable content: {successful_sources}/{len(source_pairs)} "
            f"sources succeeded, {total_chunks} chunks total — GENERATE skipped"
        )

    # Quota enforcement (free tier)
    # commit=False: defer to single commit at end of handler (P0-7 fix)
    quota = await get_or_create_quota(db, owner_user_id, commit=False)
    if quota["plan"] == "free":
        if quota["chunks_stored"] + total_chunks > FREE_LIMITS["chunks"]:
            raise QuotaExceededError("chunks", quota["chunks_stored"], FREE_LIMITS["chunks"])
        pct = (quota["chunks_stored"] + total_chunks) / FREE_LIMITS["chunks"]
        if pct >= 0.8:
            user_row = await db.execute(
                text("SELECT email FROM users WHERE id = :uid"),
                {"uid": str(owner_user_id)},
            )
            user = user_row.mappings().first()
            if user and user["email"]:
                send_quota_warning_email(user["email"], "chunks", pct)

    # Chain HARVEST → GENERATE
    generation_id = uuid.uuid4()
    # commit=False: flush only — single commit covers quota+generation+job (P0-7 fix)
    await create_pending_generation(db, inference_id, generation_id, commit=False)
    # enqueue_next inserts the job without committing (caller owns commit)
    await enqueue_next(
        db,
        kind="generate",
        payload={"inference_id": str(inference_id), "generation_id": str(generation_id)},
        owner_user_id=owner_user_id,
    )
    # Increment after successful chain — committed with the job enqueue
    await increment_quota(db, owner_user_id, chunks=total_chunks)
    await db.commit()

    logger.info(
        "HARVEST→GENERATE chain: enqueued generation_id=%s for inference_id=%s",
        generation_id,
        inference_id,
    )

    return {
        "inference_id": str(inference_id),
        "total_chunks": total_chunks,
        "successful_sources": successful_sources,
        "sources": results,
    }
