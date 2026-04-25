<div align="center">

# Verum

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/xzawed/verum/actions/workflows/ci.yml/badge.svg)](https://github.com/xzawed/verum/actions/workflows/ci.yml)
[![Codecov](https://img.shields.io/codecov/c/github/xzawed/verum?logo=codecov&logoColor=white)](https://codecov.io/gh/xzawed/verum)
[![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=xzawed_verum&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=xzawed_verum)
[![Phase](https://img.shields.io/badge/Phase-4B%20완료%20%E2%80%94%20EXPERIMENT%20%2B%20EVOLVE-brightgreen)](docs/ROADMAP.md)
[![Last Commit](https://img.shields.io/github/last-commit/xzawed/verum?logo=git&logoColor=white)](https://github.com/xzawed/verum/commits/main)
[![GitHub stars](https://img.shields.io/github/stars/xzawed/verum?style=social)](https://github.com/xzawed/verum/stargazers)

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](apps/api)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js&logoColor=white)](apps/dashboard)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?logo=typescript&logoColor=white)](apps/dashboard/tsconfig.json)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg?logo=ruff)](https://github.com/astral-sh/ruff)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20+%20pgvector-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Deployed on Railway](https://img.shields.io/badge/Deployed%20on-Railway-blueviolet?logo=railway&logoColor=white)](https://railway.app)

**Repo를 연결하세요. Verum이 AI의 실제 동작을 학습하고,  
프롬프트·RAG·평가셋·관측 시스템을 자동으로 만들고 진화시킵니다.**

[빠른 시작](#-빠른-시작) · [통합 사례](#-통합-사례-arcanainsight) · [FAQ](#-faq) · [로드맵](docs/ROADMAP.md) · [아키텍처](docs/ARCHITECTURE.md) · [루프 레퍼런스](docs/LOOP.md)

> **Verum AI Platform (verumai.com)과 무관한 별개의 프로젝트입니다.**

</div>

---

## 🔁 The Verum Loop

8단계 파이프라인이 정적 분석부터 자율 진화까지 자동으로 실행됩니다. 프롬프트를 직접 쓸 필요가 없습니다.

```
🔬 ANALYZE  →  🧠 INFER  →  🌾 HARVEST  →  ✨ GENERATE
     ↑                                              ↓
🔄 EVOLVE   ←  🧪 EXPERIMENT  ←  👁️ OBSERVE  ←  🚀 DEPLOY
```

GitHub Repo를 한 번 등록하면 루프가 자동으로 시작됩니다.

---

## ✅ 현재 구현 상태

| 단계 | 상태 | 설명 |
|---|---|---|
| 🔬 ANALYZE | ✅ 완료 | JS/TS tree-sitter 기반 LLM 호출 자동 탐지 (Python AST는 Phase 1.5에서 구현 예정) |
| 🧠 INFER | ✅ 완료 | Claude Sonnet 4.6으로 도메인·톤·사용자 유형 추론 |
| 🌾 HARVEST | ✅ 완료 | 도메인 맞춤 크롤링 → 청킹 → pgvector 임베딩 저장 |
| 🔍 RETRIEVE | ✅ 완료 | 벡터 + 전문 검색 하이브리드로 수집 지식 검색 |
| ✨ GENERATE | ✅ 완료 | 프롬프트 변형·RAG 설정·평가셋 자동 생성 (HARVEST 완료 후 자동 실행) |
| 🚀 DEPLOY | ✅ 완료 | SDK 기반 카나리 배포 + 트래픽 분할 + 롤백 |
| 👁️ OBSERVE | ✅ 완료 | 트레이스 + 스팬 수집, 비용/지연 메트릭, LLM-as-Judge 점수 |
| 🧪 EXPERIMENT | ✅ 완료 | 순차 쌍별 베이지안 A/B 테스트 (5개 프롬프트 변형, 4라운드) |
| 🔄 EVOLVE | ✅ 완료 | 승자 자동 승격, 패배자 아카이브 — 수동 개입 없음 |

---

## ⚡ 빠른 시작

### 1단계 — 셀프 호스팅 실행

```bash
git clone https://github.com/xzawed/verum
cd verum
docker compose up
# 대시보드: http://localhost:3000
# 헬스체크: http://localhost:3000/health
```

### 2단계 — GitHub OAuth로 로그인

`http://localhost:3000/login` 접속 → "Sign in with GitHub" 클릭.  
환경변수에 `AUTH_GITHUB_ID`, `AUTH_GITHUB_SECRET`이 설정되어 있어야 합니다 (`.env.example` 참조).

### 3단계 — Repo 등록 → 자동 분석

`/repos` 페이지에서 본인 GitHub Repo 중 하나를 "Register" 클릭.  
이 시점부터 **`ANALYZE → INFER → HARVEST → GENERATE`까지 자동으로 진행**됩니다.

대시보드에서 각 단계 진행 상황을 실시간으로 확인할 수 있습니다.

### 4단계 — GENERATE 결과 검토 후 승인

`/repos/<id>` 페이지에서 Verum이 생성한 5개 프롬프트 변형, RAG 설정, 평가셋을 확인하고 "Approve"를 누릅니다.  
**승인 전에는 DEPLOY가 차단됩니다** (사용자 의도 없는 자동 배포 방지).

### 5단계 — DEPLOY 후 SDK 통합

승인 시 `deployments` 행과 함께 API 키가 발급됩니다. 본인 서비스 코드에 SDK를 한 줄 추가하면 끝입니다:

```bash
pip install verum            # Python SDK
npm install @verum/sdk       # TypeScript SDK
```

```python
import verum
client = verum.Client(api_url="https://verum.dev", api_key="vrm_...")

result = await client.chat(
    messages=[...],
    deployment_id="...",
    provider="openai",
    model="gpt-4o-mini",
)
# result["messages"]를 본인 LLM SDK에 전달하면 됨
```

### 6단계 — 자동 진화 시작

이후로는 자동입니다:
- 트래픽이 5개 변형에 자동 분할 (EXPERIMENT)
- 베이지안 신뢰도가 임계치 도달 시 승자 자동 승격 (EVOLVE)
- 사용자 피드백·비용·지연·Judge 점수로 종합 판단

---

## 🔌 통합 사례 — ArcanaInsight

타로 카드 리딩 서비스에 Verum을 통합한 실제 예시입니다 ([examples/arcana-integration/](examples/arcana-integration/)).

### Before — 정적 프롬프트 + OpenAI 직접 호출

```python
# examples/arcana-integration/before.py
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM_PROMPT = """당신은 신비로운 타로 카드 리더입니다.
켈트 십자 스프레드를 사용하여..."""  # 하드코딩

def read_tarot(question, cards):
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{question} / {cards}"},
        ],
    ).choices[0].message.content
```

문제점:
- 프롬프트 개선이 사람 의존
- 관측 없음 (지연·비용·만족도 추적 불가)
- A/B 테스트 인프라 별도 구축 필요

### After — Verum 한 줄 교체

```python
# examples/arcana-integration/after.py
import verum

client = verum.Client(
    api_url=os.environ["VERUM_API_URL"],
    api_key=os.environ["VERUM_API_KEY"],
)
DEPLOYMENT_ID = os.environ["VERUM_DEPLOYMENT_ID"]

async def read_tarot(question, cards):
    result = await client.chat(
        messages=[
            {"role": "system", "content": _FALLBACK_SYSTEM},  # Verum 도달 불가 시만 사용
            {"role": "user", "content": f"{question} / {cards}"},
        ],
        deployment_id=DEPLOYMENT_ID,
        provider="openai",
        model="gpt-4o-mini",
    )
    # result["routed_to"]: "baseline" 또는 "variant/<name>"
    return result["messages"][-1]["content"]
```

자동으로 얻는 것:
- ✅ Verum 대시보드가 시스템 프롬프트의 5개 변형을 관리
- ✅ 모든 호출에 자동 트레이스 (지연·비용·모델·피드백)
- ✅ 변형 간 A/B 테스트 자동 실행
- ✅ 베이지안 수렴 시 승자 프롬프트 자동 승격

전체 코드: [examples/arcana-integration/after.py](examples/arcana-integration/after.py)

---

## ❓ FAQ

### Q1. Verum이 제 Repo 코드를 수정하거나 PR을 만드나요?

**아니요.** Verum은 사용자 코드를 절대 변경하지 않습니다.

- ANALYZE 단계는 `git clone --depth 1`로 임시 디렉토리에 받아 *읽기 전용* 정적 분석을 수행하고, 종료 시 즉시 삭제합니다 ([cloner.py](apps/api/src/loop/analyze/cloner.py)).
- 코드베이스 어디에도 `git push`, PR 생성, write-scope GitHub 토큰 사용은 **없습니다**.
- 사용자가 본인 서비스 코드에 SDK를 *직접 추가*해야 합니다 (한 줄 import + Client 인스턴스화).

### Q2. "DEPLOY"가 제 서비스를 자동으로 프로덕션에 배포한다는 의미인가요?

**아니요.** Verum의 "DEPLOY"는 다음을 의미합니다:
1. `deployments` 테이블에 행을 INSERT
2. API 키 발급 (`vrm_...`)
3. 트래픽 분할 설정 활성화

이 deployment 행을 사용자 SDK가 런타임에 polling합니다. 사용자 서비스는 본인이 평소 배포하는 방식 그대로 (Vercel, AWS, 자체 서버 등) 운영하면 됩니다.

### Q3. 단계별로 자동/수동 진행이 어떻게 나뉘나요?

| 전이 | 자동 여부 | 설명 |
|------|---------|------|
| Repo 등록 → ANALYZE | ✅ 자동 | Repo 등록 즉시 시작 |
| ANALYZE → INFER | ✅ 자동 | 분석 완료 후 워커가 다음 잡 enqueue |
| INFER → HARVEST | ✅ 자동 | 도메인 추론 후 크롤링 자동 시작 (sources auto-approve) |
| HARVEST → GENERATE | ✅ 자동 | 임베딩 완료 후 프롬프트 생성 자동 시작 |
| GENERATE → DEPLOY | ❌ **사용자 승인 필요** | 대시보드에서 "Approve" 클릭해야 진행 |
| OBSERVE → EXPERIMENT → EVOLVE | ✅ 자동 | 트래픽 누적·통계적 유의성 도달 시 자동 실행 |

### Q4. 비용이 얼마나 드나요?

Verum 자체는 **MIT 오픈소스로 무료**입니다. 비용은 사용자가 직접 호출하는 외부 API에서 발생합니다:
- **INFER + GENERATE 단계**: Claude API (Anthropic) — Sonnet 4.6 호출 비용
- **HARVEST 단계**: Voyage AI 임베딩 API — `voyage-3.5` (1024차원)
- **사용자 LLM 호출**: 본인이 사용하는 OpenAI / Anthropic / Grok 비용 (Verum이 추가로 청구하지 않음)
- **인프라**: 셀프 호스팅이면 본인 서버, Verum 클라우드(예정)는 별도 구독

### Q5. pgvector 외 다른 벡터 DB 사용 가능한가요?

**불가능합니다.** ADR-001에 의거 pgvector만 지원합니다 ([DECISIONS.md](docs/DECISIONS.md)).  
이유: PostgreSQL 단일 데이터스토어 원칙, `docker compose up` 한 줄 셀프 호스팅 제약.

### Q6. LangChain / LlamaIndex 통합은 지원하나요?

**아니요.** ADR-002에 의거 두 라이브러리 의존 금지입니다.  
Verum은 이들의 *대안*이자 *상위 레이어*이므로 의존하면 정체성이 소실됩니다. 저수준 라이브러리(`openai`, `anthropic`, `httpx`)만 직접 사용합니다.

### Q7. Python AST 분석은 언제 지원되나요?

Phase 1.5에서 구현 예정입니다 (F-1.3). 현재는 JS/TS tree-sitter 기반만 동작합니다.

### Q8. ArcanaInsight 외 다른 도메인에서도 작동하나요?

INFER 단계가 도메인을 자동 분류하고, HARVEST가 도메인별 크롤링 전략을 적용합니다. 초기 20개 도메인 카테고리 지원 (타로, 코드 리뷰, 법률 QA, 의료 상담 등). 새 도메인은 INFER가 가장 가까운 카테고리로 분류한 뒤 HARVEST 소스를 사용자가 검토·수정할 수 있습니다.

---

## 🆚 다른 도구와의 차이

| 도구 | 하는 것 | Verum이 추가로 하는 것 |
|---|---|---|
| Langfuse / LangSmith | LLM 호출 관측 | 관측 결과로 프롬프트·RAG 자동 생성·진화 |
| RAGAS | RAG 평가 | 평가셋 자동 구축 + CI 자동 실행 |
| PromptLayer | 프롬프트 버전 관리 | AI가 프롬프트를 작성하고 A/B로 승자 선택 |
| CodeRabbit / SCAManager | 코드 리뷰 | 코드 분석 결과를 AI 서비스 최적화에 사용 |

**한 줄 정리**: 다른 도구는 "사람이 LLM을 운영하는 것을 돕는" 도구이고, Verum은 "LLM이 스스로 개선되도록 돕는" 도구입니다.

---

## 🏗️ 기술 스택

**백엔드** — Python 3.13, asyncio, SQLAlchemy 2, Alembic, PostgreSQL 16 + pgvector  
**프론트엔드** — Next.js 16, React 19, TypeScript strict, Auth.js v5, Drizzle ORM  
**AI** — Claude Sonnet 4.6 (INFER + GENERATE), Voyage AI `voyage-3.5` (임베딩, 1024차원)  
**인프라** — Railway, Docker (단일 이미지: Node PID1 + Python worker 자식 프로세스)

---

## 📄 라이선스

MIT — [LICENSE](LICENSE) 참조.

모든 기능은 오픈소스입니다. 셀프 호스팅과 Verum 클라우드의 차이는 "누가 인프라를 운영하는가"뿐입니다. 기능에 유료/무료 경계를 두지 않습니다.
