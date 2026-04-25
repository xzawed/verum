"""observe: add span_attributes JSONB column for raw OTLP span attributes.

Stores the raw OpenTelemetry span attributes received from openinference-
instrumented clients so that OBSERVE-stage queries can surface any attribute
without a schema migration per new attribute key.

Revision ID: 0023_otlp_trace_attrs
Revises: 0022_force_row_level_security
Create Date: 2026-04-25
"""
from __future__ import annotations

from alembic import op

revision: str = "0023_otlp_trace_attrs"
down_revision: str = "0022_force_row_level_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE spans ADD COLUMN IF NOT EXISTS span_attributes JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE spans DROP COLUMN IF EXISTS span_attributes")
