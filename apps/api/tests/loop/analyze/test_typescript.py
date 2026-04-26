"""Tests for the TypeScript LLM call-site detector."""

import pytest

from src.loop.analyze.typescript import analyze_file

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
  async *streamReading(sp: string, up: string) {
    const r = await fetch(`${this.baseUrl}/chat/completions`, {
      body: JSON.stringify({ model: "grok-3", stream: true }),
    });
  }
}
"""

_CLAUDE_PROVIDER = b"""
import { AIProvider } from "@/types/service";
export class ClaudeProvider implements AIProvider {
  private baseUrl = "https://api.anthropic.com/v1";
  async generateReading(sp: string, up: string): Promise<string> {
    const r = await fetch(`${this.baseUrl}/messages`, {
      body: JSON.stringify({ model: "claude-3-5-sonnet", max_tokens: 1024, temperature: 0.5 }),
    });
    return "";
  }
}
"""

_SDK_IMPORT = b"""
import OpenAI from "openai";
async function run() {
  const response = await OpenAI.chat.completions.create({ model: "gpt-4o", messages: [] });
}
"""

# Pattern A — const client = new SDK() instance variable
_SDK_INSTANCE = b"""
import OpenAI from "openai";
import Anthropic from "@anthropic-ai/sdk";

const openaiClient = new OpenAI();
const anthropic = new Anthropic();

async function run() {
  const r1 = await openaiClient.chat.completions.create({ model: "gpt-4o", messages: [] });
  const r2 = await anthropic.messages.create({ model: "claude-3-5-sonnet", max_tokens: 1024, messages: [] });
}
"""

_NO_LLM = b"""
const x = 1 + 2;
export function add(a: number, b: number): number { return a + b; }
"""


def test_grok_provider_pattern_b_and_c() -> None:
    r = analyze_file("src/services/core/grok-provider.ts", _GROK_PROVIDER)
    sdks = {cs.sdk for cs in r.call_sites}
    assert sdks == {"grok"}
    # Pattern C: method-level anchors
    methods = {cs.function for cs in r.call_sites if "GrokProvider" in cs.function}
    assert "GrokProvider.generateReading" in methods
    assert "GrokProvider.streamReading" in methods
    # Pattern B: raw fetch entries
    fetches = [cs for cs in r.call_sites if cs.function.startswith("fetch->")]
    assert len(fetches) == 2
    for f in fetches:
        assert "api.x.ai" in f.function


def test_grok_provider_model_configs() -> None:
    r = analyze_file("src/services/core/grok-provider.ts", _GROK_PROVIDER)
    assert len(r.model_configs) >= 1
    mc = r.model_configs[0]
    assert mc.model == "grok-3"
    assert mc.temperature == pytest.approx(0.7)
    assert mc.max_tokens == 4000


def test_claude_provider_detected() -> None:
    r = analyze_file("src/services/core/claude-provider.ts", _CLAUDE_PROVIDER)
    sdks = {cs.sdk for cs in r.call_sites}
    assert sdks == {"anthropic"}
    fetches = [cs for cs in r.call_sites if "fetch->" in cs.function]
    assert len(fetches) == 1
    assert "anthropic.com" in fetches[0].function


def test_sdk_import_pattern_a() -> None:
    r = analyze_file("src/lib/ai.ts", _SDK_IMPORT)
    sdk_calls = [cs for cs in r.call_sites if cs.sdk == "openai"]
    assert len(sdk_calls) >= 1
    assert any("chat.completions.create" in cs.function for cs in sdk_calls)


def test_no_llm_no_call_sites() -> None:
    r = analyze_file("src/utils/math.ts", _NO_LLM)
    assert r.call_sites == []
    assert r.model_configs == []


def test_sdk_instance_variable_pattern_a() -> None:
    """const client = new SDK() — instance variable must be tracked as sdk symbol."""
    r = analyze_file("src/lib/ai.ts", _SDK_INSTANCE)
    sdks = {cs.sdk for cs in r.call_sites}
    assert "openai" in sdks, f"openai not detected; found: {sdks}"
    assert "anthropic" in sdks, f"anthropic not detected; found: {sdks}"
    openai_calls = [cs for cs in r.call_sites if cs.sdk == "openai"]
    assert any("chat.completions.create" in cs.function for cs in openai_calls)
    anthropic_calls = [cs for cs in r.call_sites if cs.sdk == "anthropic"]
    assert any("messages.create" in cs.function for cs in anthropic_calls)


def test_dedup_no_duplicate_for_same_fetch() -> None:
    r = analyze_file("src/services/core/grok-provider.ts", _GROK_PROVIDER)
    # For each line, there should be at most one fetch call site and one class method site
    fetch_lines = [cs.line for cs in r.call_sites if "fetch->" in cs.function]
    assert len(fetch_lines) == len(set(fetch_lines)), "Duplicate fetch call sites on same line"
