"""security: FORCE ROW LEVEL SECURITY — activate enforced per-user row filtering.

⚠️  PREREQUISITES — do NOT run this migration until ALL of the following are true:

    1. verum_app role exists and has DML grants (migration 0021 applied).

    2. DATABASE_URL has been changed to connect as verum_app (not the
       table-owner role).  While the owner bypasses RLS even with FORCE,
       connecting as a non-owner with FORCE active AND no current_user_id
       GUC set makes ALL rows invisible — so change the connection string
       BEFORE running this migration.
           Example:
               postgresql+asyncpg://verum_app:<password>@host:5432/verum

    3. Every Python worker request uses get_db_for_user(user_id)
       (done — apps/api/src/db/session.py and worker/runner.py).

    4. Every Drizzle (Next.js) write path that needs per-user scope uses
       withUserId(userId, fn)
       (done — apps/dashboard/src/lib/db/client.ts).

    5. Read-only dashboard queries (queries.ts) have been audited to
       confirm they already filter by owner_user_id at the SQL level
       (done — all query functions accept userId and filter accordingly).

What this migration does
────────────────────────
ALTER TABLE repos        FORCE ROW LEVEL SECURITY;
ALTER TABLE usage_quotas FORCE ROW LEVEL SECURITY;

Effect (once DATABASE_URL uses verum_app):
    • Every SELECT / INSERT / UPDATE / DELETE on repos or usage_quotas
      requires app.current_user_id to be set via set_config().
    • Requests that lack the GUC see zero rows (safe-fail, not safe-open).
    • The worker admin operations (_mark_done, _mark_failed, _claim_one)
      use bare AsyncSessionLocal() without get_db_for_user() — these will
      need to be migrated to a separate admin role or exempted via a
      BYPASSRLS grant on the admin operations.

Revision ID: 0022_force_row_level_security
Revises: 0021_rls_roles
Create Date: 2026-04-25
"""
from __future__ import annotations

from alembic import op

revision: str = "0022_force_row_level_security"
down_revision: str = "0021_rls_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE repos        FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE usage_quotas FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE usage_quotas NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE repos        NO FORCE ROW LEVEL SECURITY")
