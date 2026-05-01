"""Add mode column to sdk_pr_requests to distinguish Phase 0 vs Phase 1 PRs.

Revision ID: 0024_sdk_pr_mode
Revises: 0023_otlp_trace_attrs
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0024_sdk_pr_mode"
down_revision: str = "0023_otlp_trace_attrs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sdk_pr_requests",
        sa.Column(
            "mode",
            sa.String(32),
            nullable=False,
            server_default="observe",
        ),
    )
    op.create_index("ix_sdk_pr_requests_mode", "sdk_pr_requests", ["repo_id", "mode"])


def downgrade() -> None:
    op.drop_index("ix_sdk_pr_requests_mode", "sdk_pr_requests")
    op.drop_column("sdk_pr_requests", "mode")
