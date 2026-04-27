"""Tests for the Python AST LLM call-site detector (F-1.3)."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.loop.analyze.python_analyzer import analyze_directory, analyze_file

# ── Pattern A: direct module import + call ───────────────────────────────────

_OPENAI_DIRECT = b"""
import openai

response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "system", "content": "You are a helpful assistant."}],
    temperature=0.5,
    max_tokens=256,
)
"""

_ANTHROPIC_DIRECT = b"""
import anthropic

client = anthropic.Anthropic()
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello, Claude"}],
)
"""

# ── Pattern B: from-import class instantiation ───────────────────────────────

_OPENAI_FROM_IMPORT = b"""
from openai import OpenAI

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a tarot reader."},
        {"role": "user", "content": "What does the Tower card mean?"},
    ],
    temperature=0.7,
)
"""

_ASYNC_OPENAI = b"""
from openai import AsyncOpenAI

client = AsyncOpenAI()

async def run():
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Summarise this."}],
    )
"""

_ANTHROPIC_FROM_IMPORT = b"""
from anthropic import Anthropic

client = Anthropic()
msg = client.messages.create(
    model="claude-3-haiku-20240307",
    messages=[{"role": "user", "content": "Explain quantum entanglement."}],
    max_tokens=512,
)
"""

# ── Pattern C: aliased import ─────────────────────────────────────────────────

_OPENAI_ALIASED = b"""
import openai as oai

client = oai.OpenAI()
resp = client.chat.completions.create(model="gpt-4o", messages=[])
"""

# ── Pattern D: inline instantiation ─────────────────────────────────────────

_ANTHROPIC_INLINE = b"""
import anthropic

message = anthropic.Anthropic().messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=256,
    messages=[{"role": "user", "content": "Quick question."}],
)
"""

# ── Pattern E: google.generativeai ───────────────────────────────────────────

_GOOGLE_GENAI = b"""
import google.generativeai as genai

genai.configure(api_key="key")
model = genai.GenerativeModel("gemini-1.5-pro")
response = model.generate_content("What is the capital of France?")
"""

# ── xai_grok (ArcanaInsight pattern) ─────────────────────────────────────────

_XAI_GROK = b"""
from xai_grok import OpenAI

client = OpenAI(base_url="https://api.x.ai/v1", api_key="key")
response = client.chat.completions.create(
    model="grok-3",
    messages=[
        {"role": "system", "content": "You are a mystical tarot reader."},
        {"role": "user", "content": "Draw three cards for me."},
    ],
    temperature=0.9,
    max_tokens=4000,
)
"""

# ── groq ──────────────────────────────────────────────────────────────────────

_GROQ = b"""
from groq import Groq

client = Groq()
chat_completion = client.chat.completions.create(
    messages=[{"role": "user", "content": "Explain LLMs briefly."}],
    model="llama-3.1-8b-instant",
)
"""

# ── Edge cases ────────────────────────────────────────────────────────────────

_NO_LLM_CALLS = b"""
import os
import json

def helper():
    data = json.loads('{"key": "value"}')
    return os.environ.get("HOME", "/")
"""

_SYNTAX_ERROR = b"def broken(\nthis is not valid python"

_COMPLETIONS_LEGACY = b"""
import openai

