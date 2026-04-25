---
type: spec
phase: 3-ext
feature: Non-Invasive SDK Integration
status: approved
created: 2026-04-25
loop-stages: [5, 6]
roadmap-ids: []
adrs: [ADR-016, ADR-017]
---

# Non-Invasive SDK Integration — Design Spec

> **Loop stages:** [5] DEPLOY (integration delivery) + [6] OBSERVE (trace ingestion)
> **Depends on:** Phase 3 (DEPLOY, SDK) + Phase 4-A (OBSERVE, traces)
> **Feeds into:** All subsequent phases — better adoption means more trace data for EXPERIMENT/EVOLVE

## Goal

Remove the friction barrier of the existing v0 SDK (`verum.Client.chat()`). The v0 API requires users to restructure their call flow: call Verum first to get modified messages, then call OpenAI themselves, then call `client.record()`. This is three extra lines and a conceptual shift.

The v1 non-invasive approach requires **one import** and optionally **one header**. The user's existing `openai` call is unchanged in form; Verum instruments it in-process.

---

## 1. Two-Phase Approach

### Phase 0 — OTLP Env-Only

Integration cost: set 3 environment variables + add 1 import at startup.

The `import verum.openai` statement at application startup registers an OpenTelemetry auto-instrumentor via the `openinference-instrumentation-openai` library. All subsequent `openai` calls are automatically traced and exported to Verum's OTLP receiver at `POST /api/v1/otlp/v1/traces`.

No A/B routing occurs in Phase 0 — it is observe-only.

### Phase 1 — Bidirectional Auto-Instrument

Integration cost: Phase 0 + add `extra_headers={"x-verum-deployment": DEPLOYMENT_ID}` to the OpenAI call.

The monkey-patch intercepts the call, fetches the current traffic split config from Verum (`GET /api/v1/deploy/[id]/config`), selects a variant, modifies the system prompt in the messages list, then proceeds with the original call. The response object returned is a standard `openai.ChatCompletion` — the caller sees no difference.

---

## 2. Gateway Pattern Rejection (ADR-016)

The alternative "proxy gateway" design was evaluated and rejected. Under a gateway design, the SDK sets `client = OpenAI(base_url="https://verum.dev/openai/proxy")`. All LLM calls route through Verum's servers.

**Reason for rejection:** This creates an inherent SPOF. If Verum's gateway is down, every user LLM call fails — there is no way to fail open inside the SDK library once `base_url` has been changed, because the HTTP connection goes to Verum, not OpenAI. The user's service availability becomes dependent on Verum's availability.

The in-process monkey-patch approach does not have this property: if the Verum config fetch fails, the original call proceeds with the original messages (fail-open). See ADR-016 for full analysis.

---

## 3. Fail-Open 5-Layer Safety Net (ADR-017)

The in-process approach only works if Verum SDK problems are guaranteed to be invisible to the caller. Five layers enforce this:

| Layer | Mechanism | Fallback |
|---|---|---|
| 1 | Hard timeout 200ms on config fetch | Abort fetch, proceed to next layer |
| 2 | Circuit breaker: 5 consecutive failures → open for 300s | Skip fetch, return stale/baseline |
| 3 | Fresh cache (60s TTL) | Serve cached config without network call |
| 4 | Stale cache (24h TTL) | Serve last-known-good config |
| 5 | Fail-open fallback | Return original messages unchanged, variant = "baseline" |

The trade-off: traffic split changes take up to 24h to fully propagate in the worst case (stale cache hit during Verum outage). This is acceptable because Verum is not in the hot path.

---

## 4. ActivationCard

Before the user installs the SDK, the dashboard shows an `ActivationCard` component populated from `GET /api/v1/activation/[repoId]`. It surfaces:

- INFER result: inferred domain, tone, language
- HARVEST result: chunk count, collection name
- GENERATE result: number of prompt variants ready

Two buttons offer the Phase 0 and Phase 1 integration PRs. This replaces the old `SdkPrSection` which showed a generic install snippet regardless of whether Verum had learned anything about the service.

---

## 5. Key Files

| File | Role |
|---|---|
| `packages/sdk-python/src/verum/openai.py` | Monkey-patch entrypoint. Import-time side effect: registers OTLP instrumentor + patches `openai.OpenAI`. |
| `apps/dashboard/src/app/api/v1/otlp/v1/traces/route.ts` | OTLP receiver. Accepts openinference protobuf or JSON. Writes to `traces`/`spans` tables. |
| `apps/dashboard/src/app/api/v1/activation/[repoId]/route.ts` | ActivationCard data endpoint. Returns INFER/GENERATE/HARVEST summary. |
| `apps/dashboard/src/app/repos/[id]/ActivationCard.tsx` | Dashboard UI. Replaces `SdkPrSection`. Shows domain/chunks/variants + two PR buttons. |
| `examples/arcana-integration/after.py` | ArcanaInsight after: 2-line diff from before.py. `import verum.openai` + `extra_headers`. |
