"""DB snapshot utilities for integration test diagnostics."""
from __future__ import annotations
import json
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

_TABLES = [
    "analyses",
    "inferences",
    "harvest_sources",
    "chunks",
    "generations",
    "eval_pairs",
    "deployments",
    "experiments",
    "traces",
    "verum_jobs",
]


async def dump(db: AsyncSession, path: Path) -> None:
    """Dump key table row counts and latest rows to JSONL for debugging."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for table in _TABLES:
        try:
            count_result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))  # nosec B608
            count = count_result.scalar_one()
            sample_result = await db.execute(
                text(f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT 5")  # nosec B608
            )
            cols = list(sample_result.keys())
            sample = [
                {col: (str(v) if not isinstance(v, (int, float, bool, type(None), str)) else v)
                 for col, v in zip(cols, r)}
                for r in sample_result.fetchall()
            ]
            rows.append({"table": table, "count": count, "sample": sample})
        except Exception as exc:  # noqa: BLE001
            await db.rollback()  # clear aborted txn so next table query works
            rows.append({"table": table, "error": str(exc)})

    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


async def assert_stage_counts(db: AsyncSession, expected: dict[str, int]) -> None:
    """Assert minimum row counts for given tables. expected = {'analyses': 1, ...}"""
    for table, min_count in expected.items():
        result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))  # nosec B608
        actual = result.scalar_one()
        assert actual >= min_count, f"Expected {min_count}+ rows in {table}, got {actual}"
