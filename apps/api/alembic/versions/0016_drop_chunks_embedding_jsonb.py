"""Drop chunks.embedding JSONB column — superseded by embedding_vec (pgvector).

Revision ID: 0016_drop_chunks_embedding_jsonb
Revises: 0015_notify_trigger
Create Date: 2026-04-24

The JSONB embedding column was a transitional store before the pgvector
column (embedding_vec) was ready. All reads/writes now use embedding_vec
exclusively. Dropping the JSONB column reclaims storage and removes the
dual-write surface.

Downgrade restores the column as nullable JSONB with no data.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0016_drop_chunks_embedding_jsonb"
down_revision: str = "0015_notify_trigger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("chunks", "embedding")


def downgrade() -> None:
    op.add_column(
        "chunks",
        sa.Column("embedding", JSONB(), nullable=True),
    )
