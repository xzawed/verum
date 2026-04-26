# CLAUDE.md

This file is the single source of truth for Claude Code working on **Verum**.
Read it completely before any significant action, and re-read it when starting a new session.

## 📋 세션 시작 시 필독 순서

새 대화를 시작하면 이 순서로 읽는다:

1. **`CLAUDE.md`** (이 파일) — 프로젝트 정체성·규칙·스택 파악
2. **`docs/STATUS.md`** — 현재 구현 상태, 파일 맵, API 인덱스 (가장 자주 참조)
2.5. **`docs/INDEX.md`** — 어떤 문서가 어떤 주제의 owner인지 확인 (anti-duplication 표)
3. **`docs/ROADMAP.md`** — 다음에 구현할 Phase와 deliverable ID 확인
4. **`docs/LOOP.md`** — 특정 단계의 알고리즘·I/O 계약 확인 시
5. **`.claude/agents/test-orchestrator.md`** — 신규 모듈 추가 후 또는 커버리지 감사 시

> **단, 코드를 변경하기 전에 반드시 실제 파일을 Read로 확인한다. STATUS.md는 스냅샷이며 코드가 SoT다.**

---

## 🎯 프로젝트 정체성

### Verum이란

**Verum** (라틴어로 "진실")은 **AI 서비스를 자동으로 분석하고 최적화하는 플랫폼**입니다.

핵심 동작 원리는 단순합니다:

> **사용자가 Repo를 연결한다 → Verum이 코드를 분석한다 → LLM 호출 패턴을 이해한다 → 최적 프롬프트·RAG·평가셋·대시보드를 자동으로 만들어준다 → 실제 운영 중 A/B 테스트로 계속 진화한다.**

### 한 줄 정의

> *Connect your repo. Verum learns how your AI actually behaves, then auto-builds and auto-evolves everything around it — prompts, RAG, evals, observability.*

### 경쟁 포지셔닝

| 비교 대상 | 그들이 하는 것 | Verum이 추가로 하는 것 |
|-----------|---------------|----------------------|
| **Langfuse / LangSmith** | LLM 호출 관측 | 관측 결과로 프롬프트·RAG 자동 생성·진화 |
| **RAGAS** | RAG 평가 | 서비스 맞춤 평가셋 자동 구축 |
| **PromptLayer** | 프롬프트 버전 관리 | 프롬프트를 AI가 만들고 A/B 테스트로 고름 |
| **CodeRabbit / SCAManager** | 코드 리뷰 | 코드 분석 결과를 AI 서비스 최적화에 사용 |

**한 마디로**: 시장의 다른 도구들은 "사람이 LLM 시스템을 운영하는 걸 돕는" 도구이고, Verum은 "LLM 시스템이 스스로 개선되도록 돕는" 도구입니다.

### 왜 만드는가

1. **제품적 목적**: xzawed의 여러 AI 서비스(ArcanaInsight 외 앞으로 만들 것들)를 자동으로 고도화
2. **경력적 목적**: AI/LLM 엔지니어로 포지셔닝. "Auto-optimizing LLM infrastructure"라는 키워드는 이력서에서 희소성 최상
3. **생태계적 목적**: 오픈소스 공개. 한국발 LLM 인프라 도구로 기여

### 핵심 가치

- **Automation over instrumentation**: 사람이 손으로 하던 걸 자동화. 이게 Verum의 본질
- **Observe → Learn → Generate → Evolve**: 이 루프가 닫혀서 돌아야 Verum이다
- **Repo-first**: 모든 분석의 출발점은 Repo. 서비스 실행 중이 아니어도 분석 가능해야 함
- **Dogfood relentlessly**: xzawed 본인의 서비스에 먼저 적용. 안 되면 남에게 파는 게 의미 없음

---

## 🔁 The Verum Loop (핵심 루프)

Verum이 하는 모든 일은 이 루프 안에 있습니다. 새 기능을 만들 때 "이게 루프의 어느 단계에 해당하는가"를 먼저 답할 수 없으면 그 기능은 Verum의 기능이 아닙니다.

```
  ┌─────────────────────────────────────────────────────────────┐
  │                                                             │
  │   [1] ANALYZE         Repo 정적 분석으로 LLM 호출 패턴 추출  │
  │         ↓                                                   │
  │   [2] INFER           서비스 도메인·목적·스타일을 추론       │
  │         ↓                                                   │
  │   [3] HARVEST         도메인 관련 외부 지식을 자동 수집      │
  │         ↓                                                   │
  │   [4] GENERATE        프롬프트·RAG·평가셋·대시보드 자동 생성 │
  │         ↓                                                   │
  │   [5] DEPLOY          생성물을 서비스에 SDK/API로 주입       │
  │         ↓                                                   │
  │   [6] OBSERVE         실제 운영 중 호출·결과를 추적          │
  │         ↓                                                   │
  │   [7] EXPERIMENT      A/B 테스트로 여러 버전 비교 실행       │
  │         ↓                                                   │
  │   [8] EVOLVE          승자 버전 선택 → 패배 버전 폐기        │
  │         ↓                                                   │
  └──────── [1]로 복귀. 계속 학습하고 계속 개선 ────────────────┘
```

