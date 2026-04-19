"""Voyage AI text embedding wrapper for HARVEST stage.

Uses the Voyage REST API (https://api.voyageai.com/v1/embeddings) via httpx
so no extra SDK dependency is needed — httpx is already required for crawling.
"""
from __future__ import annotations

import os

import httpx

_MODEL = "voyage-3.5"
_BASE_URL = "https://api.voyageai.com/v1/embeddings"
_BATCH_SIZE = 128  # Voyage documented per-request limit


async def embed_texts(
    texts: list[str],
    *,
    input_type: str = "document",
) -> list[list[float]]:
    """Embed a list of texts using Voyage voyage-3.5 (1024-dim).

    Args:
        texts: Texts to embed.
        input_type: "document" for chunk indexing, "query" for search queries.

    Returns:
        List of 1024-dim float vectors in the same order as input.

    Raises:
        RuntimeError: if VOYAGE_API_KEY is not set.
        httpx.HTTPStatusError: on Voyage API failure.
    """
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        raise RuntimeError("VOYAGE_API_KEY environment variable is not set")

    results: list[list[float]] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            response = await client.post(
                _BASE_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"input": batch, "model": _MODEL, "input_type": input_type},
            )
            response.raise_for_status()
            data = response.json()
            # Voyage returns {"data": [{"embedding": [...], "index": N}, ...]}
            ordered = sorted(data["data"], key=lambda x: x["index"])
            results.extend(item["embedding"] for item in ordered)

    return results
