"""Add UNIQUE constraint on rag_configs.generation_id to prevent concurrent double-insert.

Revision ID: 0007_rag_configs_unique
Revises: 0006_phase3_generate
Create Date: 2026-04-22
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0007_rag_configs_unique"
down_revision: Union[str, None] = "0006_phase3_generate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_rag_configs_generation_id",
        "rag_configs",
        ["generation_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_rag_configs_generation_id",
        "rag_configs",
        type_="unique",
    )
