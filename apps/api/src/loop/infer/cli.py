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
from typing import Annotated

import typer
from sqlalchemy import select

from src.db.models.analyses import Analysis
from src.db.session import AsyncSessionLocal
from src.loop.analyze.models import AnalysisResult
from .engine import run_infer
from .models import ServiceInference

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

    try:
        result = asyncio.run(_run(uid))
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    print(json.dumps(result.model_dump(mode="json"), indent=2, default=str))


async def _run(analysis_id: uuid_mod.UUID) -> ServiceInference:
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(Analysis).where(Analysis.id == analysis_id))
        ).scalar_one_or_none()

    if row is None:
        raise ValueError(f"analysis {analysis_id} not found in database")

    if row.status != "done":
        raise ValueError(f"analysis {analysis_id} has status '{row.status}', expected 'done'")

    ar = AnalysisResult(
        repo_id=row.repo_id,
        call_sites=row.call_sites or [],  # type: ignore[arg-type]
        prompt_templates=row.prompt_templates or [],  # type: ignore[arg-type]
        model_configs=row.model_configs or [],  # type: ignore[arg-type]
        language_breakdown=row.language_breakdown or {},  # type: ignore[arg-type]
        analyzed_at=row.analyzed_at,  # type: ignore[arg-type]
    )

    return await run_infer(ar, analysis_id=analysis_id)


if __name__ == "__main__":
    app()
