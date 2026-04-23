# Verum — Remaining Work

> Last updated: 2026-04-24  
> All code work is complete through Phase 5. This document tracks the tasks that require xzawed's direct action (real-world data, deployment, recording, publishing).

---

## 실행 순서

```
F-4.11  →  F-5.12  →  F-5.11  →  F-5.8  →  F-5.13  →  F-5.9
(데이터)   (데모배포)  (영상)     (블로그)   (공개)      (HN)
```

뒤 작업은 앞 작업이 완료돼야 의미가 있습니다.

---

## F-4.11 — ArcanaInsight 자동 진화 1사이클

**담당:** xzawed (ArcanaInsight 운영)  
**상태:** 🔲 프로덕션 데이터 누적 대기 중

### 완료 조건

- [ ] Railway 마이그레이션 `0010_phase4b_experiment_evolve` 프로덕션 적용 확인
- [ ] ArcanaInsight에서 `original` 변형 트레이스 ≥ 100개 누적 (judge_score 있는 것)
- [ ] ArcanaInsight에서 `cot` 변형 트레이스 ≥ 100개 누적
- [ ] EXPERIMENT confidence ≥ 0.95 도달 → EVOLVE 잡 자동 실행 확인
- [ ] `docs/WEEKLY.md` before/after 메트릭 기록

### 목적

Verum의 핵심 가치 명제("프롬프트가 사람 개입 없이 자동으로 개선된다")를 실제로 증명합니다. 이 작업 없이는 케이스 스터디·HN 포스트에 "실제로 작동했다"는 숫자를 쓸 수 없습니다.

### 수렴 후 채울 내용

[docs/CASE_STUDY.md](CASE_STUDY.md) §EXPERIMENT/EVOLVE/Results 섹션의 `[TBD]` 부분을 실측값으로 교체.

---

## F-5.12 — demo.verum.dev 배포

**담당:** xzawed (Railway 설정)  
**상태:** 🔲 시드 스크립트 준비 완료, Railway 배포 미실행

### 준비된 것

- `scripts/seed_demo.py` — 실행하면 420 traces, 2개 수렴 실험, 30 chunks 포함 데모 데이터 생성 (멱등)

### 해야 할 것

1. Railway에 별도 Postgres 서비스 생성 (데모 전용 DB)
2. 환경 변수 `DATABASE_URL` 설정 후 시드 스크립트 실행:
   ```bash
   cd apps/api
   DATABASE_URL="postgresql+asyncpg://..." python ../../scripts/seed_demo.py
   ```
3. 기존 Railway 앱에 `DEMO_MODE=true` 환경 변수 추가 (또는 별도 서비스 배포)
4. `demo.verum.dev` DNS 연결

### 목적

설치 없이 5초 만에 대시보드를 볼 수 있는 링크. HN 포스트에 "지금 바로 보기" 링크가 없으면 초기 전환율이 크게 낮아집니다.

---

## F-5.11 — Loom 데모 영상 (3–5분)

**담당:** xzawed (직접 녹화)  
**상태:** 🔲 F-4.11 완료 후 진행

### 촬영 내용

1. ArcanaInsight repo 연결 (ANALYZE → INFER 결과 화면)
2. HARVEST 진행 화면 (타로 지식 수집)
3. GENERATE 결과 (5개 변형 프롬프트 생성 화면)
4. EXPERIMENT 대시보드 (Bayesian confidence bar, 실제 수렴 그래프)
5. EVOLVE 완료 — "CoT 변형이 original보다 +X% judge_score 향상으로 자동 승격"

### 목적

텍스트와 스크린샷으로 설명할 수 없는 "자동 진화 루프 전체"를 3분 안에 보여줍니다. README 상단에 영상 링크가 있으면 가입 전환율과 GitHub 스타 수에 직접 영향을 줍니다.

---

## F-5.8 — 블로그 포스트 발행

**담당:** xzawed (검토 후 발행)  
**상태:** 🔲 초안 완성, 발행 미실행

### 준비된 초안

| 파일 | 발행 플랫폼 | 제목 |
|------|------------|------|
| [docs/blog/01-why-not-langchain.md](blog/01-why-not-langchain.md) | dev.to (우선) | "We built an LLM optimization platform without LangChain. Here's why." |
| [docs/blog/02-bayesian-ab-llm-prompts.md](blog/02-bayesian-ab-llm-prompts.md) | dev.to | "Bayesian A/B Testing for LLM Prompts: Why Frequentist Statistics Don't Work" |
| [docs/blog/03-verum-architecture.md](blog/03-verum-architecture.md) | dev.to | "Architecture of Verum: 8 stages, one PostgreSQL database, no vector database" |

### 발행 순서

1. `01-why-not-langchain.md` — **HN 포스팅 2일 전**에 발행 (HN 본문에서 참조)
2. `02-bayesian-ab-llm-prompts.md` — HN 이후 당일 또는 다음 날
3. `03-verum-architecture.md` — HN 이후 1주일 이내

### 목적

HN 포스트만 올리면 "왜 만들었는가"를 설명할 공간이 부족합니다. 블로그 포스트가 기술적 깊이를 보여주고 검색 유입을 만듭니다.

---

## F-5.13 — GitHub 레포 공개

**담당:** xzawed  
**상태:** 🔲 코드 준비 완료, 레포 private 상태

### 할 일

1. `github.com/xzawed/verum` → Settings → Danger Zone → Make public
2. GitHub Actions CI가 public 레포에서 정상 실행되는지 확인
3. README 상단 CI 배지가 녹색인지 확인

### 목적

공개 레포가 없으면 HN 포스트를 올릴 수 없습니다. GitHub 스타, fork, issue가 모두 공개 이후에만 가능합니다.

---

## F-5.9 — Hacker News 런치

**담당:** xzawed  
**상태:** 🔲 킷 준비 완료, 발행 미실행

### 준비된 것

[docs/HN_LAUNCH.md](HN_LAUNCH.md) — 제출 제목·본문·Q&A 8건·타이밍 가이드·크로스포스팅 계획 포함

### 런치 선행 조건 체크리스트

- [ ] GitHub 레포 공개 (F-5.13)
- [ ] `demo.verum.dev` 라이브 (F-5.12)
- [ ] `01-why-not-langchain` 블로그 발행 (F-5.8 — 2일 전)
- [ ] F-4.11 실측 결과 존재 (케이스 스터디 숫자 채워짐)
- [ ] `docker compose up` 동작 검증 (fresh 환경)

### 목적

모든 선행 조건이 갖춰진 뒤 올려야 "그래서 실제로 됩니까?"라는 HN 댓글에 데모 링크·실측 수치로 즉시 답할 수 있습니다.

---

## 요약표

| 항목 | 담당 | 선행 조건 | 코드 준비 |
|------|------|----------|----------|
| F-4.11 ArcanaInsight 자동 진화 | xzawed (운영) | Railway 마이그레이션 적용 | ✅ |
| F-5.12 demo.verum.dev 배포 | xzawed (Railway) | 없음 (지금 바로 가능) | ✅ `scripts/seed_demo.py` |
| F-5.11 Loom 영상 녹화 | xzawed | F-4.11 완료 | — |
| F-5.8 블로그 발행 | xzawed | 초안 검토 | ✅ `docs/blog/` |
| F-5.13 GitHub 레포 공개 | xzawed | CI 녹색 확인 | ✅ |
| F-5.9 HN 런치 | xzawed | F-5.12, F-5.13, F-5.8(1편), F-4.11 | ✅ `docs/HN_LAUNCH.md` |
