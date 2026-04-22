"""Add metric_profile to generations; create deployments table.

Revision ID: 0008_metric_profile_deployments
Revises: 0007_rag_configs_unique
Create Date: 2026-04-22
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0008_metric_profile_deployments"
down_revision: Union[str, None] = "0007_rag_configs_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("generations", sa.Column("metric_profile", JSONB, nullable=True))

    op.create_table(
        "deployments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "generation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="canary"),
        sa.Column(
            "traffic_split",
            JSONB,
            nullable=False,
            server_default='{"baseline": 0.9, "variant": 0.1}',
        ),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_deployments_generation_id", "deployments", ["generation_id"])


def downgrade() -> None:
    op.drop_table("deployments")
    op.drop_column("generations", "metric_profile")
