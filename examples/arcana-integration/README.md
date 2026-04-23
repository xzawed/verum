# ArcanaInsight × Verum 통합 가이드

ArcanaInsight(타로 상담 서비스)에 Verum SDK를 적용하는 단계별 가이드입니다.
이 예제는 Verum Loop의 **[5] DEPLOY** 단계를 실제 서비스에 적용하는 방법을 보여줍니다.

## 개요

Verum SDK 통합의 핵심은 **한 줄 변경**입니다.

```python
# Before
from openai import OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# After
import verum
client = verum.Client(api_url=..., api_key=...)
```

이후 모든 LLM 호출이 Verum을 통해 라우팅되며, A/B 테스트·트레이싱·자동 진화가 자동으로 활성화됩니다.

## 사전 준비

Verum 대시보드에서 아래 단계가 완료되어야 합니다.

1. **ANALYZE** — ArcanaInsight Repo를 연결하고 분석 완료 확인
   - Grok `chat.completions.create()` 호출 지점이 모두 탐지되어야 함
2. **INFER** — 도메인 추론 결과가 `divination/tarot`으로 분류되어야 함
3. **HARVEST** — 타로 지식 청크 1,000개 이상 수집 완료
4. **GENERATE** — 프롬프트 변형(CoT, Few-shot 등) 및 평가셋 생성 완료
5. **DEPLOY** — 배포 생성 후 `DEPLOYMENT_ID` 확인

대시보드에서 위 단계를 순서대로 진행하면 `VERUM_DEPLOYMENT_ID`가 발급됩니다.

## 설치

```bash
pip install verum
```

## 환경 변수 설정

`.env.example`을 복사해서 `.env`를 만들고 값을 채웁니다.

```bash
cp .env.example .env
```

```dotenv
VERUM_API_URL=https://verum-production.up.railway.app
VERUM_API_KEY=vk_your_api_key_here
VERUM_DEPLOYMENT_ID=dep_your_deployment_id_here

OPENAI_API_KEY=sk-your_openai_key_here
```

## 코드 변경: Before → After

### Before (`before.py`)

기존 ArcanaInsight 구현 — OpenAI 클라이언트를 직접 호출하고, 시스템 프롬프트를 코드에 하드코딩합니다.

```python
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM_PROMPT = """당신은 신비로운 타로 카드 리더입니다. ..."""

def read_tarot(question: str, cards: list[str]) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"질문: {question}\n뽑힌 카드: {', '.join(cards)}"},
        ],
        temperature=0.8,
    )
    return response.choices[0].message.content or ""
```

문제점:
- 프롬프트 개선 시 코드를 직접 수정하고 재배포해야 함
- 어떤 프롬프트가 더 좋은지 비교할 방법이 없음
- 비용, 지연시간, 품질 메트릭을 별도로 구현해야 함

### After (`after.py`)

`verum.Client`로 교체합니다. 나머지 코드는 그대로입니다.

```python
import verum

client = verum.Client(
    api_url=os.environ["VERUM_API_URL"],
    api_key=os.environ["VERUM_API_KEY"],
)

DEPLOYMENT_ID = os.environ["VERUM_DEPLOYMENT_ID"]

# verum.Client.chat() is async — use async def or asyncio.run()
async def read_tarot(question: str, cards: list[str]) -> str:
    result = await client.chat(
        messages=[
            {"role": "system", "content": _FALLBACK_SYSTEM},
            {"role": "user", "content": f"질문: {question}\n뽑힌 카드: {', '.join(cards)}"},
        ],
        deployment_id=DEPLOYMENT_ID,
        provider="openai",
        model="gpt-4o-mini",
        temperature=0.8,
    )
    return result["messages"][-1]["content"]
```

> **sync 환경(Flask, Django)에서 사용 시**: `asyncio.run(read_tarot(...))` 으로 래핑하거나, `asgiref`의 `async_to_sync`를 사용하세요.

달라지는 것:
- Verum이 생성한 프롬프트 변형(CoT, Few-shot 등)이 자동으로 적용됨
- 트래픽의 10%는 새 변형으로 라우팅 — `result["routed_to"]`로 확인 가능
- 모든 호출이 Verum 대시보드에 트레이싱됨 (비용, 지연시간, 모델)
- 프롬프트 개선은 대시보드에서 승인만 하면 됨. 코드 재배포 불필요

## 동작 확인

통합 후 Verum 대시보드 → **Deployments** 탭에서 다음을 확인합니다.

| 항목 | 기대 값 |
|------|---------|
| 트래픽 분배 | baseline 90% / variant 10% |
| 트레이스 수집 | 호출마다 span이 기록됨 |
| 응답 지연 증가 | P95 기준 10ms 미만 |

## 피드백 수집 (선택)

사용자 피드백을 Verum에 전달하면 EVOLVE 단계에서 활용됩니다.

```python
# 사용자가 좋아요/싫어요를 누를 때
await client.feedback(
    trace_id=result["trace_id"],
    score=1,   # 1 = 긍정, -1 = 부정
)
```

## 다음 단계: 자동 진화 (EVOLVE)

충분한 트래픽이 쌓이면 Verum이 자동으로 A/B 결과를 분석합니다.

1. 두 변형 각각 100회 이상 호출 누적
2. Bayesian 검정으로 신뢰도 ≥ 0.95 달성 시 승자 자동 선택
3. 승자 변형이 기본 프롬프트로 승격 — 코드 변경 없음
4. 다음 사이클을 위해 새 변형 생성 → 루프 반복

이 과정이 [8] EVOLVE 단계이며, 한 번 통합하면 프롬프트가 자동으로 개선됩니다.

## 관련 파일

| 파일 | 설명 |
|------|------|
| `before.py` | Verum 적용 전 원본 구현 |
| `after.py` | Verum SDK 적용 후 구현 |
| `.env.example` | 환경 변수 템플릿 |

## 관련 로드맵 항목

- F-3.8: Python SDK `verum.chat()` + `verum.retrieve()` + `verum.feedback()`
- F-3.9: TypeScript SDK (동일 API)
- F-3.10: 이 예제 (ArcanaInsight 통합)
- F-4.11: 첫 자동 진화 사이클 완료
