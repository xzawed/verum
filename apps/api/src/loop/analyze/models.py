from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LLMCallSite(BaseModel):
    file_path: str
    line: int
    sdk: str  # "openai" | "anthropic" | "grok" | "google-generativeai" | "raw-fetch"
    function: str  # e.g. "chat.completions.create" or "fetch->api.x.ai/v1/chat/completions"
    prompt_ref: str | None = None  # ID of resolved PromptTemplate; None if unresolvable


class PromptTemplate(BaseModel):
    id: str  # stable hash: sha256(file_path + ":" + str(line) + ":" + content)[:16]
    file_path: str
    line: int
    content: str  # raw string after template-literal stripping
    language: str = "en"  # "ko" | "en" | "mixed"
    variables: list[str] = Field(default_factory=list)  # ${var} placeholder names


class ModelConfig(BaseModel):
    file_path: str
    line: int
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stop: list[str] | None = None


class AnalysisResult(BaseModel):
    repo_id: UUID
    call_sites: list[LLMCallSite]
    prompt_templates: list[PromptTemplate]
    model_configs: list[ModelConfig]
    language_breakdown: dict[str, int]
    analyzed_at: datetime