### 각 단계의 구체적 정의

**[1] ANALYZE — Repo 정적 분석**
- AST 파싱으로 LLM 호출 지점 탐지 (OpenAI/Anthropic/Grok SDK 사용 위치)
- 프롬프트 문자열·템플릿 추출
- 입력 변수·출력 소비 패턴 추적
- 모델·파라미터(temperature 등) 설정 파악
- 서비스 실행 필요 없음 — 이게 "정적 분석" 원칙

**[2] INFER — 서비스 의도 추론**
- 추출된 프롬프트 + Repo 문서(README, 주석) + 타입 정의를 LLM에 입력
- "이 서비스는 무엇을 하는가? 어떤 도메인인가? 어떤 톤을 원하는가?"를 구조화된 JSON으로 응답받음
- 예: `{"domain": "tarot_divination", "tone": "mystical", "language": "ko", "user_type": "consumer"}`

**[3] HARVEST — 도메인 지식 자동 수집**
- INFER 결과의 `domain`에 따라 크롤링 전략 선택
- 전략 예시:
  - `tarot_divination` → 타로 해석서 사이트, Wikipedia 타로 카테고리
  - `code_review` → StackOverflow 태그별, ESLint 문서
  - `legal_qa` → 국가법령정보센터, 판례 데이터베이스
- LLM이 자체적으로 "이 도메인에는 어떤 소스가 권위 있는가"를 제안하고 사용자 승인 후 크롤링
- 수집 결과는 청킹·임베딩·pgvector 저장

**[4] GENERATE — 자산 자동 생성**
- **프롬프트 템플릿**: 기존 프롬프트의 여러 변형(Chain-of-Thought, Few-shot 등) 생성
- **RAG 인덱스**: HARVEST 결과를 서비스 맞춤으로 청킹·임베딩
- **평가셋**: 예상 질의 20~50개를 LLM이 생성하고 정답 쌍을 만들어 보관
- **대시보드 설정**: 서비스 특성에 맞는 메트릭 자동 선택 (B2C 서비스라면 지연시간·만족도 우선)

**[5] DEPLOY — 서비스에 주입**
- **Phase 0 (코드 변경 0줄)**: `OTEL_EXPORTER_OTLP_ENDPOINT` 환경변수만 설정. OTLP 스팬 수신 → 관측 전용
- **Phase 1 (1줄 통합)**: `import verum.openai` (또는 `import "@verum/sdk/openai"`)만 추가 + 기존 LLM 호출에 `extra_headers={"x-verum-deployment": DEPLOYMENT_ID}` 1개 헤더. 5중 안전망(200ms timeout → circuit breaker → 60s cache → 24h stale cache → fail-open)으로 Verum 장애 시에도 사용자 서비스 100% 가용. ADR-016 (no gateway), ADR-017 (fail-open mandatory) 참조
- Verum 대시보드에서 "이 프롬프트를 운영 중 10%에 시험 배포" 같은 제어 (`traffic_split` 기본 0% — 사용자 승인 전 자동 적용 없음)

**[6] OBSERVE — 운영 중 추적**
- OpenTelemetry 호환 trace/span 수집
- 입력·출력·모델·지연·비용 모두 기록
- 사용자 피드백(👍👎) 수집

**[7] EXPERIMENT — 자동 A/B**
- 여러 프롬프트 변형이 존재하면 트래픽을 자동 분할
- RAG 전략 여러 개(예: semantic chunking vs recursive chunking)도 동시 비교
- 통계적 유의성 확보까지 자동 모니터링

**[8] EVOLVE — 승자 채택**
- 평가 지표(사용자 만족도 + LLM-as-Judge + 비용)의 가중 합이 우위인 버전이 승자
- 승자를 기본 프롬프트로 승격, 패배자는 아카이브
- 다음 개선 사이클을 위해 [1]로 복귀

---

## 👤 작업자 정보

- **소유자**: xzawed (GitHub: xzawed)
- **위치**: 서울, 한국
- **주 언어**: 한국어 (대화), 영어 (코드·커밋·문서)
- **작업 스타일**: Claude Code와 협업. 세부 구현보다 방향·의사결정 중심

### Claude와의 대화 규칙

- **한국어로 대화하기**. 코드·커밋 메시지·PR 설명·문서는 영어
- **과도한 기초 설명 자제**. xzawed는 풀스택 경험자
- **결정이 필요한 순간은 명시적으로 물어보기**. 혼자 판단해서 진행하지 말 것
- **실수는 즉시 인정**. "죄송합니다" 한 번, 수정안 바로 제시
- **"모른다"고 솔직히 말하기**. 추측을 사실처럼 말하면 프로젝트가 산으로 간다
- **루프의 어느 단계인지 항상 의식**. "이건 [4] GENERATE의 세부 구현"처럼 구조화해서 대화

---

## 🎭 타겟 사용자와 배포 모델

### 두 종류 사용자

**① 비개발자 (SaaS 사용자)**
- Verum 클라우드(verum.dev)에 가입
- GitHub OAuth로 Repo 연결
- 대시보드에서 클릭만으로 전체 루프 실행
- 월 구독 모델 (Phase 5 이후)

