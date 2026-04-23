---
type: methodology
authority: tier-2
canonical-for: [scoring-formulas, prompt-reproduction, known-limitations]
last-updated: 2026-04-23
status: active
---

# Verum — Algorithm & Methodology Reference

> **Purpose:** This document exists so that external engineers, academic reviewers, and audit partners can reproduce every score Verum produces, understand every prompt Verum sends to an LLM, and verify every design choice. It is updated in the same PR that changes the relevant implementation — never as a separate documentation sprint.
>
> **Audience:** Software engineers familiar with LLMs and RAG; no Verum-specific context required beyond reading this document.
>
> **Update rule:** Any change to a prompt, model, or scoring formula **must** include a diff to this file in the same PR.

---

## 1. The 8-Stage Loop

Verum runs a continuous pipeline: **ANALYZE → INFER → HARVEST → GENERATE → DEPLOY → OBSERVE → EXPERIMENT → EVOLVE → (repeat)**. This document covers stages [4] GENERATE, [6] OBSERVE, [7] EXPERIMENT, and [8] EVOLVE in full.

For stage-by-stage I/O contracts and trigger conditions, see [LOOP.md](LOOP.md). For completion gates and timeline, see [ROADMAP.md](ROADMAP.md).

---

## 2. GENERATE — Prompt Variant Production

### 2.1 Inputs

GENERATE receives output from two prior stages:
- **INFER** output: `domain`, `tone`, `language`, `user_type`, `summary`
- **ANALYZE** output: `prompt_templates[]` — list of extracted LLM call templates from the target repo
- **HARVEST** output: `sample_chunks[]` — up to 5 representative knowledge chunks (joined with `"---"`)

### 2.2 Base Prompt Selection

