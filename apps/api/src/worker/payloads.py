"""Typed Pydantic models for verum_jobs payload schemas."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class AnalyzePayload(BaseModel):
    repo_url: str
    branch: str
    repo_id: UUID
    analysis_id: UUID


class InferPayload(BaseModel):
    analysis_id: UUID
    inference_id: UUID


class HarvestPayload(BaseModel):
    inference_id: UUID
    source_ids: list[tuple[UUID, str]]


class GeneratePayload(BaseModel):
    inference_id: UUID
    generation_id: UUID


class DeployPayload(BaseModel):
    generation_id: UUID


class JudgePayload(BaseModel):
    trace_id: UUID
    deployment_id: UUID
    variant: str


class EvolvePayload(BaseModel):
    experiment_id: UUID
    deployment_id: UUID
    winner_variant: str
    confidence: float
    current_challenger: str


class RetrievePayload(BaseModel):
    inference_id: UUID
    query: str
    hybrid: bool = True
    top_k: int = 5
