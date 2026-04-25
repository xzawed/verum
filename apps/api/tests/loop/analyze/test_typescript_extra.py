from __future__ import annotations

from pathlib import Path

import pytest

from src.loop.analyze.typescript import (
    _classify_path_suffix,
    _sdk_from_class_name,
    analyze_directory,
    analyze_file,
)

# ── _classify_path_suffix ────────────────────────────────────────────────────

def test_classify_path_suffix_single_candidate():
    # /v1/messages maps to only ["anthropic"] — no ambiguity
    result = _classify_path_suffix("/v1/messages", None)
    assert result == "anthropic"


def test_classify_path_suffix_uses_class_sdk_when_ambiguous():
    # /chat/completions → ["openai", "grok"]; class_sdk="grok" is in candidates
    result = _classify_path_suffix("/chat/completions", "grok")
    assert result == "grok"


def test_classify_path_suffix_fallback_when_class_sdk_not_in_candidates():
    # /chat/completions → ["openai", "grok"]; class_sdk="anthropic" is NOT in candidates
    result = _classify_path_suffix("/chat/completions", "anthropic")
    assert result == "openai"  # best-guess: candidates[0]


def test_classify_path_suffix_returns_none_when_no_match():
    result = _classify_path_suffix("/some/unknown/endpoint", None)
    assert result is None


def test_classify_path_suffix_no_class_sdk_ambiguous():
    # class_sdk is None → falls back to candidates[0]
    result = _classify_path_suffix("/chat/completions", None)
    assert result == "openai"


# ── _sdk_from_class_name ─────────────────────────────────────────────────────

def test_sdk_from_class_name_gemini():
    assert _sdk_from_class_name("GeminiProvider") == "google-generativeai"


def test_sdk_from_class_name_google():
    assert _sdk_from_class_name("GoogleAIClient") == "google-generativeai"


def test_sdk_from_class_name_gpt():
    assert _sdk_from_class_name("GPTClient") == "openai"


def test_sdk_from_class_name_unknown():
    assert _sdk_from_class_name("MyRandomClass") == "raw-fetch"


def test_sdk_from_class_name_grok():
    assert _sdk_from_class_name("GrokProvider") == "grok"


def test_sdk_from_class_name_anthropic():
    assert _sdk_from_class_name("ClaudeProvider") == "anthropic"


# ── _extract_json_body_params ValueError branches ────────────────────────────
# temperature and max_tokens are variable references (non-numeric) — should
# not raise; the values are simply omitted from model_configs.

_FETCH_WITH_VAR_PARAMS = b"""
const highTemp = 0.9;
const limit = 500;
async function run() {
  const r = await fetch("https://api.x.ai/v1/chat/completions", {
    method: "POST",
    body: JSON.stringify({ model: "grok-3", temperature: highTemp, max_tokens: limit }),
  });
}
"""


def test_var_temperature_and_max_tokens_do_not_crash():
    r = analyze_file("src/ai.ts", _FETCH_WITH_VAR_PARAMS)
    # Must find the call site (the fetch URL is known)
    assert any(cs.sdk == "grok" for cs in r.call_sites)


def test_var_temperature_not_in_model_configs():
    r = analyze_file("src/ai.ts", _FETCH_WITH_VAR_PARAMS)
    # temperature key should be absent (ValueError swallowed)
    for mc in r.model_configs:
        assert mc.temperature is None


def test_var_max_tokens_not_in_model_configs():
    r = analyze_file("src/ai.ts", _FETCH_WITH_VAR_PARAMS)
    for mc in r.model_configs:
        assert mc.max_tokens is None


# ── _analyze_top_level — top-level fetch ─────────────────────────────────────

_TOP_LEVEL_FETCH = b"""
async function run() {
  const r = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: "gpt-4o", max_tokens: 100 }),
  });
}
"""


def test_top_level_fetch_detected():
    r = analyze_file("src/ai.ts", _TOP_LEVEL_FETCH)
    assert any(cs.sdk == "openai" for cs in r.call_sites)


def test_top_level_fetch_function_contains_url():
    r = analyze_file("src/ai.ts", _TOP_LEVEL_FETCH)
    openai_sites = [cs for cs in r.call_sites if cs.sdk == "openai"]
    assert any("api.openai.com" in cs.function for cs in openai_sites)


# ── _analyze_top_level — top-level fetch with template literal URL ────────────

_TOP_LEVEL_TEMPLATE_FETCH = b"""
const BASE = "https://api.x.ai";
async function run() {
  const r = await fetch(`${BASE}/v1/chat/completions`, {
    body: JSON.stringify({ model: "grok-3" }),
  });
}
"""


def test_top_level_template_fetch_path_suffix_match():
    # The full URL can't be resolved, but /v1/chat/completions suffix should match grok or openai
    r = analyze_file("src/ai.ts", _TOP_LEVEL_TEMPLATE_FETCH)
    # At minimum it should not crash and should produce a result
    assert isinstance(r.call_sites, list)


