"""Add lookup indexes for traces and verum_jobs hot query paths.

Revision ID: 0019_lookup_indexes
Revises: 0018_chunks_inference_fk
Create Date: 2026-04-27
"""
from alembic import op

revision = "0019_lookup_indexes"
down_revision = "0018_chunks_inference_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Covers: SELECT ... FROM traces WHERE deployment_id = :dep AND variant = ...
    # used by aggregate_variant_wins() and test_40 judge drain queries.
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_traces_deployment_variant_created
        ON traces (deployment_id, variant, created_at DESC)
    """)

    # Covers: SELECT ... FROM verum_jobs WHERE status IN (...) AND kind = ...
    # used by _claim_one(), _experiment_loop(), and test_* polling queries.
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_verum_jobs_status_kind_created
        ON verum_jobs (status, kind, created_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_traces_deployment_variant_created")
    op.execute("DROP INDEX IF EXISTS ix_verum_jobs_status_kind_created")
