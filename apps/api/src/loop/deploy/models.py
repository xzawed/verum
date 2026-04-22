"""Pydantic models for the DEPLOY stage ([5] of The Verum Loop)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DeploymentConfig(BaseModel):
    traffic_split: float = Field(default=0.10, ge=0.0, le=1.0)
    rollback_threshold: float = Field(default=5.0)


class Deployment(BaseModel):
    deployment_id: UUID
    generation_id: UUID
    status: str  # "canary" | "full" | "rolled_back" | "archived"
    traffic_split: dict[str, float]
    error_count: int
    total_calls: int
    created_at: datetime
    updated_at: datetime


class DeploymentConfigResponse(BaseModel):
    """Lightweight response for SDK polling."""
    deployment_id: str
    status: str
    traffic_split: float  # fraction to variant, e.g. 0.1
    variant_prompt: str | None
