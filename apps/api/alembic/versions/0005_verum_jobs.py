"""Add verum_jobs table for async job queue (Postgres SKIP LOCKED + LISTEN/NOTIFY).

Replaces HTTP coupling between Next.js and Python worker. The web layer enqueues
jobs here; the Python worker claims and processes them via SELECT ... FOR UPDATE
SKIP LOCKED, woken by NOTIFY triggers.

Revision ID: 0005_verum_jobs
Revises: 0004_users_and_repo_owner
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_verum_jobs"
down_revision = "0004_users_and_repo_owner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verum_jobs",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_verum_jobs_queued",
        "verum_jobs",
        ["status", "kind", "created_at"],
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(
        "ix_verum_jobs_owner",
        "verum_jobs",
        ["owner_user_id", "kind", sa.text("created_at DESC")],
    )

    # NOTIFY trigger: wakes LISTEN-ing worker immediately on INSERT
    op.execute("""
        CREATE OR REPLACE FUNCTION verum_jobs_notify() RETURNS trigger AS $$
        BEGIN
          PERFORM pg_notify('verum_jobs', NEW.id::text);
          RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER verum_jobs_notify_trg
          AFTER INSERT ON verum_jobs
          FOR EACH ROW EXECUTE FUNCTION verum_jobs_notify();
    """)

    # Worker heartbeat: single row updated every 30 s by the Python worker.
    # Healthcheck reads this to confirm worker is alive.
    op.create_table(
        "worker_heartbeat",
        sa.Column("id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("INSERT INTO worker_heartbeat (id) VALUES (1) ON CONFLICT DO NOTHING;")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS verum_jobs_notify_trg ON verum_jobs;")
    op.execute("DROP FUNCTION IF EXISTS verum_jobs_notify();")
    op.drop_index("ix_verum_jobs_owner", table_name="verum_jobs")
    op.drop_index("ix_verum_jobs_queued", table_name="verum_jobs")
    op.drop_table("verum_jobs")
    op.drop_table("worker_heartbeat")
