"""Pydantic models for the EXPERIMENT stage ([7] of The Verum Loop)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, computed_field


class VariantStats(BaseModel):
    variant: str
    wins: int
    n: int
    avg_winner_score: float

    @computed_field  # type: ignore[misc]
    @property
    def win_rate(self) -> float:
        return self.wins / self.n if self.n > 0 else 0.0


class ExperimentResult(BaseModel):
    experiment_id: uuid.UUID
    deployment_id: uuid.UUID
    baseline: VariantStats
    challenger: VariantStats
    confidence: float
    converged: bool
    winner_variant: str | None
