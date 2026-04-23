# Verum Loop 단계별 테스트 체크리스트

각 Loop 단계에서 "반드시 테스트해야 할 계약(contract)"을 정의합니다.
새 기능 추가 후 해당 단계의 체크리스트를 검토해 테스트 누락 여부를 확인하세요.

---

## [1] ANALYZE — Repo 정적 분석

**핵심 모듈**: `apps/api/src/loop/analyze/`

### 필수 테스트 계약

- [ ] **LLM 호출 지점 탐지 precision = 100%**: 실제로 `openai.chat.completions.create()`인 라인만 탐지 (false positive 0)
- [ ] **LLM 호출 지점 탐지 recall > 95%**: Python ast 파싱이 모든 주요 SDK 패턴 커버 (`client.chat(...)`, `anthropic.messages.create(...)`)
- [ ] **프롬프트 문자열 추출**: f-string, template literal, concatenation 모두 추출
- [ ] **파라미터 추출**: `temperature`, `max_tokens`, `model` 값 추출
- [ ] **TypeScript/JS 지원**: tree-sitter 파싱이 `.ts`, `.js`, `.tsx` 파일에서 동작
- [ ] **서비스 실행 불필요**: 분석이 파일 읽기만으로 완료 (subprocess 없이)

```python
# 테스트 예시
async def test_analyze_detects_openai_call():
    code = '''
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "hello"}],
)
'''
    result = await analyzer.analyze_python(code)
    assert len(result.call_sites) == 1
    assert result.call_sites[0].model == "gpt-4o-mini"
```

---

## [2] INFER — 서비스 의도 추론

**핵심 모듈**: `apps/api/src/loop/infer/`

### 필수 테스트 계약

- [ ] **응답 JSON 스키마 준수**: `{"domain": str, "tone": str, "language": str, "user_type": str}` 4개 필드 항상 존재
- [ ] **malformed JSON → 에러 raise**: LLM이 JSON 아닌 텍스트 반환 시 `ValueError` 또는 `InferError`
- [ ] **domain 분류 일관성**: 동일 입력에 같은 domain 값 (deterministic, temperature=0)
- [ ] **빈 프롬프트 처리**: 추출된 프롬프트가 없어도 README로만 추론 시도
- [ ] **repository 저장 idempotency**: 같은 repo_id로 두 번 INFER 실행해도 레코드 중복 없음

---

## [3] HARVEST — 도메인 지식 수집

**핵심 모듈**: `apps/api/src/loop/harvest/`

### 필수 테스트 계약

- [ ] **청킹 token budget 준수**: 각 청크가 `max_tokens`(기본 512) 이하
- [ ] **dedup**: 같은 URL에서 두 번 크롤링 시 중복 청크 없음
- [ ] **pgvector insert 성공**: 청킹 결과가 `embedding_chunks` 테이블에 정상 저장
- [ ] **robots.txt 준수**: disallowed URL은 크롤링 건너뜀 (또는 정책 명시)
- [ ] **HTTP 오류 graceful handling**: 404, 500 응답 시 해당 소스 건너뜀, 전체 HARVEST 실패 안 함
- [ ] **playwright 없이 기본 크롤링**: httpx만으로 정적 페이지 크롤링

---

## [4] GENERATE — 자산 자동 생성

**핵심 모듈**: `apps/api/src/loop/generate/`

### 필수 테스트 계약

- [ ] **프롬프트 variant 최소 3개**: Chain-of-Thought, Few-shot, 기본 포함
- [ ] **evalset 범위**: 20~50개 사이 (하드코딩 금지, 설정 가능)
- [ ] **evalset JSON 스키마**: 각 항목이 `{"question": str, "expected": str}` 구조
- [ ] **생성 idempotency**: 같은 repo_id 같은 inference_id로 두 번 실행해도 중복 생성 안 함
- [ ] **LLM 실패 시 롤백**: 생성 도중 오류 발생 시 부분 생성물 DB에 저장 안 함

---

## [5] DEPLOY — 서비스 주입

**핵심 모듈**: `apps/api/src/loop/deploy/`

### 필수 테스트 계약

- [ ] **orchestrator idempotency**: 같은 `deployment_id`로 두 번 호출해도 중복 레코드 없음
- [ ] **rollout % 반영**: `rollout_pct=10`으로 생성된 deployment가 `variant` 트래픽 10% 라우팅
- [ ] **baseline 항상 존재**: deployment에 baseline prompt가 반드시 포함
- [ ] **이미 active deployment 있을 때 처리**: 중복 배포 시 에러 또는 기존 유지 (정책 명시)
- [ ] **SDK 라우팅 계약**: `verum.chat(deployment_id=...)` 호출 시 올바른 prompt variant 선택

---

## [6] OBSERVE — 운영 추적

**핵심 모듈**: `apps/api/src/loop/observe/` 또는 Dashboard API

### 필수 테스트 계약

- [ ] **trace span 스키마 (OTel 호환)**: `trace_id`, `span_id`, `duration_ms`, `model`, `cost_usd` 필드 존재
- [ ] **비용 집계 정확성**: `prompt_tokens × token_price + completion_tokens × token_price = cost_usd` (소수점 오차 허용)
- [ ] **사용자 피드백 저장**: `score: 1 | -1`이 trace에 연결 저장
- [ ] **중복 trace 방지**: 같은 `trace_id`로 두 번 insert 시 upsert 처리

---

## [7] EXPERIMENT — A/B 테스트

**핵심 모듈**: `apps/api/src/loop/experiment/`

### 필수 테스트 계약

- [ ] **트래픽 분할 합 = 100%**: baseline% + variant% = 100 항상
- [ ] **Bayesian 수렴 기준**: confidence ≥ 0.95 달성 시 자동 종료 트리거 (엔진 로직 테스트)
- [ ] **최소 샘플 수 강제**: 각 variant 100회 미만에서 자동 종료 안 함
- [ ] **결과 저장 원자성**: 실험 결과 저장 실패 시 실험 상태 변경 없음

---

## [8] EVOLVE — 승자 채택

**핵심 모듈**: `apps/api/src/loop/evolve/`

### 필수 테스트 계약

- [ ] **승자 선택 deterministic**: 동일 입력(trace scores)에 항상 같은 승자 선택
- [ ] **승자 승격**: 승자 variant가 새 baseline으로 저장
- [ ] **패배자 아카이브**: 패배 variant 상태가 `archived`로 변경, 삭제 안 함
- [ ] **무승부 처리**: 두 variant 차이가 통계적 유의성 미달 시 기존 baseline 유지
- [ ] **다음 사이클 준비**: EVOLVE 완료 후 새 GENERATE job이 큐에 자동 추가

---

## 대시보드 공개 API

**핵심 위치**: `apps/dashboard/src/app/api/`

### 필수 테스트 계약

- [ ] **인증 없는 요청 → 401**: 모든 보호 route에서 session 없으면 401
- [ ] **타 사용자 리소스 접근 → 403 또는 404**: repo 소유권 검증
- [ ] **SDK API key 검증**: `Authorization: Bearer vk_...` 없으면 `/api/v1/` 엔드포인트 거부
- [ ] **pgvector retrieve 정확도**: `/api/v1/retrieve-sdk`가 embedding similarity top-k 반환