**② 개발자 (셀프 호스팅)**
- `docker compose up`으로 전체 스택 자체 호스팅
- SDK를 자기 서비스에 직접 통합
- 모든 자동 생성 자산을 사람이 수정 가능
- MIT 라이선스 오픈소스

### 듀얼 모드 배포 원칙

| 컴포넌트 | 오픈소스 | 클라우드 |
|---------|---------|---------|
| 엔진(The Verum Loop) | ✅ MIT | ✅ 동일 엔진 사용 |
| 대시보드 | ✅ MIT | ✅ 동일 |
| SDK (Python/TS) | ✅ MIT | ✅ 동일 |
| 호스팅·스케일링·백업 | ❌ | ✅ Verum이 운영 |
| GitHub OAuth 통합 | ✅ 사용자가 직접 설정 | ✅ 원클릭 |
| 협업 기능(팀·권한) | ❌ (Phase 5 이후) | ✅ |
| 엔터프라이즈 지원 | ❌ | ✅ (유료) |

**핵심 원칙**: **기능에 유료/무료 경계가 있어선 안 된다. 오직 "운영을 누가 하는가"가 차이다.** Langfuse 모델을 따라간다.

---

## 🏗 기술 스택

### Worker (Python)

> **Architecture note**: FastAPI/Uvicorn은 2026-04-20 Architecture Pivot에서 완전 제거됐습니다.
> 공개 HTTP는 Next.js가 전담하고, Python은 Node.js가 PID 1로 spawn하는 **asyncio 자식 프로세스**로만 동작합니다.

- **Python**: 3.13+
- **실행 모델**: asyncio 단일 프로세스. Node.js(`instrumentation.ts`)가 부팅 시 `python3 -m src.worker.main`으로 spawn
- **ORM**: SQLAlchemy 2 + Alembic (스키마 SoT)
- **Job queue**: `verum_jobs` PostgreSQL 테이블. LISTEN/NOTIFY + SKIP LOCKED 폴링
- **정적 분석(ANALYZE 단계)**: `ast` 모듈 + `libcst` (보존형 변환) + `tree-sitter` (다언어 지원)
- **크롤링(HARVEST 단계)**: `httpx` + `trafilatura`. `playwright` (JS 렌더링)는 Phase 3에서 추가 예정
- **테스트**: pytest + pytest-asyncio
- **Lint**: pylint + flake8 + bandit + ruff

### 프론트엔드 (대시보드)

> **역할 확장**: Next.js가 공개 HTTP 전담(SDK API 포함). Python worker를 부팅 시 child process로 spawn하며 Drizzle ORM으로 Postgres에 직접 읽기/쓰기합니다.

- **프레임워크**: Next.js 16 (App Router, standalone output) + React 19
- **언어**: TypeScript strict
- **스타일링**: Tailwind CSS v4
- **차트**: Recharts
- **상태 관리**: Zustand
- **인증**: Auth.js v5 (`next-auth@5` beta) — GitHub OAuth, JWT session
- **DB 클라이언트**: Drizzle ORM (`drizzle-orm` + `pg`). 스키마는 Alembic SoT → `drizzle-kit pull`로 introspect
- **Worker spawn**: `src/instrumentation.ts` (Next.js 부팅 hook) → `src/worker/spawn.ts`

### 데이터베이스

- **주 DB**: PostgreSQL 16+
- **벡터 확장**: pgvector. **다른 벡터 DB 절대 금지** — xzawed의 PostgreSQL 전문성 활용
- **전문 검색**: PostgreSQL의 tsvector (하이브리드 검색)
- **트레이스 저장**: Phase 1-3은 PostgreSQL, Phase 4+ 고볼륨 시 ClickHouse 추가 검토

### AI / LLM

- **LLM 추상화 레이어**: 자체 구현 (OpenAI, Anthropic, Grok 통합)
- **INFER 단계 LLM**: Claude Sonnet 4.6 이상 (구조화된 추론 필요)
- **임베딩**: Voyage AI voyage-3.5 (1024-dim)
- **재순위**: 미구현 (계획됨 — BGE-reranker 또는 Cohere Rerank)
- **평가**: LLM-as-a-Judge 자체 구현 (RAGAS는 미구현, 계획됨)

### Observability

- **표준**: OpenTelemetry (OTLP 호환)
- **SDK**: Python + TypeScript 2종

### 인프라

- **배포**: Railway (초기) → Docker Compose (자체 호스팅) → Kubernetes (엔터프라이즈)
- **CI/CD**: GitHub Actions
- **컨테이너**: Docker (멀티스테이지 빌드 필수, 최종 이미지 1GB 미만)
- **도메인**: verum.dev (verumai.com 충돌 회피)

#### Dockerfile 필수 체크리스트 (Next.js standalone + Railway)

`Dockerfile`을 작성하거나 수정할 때 Claude Code는 아래 항목을 반드시 확인한다.

