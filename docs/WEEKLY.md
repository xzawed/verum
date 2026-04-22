# Verum — Weekly KPI Log

Updated every Friday by xzawed.
Template: copy the section below, fill in the date and metrics.

---

## Template

### Week of YYYY-MM-DD

#### Loop Health

| Metric | Value | Notes |
|--------|-------|-------|
| ANALYZE success rate | — % | (repos analyzed / repos attempted) |
| INFER accuracy | — % | (user-confirmed "correct" / total inferences) |
| HARVEST quality | —/5 | (manual sample review score) |
| GENERATE adoption | — % | (auto-generated prompts that became winner) |
| EXPERIMENT convergence | — days | (avg A/B test to significance) |
| EVOLVE improvement | — % | (metric delta after winner promotion) |

#### Product

| Metric | Value |
|--------|-------|
| Connected repos | — |
| ArcanaInsight weekly LLM calls | — |
| Auto-generated prompts in production | — |
| Verum weekly infra cost | $— |

#### Community (Phase 5+)

| Metric | Value |
|--------|-------|
| GitHub stars | — |
| Cloud beta users | — |
| Open issues | — |

#### Notes / Blockers

- 

---

<!-- Past weeks below — newest first -->

## 2026-04-22 — Phase 1 Completion

### ArcanaInsight ANALYZE Validation (F-1.4)

**Command:** `python -m src.loop.analyze.cli --repo https://github.com/xzawed/ArcanaInsight --branch main`

**Results:**

| Metric | Value |
|--------|-------|
| Total call_sites detected | 8 |
| Grok SDK sites | 4 |
| Anthropic SDK sites | 2 |
| raw-fetch sites | 2 |
| prompt_templates extracted | 238 |

**Sample call sites:**

```
src\services\core\grok-provider.ts:53  sdk=grok  fn=GrokProvider.generateReading
src\services\core\grok-provider.ts:85  sdk=grok  fn=GrokProvider.streamReading
src\services\core\claude-provider.ts:27  sdk=anthropic  fn=ClaudeProvider.generateReading
```

**Status:** Phase 1 ANALYZE completion gate passed — all Grok call sites detected with prompt refs extracted.

---
