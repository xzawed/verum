"""add usage_quotas table

Revision ID: 0011_usage_quotas
Revises: 0010_phase4b_experiment_evolve
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_usage_quotas"
down_revision = "0010_phase4b_experiment_evolve"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_quotas",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),  # first day of the month
        sa.Column("plan", sa.Text(), server_default="free", nullable=False),
        sa.Column("traces_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("chunks_stored", sa.Integer(), server_default="0", nullable=False),
        sa.Column("repos_connected", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "period_start", name="uq_quota_user_period"),
    )
    op.create_index("ix_usage_quotas_user_id", "usage_quotas", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_usage_quotas_user_id", table_name="usage_quotas")
    op.drop_table("usage_quotas")
