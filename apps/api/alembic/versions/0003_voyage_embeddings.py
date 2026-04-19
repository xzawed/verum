"""Switch chunks.embedding_vec from vector(1536) to vector(1024) for Voyage-3.5.

Revision ID: 0003_voyage_embeddings
Revises: 0002_phase2_infer_harvest
Create Date: 2026-04-19

Safe to run because the chunks table is empty at the time of this migration
(Phase 2 merged today; no HARVEST has been triggered in production yet).
If running against a non-empty table, backfill embedding_vec manually after
upgrading using apps/api/scripts/reembed_to_voyage.py (see plan notes).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003_voyage_embeddings"
down_revision: Union[str, None] = "0002_phase2_infer_harvest"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_vec")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS embedding_vec")
    op.execute("ALTER TABLE chunks ADD COLUMN embedding_vec vector(1024)")
    op.execute(
        "CREATE INDEX ix_chunks_embedding_vec ON chunks "
        "USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_vec")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS embedding_vec")
    op.execute("ALTER TABLE chunks ADD COLUMN embedding_vec vector(1536)")
    op.execute(
        "CREATE INDEX ix_chunks_embedding_vec ON chunks "
        "USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 100)"
    )
