"""OpenAI text embedding wrapper for HARVEST stage."""
from __future__ import annotations

import os

import openai

_MODEL = "text-embedding-3-small"
_BATCH_SIZE = 100  # OpenAI allows up to 2048 inputs per call; keep modest


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using OpenAI text-embedding-3-small.

    Returns list of 1536-dim float vectors in the same order as input.

    Raises:
        RuntimeError: if OPENAI_API_KEY is not set.
        openai.APIError: on OpenAI API failure.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    client = openai.AsyncOpenAI(api_key=api_key)
    results: list[list[float]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        response = await client.embeddings.create(
            model=_MODEL,
            input=batch,
            encoding_format="float",
        )
        results.extend(item.embedding for item in response.data)

    return results
