"""Database I/O for the HARVEST stage."""
from __future__ import annotations

import uuid

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.enums import HarvestSourceStatus
from src.db.models.chunks import Chunk
from src.db.models.harvest_sources import HarvestSource

# Embedding dimension is fixed at 1024 per Voyage AI model specifications.
# This constant is part of the data model contract and is safe to embed in SQL templates.
EMBEDDING_DIM = 1024


async def get_approved_sources(
    db: AsyncSession,
    inference_id: uuid.UUID,
) -> list[HarvestSource]:
    stmt = select(HarvestSource).where(
        HarvestSource.inference_id == inference_id,
        HarvestSource.status == HarvestSourceStatus.APPROVED,
    )
    return list((await db.execute(stmt)).scalars().all())


async def mark_source_crawling(db: AsyncSession, source_id: uuid.UUID) -> None:
    await db.execute(
        update(HarvestSource).where(HarvestSource.id == source_id).values(status=HarvestSourceStatus.CRAWLING)
    )
    await db.commit()


async def mark_source_done(db: AsyncSession, source_id: uuid.UUID, chunks_count: int) -> None:
    await db.execute(
        update(HarvestSource)
        .where(HarvestSource.id == source_id)
        .values(status=HarvestSourceStatus.DONE, chunks_count=chunks_count)
    )
    await db.commit()


async def mark_source_error(db: AsyncSession, source_id: uuid.UUID, error: str) -> None:
    from src.db.error_helpers import mark_error
    await mark_error(db, HarvestSource, source_id, error)


async def save_chunks(
    db: AsyncSession,
    source_id: uuid.UUID,
    inference_id: uuid.UUID,
    texts: list[str],
    embeddings: list[list[float]],
) -> int:
    chunk_ids: list[uuid.UUID] = []
    for idx, (text_content, embedding) in enumerate(zip(texts, embeddings)):
        cid = uuid.uuid4()
        chunk_ids.append(cid)
        db.add(Chunk(
            id=cid,
            source_id=source_id,
            inference_id=inference_id,
            content=text_content,
            chunk_index=idx,
            metadata_={"source_id": str(source_id), "chunk_index": idx},
        ))

    await db.flush()
    if chunk_ids:
        row_params: dict[str, str] = {}
        value_placeholders: list[str] = []
        for i, (cid, emb) in enumerate(zip(chunk_ids, embeddings)):
            id_key = f"id{i}"
            vec_key = f"vec{i}"
            row_params[id_key] = str(cid)
            row_params[vec_key] = "[" + ",".join(str(v) for v in emb) + "]"
            value_placeholders.append(f"(cast(:{id_key} as uuid), cast(:{vec_key} as vector({EMBEDDING_DIM})))")

        await db.execute(
            text(
                "UPDATE chunks SET embedding_vec = v.vec"
                " FROM (VALUES " + ", ".join(value_placeholders) + ") AS v(id, vec)"  # nosec B608
                " WHERE chunks.id = v.id"
            ),
            row_params,
        )

    # Do not commit here — the caller (harvest handler) owns the transaction
    # and commits chunks + quota update + next-job enqueue atomically.
    return len(texts)


async def count_chunks(db: AsyncSession, inference_id: uuid.UUID) -> int:
    result = await db.execute(
        text("SELECT COUNT(*) FROM chunks WHERE inference_id = :id"),
        {"id": str(inference_id)},
    )
    row = result.fetchone()
    return int(row[0]) if row else 0


async def vector_search(
    db: AsyncSession,
    inference_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict[str, object]]:
    """Search for chunks by vector similarity.

    Uses parameterized SQL to prevent SQL injection. The embedding vector is
    passed as a bound parameter instead of being interpolated into the SQL text.

    Args:
        db: Database session.
        inference_id: Inference ID to filter chunks.
        query_embedding: Query vector (1024 dimensions).
        top_k: Number of results to return.

    Returns:
        List of chunks with similarity scores, sorted by relevance descending.
    """
    vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    result = await db.execute(
        text(
            "SELECT id, content, 1 - (embedding_vec <=> cast(:vec as vector(" + str(EMBEDDING_DIM) + "))) AS score "  # nosec B608
            "FROM chunks WHERE inference_id = :inf_id AND embedding_vec IS NOT NULL "
            "ORDER BY embedding_vec <=> cast(:vec as vector(" + str(EMBEDDING_DIM) + ")) "  # nosec B608
            "LIMIT :k"
        ),
        {"vec": vec_str, "inf_id": str(inference_id), "k": top_k},
    )
    return [
        {"chunk_id": str(r[0]), "content": r[1], "score": float(r[2])}
        for r in result.fetchall()
    ]


async def text_search(
    db: AsyncSession,
    inference_id: uuid.UUID,
    query: str,
    top_k: int = 5,
) -> list[dict[str, object]]:
    result = await db.execute(
        text(
            "SELECT id, content, ts_rank(ts_content, plainto_tsquery('english', :q)) AS score "
            "FROM chunks WHERE inference_id = :inf_id AND ts_content @@ plainto_tsquery('english', :q) "
            "ORDER BY score DESC LIMIT :k"
        ),
        {"q": query, "inf_id": str(inference_id), "k": top_k},
    )
    return [
        {"chunk_id": str(r[0]), "content": r[1], "score": float(r[2])}
        for r in result.fetchall()
    ]
