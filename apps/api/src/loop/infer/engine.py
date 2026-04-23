"""INFER engine — calls Claude Sonnet to classify a service's domain and purpose."""
from __future__ import annotations

import json
import re
import uuid

import src.config as cfg
from src.loop.llm_client import call_claude
from src.loop.analyze.models import AnalysisResult
from .models import DOMAIN_TAXONOMY, LANGUAGE_OPTIONS, TONE_OPTIONS, USER_TYPE_OPTIONS
from .models import ServiceInference, SuggestedSource

_SYSTEM_PROMPT = """\
You are an expert software analyst specializing in AI/LLM services.
Given static analysis data from a repository, infer the service's domain and characteristics.
Respond ONLY with valid JSON matching the requested schema. No markdown, no explanation.
"""

_HARVEST_SOURCES: dict[str, list[dict[str, str]]] = {
    "divination/tarot": [
        {"url": "https://en.wikipedia.org/wiki/Tarot", "title": "Tarot — Wikipedia", "description": "Comprehensive overview of tarot history, symbolism, and card meanings"},
        {"url": "https://en.wikipedia.org/wiki/Major_Arcana", "title": "Major Arcana — Wikipedia", "description": "The 22 major arcana cards and their symbolism"},
        {"url": "https://www.biddytarot.com/tarot-card-meanings/", "title": "Biddy Tarot — Card Meanings", "description": "Detailed upright and reversed meanings for all 78 tarot cards"},
        {"url": "https://labyrinthos.co/blogs/tarot-card-meanings-list", "title": "Labyrinthos — Tarot Meanings", "description": "Modern interpretations of all tarot cards with visual guides"},
    ],
    "divination/astrology": [
        {"url": "https://en.wikipedia.org/wiki/Astrology", "title": "Astrology — Wikipedia", "description": "History and principles of astrology"},
        {"url": "https://en.wikipedia.org/wiki/Astrological_sign", "title": "Astrological Signs — Wikipedia", "description": "The 12 zodiac signs and their characteristics"},
    ],
    "education/coding": [
        {"url": "https://developer.mozilla.org/en-US/docs/Web", "title": "MDN Web Docs", "description": "Comprehensive web development reference"},
        {"url": "https://en.wikipedia.org/wiki/Software_engineering", "title": "Software Engineering — Wikipedia", "description": "Overview of software engineering concepts"},
    ],
    "health/medical": [
        {"url": "https://en.wikipedia.org/wiki/Medicine", "title": "Medicine — Wikipedia", "description": "Overview of medical knowledge and practice"},
        {"url": "https://www.who.int/health-topics", "title": "WHO Health Topics", "description": "WHO's reference on health topics and conditions"},
    ],
    "legal/qa": [
        {"url": "https://en.wikipedia.org/wiki/Law", "title": "Law — Wikipedia", "description": "Overview of legal systems and principles"},
    ],
    "commerce/finance": [
        {"url": "https://en.wikipedia.org/wiki/Finance", "title": "Finance — Wikipedia", "description": "Overview of financial concepts and instruments"},
        {"url": "https://en.wikipedia.org/wiki/Investment", "title": "Investment — Wikipedia", "description": "Investment strategies and concepts"},
    ],
    "customer-service/support": [
        {"url": "https://en.wikipedia.org/wiki/Customer_service", "title": "Customer Service — Wikipedia", "description": "Best practices for customer service"},
    ],
    "creative/writing": [
        {"url": "https://en.wikipedia.org/wiki/Creative_writing", "title": "Creative Writing — Wikipedia", "description": "Techniques and genres in creative writing"},
    ],
    "other": [
        {"url": "https://en.wikipedia.org/wiki/Artificial_intelligence", "title": "Artificial Intelligence — Wikipedia", "description": "Overview of AI concepts and applications"},
    ],
}


def _get_sources_for_domain(domain: str) -> list[dict[str, str]]:
    return _HARVEST_SOURCES.get(domain, _HARVEST_SOURCES["other"])


def _build_user_message(result: AnalysisResult) -> str:
    call_sites = [
        f"  - {cs.file_path}:{cs.line} [{cs.sdk}] {cs.function}"
        for cs in result.call_sites[:20]
    ]
    prompts = [
        f"  - [{pt.language}] {pt.content[:200]}"
        for pt in result.prompt_templates[:10]
    ]
    lang_info = ", ".join(f"{k}: {v}" for k, v in result.language_breakdown.items())

    return f"""Repository analysis data:

Language breakdown: {lang_info or "unknown"}

LLM call sites ({len(result.call_sites)} total):
{chr(10).join(call_sites) or "  (none detected)"}

Prompt templates ({len(result.prompt_templates)} total):
{chr(10).join(prompts) or "  (none extracted)"}

Infer the following as JSON:
{{
  "domain": "<one of {DOMAIN_TAXONOMY}>",
  "tone": "<one of {TONE_OPTIONS}>",
  "language": "<one of {LANGUAGE_OPTIONS}>",
  "user_type": "<one of {USER_TYPE_OPTIONS}>",
  "confidence": <0.0-1.0>,
  "summary": "<1-2 sentence description of what this service does>"
}}"""


async def run_infer(result: AnalysisResult, *, analysis_id: uuid.UUID) -> ServiceInference:
    """Call Claude Sonnet to infer service domain from an AnalysisResult.

    Args:
        result: The analysis result to infer from.
        analysis_id: The analysis ID to associate with the inference result.

    Raises:
        RuntimeError: if ANTHROPIC_API_KEY is not set.
        anthropic.APIError: on Anthropic API failure.
    """
    raw_text = await call_claude(
        cfg.INFER_MODEL,
        cfg.INFER_MAX_TOKENS,
        _build_user_message(result),
        system=_SYSTEM_PROMPT,
        temperature=0.2,
    )

    raw_text = re.sub(r"^```(?:json)?\s*\n?", "", raw_text.strip(), flags=re.MULTILINE)
    raw_text = re.sub(r"\n?```\s*$", "", raw_text, flags=re.MULTILINE).strip()

    parsed: dict[str, object] = json.loads(raw_text)

    # Validate and clamp domain to taxonomy
    domain = parsed.get("domain", "other")
    from .models import DOMAIN_TAXONOMY
    if domain not in DOMAIN_TAXONOMY:
        domain = "other"

    sources = _get_sources_for_domain(domain)

    return ServiceInference(
        repo_id=result.repo_id,
        analysis_id=analysis_id,
        domain=domain,
        tone=parsed.get("tone", "professional"),
        language=parsed.get("language", "en"),
        user_type=parsed.get("user_type", "consumer"),
        confidence=float(parsed.get("confidence", 0.5)),
        summary=str(parsed.get("summary", "")),
        suggested_sources=[
            SuggestedSource(url=s["url"], title=s["title"], description=s["description"])
            for s in sources
        ],
    )
