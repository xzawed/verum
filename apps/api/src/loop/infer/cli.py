"""CLI entry point for the INFER stage.

Usage:
    python -m src.loop.infer.cli --analysis-id <uuid>

Requires:
    DATABASE_URL      — Postgres connection string
    ANTHROPIC_API_KEY — Claude API key
"""
from __future__ import annotations

import asyncio
import json
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Annotated

import typer
from sqlalchemy import select

from src.db.models.analyses import Analysis
from src.db.session import AsyncSessionLocal
from src.loop.analyze.models import AnalysisResult
from src.loop.infer.engine import run_infer
from src.loop.infer.models import ServiceInference

app = typer.Typer(add_completion=False)


@app.command()
def main(
    analysis_id: Annotated[str, typer.Option("--analysis-id", help="UUID of an existing analysis row")],
) -> None:
    """Run Verum INFER on an existing analysis and print the result as JSON."""
    try:
        uid = uuid_mod.UUID(analysis_id)
    except ValueError:
        typer.echo(f"Error: '{analysis_id}' is not a valid UUID", err=True)
        raise typer.Exit(code=1)

    result = asyncio.run(_run(uid))
    print(json.dumps(result.model_dump(mode="json"), indent=2, default=str))


async def _run(analysis_id: uuid_mod.UUID) -> ServiceInference:
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(Analysis).where(Analysis.id == analysis_id))
        ).scalar_one_or_none()

    if row is None:
        typer.echo(f"Error: analysis {analysis_id} not found in database", err=True)
        raise typer.Exit(code=1)

    ar = AnalysisResult(
        repo_id=row.repo_id,
        call_sites=row.call_sites or [],
        prompt_templates=row.prompt_templates or [],
        model_configs=row.model_configs or [],
        language_breakdown=row.language_breakdown or {},
        analyzed_at=row.analyzed_at or datetime.now(tz=timezone.utc),
    )

    return await run_infer(ar, analysis_id=analysis_id)


if __name__ == "__main__":
    app()
