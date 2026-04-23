"""Add missing indexes on inferences and traces for query performance.

Revision ID: 0017_add_missing_indexes
Revises: 0016_drop_chunks_embedding_jsonb
Create Date: 2026-04-24

Adds:
  - ix_inferences_repo_id        — fast lookup of all inferences for a repo
  - ix_inferences_analysis_id    — fast lookup of all inferences under an analysis
  - ix_traces_deployment_created — composite covering dashboard time-series queries

Notes:
  - repos(owner_user_id, github_url) unique constraint already added in 0004.
  - traces(deployment_id) simple index already exists from 0009; this adds
    the composite (deployment_id, created_at DESC) for range scans.
"""
from __future__ import annotations

from alembic import op

revision: str = "0017_add_missing_indexes"
down_revision: str = "0016_drop_chunks_embedding_jsonb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_inferences_repo_id", "inferences", ["repo_id"])
    op.create_index("ix_inferences_analysis_id", "inferences", ["analysis_id"])
    op.execute(
        "CREATE INDEX ix_traces_deployment_created"
        " ON traces(deployment_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_traces_deployment_created")
    op.drop_index("ix_inferences_analysis_id", table_name="inferences")
    op.drop_index("ix_inferences_repo_id", table_name="inferences")
