"""Phase 2 INFER + HARVEST tables: inferences, harvest_sources, chunks.

Revision ID: 0002_phase2_infer_harvest
Revises: 0001_phase1_analyze
Create Date: 2026-04-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0002_phase2_infer_harvest"
down_revision: Union[str, None] = "0001_phase1_analyze"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "inferences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("repo_id", UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("domain", sa.String(64), nullable=True),
        sa.Column("tone", sa.String(32), nullable=True),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("user_type", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("raw_response", JSONB, nullable=True),
        sa.Column("error", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_inferences_analysis_id", "inferences", ["analysis_id"])
    op.create_index("ix_inferences_repo_id", "inferences", ["repo_id"])

    op.create_table(
        "harvest_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "inference_id",
            UUID(as_uuid=True),
            sa.ForeignKey("inferences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="proposed"),
        sa.Column("chunks_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_harvest_sources_inference_id", "harvest_sources", ["inference_id"])

    op.create_table(
        "chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            UUID(as_uuid=True),
            sa.ForeignKey("harvest_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("inference_id", UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("embedding", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_chunks_inference_id", "chunks", ["inference_id"])
    op.create_index("ix_chunks_source_id", "chunks", ["source_id"])

    # pgvector column — added as raw DDL because Alembic doesn't know the VECTOR type
    op.execute("ALTER TABLE chunks ADD COLUMN embedding_vec vector(1536)")
    op.execute(
        "CREATE INDEX ix_chunks_embedding_vec ON chunks "
        "USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 100)"
    )

    # tsvector for hybrid full-text search
    op.execute("ALTER TABLE chunks ADD COLUMN ts_content tsvector")
    op.execute(
        "CREATE INDEX ix_chunks_ts_content ON chunks USING GIN (ts_content)"
    )
    op.execute(
        "CREATE OR REPLACE FUNCTION chunks_ts_trigger() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN NEW.ts_content := to_tsvector('english', coalesce(NEW.content, '')); RETURN NEW; END; $$"
    )
    op.execute(
        "CREATE TRIGGER trg_chunks_ts BEFORE INSERT OR UPDATE ON chunks "
        "FOR EACH ROW EXECUTE FUNCTION chunks_ts_trigger()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_chunks_ts ON chunks")
    op.execute("DROP FUNCTION IF EXISTS chunks_ts_trigger()")
    op.drop_table("chunks")
    op.drop_table("harvest_sources")
    op.drop_table("inferences")
