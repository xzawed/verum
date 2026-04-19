"""HARVEST job handler.

Payload schema:
  inference_id: str (UUID)
  source_ids: list of [source_id_str, url_str] pairs
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.harvest.pipeline import harvest_source


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

    return {
        "inference_id": str(inference_id),
        "total_chunks": total_chunks,
        "sources": results,
    }
