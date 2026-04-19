"""Database I/O for the HARVEST stage."""
from __future__ import annotations

import uuid

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.chunks import Chunk
from src.db.models.harvest_sources import HarvestSource


async def get_approved_sources(
    db: AsyncSession,
    inference_id: uuid.UUID,
) -> list[HarvestSource]:
    stmt = select(HarvestSource).where(
        HarvestSource.inference_id == inference_id,
        HarvestSource.status == "approved",
    )
    return list((await db.execute(stmt)).scalars().all())


async def mark_source_crawling(db: AsyncSession, source_id: uuid.UUID) -> None:
    await db.execute(
        update(HarvestSource).where(HarvestSource.id == source_id).values(status="crawling")
    )
    await db.commit()


async def mark_source_done(db: AsyncSession, source_id: uuid.UUID, chunks_count: int) -> None:
    await db.execute(
        update(HarvestSource)
        .where(HarvestSource.id == source_id)
        .values(status="done", chunks_count=chunks_count)
    )
    await db.commit()


async def mark_source_error(db: AsyncSession, source_id: uuid.UUID, error: str) -> None:
    await db.execute(
        update(HarvestSource)
        .where(HarvestSource.id == source_id)
        .values(status="error", error=error[:1024])
    )
    await db.commit()


async def save_chunks(
    db: AsyncSession,
    source_id: uuid.UUID,
    inference_id: uuid.UUID,
    texts: list[str],
    embeddings: list[list[float]],
) -> int:
    for idx, (text_content, embedding) in enumerate(zip(texts, embeddings)):
        chunk = Chunk(
            id=uuid.uuid4(),
            source_id=source_id,
            inference_id=inference_id,
            content=text_content,
            chunk_index=idx,
            embedding=embedding,
            metadata_={"source_id": str(source_id), "chunk_index": idx},
        )
        db.add(chunk)
        # Also update the pgvector column via raw SQL after flush
        await db.flush()
        vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
        await db.execute(
            text("UPDATE chunks SET embedding_vec = :vec WHERE id = :id"),
            {"vec": vec_str, "id": str(chunk.id)},
        )

    await db.commit()
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
    dim = len(query_embedding)
    vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    result = await db.execute(
        text(
            f"SELECT id, content, 1 - (embedding_vec <=> :vec::vector({dim})) AS score "
            "FROM chunks WHERE inference_id = :inf_id AND embedding_vec IS NOT NULL "
            f"ORDER BY embedding_vec <=> :vec::vector({dim}) "
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
