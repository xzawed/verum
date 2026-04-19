"""Database I/O for the INFER stage."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.inferences import Inference
from src.db.models.harvest_sources import HarvestSource
from .models import ServiceInference


async def create_pending_inference(
    db: AsyncSession,
    repo_id: uuid.UUID,
    analysis_id: uuid.UUID,
) -> Inference:
    row = Inference(
        id=uuid.uuid4(),
        repo_id=repo_id,
        analysis_id=analysis_id,
        status="pending",
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(row)
    await db.flush()
    await db.commit()
    return row


async def save_inference_result(
    db: AsyncSession,
    inference_id: uuid.UUID,
    result: ServiceInference,
    raw: dict,
) -> None:
    stmt = select(Inference).where(Inference.id == inference_id)
    row = (await db.execute(stmt)).scalar_one()
    row.status = "done"
    row.domain = result.domain
    row.tone = result.tone
    row.language = result.language
    row.user_type = result.user_type
    row.confidence = result.confidence
    row.summary = result.summary
    row.raw_response = raw

    # Persist suggested harvest sources as proposed rows
    for src in result.suggested_sources:
        db.add(HarvestSource(
            id=uuid.uuid4(),
            inference_id=inference_id,
            url=src.url,
            title=src.title,
            description=src.description,
            status="proposed",
        ))

    await db.commit()


async def mark_inference_error(
    db: AsyncSession,
    inference_id: uuid.UUID,
    error: str,
) -> None:
    stmt = select(Inference).where(Inference.id == inference_id)
    row = (await db.execute(stmt)).scalar_one()
    row.status = "error"
    row.error = error[:1024]
    await db.commit()


async def get_inference(
    db: AsyncSession,
    inference_id: uuid.UUID,
) -> Inference | None:
    stmt = select(Inference).where(Inference.id == inference_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_analysis_inferences(
    db: AsyncSession,
    analysis_id: uuid.UUID,
) -> list[Inference]:
    stmt = (
        select(Inference)
        .where(Inference.analysis_id == analysis_id)
        .order_by(Inference.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_harvest_sources(
    db: AsyncSession,
    inference_id: uuid.UUID,
) -> list[HarvestSource]:
    stmt = select(HarvestSource).where(HarvestSource.inference_id == inference_id)
    return list((await db.execute(stmt)).scalars().all())


async def approve_source(
    db: AsyncSession,
    source_id: uuid.UUID,
) -> HarvestSource:
    stmt = select(HarvestSource).where(HarvestSource.id == source_id)
    row = (await db.execute(stmt)).scalar_one()
    row.status = "approved"
    await db.commit()
    return row


async def reject_source(
    db: AsyncSession,
    source_id: uuid.UUID,
) -> HarvestSource:
    stmt = select(HarvestSource).where(HarvestSource.id == source_id)
    row = (await db.execute(stmt)).scalar_one()
    row.status = "rejected"
    await db.commit()
    return row
