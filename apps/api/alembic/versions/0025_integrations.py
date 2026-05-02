"""deploy: add integrations table for Railway API env-var injection.

Revision ID: 0025_integrations
Revises: 0024_sdk_pr_mode
Create Date: 2026-05-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0025_integrations"
down_revision: str = "0024_sdk_pr_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integrations",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("repo_id", sa.UUID(), nullable=True),
        sa.Column("deployment_id", sa.UUID(), nullable=True),
        sa.Column(
            "integration_type",
            sa.String(32),
            nullable=False,
            server_default="railway",
        ),
        sa.Column("platform_project_id", sa.String(512), nullable=True),
        sa.Column("platform_service_id", sa.String(512), nullable=True),
        sa.Column("platform_environment_id", sa.String(512), nullable=True),
        sa.Column("platform_service_name", sa.String(512), nullable=True),
        sa.Column("platform_token_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="connecting",
        ),
        sa.Column(
            "injected_vars",
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("last_health_check", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repo_id"], ["repos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["deployment_id"], ["deployments.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integrations_user_id", "integrations", ["user_id"])
    op.create_index("ix_integrations_repo_id", "integrations", ["repo_id"])


def downgrade() -> None:
    op.drop_index("ix_integrations_repo_id", "integrations")
    op.drop_index("ix_integrations_user_id", "integrations")
    op.drop_table("integrations")
