# ArcanaInsight × Verum: Case Study

> First dogfood deployment of The Verum Loop on a live tarot-reading AI service.

---

## The Problem

Building an AI-powered service is the easy part. Keeping it good — without burning hours tuning prompts manually — is the hard part.

xzawed's tarot reading app, ArcanaInsight, ran on a handful of Grok and Anthropic LLM calls written over several months. Each prompt was authored by hand, tested informally, and never systematically evaluated against alternatives. When a reading felt off, there was no data to explain why. When a prompt was updated, there was no way to know if the new version was actually better.

This is the problem Verum was built to solve: connect a repo, let the system understand what the service is doing, and close the loop from observation to evolution — automatically.

ArcanaInsight became Verum's first real test.

---

## ArcanaInsight at a Glance

ArcanaInsight is a Korean-language AI tarot reading service targeting consumer users (B2C). Users submit a question or situation; the service draws cards and returns a structured reading in a mystical, empathetic tone.

Key characteristics:
- **LLM usage**: Grok (primary), Anthropic (secondary), with a small number of raw HTTP fetches to LLM APIs
- **Language**: Korean (UI and LLM output)
- **Tone requirement**: mystical, narrative, emotionally resonant
- **User type**: consumer, not technical

These characteristics shaped every decision Verum made downstream.

---

## How Verum Connected

Connection took under two minutes. After GitHub OAuth authorization, Verum was granted read access to the ArcanaInsight repository. No service execution was required. All analysis was performed statically — Verum never ran ArcanaInsight's code.

Once connected, Verum queued a full loop run: ANALYZE → INFER → HARVEST → GENERATE → DEPLOY. OBSERVE, EXPERIMENT, and EVOLVE are running as the service accumulates traces.

---

## Stage-by-Stage: What Happened

### ANALYZE

Verum's static analysis engine parsed the ArcanaInsight repository using Python AST and tree-sitter, scanning for LLM call sites across all files.

**Findings:**
- **8 LLM call sites detected**
  - 4 using the Grok SDK (`xai_grok.chat.completions.create`)
  - 2 using the Anthropic SDK (`anthropic.messages.create`)
  - 2 raw HTTP fetches to LLM API endpoints
- **238 prompt templates extracted** — including inline strings, f-string templates, and multiline docstring-style prompts
- **Model and parameter inventory**: temperature settings ranged from 0.7 to 1.1 across call sites; max_tokens was inconsistently set
- **Input variables identified**: `card_names`, `user_question`, `spread_type`, `reading_context`

The raw-fetch call sites were the most fragile — they bypassed SDK abstractions entirely and would be opaque to any observability layer not specifically looking for them. Verum flagged these for attention.

The ANALYZE stage produced a structured JSON artifact that served as the input to every subsequent stage.

### INFER

The ANALYZE output — prompts, parameter configs, README content, and type definitions — was passed to Claude Sonnet 4.6 for service intent inference.

**INFER output:**

```json
{
  "domain": "tarot_divination",
  "tone": "mystical",
  "language": "ko",
  "user_type": "consumer",
  "primary_sdk": "grok",
  "key_variables": ["card_names", "user_question", "spread_type"],
  "confidence": 0.94
}
```

The classification was correct on the first pass. The `tarot_divination` domain label unlocked domain-specific crawling strategies in HARVEST. The `mystical` tone label later constrained prompt variant generation to avoid clinical or analytical phrasing. The `ko` language flag forced Korean-language source prioritization during crawling.

### HARVEST

Using the INFER domain classification, Verum selected crawling sources appropriate for tarot divination knowledge:

- Tarot interpretation reference sites (card meanings, spread interpretations)
- Wikipedia Korean tarot category and linked articles
- Public tarot study guides with permissive licensing

Verum proposed these sources to xzawed for review before crawling began. After approval, the crawler fetched, cleaned, and chunked the content using recursive character splitting (chunk size 512, overlap 64). Chunks were embedded using `text-embedding-3-small` and stored in pgvector.

**HARVEST result:** Tarot knowledge corpus loaded into pgvector, ready to serve RAG queries during generation and live inference.

Korean-language sources required special handling. Many reference sites mixed Korean and classical Chinese characters in card interpretations. The crawl pipeline needed explicit language filtering to keep chunks coherent.

### GENERATE

