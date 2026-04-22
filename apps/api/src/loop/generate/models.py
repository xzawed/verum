"""Pydantic models for the GENERATE stage."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from src.loop.generate.metric_profile import MetricProfile

VARIANT_TYPES = ["original", "cot", "few_shot", "role_play", "concise"]


class PromptVariant(BaseModel):
    """A single prompt variation for A/B testing in the EXPERIMENT stage."""

    variant_type: str = Field(
        description=f"One of: {VARIANT_TYPES}"
    )
    content: str = Field(
        description="Full prompt text with {variable} placeholders"
    )
    variables: list[str] = Field(
        default_factory=list,
        description="Variable names found in content"
    )


class RagConfig(BaseModel):
    """Retrieval-Augmented Generation configuration."""

    chunking_strategy: str = Field(
        default="recursive",
        description="'recursive' or 'semantic'"
    )
    chunk_size: int = Field(
        default=512,
        ge=128,
        le=2048,
        description="Characters per chunk"
    )
    chunk_overlap: int = Field(
        default=50,
        ge=0,
        le=256,
        description="Character overlap between chunks"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of chunks to retrieve"
    )
    hybrid_alpha: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Weight for vector vs text search (1.0 = vector only, 0.0 = text only)"
    )


class EvalPair(BaseModel):
    """A single query-answer pair for evaluation."""

    query: str = Field(
        description="Realistic user query"
    )
    expected_answer: str = Field(
        description="Outline of correct answer"
    )
    context_needed: bool = Field(
        default=True,
        description="Whether RAG context is required for accurate answer"
    )


class GenerateResult(BaseModel):
    """Output of the GENERATE stage ([4] in The Verum Loop)."""

    inference_id: UUID = Field(
        description="Reference to the INFER stage output"
    )
    prompt_variants: list[PromptVariant] = Field(
        description="Multiple prompt variations for testing"
    )
    rag_config: RagConfig = Field(
        description="RAG retrieval configuration"
    )
    eval_pairs: list[EvalPair] = Field(
        description="Generated evaluation dataset"
    )
    metric_profile: MetricProfile | None = None