| 항목 | 올바른 값 | 이유 |
|------|-----------|------|
| `ENV HOSTNAME` | `0.0.0.0` | Docker가 `HOSTNAME=<container_id>`를 자동 주입. Next.js standalone `server.js`는 이 값을 bind 주소로 사용 → 미설정 시 외부 도달 불가 |
| `EXPOSE` | `8080` | Railway가 `PORT=8080`을 주입. EXPOSE는 문서 목적이므로 실제 listen 포트와 일치시킨다 |
| startup I/O | 비동기 (`promisify(execFile)` 등) | Node.js event loop를 블로킹하면 Railway의 첫 healthcheck probe가 timeout |
| `/health` endpoint | 인증 우회 + 즉시 200 | Auth.js middleware matcher에서 제외. DB/worker I/O 금지 — Railway probe timeout(5s)을 초과하면 실패 |

**Railway 배포 전 로컬 검증 필수**: Dockerfile 또는 `alembic/`, `apps/api/src/worker/`를 건드린 PR은 push 전에 반드시 `make docker-healthcheck`를 실행한다. `pnpm dev`는 standalone을 사용하지 않으므로 이 종류의 버그가 로컬에서 재현되지 않는다.

---

## 📁 프로젝트 구조

```
verum/
├── .claude/                    # Claude Code 전용 설정
├── .github/                    # GitHub Actions, issue/PR 템플릿
├── docs/
│   ├── ARCHITECTURE.md        # The Verum Loop 상세 설계
│   ├── DECISIONS.md           # ADR (Architecture Decision Records)
│   ├── ROADMAP.md             # 6개월 로드맵
│   ├── LOOP.md                # 루프 각 단계의 구현 문서
│   └── guides/                # 사용자 가이드
├── apps/
│   ├── api/                   # Python Worker (asyncio subprocess, FastAPI 아님)
│   │   ├── src/
│   │   │   ├── worker/        # Node.js가 spawn하는 worker entrypoint
│   │   │   │   ├── main.py    # asyncio entrypoint (`python3 -m src.worker.main`)
│   │   │   │   ├── runner.py  # LISTEN/NOTIFY + SKIP LOCKED job loop
│   │   │   │   └── handlers/  # analyze / infer / harvest 핸들러
│   │   │   ├── loop/          # The Verum Loop 핵심 로직 (무수정 보존)
│   │   │   │   ├── analyze/   # [1] Repo 정적 분석
│   │   │   │   ├── infer/     # [2] 서비스 의도 추론
│   │   │   │   ├── harvest/   # [3] 도메인 지식 수집
│   │   │   │   ├── generate/  # [4] 자산 자동 생성
│   │   │   │   ├── deploy/    # [5] 서비스 주입
│   │   │   │   ├── observe/   # [6] 운영 추적
│   │   │   │   ├── experiment/# [7] A/B 테스트
│   │   │   │   └── evolve/    # [8] 승자 선택
│   │   │   └── db/            # SQLAlchemy 모델, 세션
│   │   ├── tests/
│   │   └── alembic/           # 스키마 SoT (verum_jobs, worker_heartbeat 포함)
│   └── dashboard/             # Next.js — 공개 HTTP 전담 (UI + SDK API + Worker spawn)
│       └── src/
│           ├── worker/        # spawn.ts — Python worker 생애주기 관리
│           ├── lib/
│           │   └── db/        # Drizzle ORM client + introspected schema
│           └── app/           # Next.js App Router pages & API routes
├── packages/
│   ├── sdk-python/            # `pip install verum`
│   └── sdk-typescript/        # `npm install @verum/sdk`
├── examples/
│   └── arcana-integration/    # ArcanaInsight 통합 예제 (첫 dogfood)
├── Dockerfile                 # 단일 통합 이미지 (Node PID1 + Python worker)
├── docker-compose.yml
├── railway.toml
├── CLAUDE.md
├── README.md                  # 영문
├── README.ko.md               # 한글
└── LICENSE                    # MIT
```

### 디렉토리 설계 원칙

- **`apps/api/src/loop/`는 신성불가침**. The Verum Loop의 각 단계가 디렉토리로 존재해야 함. 이걸 함부로 리팩터링하지 말 것
- **`apps/` = 실행 가능한 애플리케이션**
- **`packages/` = 재사용 패키지 (SDK)**
- **`examples/` = 실전 통합 사례**. ArcanaInsight는 예제이자 첫 사용자

---

## 🗓 6개월 로드맵

### Phase 0: Foundation (Week 1-2)

**목표**: 프로젝트 기반. "Hello World" 수준이라도 배포까지.

- [x] Monorepo 초기화 (pnpm workspace + pip workspace)
- [x] GitHub 저장소 생성 (`github.com/xzawed/verum`)
- [x] MIT 라이선스
- [x] 영문 README + 한글 README
- [x] Docker Compose + Dockerfile (Node PID1 + Python worker child + PostgreSQL + pgvector)
- [x] GitHub Actions CI (lint + test) — CI workflow 존재, lint/test 타겟 구현 필요
- [x] Railway 배포 파이프라인
- [x] `/health` 헬스체크 엔드포인트

**완료 기준**: `curl https://verum-production.up.railway.app/health` → 200 OK ✅

---

### Phase 1: ANALYZE (Week 3-5)

**목표**: 루프 1단계 — Repo를 받아서 LLM 호출 패턴을 추출.

