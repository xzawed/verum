"""Add users table and make repos.owner_user_id a required FK.

Phase 2.5: Multi-tenant foundation. Any user can log in via GitHub OAuth
and register their own Repos. Ownership is enforced at the API layer.

Revision ID: 0004_users_and_repo_owner
Revises: 0003_voyage_embeddings
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_users_and_repo_owner"
down_revision = "0003_voyage_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("github_id", sa.BigInteger(), nullable=False),
        sa.Column("github_login", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_github_id", "users", ["github_id"], unique=True)

    # Wipe repos so we can enforce NOT NULL + FK.
    # In production: run `alembic downgrade base && alembic upgrade head` to
    # reset the schema. All existing Phase 2 data should be re-generated after
    # the first GitHub login by xzawed.
    op.execute("DELETE FROM repos")

    op.alter_column(
        "repos", "owner_user_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_repos_owner_user_id",
        "repos", "users",
        ["owner_user_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_repos_owner_user_id", "repos", ["owner_user_id"])

    # Two different users may independently register the same public repo.
    # Drop the old single-column unique and replace with a composite one.
    try:
        op.drop_constraint("repos_github_url_key", "repos", type_="unique")
    except Exception:
        pass  # constraint may not exist with that exact name
    op.create_unique_constraint(
        "uq_repos_owner_github_url",
        "repos",
        ["owner_user_id", "github_url"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_repos_owner_github_url", "repos", type_="unique")
    op.create_unique_constraint("repos_github_url_key", "repos", ["github_url"])
    op.drop_index("ix_repos_owner_user_id", table_name="repos")
    op.drop_constraint("fk_repos_owner_user_id", "repos", type_="foreignkey")
    op.alter_column(
        "repos", "owner_user_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.drop_index("ix_users_github_id", table_name="users")
    op.drop_table("users")
