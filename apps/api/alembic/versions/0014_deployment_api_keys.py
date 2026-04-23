"""Add api_key_hash to deployments table

Revision ID: 0014_deployment_api_keys
Revises: 0013_unique_evolve_job
Create Date: 2026-04-24
"""
from __future__ import annotations
import secrets, hashlib
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0014_deployment_api_keys"
down_revision = "0013_unique_evolve_job"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add nullable column first
    op.add_column("deployments", sa.Column("api_key_hash", sa.String(64), nullable=True))
    # Backfill: generate a random key hash for all existing deployments
    conn = op.get_bind()
    rows = conn.execute(text("SELECT id FROM deployments")).fetchall()
    for row in rows:
        token = secrets.token_urlsafe(32)
        h = hashlib.sha256(token.encode()).hexdigest()
        conn.execute(
            text("UPDATE deployments SET api_key_hash = :h WHERE id = :id"),
            {"h": h, "id": str(row[0])}
        )
    # Now make it NOT NULL and add unique index
    op.alter_column("deployments", "api_key_hash", nullable=False)
    op.create_index("ix_deployments_api_key_hash", "deployments", ["api_key_hash"], unique=True)
    print(
        "\n[MIGRATION 0014] WARNING: Existing deployments have been assigned new random API keys.\n"
        "These keys cannot be recovered. Deployment owners must regenerate their API keys\n"
        "from the dashboard Settings → Deployments → Regenerate Key.\n"
    )

def downgrade() -> None:
    op.drop_index("ix_deployments_api_key_hash", table_name="deployments")
    op.drop_column("deployments", "api_key_hash")
