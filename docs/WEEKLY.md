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

## 2026-04-23 — Phase 4-B Completion (EXPERIMENT + EVOLVE shipped)

### F-4.11 ArcanaInsight Auto-Evolution Tracking

Phase 4-B 코드가 main에 머지됐다. F-4.11 완료 게이트를 위해 아래 항목을 xzawed가 채워야 한다.

**완료 조건:**
- [ ] Railway 마이그레이션 `0010_phase4b_experiment_evolve` 프로덕션 적용 확인
- [ ] ArcanaInsight baseline(`original`) 콜 ≥ 100 누적 (judge_score 있는 것)
- [ ] ArcanaInsight challenger(`cot`) 콜 ≥ 100 누적
- [ ] confidence ≥ 0.95 수렴 → EVOLVE 잡 자동 실행 확인
- [ ] before/after judge_score delta 기록 (아래 표)

**Before/After 메트릭 (수렴 후 xzawed 기입):**

| 지표 | original (before) | {winner} (after) | delta |
|------|------------------|-----------------|-------|
| avg judge_score | — | — | — |
| avg cost_usd | $— | $— | — |
| avg winner_score | — | — | — |
| convergence confidence | — | — | — |
| round (1~4) | — | — | — |

---

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
