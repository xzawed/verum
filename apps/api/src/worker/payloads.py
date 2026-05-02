"""Typed Pydantic models for verum_jobs payload schemas."""
from __future__ import annotations

import os
import re
from uuid import UUID

from pydantic import BaseModel, field_validator

# Mirrors the regex in cloner.py — must stay in sync.
_GITHUB_URL_RE = re.compile(r"^https://github\.com/[\w.\-]+/[\w.\-]+(\.git)?$")
# Allowed branch characters — mirrors cloner._BRANCH_RE.
_BRANCH_RE = re.compile(r"^[a-zA-Z0-9._/\-]{1,200}$")


class AnalyzePayload(BaseModel):
    repo_url: str
    branch: str
    repo_id: UUID
    analysis_id: UUID

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: str) -> str:
        """Reject non-GitHub HTTPS URLs at the payload level.

        Defence-in-depth: the API layer validates ownership, and cloner.py
        validates at clone time.  This layer catches jobs inserted directly
        into verum_jobs (e.g. via a compromised DB connection or test harness).
        Override is only permitted when VERUM_TEST_MODE=1.
        """
        if not _GITHUB_URL_RE.match(v):
            if os.environ.get("VERUM_TEST_MODE") != "1":
                raise ValueError(
                    f"repo_url must be a github.com HTTPS URL, got {v!r}"
                )
        return v

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, v: str) -> str:
        if not _BRANCH_RE.match(v):
            raise ValueError(f"branch contains invalid characters: {v!r}")
        return v


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


class WebhookPayload(BaseModel):
    subscription_id: UUID
    event: str
    data: dict