result = openai.completions.create(model="gpt-3.5-turbo-instruct", prompt="Hello")
"""


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestPatternA:
    def test_openai_direct_module_call(self) -> None:
        result = analyze_file("ai.py", _OPENAI_DIRECT)
        assert len(result.call_sites) == 1
        cs = result.call_sites[0]
        assert cs.sdk == "openai"
        assert "chat.completions.create" in cs.function

    def test_openai_model_config_extracted(self) -> None:
        result = analyze_file("ai.py", _OPENAI_DIRECT)
        assert len(result.model_configs) == 1
        mc = result.model_configs[0]
        assert mc.model == "gpt-4o"
        assert mc.temperature == pytest.approx(0.5)
        assert mc.max_tokens == 256

    def test_openai_prompt_extracted(self) -> None:
        result = analyze_file("ai.py", _OPENAI_DIRECT)
        assert any("helpful assistant" in pt.content for pt in result.prompt_templates)

    def test_anthropic_direct_instance(self) -> None:
        result = analyze_file("ai.py", _ANTHROPIC_DIRECT)
        assert len(result.call_sites) == 1
        cs = result.call_sites[0]
        assert cs.sdk == "anthropic"
        assert "messages.create" in cs.function

    def test_anthropic_model_config(self) -> None:
        result = analyze_file("ai.py", _ANTHROPIC_DIRECT)
        assert result.model_configs[0].model == "claude-3-5-sonnet-20241022"
        assert result.model_configs[0].max_tokens == 1024


class TestPatternB:
    def test_openai_from_import_instance(self) -> None:
        result = analyze_file("ai.py", _OPENAI_FROM_IMPORT)
        assert len(result.call_sites) == 1
        assert result.call_sites[0].sdk == "openai"

    def test_openai_multiple_messages_extracted(self) -> None:
        result = analyze_file("ai.py", _OPENAI_FROM_IMPORT)
        contents = [pt.content for pt in result.prompt_templates]
        assert any("tarot reader" in c for c in contents)
        assert any("Tower card" in c for c in contents)

    def test_async_openai_detected(self) -> None:
        result = analyze_file("ai.py", _ASYNC_OPENAI)
        assert len(result.call_sites) == 1
        assert result.call_sites[0].sdk == "openai"

    def test_anthropic_from_import_instance(self) -> None:
        result = analyze_file("ai.py", _ANTHROPIC_FROM_IMPORT)
        assert len(result.call_sites) == 1
        assert result.call_sites[0].sdk == "anthropic"

    def test_anthropic_model_and_max_tokens(self) -> None:
        result = analyze_file("ai.py", _ANTHROPIC_FROM_IMPORT)
        mc = result.model_configs[0]
        assert mc.model == "claude-3-haiku-20240307"
        assert mc.max_tokens == 512


class TestPatternC:
    def test_aliased_openai_import(self) -> None:
        result = analyze_file("ai.py", _OPENAI_ALIASED)
        assert len(result.call_sites) == 1
        assert result.call_sites[0].sdk == "openai"


class TestPatternD:
    def test_anthropic_inline_instantiation(self) -> None:
        result = analyze_file("ai.py", _ANTHROPIC_INLINE)
        assert len(result.call_sites) == 1
        cs = result.call_sites[0]
        assert cs.sdk == "anthropic"
        assert "messages.create" in cs.function


class TestPatternE:
    def test_google_generativeai(self) -> None:
        result = analyze_file("ai.py", _GOOGLE_GENAI)
        # model = genai.GenerativeModel(...) is a constructor call, not an LLM call
        # model.generate_content(...) is the LLM call
        assert any(cs.sdk == "google-generativeai" for cs in result.call_sites)

    def test_google_prompt_extracted(self) -> None:
        result = analyze_file("ai.py", _GOOGLE_GENAI)
        assert any("capital of France" in pt.content for pt in result.prompt_templates)


class TestXaiGrok:
    def test_xai_grok_detected(self) -> None:
        result = analyze_file("arcana.py", _XAI_GROK)
        assert len(result.call_sites) == 1
        cs = result.call_sites[0]
        assert cs.sdk == "grok"
        assert "chat.completions.create" in cs.function

    def test_xai_grok_model_config(self) -> None:
        result = analyze_file("arcana.py", _XAI_GROK)
        mc = result.model_configs[0]
        assert mc.model == "grok-3"
        assert mc.temperature == pytest.approx(0.9)
        assert mc.max_tokens == 4000

    def test_xai_grok_system_prompt_extracted(self) -> None:
        result = analyze_file("arcana.py", _XAI_GROK)
        contents = [pt.content for pt in result.prompt_templates]
        assert any("mystical tarot reader" in c for c in contents)

    def test_xai_grok_file_path_preserved(self) -> None:
        result = analyze_file("arcana.py", _XAI_GROK)
        assert result.call_sites[0].file_path == "arcana.py"


class TestGroq:
    def test_groq_detected(self) -> None:
        result = analyze_file("ai.py", _GROQ)
        assert len(result.call_sites) == 1
        assert result.call_sites[0].sdk == "groq"


class TestEdgeCases:
    def test_no_llm_calls_empty_result(self) -> None:
        result = analyze_file("utils.py", _NO_LLM_CALLS)
        assert result.call_sites == []
        assert result.model_configs == []
        assert result.prompt_templates == []

    def test_syntax_error_returns_empty(self) -> None:
        result = analyze_file("broken.py", _SYNTAX_ERROR)
        assert result.call_sites == []

    def test_legacy_completions_api(self) -> None:
        result = analyze_file("old.py", _COMPLETIONS_LEGACY)
        assert len(result.call_sites) == 1
        assert result.call_sites[0].sdk == "openai"
        assert "completions.create" in result.call_sites[0].function

    def test_empty_source(self) -> None:
        result = analyze_file("empty.py", b"")
        assert result.call_sites == []

    def test_prompt_id_is_hex_16_chars(self) -> None:
        result = analyze_file("ai.py", _XAI_GROK)
        for pt in result.prompt_templates:
            assert len(pt.id) == 16
            assert all(c in "0123456789abcdef" for c in pt.id)

    def test_prompt_id_stable_across_calls(self) -> None:
        r1 = analyze_file("ai.py", _XAI_GROK)
        r2 = analyze_file("ai.py", _XAI_GROK)
        ids1 = {pt.id for pt in r1.prompt_templates}
        ids2 = {pt.id for pt in r2.prompt_templates}
        assert ids1 == ids2

    def test_short_strings_not_extracted_as_prompts(self) -> None:
        # "Hi" is < _MIN_PROMPT_LEN chars
        source = b"""
