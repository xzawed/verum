"""Phase 3 GENERATE tables: generations, prompt_variants, rag_configs, eval_pairs.

Revision ID: 0006_phase3_generate
Revises: 0005_verum_jobs
Create Date: 2026-04-22
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0006_phase3_generate"
down_revision: Union[str, None] = "0005_verum_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "inference_id",
            UUID(as_uuid=True),
            sa.ForeignKey("inferences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("error", sa.String(1024), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_generations_inference_id", "generations", ["inference_id"])

    op.create_table(
        "prompt_variants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("variant_type", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("variables", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_prompt_variants_generation_id", "prompt_variants", ["generation_id"])

    op.create_table(
        "rag_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunking_strategy", sa.String(32), nullable=False, server_default="recursive"),
        sa.Column("chunk_size", sa.Integer, nullable=False, server_default="512"),
        sa.Column("chunk_overlap", sa.Integer, nullable=False, server_default="50"),
        sa.Column("top_k", sa.Integer, nullable=False, server_default="5"),
        sa.Column("hybrid_alpha", sa.Float, nullable=False, server_default="0.7"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "eval_pairs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("expected_answer", sa.Text, nullable=False),
        sa.Column("context_needed", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_eval_pairs_generation_id", "eval_pairs", ["generation_id"])


def downgrade() -> None:
    op.drop_table("eval_pairs")
    op.drop_table("rag_configs")
    op.drop_table("prompt_variants")
    op.drop_table("generations")
