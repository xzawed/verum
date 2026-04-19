"""CLI entry point for the ANALYZE stage — F-1.G dogfood target.

Usage:
    python -m src.loop.analyze.cli --repo https://github.com/xzawed/ArcanaInsight
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Annotated

import typer

from .pipeline import run_analysis

app = typer.Typer(add_completion=False)


@app.command()
def main(
    repo: Annotated[str, typer.Option("--repo", help="GitHub repository URL")],
    branch: Annotated[str, typer.Option("--branch", help="Branch to analyze")] = "main",
) -> None:
    """Run Verum ANALYZE on a GitHub repository and print the result as JSON."""
    result = asyncio.run(_run(repo, branch))
    print(json.dumps(result.model_dump(mode="json"), indent=2, default=str))


async def _run(repo_url: str, branch: str):  # type: ignore[return]
    return await run_analysis(repo_url, branch=branch, repo_id=uuid.uuid4())


if __name__ == "__main__":
    app()
