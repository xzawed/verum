"""Pydantic models for the INFER stage."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

# Closed vocabulary — 20 canonical domains (Phase 2 decision: closed, extend at Phase 4)
DOMAIN_TAXONOMY: list[str] = [
    "divination/tarot",
    "divination/astrology",
    "creative/writing",
    "creative/art",
    "commerce/ecommerce",
    "commerce/finance",
    "health/medical",
    "health/fitness",
    "education/tutoring",
    "education/coding",
    "legal/qa",
    "customer-service/support",
    "productivity/assistant",
    "productivity/scheduling",
    "data/analysis",
    "gaming/companion",
    "content/moderation",
    "content/generation",
    "search/rag",
    "other",
]

TONE_OPTIONS = ["mystical", "professional", "casual", "formal", "playful"]
LANGUAGE_OPTIONS = ["ko", "en", "ja", "zh", "mixed"]
USER_TYPE_OPTIONS = ["consumer", "developer", "enterprise", "mixed"]


class ServiceInference(BaseModel):
    repo_id: UUID
    analysis_id: UUID

    domain: str = Field(description=f"One of: {DOMAIN_TAXONOMY}")
    tone: str = Field(description=f"One of: {TONE_OPTIONS}")
    language: str = Field(description=f"One of: {LANGUAGE_OPTIONS}")
    user_type: str = Field(description=f"One of: {USER_TYPE_OPTIONS}")
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(description="1-2 sentence natural language summary of the service")

    # harvest hints — LLM-suggested source URLs for this domain
    suggested_sources: list[SuggestedSource] = Field(default_factory=list)


class SuggestedSource(BaseModel):
    url: str
    title: str
    description: str
