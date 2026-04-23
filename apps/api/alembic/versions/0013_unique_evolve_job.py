"""add partial unique index for evolve job deduplication

Revision ID: 0013_unique_evolve_job
Revises: 0011_usage_quotas
Create Date: 2026-04-23
"""
from alembic import op

revision = "0013_unique_evolve_job"
down_revision = "0011_usage_quotas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE UNIQUE INDEX ix_verum_jobs_evolve_experiment_unique
        ON verum_jobs ((payload->>'experiment_id'))
        WHERE kind = 'evolve' AND status IN ('queued', 'running')
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_verum_jobs_evolve_experiment_unique")
