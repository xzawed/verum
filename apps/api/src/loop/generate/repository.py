"""Database I/O for the GENERATE stage."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.generations import Generation
from src.loop.generate.models import GenerateResult


async def create_pending_generation(
    db: AsyncSession,
    inference_id: uuid.UUID,
    generation_id: uuid.UUID,
) -> None:
    db.add(Generation(
        id=generation_id,
        inference_id=inference_id,
        status="pending",
        created_at=datetime.now(tz=timezone.utc),
    ))
    await db.flush()
    await db.commit()


async def save_generate_result(
    db: AsyncSession,
    generation_id: uuid.UUID,
    result: GenerateResult,
) -> None:
    stmt = select(Generation).where(Generation.id == generation_id)
    row = (await db.execute(stmt)).scalar_one()
    row.status = "done"
    row.generated_at = datetime.now(tz=timezone.utc)

    for variant in result.prompt_variants:
        await db.execute(
            text(
                "INSERT INTO prompt_variants (id, generation_id, variant_type, content, variables)"
                " VALUES (:id, :gid, :vtype, :content, :vars::jsonb)"
            ),
            {
                "id": str(uuid.uuid4()),
                "gid": str(generation_id),
                "vtype": variant.variant_type,
                "content": variant.content,
                "vars": json.dumps(variant.variables),
            },
        )

    cfg = result.rag_config
    await db.execute(
        text(
            "INSERT INTO rag_configs (id, generation_id, chunking_strategy, chunk_size,"
            " chunk_overlap, top_k, hybrid_alpha)"
            " VALUES (:id, :gid, :strategy, :csize, :coverlap, :topk, :alpha)"
        ),
        {
            "id": str(uuid.uuid4()),
            "gid": str(generation_id),
            "strategy": cfg.chunking_strategy,
            "csize": cfg.chunk_size,
            "coverlap": cfg.chunk_overlap,
            "topk": cfg.top_k,
            "alpha": cfg.hybrid_alpha,
        },
    )

    for pair in result.eval_pairs:
        await db.execute(
            text(
                "INSERT INTO eval_pairs (id, generation_id, query, expected_answer, context_needed)"
                " VALUES (:id, :gid, :query, :answer, :ctx)"
            ),
            {
                "id": str(uuid.uuid4()),
                "gid": str(generation_id),
                "query": pair.query,
                "answer": pair.expected_answer,
                "ctx": pair.context_needed,
            },
        )

    await db.commit()


async def mark_generate_error(
    db: AsyncSession,
    generation_id: uuid.UUID,
    error: str,
) -> None:
    stmt = select(Generation).where(Generation.id == generation_id)
    row = (await db.execute(stmt)).scalar_one()
    row.status = "error"
    row.error = error[:1024]
    await db.commit()


async def get_generation_summary(
    db: AsyncSession,
    inference_id: uuid.UUID,
) -> dict[str, object] | None:
    """Return latest generation status + counts for a given inference."""
    result = await db.execute(
        text(
            "SELECT g.id, g.status, g.generated_at,"
            " (SELECT COUNT(*) FROM prompt_variants WHERE generation_id = g.id) AS variant_count,"
            " (SELECT COUNT(*) FROM eval_pairs WHERE generation_id = g.id) AS eval_count"
            " FROM generations g"
            " WHERE g.inference_id = :inf"
            " ORDER BY g.created_at DESC LIMIT 1"
        ),
        {"inf": str(inference_id)},
    )
    row = result.mappings().first()
    return dict(row) if row else None
