import json
from datetime import datetime, timezone
from uuid import uuid4

from src.loop.analyze.models import (
    AnalysisResult,
    LLMCallSite,
    ModelConfig,
    PromptTemplate,
)


def _site(**kwargs: object) -> LLMCallSite:
    defaults = {"file_path": "src/foo.ts", "line": 10, "sdk": "grok", "function": "fetch->api.x.ai"}
    return LLMCallSite(**{**defaults, **kwargs})  # type: ignore[arg-type]


def test_llm_call_site_round_trip() -> None:
    site = _site(sdk="anthropic", prompt_ref="abc123")
    assert LLMCallSite.model_validate_json(site.model_dump_json()) == site


def test_prompt_template_round_trip() -> None:
    pt = PromptTemplate(
        id="deadbeef",
        file_path="src/prompts.ts",
        line=42,
        content="You are a tarot reader. ${cards}",
        language="en",
        variables=["cards"],
    )
    assert PromptTemplate.model_validate_json(pt.model_dump_json()) == pt


def test_analysis_result_round_trip() -> None:
    result = AnalysisResult(
        repo_id=uuid4(),
        call_sites=[_site()],
        prompt_templates=[],
        model_configs=[ModelConfig(file_path="src/foo.ts", line=5, model="grok-3", temperature=0.7)],
        language_breakdown={"typescript": 100},
        analyzed_at=datetime.now(tz=timezone.utc),
    )
    restored = AnalysisResult.model_validate(json.loads(result.model_dump_json()))
    assert restored.repo_id == result.repo_id
    assert len(restored.call_sites) == 1
    assert restored.language_breakdown["typescript"] == 100


def test_prompt_ref_optional() -> None:
    site = _site()
    assert site.prompt_ref is None


def test_sdk_field_stored_as_string() -> None:
    # sdk is a plain str — no enum; callers may use "raw-fetch" or provider names
    site = _site(sdk="raw-fetch")
    assert site.sdk == "raw-fetch"