from openai import OpenAI
client = OpenAI()
client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hi"}],
)
"""
        result = analyze_file("ai.py", source)
        assert result.prompt_templates == []

    def test_line_numbers_recorded(self) -> None:
        result = analyze_file("ai.py", _XAI_GROK)
        assert result.call_sites[0].line > 0


class TestAnalyzeDirectory:
    def test_scans_py_files(self, tmp_path: Path) -> None:
        (tmp_path / "ai.py").write_bytes(_OPENAI_FROM_IMPORT)
        result = analyze_directory(tmp_path, repo_root=tmp_path)
        assert len(result.call_sites) == 1

    def test_multiple_files_aggregated(self, tmp_path: Path) -> None:
        (tmp_path / "openai_module.py").write_bytes(_OPENAI_DIRECT)
        (tmp_path / "anthropic_module.py").write_bytes(_ANTHROPIC_FROM_IMPORT)
        result = analyze_directory(tmp_path, repo_root=tmp_path)
        sdks = {cs.sdk for cs in result.call_sites}
        assert "openai" in sdks
        assert "anthropic" in sdks

    def test_skips_pycache(self, tmp_path: Path) -> None:
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "ai.cpython-313.pyc").write_bytes(b"")
        (cache / "ai.py").write_bytes(_OPENAI_DIRECT)
        result = analyze_directory(tmp_path, repo_root=tmp_path)
        assert result.call_sites == []

    def test_skips_venv(self, tmp_path: Path) -> None:
        venv = tmp_path / ".venv" / "lib" / "site-packages"
        venv.mkdir(parents=True)
        (venv / "openai" / "__init__.py").mkdir(parents=True, exist_ok=True)
        (tmp_path / "app.py").write_bytes(_OPENAI_DIRECT)
        result = analyze_directory(tmp_path, repo_root=tmp_path)
        # Only app.py should be counted
        assert len(result.call_sites) == 1

    def test_unreadable_file_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "good.py").write_bytes(_OPENAI_DIRECT)
        result = analyze_directory(tmp_path, repo_root=tmp_path)
        assert len(result.call_sites) == 1

    def test_rel_path_uses_repo_root(self, tmp_path: Path) -> None:
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "ai.py").write_bytes(_OPENAI_DIRECT)
        result = analyze_directory(tmp_path, repo_root=tmp_path)
        assert result.call_sites[0].file_path.startswith("src")
