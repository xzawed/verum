"""Add pg_notify trigger on verum_jobs INSERT.

Revision ID: 0015_notify_trigger
Revises: 0014_deployment_api_keys
"""
from __future__ import annotations

from alembic import op

revision = "0015_notify_trigger"
down_revision = "0014_deployment_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_verum_jobs()
        RETURNS TRIGGER AS $$
        BEGIN
            PERFORM pg_notify('verum_jobs', NEW.id::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_verum_jobs_notify
            AFTER INSERT ON verum_jobs
            FOR EACH ROW EXECUTE FUNCTION notify_verum_jobs();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_verum_jobs_notify ON verum_jobs")
    op.execute("DROP FUNCTION IF EXISTS notify_verum_jobs()")
