"""RETRIEVE job handler.

Payload schema:
  inference_id: str (UUID)
  query: str
  hybrid: bool  (default True)
  top_k: int    (default 5)
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.harvest.embedder import embed_texts
from src.loop.harvest.repository import text_search, vector_search


async def handle_retrieve(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    inference_id = uuid.UUID(payload["inference_id"])
    query: str = payload["query"]
    hybrid: bool = payload.get("hybrid", True)
    top_k: int = int(payload.get("top_k", 5))

    if hybrid:
        embeddings = await embed_texts([query])
        vector_results = await vector_search(db, inference_id, embeddings[0], top_k=top_k)
        text_results = await text_search(db, inference_id, query, top_k=top_k)
        # Merge: interleave and dedupe by content, prefer higher score
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for r in sorted(vector_results + text_results, key=lambda x: -x["score"]):
            if r["content"] not in seen:
                seen.add(str(r["content"]))
                merged.append(r)
        results = merged[:top_k]
    else:
        embeddings = await embed_texts([query])
        results = await vector_search(db, inference_id, embeddings[0], top_k=top_k)

    return {
        "results": [{"content": r["content"], "score": r["score"]} for r in results],
        "total_chunks": len(results),
    }
