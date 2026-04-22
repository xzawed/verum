"""HARVEST pipeline: crawl approved sources → chunk → embed → store."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

import src.config as cfg
from .chunker import recursive_split, semantic_split
from .crawler import CrawlError, fetch_and_extract
from .embedder import embed_texts
from .repository import (
    mark_source_crawling,
    mark_source_done,
    mark_source_error,
    save_chunks,
)


async def harvest_source(
    db: AsyncSession,
    source_id: uuid.UUID,
    source_url: str,
    inference_id: uuid.UUID,
    *,
    chunk_size: int = cfg.CHUNK_SIZE,
    overlap: int = cfg.CHUNK_OVERLAP,
    chunking_strategy: str = "recursive",
) -> int:
    """Crawl one approved source, chunk, embed, and store.

    Returns number of chunks stored.
    """
    await mark_source_crawling(db, source_id)

    try:
        text = await fetch_and_extract(source_url)
    except CrawlError as exc:
        await mark_source_error(db, source_id, f"{exc.kind}: {exc}")
        return 0

    if not text.strip():
        await mark_source_error(db, source_id, "empty content after extraction")
        return 0

    split_fn = semantic_split if chunking_strategy == "semantic" else recursive_split
    chunks = split_fn(text, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        await mark_source_error(db, source_id, "no chunks produced after split")
        return 0

    try:
        embeddings = await embed_texts(chunks)
    except Exception as exc:
        await mark_source_error(db, source_id, f"embedding failed: {exc}")
        return 0

    count = await save_chunks(db, source_id, inference_id, chunks, embeddings)
    await mark_source_done(db, source_id, count)
    return count
