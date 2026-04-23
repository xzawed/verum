# apps/api/alembic/versions/0010_phase4b_experiment_evolve.py
"""Add experiments table; add experiment_status, current_baseline_variant to deployments.

Revision ID: 0010_phase4b_experiment_evolve
Revises: 0009_phase4a_observe
Create Date: 2026-04-23
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0010_phase4b_experiment_evolve"
down_revision: Union[str, None] = "0009_phase4a_observe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. New columns on deployments
    op.add_column(
        "deployments",
        sa.Column("experiment_status", sa.Text, nullable=False, server_default="idle"),
    )
    op.add_column(
        "deployments",
        sa.Column(
            "current_baseline_variant",
            sa.Text,
            nullable=False,
            server_default="original",
        ),
    )

    # 2. New experiments table
    op.create_table(
        "experiments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "deployment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("deployments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("baseline_variant", sa.Text, nullable=False),
        sa.Column("challenger_variant", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="running"),
        sa.Column("winner_variant", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("baseline_wins", sa.Integer, nullable=False, server_default="0"),
        sa.Column("baseline_n", sa.Integer, nullable=False, server_default="0"),
        sa.Column("challenger_wins", sa.Integer, nullable=False, server_default="0"),
        sa.Column("challenger_n", sa.Integer, nullable=False, server_default="0"),
        sa.Column("win_threshold", sa.Float, nullable=False, server_default="0.6"),
        sa.Column("cost_weight", sa.Float, nullable=False, server_default="0.1"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("converged_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_experiments_deployment_id", "experiments", ["deployment_id"])
    op.create_index("ix_experiments_status", "experiments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_experiments_status", table_name="experiments")
    op.drop_index("ix_experiments_deployment_id", table_name="experiments")
    op.drop_table("experiments")
    op.drop_column("deployments", "current_baseline_variant")
    op.drop_column("deployments", "experiment_status")
