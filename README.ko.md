# Verum

> *Repo를 연결하세요. Verum이 AI의 실제 동작을 학습하고, 프롬프트·RAG·평가셋·관측 시스템을 자동으로 만들고 진화시킵니다.*

> **Verum AI Platform (verumai.com)과 무관한 별개의 프로젝트입니다.**

---

## Verum이 하는 일

Verum은 AI 서비스를 자동으로 분석하고 최적화하는 오픈소스 플랫폼입니다.

GitHub Repo 연결 → Verum이 LLM 호출을 정적 분석 → 서비스 도메인 이해 → 프롬프트·RAG 파이프라인·평가셋 자동 생성 → A/B 테스트로 배포 → 수동 개입 없이 승자 버전으로 진화.

```
[1] ANALYZE  →  [2] INFER  →  [3] HARVEST  →  [4] GENERATE
      ↑                                               ↓
[8] EVOLVE   ←  [7] EXPERIMENT  ←  [6] OBSERVE  ←  [5] DEPLOY
```

이 루프가 계속 돌아갑니다. 프롬프트 한 줄 안 써도 AI 서비스가 좋아집니다.

---

## 다른 도구와의 차이

| 도구 | 하는 것 | Verum이 추가로 하는 것 |
|---|---|---|
| Langfuse / LangSmith | LLM 호출 관측 | 관측 결과로 프롬프트·RAG 자동 생성·진화 |
| RAGAS | RAG 평가 | 평가셋 자동 구축 + CI 자동 실행 |
| PromptLayer | 프롬프트 버전 관리 | AI가 프롬프트를 작성하고 A/B로 승자 선택 |

---

## 빠른 시작

> 사용자 가이드는 [Phase 5](docs/ROADMAP.md#phase-5-launch-week-19-24)에 공개됩니다.

셀프 호스팅 미리보기 (Phase 0):

```bash
git clone https://github.com/xzawed/verum
cd verum
docker compose up
curl http://localhost:8000/health
```

---

## 저장소 구조

전체 파일 트리는 [docs/ARCHITECTURE.md §2](docs/ARCHITECTURE.md#2-repository-layout) 참조.

| 경로 | 목적 |
|---|---|
| `apps/api/src/loop/` | 8단계 루프 구현 (ADR-008에 의해 구조 변경 불가) |
| `apps/dashboard/` | Next.js 16 대시보드 |
| `packages/sdk-python/` | `pip install verum` |
| `packages/sdk-typescript/` | `npm install @verum/sdk` |
| `examples/arcana-integration/` | 첫 dogfood: ArcanaInsight 통합 예제 |
| `docs/` | 아키텍처·로드맵·루프 레퍼런스·ADR |

---

## 라이선스

MIT — [LICENSE](LICENSE) 참조.

모든 기능은 오픈소스입니다. 셀프 호스팅과 Verum 클라우드의 차이는 "누가 인프라를 운영하는가"뿐입니다.
