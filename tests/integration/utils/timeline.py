"""Timeline report generator — reads verum_jobs and produces human-readable Markdown."""
from __future__ import annotations
import textwrap
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def build(db: AsyncSession, output_path: Path) -> str:
    """Query verum_jobs and write timeline.md. Returns rendered text."""
    result = await db.execute(
        text(
            "SELECT kind, status, created_at, started_at, finished_at, attempts "
            "FROM verum_jobs ORDER BY created_at"
        )
    )
    rows = result.fetchall()

    lines = ["# Verum Loop Integration — Timeline\n"]
    lines.append(f"Total jobs: {len(rows)}\n")
    lines.append("| Stage | Status | Created | Duration | Attempts |")
    lines.append("|---|---|---|---|---|")

    for row in rows:
        kind, status, created_at, started_at, finished_at, attempts = row
        duration = ""
        if started_at and finished_at:
            delta = finished_at - started_at
            duration = f"{delta.total_seconds():.1f}s"
        elif started_at:
            duration = "running…"
        created_str = created_at.strftime("%H:%M:%S") if created_at else "—"
        lines.append(f"| {kind} | {status} | {created_str} | {duration} | {attempts} |")

    rendered = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered)
    return rendered