- [x] GitHub OAuth 통합 (사용자가 Repo 접근 권한 부여) — public_repo scope, 스크롤 picker UI
- [x] Repo 클론 & 격리된 임시 환경
- [ ] Python AST 기반 LLM 호출 탐지 (openai, anthropic, google.generativeai 등) — **deferred to Phase 1.5** (F-1.3)
- [x] TypeScript/JavaScript tree-sitter 기반 동일 기능
- [x] 프롬프트 문자열 추출 (f-string, template literal 등 포함)
- [x] 모델·파라미터 설정 추출
- [x] 분석 결과를 구조화된 JSON으로 저장

**완료 기준**: ArcanaInsight의 Grok 호출 지점을 모두 자동 탐지하고, 프롬프트와 파라미터를 정확히 추출

---

### Phase 2: INFER + HARVEST (Week 6-9)

**목표**: 루프 2-3단계 — 서비스 의도를 이해하고 지식을 수집.

- [x] INFER 엔진: 프롬프트 + 문서 → 도메인 JSON
- [x] 도메인 분류 체계 정의 (초기 20개 도메인 카테고리)
- [x] HARVEST 엔진: 도메인별 크롤링 전략
- [x] 크롤링 소스 제안 + 사용자 승인 플로우
- [x] 크롤링 결과 청킹 (Recursive + Semantic 비교)
- [x] pgvector에 임베딩 저장
- [x] 대시보드: INFER 결과 시각화, HARVEST 진행 상황

**완료 기준**: ArcanaInsight → `{"domain": "divination/tarot"}` 추론 성공, 타로 관련 지식 1,000 청크 이상 자동 수집

---

### Phase 3: GENERATE + DEPLOY (Week 10-13)

**목표**: 루프 4-5단계 — 자동으로 만들고 자동으로 주입.

- [x] 프롬프트 변형 생성기 (Chain-of-Thought, Few-shot, Role-play 등 5가지 패턴)
- [x] RAG 인덱스 자동 구성 (수집한 청크를 서비스 맞춤 청킹으로 재구성)
- [x] 평가셋 자동 생성 (예상 질의 + 정답 쌍 30-50개)
- [x] 대시보드 설정 자동 구성 (서비스 타입별 메트릭 선택)
- [x] Python SDK: `import verum.openai` auto-instrument (Phase 1) + `verum.retrieve()` / `verum.feedback()`. `verum.Client.chat()` deprecated (v1.x)
- [x] TypeScript SDK: `import "@verum/sdk/openai"` auto-instrument (Phase 1). `VerumClient.chat()` deprecated
- [x] **ArcanaInsight에 SDK 적용** (첫 완전 dogfood)

**완료 기준**: ArcanaInsight의 타로 상담이 Verum이 생성한 프롬프트와 RAG로 작동

---

### Phase 4: OBSERVE + EXPERIMENT + EVOLVE (Week 14-18)

**목표**: 루프 6-8단계 — 닫힌 루프 완성. 자동 진화.

- [x] OpenTelemetry 호환 trace/span 수집
- [x] 비용·지연·품질 메트릭 대시보드
- [x] A/B 테스트 엔진: 트래픽 분할, 통계적 유의성 검정
- [x] 평가 지표 통합 (RAGAS + LLM-as-Judge + 사용자 피드백)
- [x] 자동 승자 선택 로직 (가중 평균 + 신뢰구간)
- [x] 승자 승격 + 패배자 아카이브
- [ ] **ArcanaInsight에서 프롬프트 자동 진화 시연** (F-4.11 — 프로덕션 데이터 누적 필요)

**완료 기준**: ArcanaInsight 프롬프트가 사람 개입 없이 1회 이상 자동 개선되어 메트릭 향상 측정됨

---

### Phase 5: Launch (Week 19-24)

**목표**: 오픈소스 공개. 첫 외부 사용자.

- [ ] 영문 문서 완성 (docs.verum.dev)
- [ ] "How Verum Works" 기술 블로그 3편 (dev.to + Medium + velog)
- [ ] Hacker News / Reddit r/MachineLearning 런칭
- [ ] Langfuse vs Verum 정직한 비교 문서
- [ ] 3-5분 데모 영상 (ArcanaInsight 자동 최적화 실시간 시연)
- [ ] 클라우드 SaaS MVP 오픈 (verum.dev)
- [ ] 초기 10명 베타 사용자 확보

**완료 기준**: GitHub 스타 100+, 비-xzawed 사용자 10명 이상의 Repo 연결

---

## 🎨 코딩 컨벤션

### Python

- **Type hints 필수**. 모든 공개 함수
- **Async-first**. I/O는 `async def` 기본
- **Pydantic v2**. 모든 데이터 구조
- **Google 스타일 docstring**. 공개 API
- **파일 최대 500줄**. 초과 시 분리
- **한 함수 최대 50줄**. 초과 시 리팩터링

```python
# ✅ 좋은 예
async def analyze_repository(
    repo_url: str,
    *,
    branch: str = "main",
    depth: int | None = None,
) -> AnalysisResult:
    """Run ANALYZE stage on a repository.

    This is step [1] of The Verum Loop. It statically analyzes the code
    to extract LLM call patterns without executing the service.

    Args:
        repo_url: GitHub repository URL.
        branch: Target branch. Defaults to main.
        depth: Optional shallow clone depth.

    Returns:
        Structured analysis including detected LLM call sites.

    Raises:
        RepoCloneError: If the repo cannot be cloned.
        UnsupportedLanguageError: If no supported language is detected.
    """
    ...
```