With the domain context and knowledge corpus in place, Verum generated five prompt variants from the original ArcanaInsight prompts:

| Variant ID | Strategy | Description |
|---|---|---|
| `original` | Baseline | Preserved original prompt unchanged |
| `cot` | Chain-of-Thought | Added explicit reasoning steps before the final reading |
| `few_shot` | Few-Shot | Injected two example card readings before the user's question |
| `role_play` | Role-Play Persona | Framed the LLM as a named mystical reader with a defined voice |
| `concise` | Concise | Stripped elaboration, focused on directness and card keywords |

Each variant was saved as a versioned prompt template. The `original` variant was designated as the current champion.

Verum also generated:
- **RAG configuration**: semantic retrieval over the tarot knowledge corpus, top-k=5, with MMR reranking to reduce redundancy
- **Evaluation dataset**: 20 question-answer pairs covering common tarot query patterns (relationship spreads, career spreads, single-card pulls), with expected tone markers and forbidden patterns (clinical language, direct fortune-telling claims)

### DEPLOY

Verum deployed via in-process auto-instrumentation. The ArcanaInsight integration added three lines:

```python
import verum.openai  # replaces: import openai

# All existing openai.chat.completions.create() calls are intercepted in-process.
# Pass the deployment ID to activate variant routing and RAG injection:
response = client.chat.completions.create(
    ...,
    extra_headers={"x-verum-deployment": DEPLOYMENT_ID},
)
```

Verum intercepts the call inside the process — there is no gateway or proxy involved. The interception handles:

- Prompt variant selection based on active experiment configuration
- RAG context injection before the LLM call
- Trace capture (input, output, model, latency, token counts) via OpenTelemetry spans
- Traffic splitting across variants according to experiment weights

The integration is **fail-open**: a 5-layer safety net (timeout guard, circuit breaker, exception catch, flag check, import-time fallback) ensures that any Verum outage or error falls through to the original LLM call transparently. ArcanaInsight's users are never impacted by Verum infrastructure issues.

Initial deployment split: 90% `original`, 10% across challenger variants (2.5% each). This canary phase ran for 48 hours before the experiment formally started.

No prompts were applied without xzawed's explicit approval of the variant generation output. Verum treats all generated assets as proposals until a human confirms.

### OBSERVE

During live operation, Verum captures per-request traces including:
- Full prompt (variant ID, not raw text — privacy boundary)
- Model, temperature, token counts (input and output)
- Wall-clock latency
- LLM-as-Judge score — evaluated via a separate judge call using token metadata, not the response text itself, to keep user content private

Judge scoring criteria for tarot readings:
1. Tone consistency with `mystical` domain profile
2. Korean fluency and register appropriateness
3. Structural completeness (card interpretation + synthesis)
4. Absence of disallowed patterns (clinical certainty claims, off-domain tangents)

Cost and latency dashboards are live. Per-trace cost is computed from token counts and model pricing.

### EXPERIMENT

Verum runs sequential pairwise Bayesian A/B comparison. The challenger order is:

```
cot → few_shot → role_play → concise
```

Each challenger is compared against the current champion in turn. A challenger is promoted only when the convergence condition is met:

- **n ≥ 100 traces per variant** AND
- **posterior confidence ≥ 0.95** (challenger wins) or **≤ 0.05** (challenger loses)

The winner score formula used to rank variants:

```
winner_score = judge_score - 0.1 × (cost_usd / max_cost_in_window)
```

This formula trades a small cost penalty against quality, biased heavily toward quality (0.9 weight) with a light cost correction. The `max_cost_in_window` denominator normalizes across variants running concurrently.

**Current status:** F-4.11 (the live auto-evolution gate) is pending. Trace accumulation is ongoing. Metrics will be filled in once each variant has reached n ≥ 100 traces.

| Challenger | Traces (n) | Judge Score (avg) | Cost/req (avg) | Winner Score | Outcome |
|---|---|---|---|---|---|
| `cot` vs `original` | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| `few_shot` vs winner | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| `role_play` vs winner | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| `concise` vs winner | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |

*[TBD — fill after F-4.11 completes and n ≥ 100 per variant is reached]*

### EVOLVE

When the EXPERIMENT stage reaches convergence, Verum will automatically promote the highest-scoring variant to champion status. The previous champion is archived, not deleted — every version remains accessible for audit or rollback.

