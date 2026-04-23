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

## 2026-04-26 — Test Orchestration Role 구축 + 커버리지 전면 확장

### 작업 내용

이번 주는 신규 기능 없이 **테스트 인프라 전면 구축**에 집중했다.

#### .claude/ Test Role 시스템 (Phase 0)

6개 전문가 에이전트 + 3개 스킬 + PostToolUse hook + settings.json을 `.claude/`에 추가.

| 구성 요소 | 파일 |
|---------|------|
| 오케스트레이터 | `.claude/agents/test-orchestrator.md` |
| 갭 분석기 | `.claude/agents/test-gap-analyzer.md` |
| 단위 테스트 작성기 | `.claude/agents/test-unit-writer.md` |
| 통합 테스트 작성기 | `.claude/agents/test-integration-writer.md` |
| E2E 작성기 | `.claude/agents/test-e2e-writer.md` |
| 커버리지 감사기 | `.claude/agents/test-coverage-auditor.md` |
| Hook (비블로킹) | `.claude/hooks/post_test_edit.py` |

#### Python API 단위 테스트 (Phase 1)

Worker + Loop 엔진 핵심 모듈에 45개 신규 테스트 추가.
- `worker/test_chain.py`, `worker/test_runner.py` (7개 추가)
- `loop/test_utils.py` (12), `loop/test_llm_client.py` (8)
- `loop/infer/test_engine.py` (6), `loop/deploy/test_orchestrator.py` (6)

#### Dashboard 단위 테스트 (Phase 2)

16개 route handler + lib 모듈에 104개 테스트 추가 (22 Jest suites).
- `v1/analyze`, `v1/infer`, `v1/infer/[id]/confirm`, `v1/generate`, `v1/deploy` 등 16개 route
- `lib/api/validateApiKey`, `lib/github/repos`
- E2E spec 3개: `smoke.spec.ts`, `authenticated-flow.spec.ts`, `repos-flow.spec.ts`

#### Repository 단위 테스트 (Phase 3)

5개 loop stage repository 파일에 39개 신규 테스트 추가.
- `loop/analyze/repository.py` — 8 tests
- `loop/infer/repository.py` — 7 tests
- `loop/deploy/repository.py` — 8 tests (SHA-256 hash 계약 포함)
- `loop/evolve/repository.py` — 6 tests
- `loop/experiment/repository.py` — 10 tests (aggregate_variant_wins SQL 파라미터 계약)

### 최종 테스트 현황

| 구분 | 결과 |
|------|------|
| Python (non-DB) | **265 passed, 1 skipped** |
| Dashboard Jest | **104 passed (22 suites)** |
| E2E Playwright | 3 spec 파일 (dev server 필요, CI 실행) |
| Python 테스트 파일 | **38개** (loop 전 단계 + worker 전체 핸들러) |

### Loop Health (이번 주 신규 데이터 없음)

F-4.11(ArcanaInsight 자동 진화)은 프로덕션 트레이스 누적 대기 중. 데이터 수집 후 아래 표 채울 것.

| 지표 | 값 |
|------|---|
| 연결된 Repo | — |
| ArcanaInsight 주간 LLM 호출 수 | — |
| 프로덕션 중인 자동 생성 프롬프트 | — |
| Verum 주간 인프라 비용 | $— |

---

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
