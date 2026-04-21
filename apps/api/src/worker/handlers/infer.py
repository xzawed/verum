"""INFER job handler.

Payload schema:
  analysis_id: str (UUID)
  inference_id: str (UUID)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.analyses import Analysis
from src.loop.analyze.models import AnalysisResult
from src.loop.infer.engine import run_infer
from src.loop.infer.repository import mark_inference_error, save_inference_result


async def handle_infer(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    analysis_id = uuid.UUID(payload["analysis_id"])
    inference_id = uuid.UUID(payload["inference_id"])

    analysis = (
        await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    ).scalar_one_or_none()
    if analysis is None:
        raise ValueError(f"Analysis {analysis_id} not found")

    # Reconstruct AnalysisResult from DB row to pass into engine
    ar = AnalysisResult(
        repo_id=analysis.repo_id,
        call_sites=analysis.call_sites or [],
        prompt_templates=analysis.prompt_templates or [],
        model_configs=analysis.model_configs or [],
        language_breakdown=analysis.language_breakdown or {},
        analyzed_at=analysis.analyzed_at or datetime.now(tz=timezone.utc),
    )

    try:
        result = await run_infer(ar, analysis_id=analysis_id)
        raw: dict[str, Any] = {
            "domain": result.domain,
            "tone": result.tone,
            "language": result.language,
            "user_type": result.user_type,
            "confidence": result.confidence,
            "summary": result.summary,
        }
        await save_inference_result(db, inference_id, result, raw)
        return {"inference_id": str(inference_id), "domain": result.domain}
    except Exception as exc:
        await mark_inference_error(db, inference_id, str(exc))
        raise
