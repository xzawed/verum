"""Phase 1 ANALYZE tables: repos + analyses.

Revision ID: 0001_phase1_analyze
Revises:
Create Date: 2026-04-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001_phase1_analyze"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("github_url", sa.Text, unique=True, nullable=False),
        sa.Column("owner_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("default_branch", sa.String(255), nullable=False, server_default="main"),
        sa.Column("last_analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_repos_github_url", "repos", ["github_url"])

    op.create_table(
        "analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repo_id",
            UUID(as_uuid=True),
            sa.ForeignKey("repos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("call_sites", JSONB, nullable=True),
        sa.Column("prompt_templates", JSONB, nullable=True),
        sa.Column("model_configs", JSONB, nullable=True),
        sa.Column("language_breakdown", JSONB, nullable=True),
        sa.Column("error", sa.String(1024), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_analyses_repo_id", "analyses", ["repo_id"])


def downgrade() -> None:
    op.drop_table("analyses")
    op.drop_table("repos")