After promotion, the loop restarts: the promoted variant becomes the new baseline, and the next GENERATE cycle can produce further refinements.

**Final champion:** [TBD — fill after F-4.11 completes]

---

## Results

*Placeholder — to be updated after F-4.11 completes and all challenger rounds converge.*

| Metric | Baseline (`original`) | Best Challenger | Delta |
|---|---|---|---|
| Avg judge score | — | — | — |
| Avg cost per request (USD) | — | — | — |
| Avg latency (p50, ms) | — | — | — |
| Avg latency (p95, ms) | — | — | — |
| Winner score | — | — | — |
| Traces to convergence | — | — | — |

*[TBD — fill after F-4.11 completes]*

---

## Lessons Learned

**1. Mystical tone is a first-class constraint, not a style preference.**

The `mystical` tone classification from INFER had to propagate through every downstream stage: crawl source selection, few-shot example curation, judge scoring criteria, and forbidden pattern detection. When it was treated as an afterthought, generated variants drifted toward analytical or clinical language — technically correct but tonally wrong for ArcanaInsight's users. Building tone as a structured constraint from INFER forward fixed this.

**2. Korean content required domain-specific crawl sources.**

Generic web crawling strategies for tarot divination returned predominantly English results. Korean tarot interpretation resources are distributed across niche blogs, Naver Cafe communities, and a small number of curated reference sites. The crawl strategy had to be explicitly Korean-first. Mixed Korean/classical Chinese content in traditional card interpretations also required filtering — raw chunks from some sources were linguistically incoherent without cleanup.

**3. Judge scoring via token metadata, not response text.**

ArcanaInsight readings contain personal user data — the questions users ask are sensitive. Passing full response text to a judge LLM would mean routing user content through a second model call, creating a privacy exposure. Verum's judge operates on token count metadata, latency, and variant ID — not the text of the reading itself. The judge prompt evaluates the prompt template against the domain profile rather than the actual output. This is a meaningful privacy tradeoff, and it means the judge is assessing prompt quality (structural, tonal) rather than output quality (factual, helpful). Both matter; Verum currently covers the former.

**4. Raw HTTP fetch sites need explicit instrumentation.**

The two raw-fetch LLM calls in ArcanaInsight were invisible to SDK-level auto-instrumentation. Verum flagged them during ANALYZE but could not automatically intercept them. They required a one-time manual update to use the `openai` SDK (so that `import verum.openai` could intercept them) or to export OTLP spans directly to Verum's receiver at `POST /api/v1/otlp/v1/traces`. This is a known gap — future ANALYZE versions will generate migration boilerplate for raw fetch patterns automatically.

**5. Canary deployment is non-negotiable for consumer services.**

Starting at 90/10 traffic split and running 48 hours before formal experiment start gave Verum time to detect instrumentation bugs (one trace field was missing a variant ID for the first 6 hours) without exposing all users to unvalidated variants. For B2C services with emotionally sensitive content, gradual rollout matters more than speed to convergence.

---

## What's Next

**F-4.11 completion**: Once each variant accumulates n ≥ 100 traces, the experiment rounds will converge and the first automatic promotion will execute. This will be the first time a Verum-managed prompt replaces a human-authored one in a live service.

**Eval dataset expansion**: The 20-pair evaluation dataset is sufficient for initial tuning but limited for systematic quality assessment. The next GENERATE cycle will expand it to 50 pairs with coverage across all major spread types (Celtic Cross, three-card, single-card) and question categories (relationships, career, personal growth).

**HARVEST refresh cycle**: Tarot interpretation is a relatively stable domain, but seasonal content (new year spreads, eclipse readings) is worth capturing. A scheduled quarterly re-harvest will keep the knowledge corpus current.

**Multi-service generalization**: ArcanaInsight is one service. The patterns here — especially the tone-as-constraint architecture and Korean-language crawl handling — are being extracted into Verum's domain configuration layer so they apply automatically when a new service with similar characteristics is connected.

---

*This case study reflects the state of the ArcanaInsight × Verum deployment as of 2026-04-23. EXPERIMENT and EVOLVE metrics will be updated when F-4.11 converges.*

*Verum is open source under the MIT License. Self-hosting instructions: [SELF_HOSTING.md](./SELF_HOSTING.md)*