The base prompt for variant generation is selected by [`engine.py:28-32`](apps/api/src/loop/generate/engine.py#L28) — the **longest** extracted template by character count:

```python
def _best_prompt(templates: list[dict[str, Any]]) -> str:
    if not templates:
        return "(no prompt detected — generate a suitable system prompt for this service)"
    return max(templates, key=lambda t: len(t.get("content", "")))["content"]
```

**Known limitation L-4:** Length as proxy for "most complete prompt" may select verbose but low-quality templates. See §10.

### 2.3 LLM Call Parameters (shared by all three GENERATE calls)

| Parameter | Value | Source |
|---|---|---|
| Model | `claude-sonnet-4-6` (default) | `GENERATE_MODEL` env var; defaults to `INFER_MODEL` → `"claude-sonnet-4-6"` |
| max_tokens | `2048` (default) | `GENERATE_MAX_TOKENS` env var |
| temperature | SDK default | Not specified — see L-5 |
| system prompt | `"You are an expert prompt engineer and AI quality specialist. Respond ONLY with valid JSON. No markdown, no explanation."` | [`engine.py:17`](apps/api/src/loop/generate/engine.py#L17) |

### 2.4 Variant Generation Meta-prompt

Source: [`engine.py:56-76`](apps/api/src/loop/generate/engine.py#L56)

```
SERVICE CONTEXT:
- Domain: {domain}
- Tone: {tone}
- Target users: {user_type}
- Language: {language}
- Summary: {summary}

ORIGINAL PROMPT:
{base_prompt}

Generate exactly 5 optimized variants of this prompt. Use {variable} for dynamic placeholders.
Respond as JSON:
{
  "variants": [
    {"variant_type": "original", "content": "...", "variables": []},
    {"variant_type": "cot",      "content": "...", "variables": []},
    {"variant_type": "few_shot", "content": "...", "variables": []},
    {"variant_type": "role_play","content": "...", "variables": []},
    {"variant_type": "concise",  "content": "...", "variables": []}
  ]
}
```

The five variant types are defined in [`models.py:10`](apps/api/src/loop/generate/models.py#L10): `original`, `cot`, `few_shot`, `role_play`, `concise`.

---

## 3. GENERATE — RAG Configuration

### 3.1 Meta-prompt

Source: [`engine.py:95-107`](apps/api/src/loop/generate/engine.py#L95)

```
SERVICE: {domain} AI for {user_type} users.
SAMPLE KNOWLEDGE CHUNKS:
{chunks_preview}

Recommend optimal RAG retrieval config. Respond as JSON:
{
  "chunking_strategy": "recursive",
  "chunk_size": 512,
  "chunk_overlap": 50,
  "top_k": 5,
  "hybrid_alpha": 0.7
}
Rules: chunking_strategy must be "recursive" or "semantic"; chunk_size 128-1024;
top_k 3-10; hybrid_alpha 0.0-1.0 (higher = more vector weight).
```

### 3.2 Parameter Constraints and Defaults

| Parameter | Meta-prompt rule | Pydantic constraint | Default |
|---|---|---|---|
| `chunking_strategy` | `"recursive"` or `"semantic"` | same | `"recursive"` |
| `chunk_size` | 128–1024 | 128–2048 ⚠️ | 512 |
| `chunk_overlap` | unspecified | 0–256 | 50 |
| `top_k` | 3–10 | 1–20 ⚠️ | 5 |
| `hybrid_alpha` | 0.0–1.0 | 0.0–1.0 | 0.7 |

`hybrid_alpha = 1.0` → vector-only search; `0.0` → full-text-only search.

⚠️ marks cases where Pydantic accepts values outside the meta-prompt's stated range (L-1, L-2 in §10).

Source: [`models.py:28-58`](apps/api/src/loop/generate/models.py#L28)

---

## 4. GENERATE — Evaluation Dataset

### 4.1 Meta-prompt

Source: [`engine.py:126-138`](apps/api/src/loop/generate/engine.py#L126)

```
You are testing a {domain} AI service for {user_type} users.
Service: {summary}

Sample knowledge:
{chunks_preview}

Generate 30 diverse test Q&A pairs. Include edge cases and common queries.
Respond as JSON:
{
  "pairs": [
    {"query": "...", "expected_answer": "...", "context_needed": true}
  ]
}
```

### 4.2 Output Schema

Defined in [`models.py:61-73`](apps/api/src/loop/generate/models.py#L61):

| Field | Type | Description |
|---|---|---|
| `query` | `str` | Realistic user query for the service's domain |
| `expected_answer` | `str` | Outline of a correct answer (not a full gold response) |
| `context_needed` | `bool` | Whether RAG retrieval is required to answer correctly |

**Known limitation L-3:** The meta-prompt requests 20 pairs. ROADMAP.md F-3.3 targets 30–50. The two are inconsistent; SoT must be resolved before Phase 4-B begins. See §10.

---

## 5. OBSERVE — LLM-as-Judge

### 5.1 Trigger and Idempotency

Every trace ingested via `POST /api/v1/traces` enqueues a `judge` job in `verum_jobs`. The worker handler runs asynchronously. Idempotency: if `traces.judge_score` is already non-NULL the job exits immediately ([`judge.py:90-96`](apps/api/src/worker/handlers/judge.py#L90)) — re-queuing is safe.

### 5.2 Context Loading

The handler resolves two context inputs via SQL:

1. **Domain + tone** — via `deployments → generations → inferences` chain ([`judge.py:99-113`](apps/api/src/worker/handlers/judge.py#L99)). Fallback: `"general"` / `"professional"`.
2. **Up to 3 eval_pairs** — oldest first by `eval_pairs.created_at ASC LIMIT 3` ([`judge.py:116-129`](apps/api/src/worker/handlers/judge.py#L116)).

Known limitation L-7: oldest 3 pairs are used with no relevance-based selection.

### 5.3 Judge Prompt (full text)

Source: [`judge.py:27-44`](apps/api/src/worker/handlers/judge.py#L27)

```
You are evaluating an AI assistant response for quality.
Score from 0.0 to 1.0 based on: domain appropriateness, completeness,
and alignment with the expected answer direction.

Domain: {domain} | Tone: {tone}

Reference examples from this domain:
  Q: {eval_pairs[0].query}
  A: {eval_pairs[0].expected_answer}
  Q: {eval_pairs[1].query}
  A: {eval_pairs[1].expected_answer}
  ...

Respond ONLY with JSON: {"score": 0.0-1.0, "reason": "one sentence"}
```

### 5.4 LLM Call Parameters

| Parameter | Value |
|---|---|
| Model | `claude-sonnet-4-6` (hardcoded; [`judge.py:24`](apps/api/src/worker/handlers/judge.py#L24)) |
| max_tokens | `128` |
| temperature | SDK default (not specified — see L-5) |
| system prompt | None — user message only |

### 5.5 Score Parsing, Clamping, and Retry

Response is parsed from `{"score": float, "reason": string}` ([`judge.py:47-56`](apps/api/src/worker/handlers/judge.py#L47)). Score is clamped to `[0.0, 1.0]` regardless of model output.

On parse failure: retried once (2 total attempts). If both fail: `judge_score` stays `NULL`, job marked done. The trace remains fully observable; the dashboard shows "채점 중..." indefinitely for NULL-scored traces.

### 5.6 Audit Trail

Every successfully scored trace produces a `judge_prompts` row:

```
traces.id
  └─ judge_prompts.trace_id (PK, FK)
       ├─ judge_prompts.prompt_sent   ← full prompt string sent to Claude
       ├─ judge_prompts.raw_response  ← Claude's raw JSON response
       └─ judge_prompts.judged_at
```

This chain is queryable via `GET /api/v1/traces/[id]` (requires Auth.js session) and visible in the dashboard SpanWaterfall slide-over panel.

Insert logic: [`observe/repository.py:119-147`](apps/api/src/loop/observe/repository.py#L119) — upsert on `trace_id`, so re-judging a trace overwrites the previous audit record.

### 5.7 Score Semantics

The judge score is a **domain alignment proxy**, not response correctness. The judge does not see the actual user query or assistant response (privacy decision: `spans` stores token counts and latency only, not text content — deferred opt-in to Phase 5). The score answers: *"Is this deployment producing responses consistent with the service's domain and the eval_pair reference set?"*

---

## 6. OBSERVE — Cost Calculation

### 6.1 Formula

Cost is calculated at trace ingestion time in the `POST /api/v1/traces` handler:

```
cost_usd = (input_tokens  / 1,000,000 × input_per_1m_usd)
         + (output_tokens / 1,000,000 × output_per_1m_usd)
```

Rates are looked up from the `model_pricing` table by exact `model_name` string match. The table has an `effective_from` column; currently the latest row per model name is used.

### 6.2 Seeded Pricing (migration `0009`, 2026-04-23)

| Model | Input / 1M USD | Output / 1M USD | Provider |
|---|---|---|---|
| `grok-2-1212` | $2.00 | $10.00 | xai |
| `grok-2-mini` | $0.20 | $0.40 | xai |
| `claude-sonnet-4-6` | $3.00 | $15.00 | anthropic |
| `claude-haiku-4-5` | $0.80 | $4.00 | anthropic |
| `gpt-4o` | $2.50 | $10.00 | openai |
| `gpt-4o-mini` | $0.15 | $0.60 | openai |

Rates are managed via direct DB edit. A management UI is deferred to Phase 5.

### 6.3 Unknown Model Fallback

If `model_name` is not found in `model_pricing`: `cost_usd` is stored as `0.000000` and a warning is logged. Trace ingestion is **never blocked** by a missing pricing entry.

---

## 7. EXPERIMENT — Bayesian A/B Testing

> **Loop stage:** [7] EXPERIMENT
> **Implemented in:** Phase 4-B (F-4.5)
> **Source:** `apps/api/src/loop/experiment/engine.py`

### Challenger Order

Experiments run sequentially in fixed order:

| Round | Baseline | Challenger |
|---|---|---|
| 1 | original | cot |
| 2 | {winner} | few_shot |
| 3 | {winner} | role_play |
| 4 | {winner} | concise |

`CHALLENGER_ORDER = ["cot", "few_shot", "role_play", "concise"]`

### winner_score Formula

```python
# apps/api/src/loop/experiment/engine.py
def compute_winner_score(
    judge_score: float,
    cost_usd: float,
    max_cost_in_window: float,
    cost_weight: float = 0.1,
) -> float:
    cost_normalized = cost_usd / max_cost_in_window if max_cost_in_window > 0 else 0.0
    return judge_score - cost_weight * cost_normalized
```

Binary win: `1 if winner_score > 0.6 else 0` (win_threshold = 0.6).
`max_cost_in_window` = max cost_usd across all deployment traces in the last 7 days.
Traces with `judge_score IS NULL` are excluded.

### Beta-Bernoulli Bayesian Model

Posterior: `Beta(1 + wins, 1 + losses)` (uniform prior).

```python
# apps/api/src/loop/experiment/engine.py
def bayesian_confidence(b_wins, b_n, c_wins, c_n, samples=10_000):
    baseline   = scipy.stats.beta(1 + b_wins, 1 + (b_n - b_wins))
    challenger = scipy.stats.beta(1 + c_wins, 1 + (c_n - c_wins))
    return float(np.mean(challenger.rvs(samples) > baseline.rvs(samples)))
```

**Convergence conditions (both required):**
- `baseline_n ≥ 100 AND challenger_n ≥ 100`
- `P(challenger > baseline) ≥ 0.95` (challenger wins) OR `≤ 0.05` (baseline holds)

**Reproducibility:** Prior = Beta(1,1), samples = 10,000, unseeded RNG (non-deterministic per run).

### Periodic Evaluation

`_experiment_loop()` in `apps/api/src/worker/runner.py` polls every 300 seconds. On convergence, enqueues an `evolve` job (idempotent — ignores duplicate if a job is already queued/running).

---

## 8. EVOLVE — Winner Promotion

> **Loop stage:** [8] EVOLVE
> **Implemented in:** Phase 4-B (F-4.8, F-4.9, F-4.10)
> **Source:** `apps/api/src/loop/evolve/engine.py`, `apps/api/src/worker/handlers/evolve.py`

### State Transitions

```
DEPLOY completes
  → experiments INSERT (baseline="original", challenger="cot", status="running")
  → deployments UPDATE (experiment_status="running")
  → deployments UPDATE (traffic_split={"original": 0.9, "cot": 0.1})

Every 5 min (_experiment_loop):
  → aggregate traces → check bayesian_confidence
  → If converged → INSERT verum_jobs(kind="evolve", ...)

EVOLVE job (handle_evolve):
  → experiments UPDATE (winner_variant, confidence, status="converged", converged_at)
  → deployments UPDATE (current_baseline_variant = winner_variant)
  → If next challenger exists:
      → experiments INSERT (new round)
      → deployments UPDATE (traffic_split={winner: 0.9, next: 0.1})
  → Else:
      → deployments UPDATE (traffic_split={winner: 1.0})
      → deployments UPDATE (experiment_status="completed")
```

### Winner Determination

| confidence | Outcome |
|---|---|
| ≥ 0.95 | Challenger promoted to new baseline |
| ≤ 0.05 | Baseline holds |
| otherwise | Continue observing |

### ArcanaInsight Validation Gate (F-4.11)

Phase 4-B is complete when at least one experiment round converges (n ≥ 100 per variant), the winner is automatically promoted (no manual intervention), and the judge_score delta is documented in `docs/WEEKLY.md`.

---

## 9. External Validation — RAGAS

> **TODO (F-4.6):** This section is completed in the Phase 4-B implementation PR. Required elements to document when implemented:
>
> - RAGAS metrics computed: `faithfulness`, `answer_relevancy`, `context_precision` (cite Es et al. 2023)
> - Computation trigger: parallel job alongside `judge`, or sequential after judge completes?
> - New DB table: `ragas_scores (trace_id PK FK, faithfulness FLOAT, answer_relevancy FLOAT, context_precision FLOAT, computed_at TIMESTAMPTZ)`
> - Relationship to Judge score: displayed together in SpanWaterfall; both feed into EVOLVE weighted sum (§8)
> - Divergence alerting: threshold for Judge/RAGAS contradiction and what action is taken

---

## 10. Known Limitations & Biases

This table is **append-only**. Resolved items are annotated `Resolved: YYYY-MM-DD (F-X.Y)` but never deleted.

| ID | Area | Description | Severity | Status |
|---|---|---|---|---|
| L-1 | GENERATE RAG | `chunk_size` meta-prompt constraint (128–1024) is narrower than Pydantic validator (128–2048). LLM may return values outside the stated range; Pydantic will accept them. | Low | Open — fix in Phase 4-B (align constraints) |
| L-2 | GENERATE RAG | `top_k` meta-prompt constraint (3–10) narrower than Pydantic (1–20). Same issue as L-1. | Low | Open — fix in Phase 4-B |
| L-3 | GENERATE Eval | Meta-prompt requests 20 eval pairs; ROADMAP F-3.3 targets 30–50. Resolution needed before Phase 4-B: pick one as SoT and update the other. | Medium | Open — resolve before Phase 4-B start |
| L-4 | GENERATE Base | Longest prompt selected as base for variant generation. May select a verbose but low-signal template. | Low | Open — no fix planned; acceptable heuristic |
| L-5 | Judge + GENERATE | Temperature not explicitly set on any LLM call. SDK default may change across versions, affecting score reproducibility. Fix: add `temperature=0` or `temperature=1` with documented rationale. | Low | Open — fix in Phase 4-B |
| L-6 | Judge semantics | Judge scores domain alignment, not response correctness (actual call text not stored — privacy decision). Intentional for Phase 4-A. Opt-in text storage deferred to Phase 5. | By design | Deferred to Phase 5 |
| L-7 | Judge context | Oldest 3 eval_pairs used as judge reference; no relevance-based selection. Newer, more representative pairs may exist but are not used. | Medium | Open — improve in Phase 4-B |

---

## 11. References

- **DSPy**: Khattab, O., Singhvi, A., et al. "DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines." arXiv:2310.03714 (2023). Informs EVOLVE's automated prompt optimization approach (§8).
- **RAGAS**: Es, S., James, J., et al. "RAGAS: Automated Evaluation of Retrieval Augmented Generation." arXiv:2309.15217 (2023). Defines metrics used in §9.
- **HyDE**: Gao, L., et al. "Precise Zero-Shot Dense Retrieval without Relevance Labels." ACL 2023. Informed HARVEST query generation design.
- **Contextual Retrieval**: Anthropic (2024). "Contextual Retrieval" technical report. Informed chunk-level context injection in HARVEST.
- **Bayesian A/B Stopping**: Deng, A., et al. "Objective Bayesian Two Sample Hypothesis Testing for Online Controlled Experiments." WWW 2016. Will underpin §7 stopping criterion.

---

_Last updated: 2026-04-23 | Maintainer: Update this file in the same PR as any prompt, model, or formula change_
