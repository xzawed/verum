"""security: enable Row-Level Security on tenant-scoped tables.

Row-Level Security policies are enabled on tables that have a direct user
ownership column.  Policies reference current_setting('app.current_user_id')
which the application must SET per connection to activate enforcement.

Current state — RLS is enabled but NOT forced:
    PostgreSQL applies RLS to non-owner roles only.  Since the application
    currently connects with the same role that owns the tables (the DATABASE_URL
    user), that role bypasses RLS by default.  Existing queries are unaffected.

To fully enforce RLS (recommended before public launch):
    1. Create a dedicated app role:
           CREATE ROLE verum_app LOGIN PASSWORD '...';
           GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO verum_app;
           GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO verum_app;
    2. Change DATABASE_URL to connect as verum_app (not the table-owner role).
    3. In SQLAlchemy event hook and Drizzle ORM middleware, execute:
           SET LOCAL app.current_user_id = '<authenticated-user-uuid>';
       at the start of every request transaction.
    4. Add a follow-up migration that runs:
           ALTER TABLE repos        FORCE ROW LEVEL SECURITY;
           ALTER TABLE usage_quotas FORCE ROW LEVEL SECURITY;
    Until step 4, rows are visible to all connections using the owner role.

Revision ID: 0020_row_level_security
Revises: 0019_lookup_indexes
Create Date: 2026-04-25
"""
from __future__ import annotations

from alembic import op

revision: str = "0020_row_level_security"
down_revision: str = "0019_lookup_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── repos ─────────────────────────────────────────────────────────────────
    op.execute("ALTER TABLE repos ENABLE ROW LEVEL SECURITY")

    # All four policies use (true) for the superuser/owner bypass path.
    # A non-owner connection only sees rows whose owner_user_id matches the
    # current_setting GUC. If the GUC is not set, current_setting returns NULL
    # and uuid comparison yields NULL (= false), so no rows are visible —
    # safe-fail rather than safe-open.
    op.execute("""
        CREATE POLICY repos_select ON repos
          FOR SELECT
          USING (
            owner_user_id = current_setting('app.current_user_id', true)::uuid
          )
    """)
    op.execute("""
        CREATE POLICY repos_insert ON repos
          FOR INSERT
          WITH CHECK (
            owner_user_id = current_setting('app.current_user_id', true)::uuid
          )
    """)
    op.execute("""
        CREATE POLICY repos_update ON repos
          FOR UPDATE
          USING (
            owner_user_id = current_setting('app.current_user_id', true)::uuid
          )
    """)
    op.execute("""
        CREATE POLICY repos_delete ON repos
          FOR DELETE
          USING (
            owner_user_id = current_setting('app.current_user_id', true)::uuid
          )
    """)

    # ── usage_quotas ──────────────────────────────────────────────────────────
    op.execute("ALTER TABLE usage_quotas ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY quotas_select ON usage_quotas
          FOR SELECT
          USING (
            user_id = current_setting('app.current_user_id', true)::uuid
          )
    """)
    op.execute("""
        CREATE POLICY quotas_insert ON usage_quotas
          FOR INSERT
          WITH CHECK (
            user_id = current_setting('app.current_user_id', true)::uuid
          )
    """)
    op.execute("""
        CREATE POLICY quotas_update ON usage_quotas
          FOR UPDATE
          USING (
            user_id = current_setting('app.current_user_id', true)::uuid
          )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS quotas_update   ON usage_quotas")
    op.execute("DROP POLICY IF EXISTS quotas_insert   ON usage_quotas")
    op.execute("DROP POLICY IF EXISTS quotas_select   ON usage_quotas")
    op.execute("ALTER TABLE usage_quotas DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS repos_delete ON repos")
    op.execute("DROP POLICY IF EXISTS repos_update ON repos")
    op.execute("DROP POLICY IF EXISTS repos_insert ON repos")
    op.execute("DROP POLICY IF EXISTS repos_select ON repos")
    op.execute("ALTER TABLE repos DISABLE ROW LEVEL SECURITY")
