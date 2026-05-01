"""GENERATE job handler.

Payload schema:
  inference_id: str (UUID)
  generation_id: str (UUID)
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.inferences import Inference
from src.loop.email import send_generate_complete_email
from src.loop.generate.engine import run_generate
from src.loop.generate.repository import mark_generate_error, save_generate_result
from src.worker.utils import safe_rollback

logger = logging.getLogger(__name__)


async def handle_generate(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    inference_id = uuid.UUID(payload["inference_id"])
    generation_id = uuid.UUID(payload["generation_id"])

    # Load inference row
    inference = (
        await db.execute(select(Inference).where(Inference.id == inference_id))
    ).scalar_one_or_none()
    if inference is None:
        raise ValueError(f"Inference {inference_id} not found")

    # Load prompt templates from the analysis
    rows = (
        await db.execute(
            text("SELECT prompt_templates FROM analyses WHERE id = :aid"),
            {"aid": str(inference.analysis_id)},
        )
    ).fetchone()
    prompt_templates: list[dict[str, Any]] = (rows[0] or []) if rows else []

    # Get sample chunks from HARVEST (top 5)
    chunk_rows = (
        await db.execute(
            text("SELECT content FROM chunks WHERE inference_id = :inf LIMIT 5"),
            {"inf": str(inference_id)},
        )
    ).fetchall()
    sample_chunks = [r[0] for r in chunk_rows]

    try:
        result = await run_generate(
            inference_id=str(inference_id),
            domain=inference.domain or "other",
            tone=inference.tone or "professional",
            language=inference.language or "en",
            user_type=inference.user_type or "consumer",
            summary=inference.summary or "",
            prompt_templates=prompt_templates,
            sample_chunks=sample_chunks,
        )
        await save_generate_result(db, generation_id, result)

        logger.info(
            "GENERATE complete: %d variants, %d eval pairs for inference_id=%s",
            len(result.prompt_variants),
            len(result.eval_pairs),
            inference_id,
        )

        try:
            user_row = (
                await db.execute(
                    text(
                        "SELECT u.email, r.github_url"
                        " FROM users u"
                        " JOIN repos r ON r.user_id = u.id"
                        " JOIN analyses a ON a.repo_id = r.id"
                        " WHERE a.id = CAST(:aid AS UUID)"
                        " AND u.id = CAST(:uid AS UUID)"
                    ),
                    {"aid": str(inference.analysis_id), "uid": str(owner_user_id)},
                )
            ).fetchone()
            if user_row and user_row[0]:
                await send_generate_complete_email(
                    user_email=user_row[0],
                    domain=inference.domain or "unknown",
                    repo_url=user_row[1] or "",
                )
        except Exception as exc:
            logger.debug("Failed to send generate-complete email: %s", exc)

        return {
            "generation_id": str(generation_id),
            "variant_count": len(result.prompt_variants),
            "eval_pair_count": len(result.eval_pairs),
            "rag_strategy": result.rag_config.chunking_strategy,
        }
    except Exception as exc:
        await safe_rollback(db)
        await mark_generate_error(db, generation_id, str(exc))
        raise
