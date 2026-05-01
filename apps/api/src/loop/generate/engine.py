# apps/api/src/loop/generate/engine.py
"""GENERATE engine — 3 Claude Sonnet calls: variants → RAG config → eval pairs."""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import src.config as cfg
from src.loop.llm_client import call_claude
from src.loop.utils import parse_json_response
from src.loop.generate.metric_profile import select_metric_profile
from src.loop.generate.models import EvalPair, GenerateResult, PromptVariant, RagConfig

_log = logging.getLogger(__name__)
_EVAL_PAIRS_MIN = 10

_SYSTEM = "You are an expert prompt engineer and AI quality specialist. Respond ONLY with valid JSON. No markdown, no explanation."


def _parse_json(text: str) -> Any:
    return parse_json_response(text)


def _best_prompt(templates: list[dict[str, Any]]) -> str:
    """Pick the longest prompt template as the base for variant generation."""
    if not templates:
        return "(no prompt detected — generate a suitable system prompt for this service)"
    return max(templates, key=lambda t: len(t.get("content", "")))["content"]


async def _call_generate(prompt: str) -> Any:
    raw = await call_claude(
        cfg.GENERATE_MODEL,
        cfg.GENERATE_MAX_TOKENS,
        prompt,
        system=_SYSTEM,
        temperature=cfg.GENERATE_LLM_TEMPERATURE,
    )
    return _parse_json(raw)


async def _generate_variants(
    base_prompt: str,
    domain: str,
    tone: str,
    user_type: str,
    language: str,
    summary: str,
) -> list[PromptVariant]:
    """Call Claude to produce 5 optimized prompt variants."""
    variants_prompt = f"""SERVICE CONTEXT:
- Domain: {domain}
- Tone: {tone}
- Target users: {user_type}
- Language: {language}
- Summary: {summary}

ORIGINAL PROMPT:
{base_prompt}

Generate exactly 5 optimized variants of this prompt. Use {{variable}} for dynamic placeholders.
Respond as JSON:
{{
  "variants": [
    {{"variant_type": "original", "content": "...", "variables": []}},
    {{"variant_type": "cot", "content": "...", "variables": []}},
    {{"variant_type": "few_shot", "content": "...", "variables": []}},
    {{"variant_type": "role_play", "content": "...", "variables": []}},
    {{"variant_type": "concise", "content": "...", "variables": []}}
  ]
}}"""
    data = await _call_generate(variants_prompt)
    return [
        PromptVariant(
            variant_type=v["variant_type"],
            content=v["content"],
            variables=v.get("variables", []),
        )
        for v in data.get("variants", [])
    ]


async def _generate_rag_config(
    domain: str,
    user_type: str,
    chunks_preview: str,
) -> RagConfig:
    """Call Claude to recommend an optimal RAG retrieval configuration."""
    rag_prompt = f"""SERVICE: {domain} AI for {user_type} users.
SAMPLE KNOWLEDGE CHUNKS:
{chunks_preview}

Recommend optimal RAG retrieval config. Respond as JSON:
{{
  "chunking_strategy": "recursive",
  "chunk_size": 512,
  "chunk_overlap": 50,
  "top_k": 5,
  "hybrid_alpha": 0.7
}}
Rules: chunking_strategy must be "recursive" or "semantic"; chunk_size 128-1024; top_k 3-10; hybrid_alpha 0.0-1.0 (higher = more vector weight)."""
    data = await _call_generate(rag_prompt)
    return RagConfig(
        chunking_strategy=data.get("chunking_strategy", "recursive"),
        chunk_size=int(data.get("chunk_size", 512)),
        chunk_overlap=int(data.get("chunk_overlap", 50)),
        top_k=int(data.get("top_k", 5)),
        hybrid_alpha=float(data.get("hybrid_alpha", 0.7)),
    )


async def _generate_eval_pairs(
    domain: str,
    user_type: str,
    summary: str,
    chunks_preview: str,
) -> list[EvalPair]:
    """Call Claude to produce 30 diverse evaluation Q&A pairs."""
    eval_prompt = f"""You are testing a {domain} AI service for {user_type} users.
Service: {summary}

Sample knowledge:
{chunks_preview}

Generate 30 diverse test Q&A pairs. Include edge cases and common queries.
Respond as JSON:
{{
  "pairs": [
    {{"query": "...", "expected_answer": "...", "context_needed": true}}
  ]
}}"""
    data = await _call_generate(eval_prompt)
    pairs = data.get("pairs", [])
    if len(pairs) < _EVAL_PAIRS_MIN:
        _log.warning(
            "generate/eval_pairs: Claude returned %d pairs (expected ≥%d); "
            "proceeding with what was returned",
            len(pairs),
            _EVAL_PAIRS_MIN,
        )
    return [
        EvalPair(
            query=p["query"],
            expected_answer=p["expected_answer"],
            context_needed=bool(p.get("context_needed", True)),
        )
        for p in pairs
    ]


async def run_generate(
    inference_id: str,
    domain: str,
    tone: str,
    language: str,
    user_type: str,
    summary: str,
    prompt_templates: list[dict[str, Any]],
    sample_chunks: list[str],
) -> GenerateResult:
    """Call Claude Sonnet 3 times to produce prompt variants, RAG config, and eval pairs.

    This is step [4] of The Verum Loop. It auto-generates prompt variants,
    RAG configuration, and an evaluation dataset based on INFER output.

    Args:
        inference_id: UUID string of the INFER stage result.
        domain: Service domain from INFER (e.g. "divination/tarot").
        tone: Tone classification from INFER (e.g. "mystical").
        language: Language code from INFER (e.g. "ko").
        user_type: Target user type from INFER (e.g. "consumer").
        summary: Service summary from INFER.
        prompt_templates: Extracted prompt templates from ANALYZE stage.
        sample_chunks: Sample knowledge chunks from HARVEST stage (may be empty).

    Returns:
        GenerateResult with prompt_variants, rag_config, and eval_pairs.

    Raises:
        RuntimeError: If ANTHROPIC_API_KEY is not set.
        anthropic.APIError: On Anthropic API failure.
    """
    base_prompt = _best_prompt(prompt_templates)
    chunks_preview = "\n---\n".join(sample_chunks[:5]) if sample_chunks else "(no chunks yet)"

    prompt_variants, rag_config, eval_pairs = await asyncio.gather(
        _generate_variants(base_prompt, domain, tone, user_type, language, summary),
        _generate_rag_config(domain, user_type, chunks_preview),
        _generate_eval_pairs(domain, user_type, summary, chunks_preview),
    )
    metric_profile = select_metric_profile(user_type, domain)

    return GenerateResult(
        inference_id=uuid.UUID(inference_id),
        prompt_variants=prompt_variants,
        rag_config=rag_config,
        eval_pairs=eval_pairs,
        metric_profile=metric_profile,
    )
