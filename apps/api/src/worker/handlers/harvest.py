"""HARVEST job handler.

Payload schema:
  inference_id: str (UUID)
  source_ids: list of [source_id_str, url_str] pairs
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.generate.repository import create_pending_generation
from src.loop.harvest.pipeline import harvest_source
from src.worker.chain import enqueue_next

logger = logging.getLogger(__name__)


async def handle_harvest(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    inference_id = uuid.UUID(payload["inference_id"])
    source_pairs: list[list[str]] = payload["source_ids"]  # [[source_id, url], ...]

    total_chunks = 0
    results: list[dict[str, Any]] = []
    for source_id_str, url in source_pairs:
        source_id = uuid.UUID(source_id_str)
        try:
            count = await harvest_source(db, source_id, url, inference_id)
            total_chunks += count
            results.append({"source_id": source_id_str, "chunks": count, "status": "done"})
        except Exception as exc:
            results.append({"source_id": source_id_str, "error": str(exc), "status": "error"})

    # Chain HARVEST → GENERATE
    generation_id = uuid.uuid4()
    # create_pending_generation flushes and commits the generation row
    await create_pending_generation(db, inference_id, generation_id)
    # enqueue_next inserts the job without committing (caller owns commit)
    await enqueue_next(
        db,
        kind="generate",
        payload={"inference_id": str(inference_id), "generation_id": str(generation_id)},
        owner_user_id=owner_user_id,
    )
    await db.commit()

    logger.info(
        "HARVEST→GENERATE chain: enqueued generation_id=%s for inference_id=%s",
        generation_id,
        inference_id,
    )

    return {
        "inference_id": str(inference_id),
        "total_chunks": total_chunks,
        "sources": results,
    }