### TypeScript

- **Strict mode**. 모든 strict 옵션 true
- **`any` 금지**. `unknown` 사용 후 좁히기
- **Zod로 API 응답 검증**
- **Named exports 선호**

### SQL

- **Alembic 필수**. 직접 SQL 실행 금지
- **성능 영향 쿼리는 의도적 인덱스 설계**
- **SCAManager의 FailoverSessionFactory 패턴 재사용**
- **`text()` 안에서 `:param::type` 금지** → `CAST(:param AS type)` 사용. SQLAlchemy 토크나이저가 `::` 뒤를 두 번째 named parameter로 파싱하여 asyncpg에서 `PostgresSyntaxError` 발생. 상세: [ADR-013](docs/ARCHITECTURE.md#adr-013)
- **백그라운드 루프의 `except Exception`은 반드시 `logger.exception()` 사용** — `logger.warning("%s", exc)`는 트레이스백을 삼켜 근본 원인을 숨김. 특히 `_experiment_loop` 같은 주기적 루프에서 치명적 오류가 침묵함

### 커밋 메시지 (Conventional Commits)

루프 단계를 스코프로 사용:

```
feat(analyze): add tree-sitter based JS/TS call detection
fix(infer): prevent domain misclassification for mixed-content repos
feat(harvest): implement Wikipedia crawling strategy
feat(generate): add chain-of-thought prompt variant template
fix(deploy): handle SDK version mismatch gracefully
feat(observe): add user feedback collection endpoint
feat(experiment): implement Bayesian A/B stopping criterion
feat(evolve): auto-promote winner when confidence > 0.95

docs: update Korean README with Phase 2 completion
refactor(sdk-python): extract embedding provider interface
test(generate): add prompt variant generation test cases
```

### 테스트

- **Phase 1까지**: 빠른 프로토타이핑 허용. 커버리지 무관
- **Phase 2 이상**: 커버리지 95% 이상 (`pytest --cov-fail-under=95` / Jest lines 90%, branches 78%)
- **Unit + Integration + E2E (Playwright)** 3단 구조
- **CI 실패 시 머지 차단**
- **Sonar exclusions ↔ Jest `collectCoverageFrom` 동기화 필수**: 한 쪽만 수정하면 LCOV 분모가 달라져 Jest가 Sonar 없이 실패함. 둘을 항상 쌍으로 관리할 것

---

## ⚠️ 하지 말아야 할 것 (Do Not List)

절대 금지. 예외가 필요하면 xzawed 승인.

1. **커밋 메시지·코드·주석·README에 Claude 언급 금지**
   - "Generated by Claude", "Co-authored by Claude" 등 전부 금지
   - 저자는 xzawed. Claude는 도구이자 협업자이지 공동 저자 아님

2. **비-pgvector 벡터 DB 도입 금지**
   - Pinecone/Weaviate/Qdrant/Chroma 등 전부 금지
   - PostgreSQL 통일 원칙

3. **LangChain/LlamaIndex 의존 금지**
   - Verum은 이들의 대안이자 상위 레이어
   - 의존하면 Verum의 정체성 소실
   - 저수준 라이브러리(`openai`, `anthropic`)만 직접 사용

4. **The Verum Loop 구조 훼손 금지**
   - `apps/api/src/loop/` 아래 8개 서브디렉토리 구조 유지
   - 새 기능은 반드시 "어느 단계에 속하는가" 명시
   - 단계 간 경계 모호한 PR은 반려

5. **유료/무료 기능 경계 만들지 말 것**
   - Verum의 모든 "기능"은 오픈소스. 차이는 "호스팅·운영"뿐
   - 오픈소스에서 막힌 기능이 유료에만 있으면 안 됨

6. **영문 README 없이 배포 금지**
   - 영어가 기본, 한글은 병기
   - `README.md` = 영문, `README.ko.md` = 한글

7. **ArcanaInsight 미적용 상태로 Phase 완료 선언 금지**
   - 모든 Phase는 ArcanaInsight에서 실제 작동해야 완료
   - "이론상 작동할 것"은 완료가 아님

8. **브랜드 혼동 유발 금지**
   - 정식 명칭은 **"Verum"** 단독
   - "Verum AI" 표기 금지 (verumai.com과 혼동 방지)
   - README 상단에 `> Not affiliated with Verum AI Platform (verumai.com).` 명시

9. **서비스 실행을 요구하는 분석 금지**
   - ANALYZE는 **정적 분석** 전제
   - "서비스를 돌려놔야 분석 가능"한 기능은 Verum의 핵심 원칙 위배
   - OBSERVE 단계만 예외 (당연히 운영 중 데이터 필요)

10. **자동 생성물을 강제 적용 금지**
    - GENERATE가 만든 프롬프트/RAG는 **제안**. 사용자 승인 필요
    - DEPLOY 단계에서 사람 손 거치지 않고 프로덕션 반영은 위험
    - Phase 5 이후 신뢰 축적 시 옵션으로 자동 적용 검토

---

## 🛠 개발 명령어

```bash
# === 로컬 개발 ===
make dev                 # 전체 스택 실행
make api-dev             # API만 (port 8000)
make dashboard-dev       # 대시보드만 (port 3000)

# === 루프 단계별 테스트 ===
make loop-analyze REPO=https://github.com/xzawed/ArcanaInsight
make loop-infer ANALYSIS_ID=xxx
make loop-harvest DOMAIN=tarot
make loop-full REPO=https://github.com/xzawed/ArcanaInsight  # 전체 루프 실행

# === 테스트 ===
make test                # 전체
make test-api            # Python
make test-dashboard      # Next.js + Playwright
make test-cov            # 커버리지

# === 품질 ===
make lint                # pylint + flake8 + bandit + ruff + eslint
make type-check          # mypy + tsc --noEmit

# === DB ===
make db-migrate
make db-revision m="설명"
make db-reset            # 주의: 로컬 DB 초기화
# alembic 마이그레이션 후 반드시 실행 — Drizzle 스키마 동기화
cd apps/dashboard && pnpm drizzle-kit pull

# === SDK ===
make sdk-python-build
make sdk-ts-build
make sdk-publish-dry

# === 배포 ===
make deploy-staging
make deploy-prod         # 수동 승인 필요

# === Railway 로컬 smoke test ===
# Dockerfile, alembic/, worker/ 변경 후 push 전에 반드시 실행
make docker-healthcheck
```

---

## 📊 핵심 지표 (KPI)

매주 금요일 `docs/WEEKLY.md`에 기록:

### 루프 건전성 지표
- ANALYZE 성공률 (연결된 Repo 중 분석 성공 비율)
- INFER 정확도 (사용자 확인 후 "맞다" 비율)
- HARVEST 지식 품질 (샘플 청크에 대한 수작업 평가)
- GENERATE 채택률 (자동 생성 프롬프트가 실제 승자가 되는 비율)
- EXPERIMENT 수렴 시간 (A/B 테스트가 유의미한 결과 내기까지)
- EVOLVE 개선폭 (승자 승격 후 메트릭 향상 %)

### 제품 지표
- 연결된 Repo 수
- ArcanaInsight의 주간 LLM 호출 수
- 자동 생성된 프롬프트 중 운영 중인 것
- 주간 Verum 자체 비용 ($)

### 커뮤니티 지표 (Phase 5+)
- GitHub 스타, 이슈, PR
- 클라우드 베타 가입자
- Discord/Slack 커뮤니티 규모

---

## 🧭 의사결정 가이드

Claude Code가 판단이 애매할 때 참고:

### "A와 B 중 무엇을 먼저?"
→ **The Verum Loop에서 더 앞 단계인 쪽 우선**. 뒷 단계는 앞 단계 없이 작동 안 함

### "간단한 구현 vs 확장성 있는 구현?"
→ **Phase 0-1은 간단하게. Phase 2부터 확장성**
→ 루프 코어(`apps/api/src/loop/`)는 처음부터 확장 가능하게

### "직접 구현 vs 라이브러리?"
→ **루프 8단계의 핵심은 직접 구현** (Verum의 차별점이니까)
→ **주변 기능(인증·업로드·결제)은 라이브러리**

### "추상화 계층을 지금 만들까?"
→ **3번째 사용처가 생겼을 때 추상화**. 그 전엔 복붙 허용
→ 단, 루프 단계 간 인터페이스는 처음부터 명확히

### "이 PR을 머지해도 될까?"
체크리스트:
1. 테스트 통과?
2. 린트 통과?
3. 루프의 어느 단계에 속하는지 명시했나?
4. ArcanaInsight가 여전히 작동하나?
5. `docs/DECISIONS.md`에 기록할 결정이 있으면 기록했나?

모두 Yes면 머지. 하나라도 No면 xzawed에게 확인.

### "이건 오픈소스에 넣을까, 클라우드 전용으로 할까?"
→ **기능은 무조건 오픈소스**. "호스팅·운영·백업·모니터링"만 클라우드 차별점

### "Railway healthcheck가 실패한다?"

이 순서대로 점검한다. 역순으로 접근하면 6회 이상 배포를 낭비할 수 있다.

1. **네트워크 도달 가능성** — 배포 로그에서 `Local: http://...` 확인. `0.0.0.0`이 아닌 hex 문자열이면 `ENV HOSTNAME=0.0.0.0` 누락
2. **프로세스 시작 블로킹** — startup에서 `execFileSync` 등 동기 I/O가 event loop를 막고 있는지 확인. `promisify(execFile)` 또는 `await` 기반으로 교체
3. **인증 미들웨어 차단** — Auth.js middleware matcher가 `/health`를 포함하고 있으면 Railway probe가 307 → `/login`으로 리다이렉트
4. **endpoint 응답 속도** — `/health` 내부에 DB ping, 외부 API 호출 등이 있으면 cold start 시 Railway probe timeout(기본 5s) 초과

위 4개가 모두 정상이면 배포 성공. 하나라도 의심되면 `make docker-healthcheck`로 로컬 재현 후 수정.

### "Railway 대시보드가 잘못된 Dockerfile / start command를 보여준다?"

Railway는 서비스를 처음 연결할 때 설정을 캐시하며, `railway.toml` 변경이 대시보드에 자동 반영되지 않을 수 있다.

**증상**: Railway 대시보드 Configuration에 `apps/api/Dockerfile` 또는 `npm run start`가 표시됨  
**원인**: 초기 커밋(`ab20748`) 시점의 설정이 캐시된 것. `railway.toml`이 배포 시 override하도록 설계되어 있으나 대시보드 표시는 stale할 수 있음  
**해결**: Railway 대시보드에서 직접 수동으로 변경 필요:
- Dockerfile path → `Dockerfile` (root)
- Start command → `dumb-init node server.js`

> **중요**: `apps/api/Dockerfile`은 삭제됨. 아키텍처 피벗(2026-04-20) 후 FastAPI + uvicorn이 제거되어 더 이상 유효하지 않은 파일이었음. 프로덕션 이미지는 루트 `Dockerfile`(3-stage: Next.js + Python + combined runtime)만 사용.

---

## 🌐 외부 리소스

- **프로젝트 홈**: `github.com/xzawed/verum` (예정)
- **클라우드**: `verum.dev` (예정)
- **문서**: `docs.verum.dev` (예정)
- **데모**: `demo.verum.dev` (예정)

### 참고 프로젝트

- **Langfuse** — Observability 표준. 구조 참고.
- **RAGAS** — 평가. 직접 통합.
- **pgvector** — 벡터 저장소. 공식 문서 숙지.
- **OpenTelemetry** — Observability 표준. 호환 필수.
- **tree-sitter** — 다언어 AST 파싱. ANALYZE 단계 코어.
- **libcst** — Python 보존형 CST. 프롬프트 추출 정확도.

### 참고 논문

- Contextual Retrieval (Anthropic, 2024) — HARVEST/GENERATE에서 참고
- Self-RAG (Asai et al., 2024) — GENERATE의 적응형 검색
- HyDE (Gao et al., 2023) — 쿼리 생성 패턴
- DSPy (Stanford, 2024) — 프롬프트 자동 최적화 이론. EVOLVE 단계 참고.

---

## 🔄 이 문서의 관리

### 수정 주체 구분

| 섹션 | 수정 주체 |
|------|-----------|
| 프로젝트 정체성, 핵심 가치, 철학 | **xzawed만** |
| 로드맵, Phase 체크박스 갱신 | **xzawed만** |
| 기술 스택 (새 기술 도입·제거) | **xzawed 승인 후** Claude 반영 가능 |
| 프로젝트 구조도 | 코드와 불일치 발생 시 **Claude가 동기화** |
| 인프라 규칙·디버깅 체크리스트 | 회고 후 **Claude가 업데이트** |
| Do Not List 항목 추가 | **xzawed만** |

- **모든 세션 시작 시 이 문서를 먼저 읽기**.
- 루프의 단계가 추가/변경되면 이 문서가 먼저 업데이트되어야 함.
- Last updated 날짜는 xzawed가 직접 관리.

---

## 📜 프로젝트 철학

> *Verum watches what your AI actually does, understands what it's trying to do, and makes it better — without you writing a single prompt.*

자동화가 본질이다.
루프가 닫혀야 한다.
Repo가 출발점이다.
ArcanaInsight가 먼저다.
측정 없는 개선은 없다.

이게 Verum이다.

---

## 🧪 테스트 Role

Verum은 `.claude/agents/`에 테스트 전담 에이전트 시스템을 갖추고 있습니다.

### 에이전트 구조

| 에이전트 | 역할 |
|---------|------|
| `test-orchestrator` | 총괄. gap-analyzer → writer 병렬 → coverage-auditor 순서로 디스패치 |
| `test-gap-analyzer` | 미테스트 모듈 랭킹. 리스크 가중치 × LOC로 P0/P1/P2 분류 |
| `test-unit-writer` | 순수 함수·단일 모듈 단위 테스트 (AsyncMock, no DB) |
| `test-integration-writer` | DB/worker/route 통합 테스트 (`requires_db` 마커) |
| `test-e2e-writer` | Playwright E2E. `/test/login` bypass 활용 |
| `test-coverage-auditor` | 커버리지 집계 → CI artifact (`coverage/coverage-summary.json`) |

### 호출 방법

신규 모듈 추가 후 또는 커버리지 감사가 필요할 때:
```
@test-orchestrator 이번에 추가한 loop/experiment/repository.py와 worker/chain.py 테스트를 작성해줘
```

### PostToolUse Hook

`src/` 파일 편집 시 `.claude/hooks/post_test_edit.py`가 자동으로 대응 테스트 파일을 찾아 실행합니다.
테스트 파일이 없으면 `[test-orchestrator] No test found` 경고를 출력합니다. **비블로킹** — 작업은 계속됩니다.

### 참조 문서

- `.claude/skills/test-run.md` — 테스트 실행 표준 명령
- `.claude/skills/test-patterns.md` — Python/TypeScript/Playwright 패턴
- `.claude/skills/loop-stage-coverage.md` — Loop 8단계별 테스트 계약 체크리스트

---

_Last updated: 2026-04-25_
_Maintainer: xzawed_
