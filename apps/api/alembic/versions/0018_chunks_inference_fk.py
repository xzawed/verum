"""Add FK constraint from chunks.inference_id to inferences.id.

Revision ID: 0018_chunks_inference_fk
Revises: 0017_add_missing_indexes
Create Date: 2026-04-24

chunks.inference_id was added in 0002 as a plain UUID column with no FK
enforcement. Adding the constraint now prevents orphan chunk rows when an
inference is deleted, and enables ON DELETE CASCADE cleanup.

Pre-migration: delete any orphan chunks (inference_id references a
non-existent inference row). In a fresh deployment the table is empty;
for existing data run the orphan cleanup manually if needed:

    DELETE FROM chunks WHERE inference_id NOT IN (SELECT id FROM inferences);
"""
from __future__ import annotations

from alembic import op

revision: str = "0018_chunks_inference_fk"
down_revision: str = "0017_add_missing_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM chunks"
        " WHERE inference_id NOT IN (SELECT id FROM inferences)"
    )
    op.create_foreign_key(
        "fk_chunks_inference_id",
        "chunks",
        "inferences",
        ["inference_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_chunks_inference_id", "chunks", type_="foreignkey")
