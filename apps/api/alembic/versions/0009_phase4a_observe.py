# apps/api/alembic/versions/0009_phase4a_observe.py
"""Create model_pricing, traces, spans, judge_prompts tables.

Revision ID: 0009_phase4a_observe
Revises: 0008_metric_profile_deployments
Create Date: 2026-04-23
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0009_phase4a_observe"
down_revision: Union[str, None] = "0008_metric_profile_deployments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "model_pricing",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("model_name", sa.Text, nullable=False, unique=True),
        sa.Column("input_per_1m_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("output_per_1m_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "traces",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "deployment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("deployments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("variant", sa.Text, nullable=False, server_default="baseline"),
        sa.Column("user_feedback", sa.SmallInteger, nullable=True),
        sa.Column("judge_score", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_traces_deployment_id", "traces", ["deployment_id"])
    op.create_index("ix_traces_created_at", "traces", ["created_at"])

    op.create_table(
        "spans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "trace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("traces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_spans_trace_id", "spans", ["trace_id"])
    op.create_index("ix_spans_started_at", "spans", ["started_at"])

    op.create_table(
        "judge_prompts",
        sa.Column(
            "trace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("traces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("prompt_sent", sa.Text, nullable=False),
        sa.Column("raw_response", sa.Text, nullable=False),
        sa.Column(
            "judged_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Seed initial pricing data
    op.execute("""
        INSERT INTO model_pricing (model_name, input_per_1m_usd, output_per_1m_usd, provider) VALUES
        ('grok-2-1212',       2.000000, 10.000000, 'xai'),
        ('grok-2-mini',       0.200000,  0.400000, 'xai'),
        ('claude-sonnet-4-6', 3.000000, 15.000000, 'anthropic'),
        ('claude-haiku-4-5',  0.800000,  4.000000, 'anthropic'),
        ('gpt-4o',            2.500000, 10.000000, 'openai'),
        ('gpt-4o-mini',       0.150000,  0.600000, 'openai')
        ON CONFLICT (model_name) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("judge_prompts")
    op.drop_table("spans")
    op.drop_table("traces")
    op.drop_table("model_pricing")
