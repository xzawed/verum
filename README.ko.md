<div align="center">

# Verum

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Phase](https://img.shields.io/badge/Phase-3%20진행중%20%E2%80%94%20GENERATE-orange)](docs/ROADMAP.md)
[![Deployed on Railway](https://img.shields.io/badge/Deployed%20on-Railway-blueviolet?logo=railway&logoColor=white)](https://railway.app)
[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](apps/api)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js&logoColor=white)](apps/dashboard)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20+%20pgvector-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)

**Repo를 연결하세요. Verum이 AI의 실제 동작을 학습하고,  
프롬프트·RAG·평가셋·관측 시스템을 자동으로 만들고 진화시킵니다.**

[로드맵](docs/ROADMAP.md) · [아키텍처](docs/ARCHITECTURE.md) · [루프 레퍼런스](docs/LOOP.md)

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
| 🔬 ANALYZE | ✅ 완료 | Python·JS/TS AST 기반 LLM 호출 자동 탐지 |
| 🧠 INFER | ✅ 완료 | Claude Sonnet 4.6으로 도메인·톤·사용자 유형 추론 |
| 🌾 HARVEST | ✅ 완료 | 도메인 맞춤 크롤링 → 청킹 → pgvector 임베딩 저장 |
| 🔍 RETRIEVE | ✅ 완료 | 벡터 + 전문 검색 하이브리드로 수집 지식 검색 |
| ✨ GENERATE | 🚧 진행중 | 프롬프트 변형·RAG 설정·평가셋 자동 생성 (HARVEST 완료 후 자동 실행) |
| 🚀 DEPLOY | 🔲 예정 | SDK 기반 카나리 배포 + 트래픽 분할 |
| 👁️ OBSERVE | 🔲 예정 | OpenTelemetry 트레이스 수집 + 비용/지연 메트릭 |
| 🧪 EXPERIMENT | 🔲 예정 | 베이지안 A/B 테스트로 프롬프트 변형 비교 |
| 🔄 EVOLVE | 🔲 예정 | 승자 자동 승격, 패배자 아카이브 |

---

## ⚡ 셀프 호스팅 미리보기

```bash
git clone https://github.com/xzawed/verum
cd verum
docker compose up
# 대시보드: http://localhost:3000
# 헬스체크: http://localhost:3000/health
```

---

## 🆚 다른 도구와의 차이

| 도구 | 하는 것 | Verum이 추가로 하는 것 |
|---|---|---|
| Langfuse / LangSmith | LLM 호출 관측 | 관측 결과로 프롬프트·RAG 자동 생성·진화 |
| RAGAS | RAG 평가 | 평가셋 자동 구축 + CI 자동 실행 |
| PromptLayer | 프롬프트 버전 관리 | AI가 프롬프트를 작성하고 A/B로 승자 선택 |

---

## 🏗️ 기술 스택

**백엔드** — Python 3.13, asyncio, SQLAlchemy 2, Alembic, PostgreSQL 16 + pgvector  
**프론트엔드** — Next.js 16, React 19, TypeScript strict, Auth.js v5, Drizzle ORM  
**AI** — Claude Sonnet 4.6 (INFER + GENERATE), Voyage AI `voyage-3.5` (임베딩, 1024차원)  
**인프라** — Railway, Docker (단일 이미지: Node PID1 + Python worker 자식 프로세스)

---

## 📄 라이선스

MIT — [LICENSE](LICENSE) 참조.

모든 기능은 오픈소스입니다. 셀프 호스팅과 Verum 클라우드의 차이는 "누가 인프라를 운영하는가"뿐입니다.
