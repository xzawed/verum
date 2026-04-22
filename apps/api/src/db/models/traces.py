"""SQLAlchemy ORM model for the traces table."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class Trace(Base):
    __tablename__ = "traces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    deployment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    variant: Mapped[str] = mapped_column(String(64), nullable=False, server_default="baseline")
    user_feedback: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    judge_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
