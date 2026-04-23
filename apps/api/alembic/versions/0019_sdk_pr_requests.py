"""Add sdk_pr_requests table for Auto SDK PR Generation feature ([5] DEPLOY).

Revision ID: 0019_sdk_pr_requests
Revises: 0018_chunks_inference_fk
Create Date: 2026-04-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_sdk_pr_requests"
down_revision: str = "0018_chunks_inference_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sdk_pr_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "repo_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("repos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("pr_url", sa.Text(), nullable=True),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("branch_name", sa.String(255), nullable=True),
        sa.Column("files_changed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_sdk_pr_requests_repo_id", "sdk_pr_requests", ["repo_id"])
    op.create_index(
        "ix_sdk_pr_requests_owner_user_id", "sdk_pr_requests", ["owner_user_id"]
    )
    op.create_index(
        "ix_sdk_pr_requests_analysis_id", "sdk_pr_requests", ["analysis_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_sdk_pr_requests_analysis_id", "sdk_pr_requests")
    op.drop_index("ix_sdk_pr_requests_owner_user_id", "sdk_pr_requests")
    op.drop_index("ix_sdk_pr_requests_repo_id", "sdk_pr_requests")
    op.drop_table("sdk_pr_requests")
