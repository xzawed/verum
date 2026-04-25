"""security: create verum_app role and grant DML for enforced RLS.

This migration creates the dedicated application database role that will be
used to ENFORCE Row-Level Security.  When the application connects as
``verum_app`` (instead of the table-owner role), PostgreSQL applies RLS
policies without the owner bypass.

What this migration does
────────────────────────
1. Creates ``verum_app`` login role (IF NOT EXISTS — idempotent).
2. Grants CONNECT on the database.
3. Grants USAGE on the public schema.
4. Grants SELECT, INSERT, UPDATE, DELETE on all existing tables.
5. Grants USAGE / SELECT on all existing sequences.
6. Sets default privileges so future tables/sequences are also covered.

What you still need to do to fully enforce RLS
──────────────────────────────────────────────
After this migration and after verifying that the application works correctly
when connecting as ``verum_app``:

    Step A — Change the connection string:
        Update DATABASE_URL (Railway / .env) to use verum_app credentials:
            postgresql+asyncpg://verum_app:<password>@host:5432/verum
        (Set the password: ALTER ROLE verum_app PASSWORD '...' )

    Step B — Wire the GUC into every request:
        Python worker   → already done via get_db_for_user() context manager
                          in apps/api/src/db/session.py
        Drizzle routes  → use withUserId(userId, fn) from apps/dashboard/src/lib/db/client.ts

    Step C — Run the FORCE ROW LEVEL SECURITY migration (0022):
            ALTER TABLE repos        FORCE ROW LEVEL SECURITY;
            ALTER TABLE usage_quotas FORCE ROW LEVEL SECURITY;
        Until this step the owner-role bypass is still active.

Revision ID: 0021_rls_roles
Revises: 0020_row_level_security
Create Date: 2026-04-25
"""
from __future__ import annotations

from alembic import op

revision: str = "0021_rls_roles"
down_revision: str = "0020_row_level_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # asyncpg uses the extended query protocol (prepared statements), which
    # rejects multi-statement strings. Each DDL statement must be a separate call.
    op.execute(
        """
        DO $$
        DECLARE
          db_name text := current_database();
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'verum_app') THEN
            CREATE ROLE verum_app LOGIN;
          END IF;
          EXECUTE format('GRANT CONNECT ON DATABASE %I TO verum_app', db_name);
        END
        $$
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO verum_app")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO verum_app"
    )
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO verum_app")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public"
        " GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO verum_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public"
        " GRANT USAGE, SELECT ON SEQUENCES TO verum_app"
    )


def downgrade() -> None:
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public"
        " REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM verum_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public"
        " REVOKE USAGE, SELECT ON SEQUENCES FROM verum_app"
    )
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM verum_app"
    )
    op.execute("REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public FROM verum_app")
    op.execute("REVOKE USAGE ON SCHEMA public FROM verum_app")
