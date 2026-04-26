"""Verum SDK — connect your AI service to The Verum Loop."""
from __future__ import annotations

from typing import Any

from verum.client import Client

__version__ = "0.1.0"

# ── Module-level singleton for convenience functions ─────────────────────────

_default_client: Client | None = None


def _get_client() -> Client:
    global _default_client  # noqa: PLW0603
    if _default_client is None:
        _default_client = Client()
    return _default_client


async def retrieve(query: str, *, collection_name: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Retrieve knowledge chunks from the Verum RAG index.

    Convenience wrapper — equivalent to ``verum.Client().retrieve(...)``.

    Args:
        query: The search query.
        collection_name: The RAG collection to search.
        top_k: Number of chunks to return.

    Returns:
        List of chunk dicts with at least a "content" key.
    """
    return await _get_client().retrieve(query=query, collection_name=collection_name, top_k=top_k)


async def feedback(trace_id: str, score: int) -> None:
    """Record user feedback for a trace.

    Convenience wrapper — equivalent to ``verum.Client().feedback(...)``.

    Args:
        trace_id: The trace UUID returned by the SDK or /api/v1/traces.
        score: +1 (positive) or -1 (negative).
    """
    await _get_client().feedback(trace_id=trace_id, score=score)


__all__ = ["Client", "retrieve", "feedback"]
