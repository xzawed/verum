"""evolve: add webhook_subscriptions table for HMAC-signed event delivery.

Revision ID: 0026_webhook_subscriptions
Revises: 0025_integrations
Create Date: 2026-05-02
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0026_webhook_subscriptions"
down_revision: str = "0025_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_subscriptions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("deployment_id", sa.UUID(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "events",
            JSONB,
            nullable=False,
            server_default='["experiment.winner_promoted"]',
        ),
        sa.Column("signing_secret", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["deployment_id"], ["deployments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_webhook_subscriptions_user_id",
        "webhook_subscriptions",
        ["user_id"],
    )
    op.create_index(
        "ix_webhook_subscriptions_deployment_id",
        "webhook_subscriptions",
        ["deployment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_subscriptions_deployment_id", "webhook_subscriptions")
    op.drop_index("ix_webhook_subscriptions_user_id", "webhook_subscriptions")
    op.drop_table("webhook_subscriptions")