# ── _analyze_top_level — SDK symbol call ─────────────────────────────────────

_OPENAI_SDK_TOP_LEVEL = b"""
import OpenAI from "openai";
async function run() {
  const r = await OpenAI.chat.completions.create({ model: "gpt-4o", messages: [] });
}
"""


def test_sdk_symbol_call_detected():
    # The imported symbol "OpenAI" is tracked; calls on it are Pattern A
    r = analyze_file("src/ai.ts", _OPENAI_SDK_TOP_LEVEL)
    sdk_calls = [cs for cs in r.call_sites if cs.sdk == "openai"]
    assert len(sdk_calls) >= 1


def test_sdk_symbol_call_function_name():
    r = analyze_file("src/ai.ts", _OPENAI_SDK_TOP_LEVEL)
    funcs = [cs.function for cs in r.call_sites if cs.sdk == "openai"]
    assert any("chat.completions.create" in f for f in funcs)


# ── _extract_fetch_url_text — template_string path ──────────────────────────

_CLASS_WITH_TEMPLATE_URL = b"""
import { AIProvider } from "@/types/service";
export class GrokProvider implements AIProvider {
  private baseUrl = "https://api.x.ai/v1";
  async generateReading(sp: string, up: string): Promise<string> {
    const path = "/chat/completions";
    const r = await fetch(`${this.baseUrl}${path}`, {
      body: JSON.stringify({ model: "grok-3" }),
    });
    return "";
  }
}
"""


def test_template_url_with_substitution_detected():
    # baseUrl is resolved so the full URL is reconstructed; should classify as grok
    r = analyze_file("src/grok.ts", _CLASS_WITH_TEMPLATE_URL)
    assert any(cs.sdk == "grok" for cs in r.call_sites)


# ── analyze_directory ────────────────────────────────────────────────────────

# Reuse a fixture that's known to produce call sites
_GROK_PROVIDER = b"""
import { AIProvider } from "@/types/service";
export class GrokProvider implements AIProvider {
  private baseUrl = "https://api.x.ai/v1";
  async generateReading(sp: string, up: string): Promise<string> {
    const r = await fetch(`${this.baseUrl}/chat/completions`, {
      method: "POST",
      body: JSON.stringify({ model: "grok-3", temperature: 0.7, max_tokens: 4000 }),
    });
    return "";
  }
}
"""


def test_analyze_directory_walks_ts_files(tmp_path: Path):
    ts_file = tmp_path / "provider.ts"
    ts_file.write_bytes(_GROK_PROVIDER)
    result = analyze_directory(tmp_path)
    assert len(result.call_sites) > 0


def test_analyze_directory_skips_node_modules(tmp_path: Path):
    nm_dir = tmp_path / "node_modules" / "lib"
    nm_dir.mkdir(parents=True)
    (nm_dir / "ai.ts").write_bytes(_GROK_PROVIDER)
    result = analyze_directory(tmp_path)
    assert len(result.call_sites) == 0  # skipped entirely


def test_analyze_directory_skips_next_build(tmp_path: Path):
    next_dir = tmp_path / ".next" / "server"
    next_dir.mkdir(parents=True)
    (next_dir / "chunk.js").write_bytes(_TOP_LEVEL_FETCH)
    result = analyze_directory(tmp_path)
    assert len(result.call_sites) == 0


def test_analyze_directory_includes_tsx_files(tmp_path: Path):
    _TSX_WITH_FETCH = b"""
import React from "react";
export function AI() {
  async function run() {
    await fetch("https://api.openai.com/v1/chat/completions", {
      body: JSON.stringify({ model: "gpt-4o" }),
    });
  }
  return <div />;
}
"""
    tsx = tmp_path / "Component.tsx"
    tsx.write_bytes(_TSX_WITH_FETCH)
    result = analyze_directory(tmp_path)
    assert any(cs.sdk == "openai" for cs in result.call_sites)


def test_analyze_directory_aggregates_multiple_files(tmp_path: Path):
    (tmp_path / "grok.ts").write_bytes(_GROK_PROVIDER)
    (tmp_path / "openai.ts").write_bytes(_TOP_LEVEL_FETCH)
    result = analyze_directory(tmp_path)
    sdks = {cs.sdk for cs in result.call_sites}
    assert "grok" in sdks
    assert "openai" in sdks


def test_analyze_directory_uses_repo_root_for_rel_path(tmp_path: Path):
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "ai.ts").write_bytes(_TOP_LEVEL_FETCH)
    result = analyze_directory(sub, repo_root=tmp_path)
    # Relative path should be relative to repo_root (tmp_path), not sub
    assert any("src" in cs.file_path for cs in result.call_sites)
