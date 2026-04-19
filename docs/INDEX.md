---
type: index
authority: tier-3
canonical-for: [navigation]
last-updated: 2026-04-19
status: active
---

# Verum Documentation Index

> **Claude instructions:** Read this file immediately after CLAUDE.md in every session.
> It tells you which document owns each topic. Never duplicate content from another owner — link instead.
> If two documents conflict on the same topic, the owner in the Anti-duplication table below wins.
> Authority: CLAUDE.md > canonical owner > this file.

---

## Read in This Order

1. **[CLAUDE.md](../CLAUDE.md)** — vision, The Verum Loop, do-not-list, tech stack, KPIs. Tier 1 authority.
2. **[docs/INDEX.md](INDEX.md)** — this file. Navigation only.
3. **[docs/LOOP.md](LOOP.md)** — stage algorithms, I/O contracts, completion criteria.
4. **[docs/ARCHITECTURE.md](ARCHITECTURE.md)** — file tree, schemas, API/SDK surface, ADRs.
5. **[docs/ROADMAP.md](ROADMAP.md)** — phase timing, deliverables with F-IDs, completion gates.
6. **[docs/DECISIONS.md](DECISIONS.md)** — ADR index, product-scope decisions, superseded decisions.
7. **[docs/GLOSSARY.md](GLOSSARY.md)** — vocabulary disambiguation.

---

## Find by Question

| Question | Go to |
|---|---|
| What is Verum trying to accomplish? | [CLAUDE.md §🎯 프로젝트 정체성](../CLAUDE.md) |
| What is The Verum Loop? | [CLAUDE.md §🔁 The Verum Loop](../CLAUDE.md) |
| What does stage [N] do exactly? | [LOOP.md §Stage [N]](LOOP.md) |
| Which phase ships stage [N]? | [ROADMAP.md](ROADMAP.md) |
| What are the acceptance criteria for a deliverable? | [ROADMAP.md §F-{phase}.{n}](ROADMAP.md) |
| Which file does this code belong in? | [ARCHITECTURE.md §2. Repository Layout](ARCHITECTURE.md) |
| What is the database schema? | [ARCHITECTURE.md §4. Data Models](ARCHITECTURE.md) |
| What is the API contract? | [ARCHITECTURE.md §5. API Surface](ARCHITECTURE.md) |
| What is the SDK surface? | [ARCHITECTURE.md §6. SDK Surface](ARCHITECTURE.md) |
| Why was this technical decision made? | [DECISIONS.md](DECISIONS.md) → [ARCHITECTURE.md §7. ADRs](ARCHITECTURE.md) |
| Can I add this dependency? | [DECISIONS.md](DECISIONS.md) — check ADR-001 through ADR-008 first |
| What are the hard constraints? | [CLAUDE.md §⚠️ 하지 말아야 할 것](../CLAUDE.md) |
| What is this week's status? | [WEEKLY.md](WEEKLY.md) (Phase 1+, maintained by xzawed) |
| What does this term mean? | [GLOSSARY.md](GLOSSARY.md) |

---

## The 8 Stages

| # | Stage | Owner doc | Ships in |
|---|---|---|---|
| [1] | ANALYZE | [LOOP.md §Stage 1](LOOP.md#3-stage-1-analyze) | [Phase 1](ROADMAP.md#phase-1-analyze-week-3-5) |
| [2] | INFER | [LOOP.md §Stage 2](LOOP.md#4-stage-2-infer) | [Phase 2](ROADMAP.md#phase-2-infer--harvest-week-6-9) |
| [3] | HARVEST | [LOOP.md §Stage 3](LOOP.md#5-stage-3-harvest) | [Phase 2](ROADMAP.md#phase-2-infer--harvest-week-6-9) |
| [4] | GENERATE | [LOOP.md §Stage 4](LOOP.md#6-stage-4-generate) | [Phase 3](ROADMAP.md#phase-3-generate--deploy-week-10-13) |
| [5] | DEPLOY | [LOOP.md §Stage 5](LOOP.md#7-stage-5-deploy) | [Phase 3](ROADMAP.md#phase-3-generate--deploy-week-10-13) |
| [6] | OBSERVE | [LOOP.md §Stage 6](LOOP.md#8-stage-6-observe) | [Phase 4](ROADMAP.md#phase-4-observe--experiment--evolve-week-14-18) |
| [7] | EXPERIMENT | [LOOP.md §Stage 7](LOOP.md#9-stage-7-experiment) | [Phase 4](ROADMAP.md#phase-4-observe--experiment--evolve-week-14-18) |
| [8] | EVOLVE | [LOOP.md §Stage 8](LOOP.md#10-stage-8-evolve) | [Phase 4](ROADMAP.md#phase-4-observe--experiment--evolve-week-14-18) |

---

## Current Phase Status

| Phase | Status | Completion Gate |
|---|---|---|
| Phase 0: Foundation | 🔲 Not started | `curl https://verum-api.up.railway.app/health` → 200 OK |
| Phase 1: ANALYZE | 🔲 Not started | ArcanaInsight's LLM call sites auto-detected |
| Phase 2: INFER + HARVEST | 🔲 Not started | Domain inferred; 1,000+ knowledge chunks indexed |
| Phase 3: GENERATE + DEPLOY | 🔲 Not started | ArcanaInsight running on Verum-generated prompts + RAG |
| Phase 4: OBSERVE + EXPERIMENT + EVOLVE | 🔲 Not started | ArcanaInsight prompt auto-improved ≥1 time with metric gain |
| Phase 5: Launch | 🔲 Not started | GitHub stars ≥ 100; ≥ 10 non-xzawed Repo connections |

> xzawed updates this table as phases complete. Claude reads it to know what exists vs. what is planned.

---

## Authority Order

When documents conflict on the same topic, apply this order:

1. **CLAUDE.md** — absolute authority. Vision, loop definition, do-not-list, tech stack.
2. **docs/LOOP.md** — stage algorithms, I/O, invariants.
3. **docs/ARCHITECTURE.md** — file paths, schemas, API contracts, ADRs.
4. **docs/ROADMAP.md** — phase timing, completion gates.
5. **docs/DECISIONS.md** — ADR index, product-scope decisions.
6. **docs/INDEX.md / docs/GLOSSARY.md** — navigation and vocabulary only. Never override higher tiers.

---

## Anti-Duplication Table

Each topic has exactly one canonical owner. All other files must link, never restate.

| Topic | Canonical Owner |
|---|---|
| Vision, loop definition, do-not-list, tech stack, KPIs | CLAUDE.md |
| Stage [1]–[8] algorithms, inputs, outputs, failure modes | LOOP.md |
| Repository file tree | ARCHITECTURE.md §2 |
| Database schemas | ARCHITECTURE.md §4 |
| API contracts | ARCHITECTURE.md §5 |
| SDK surface | ARCHITECTURE.md §6 |
| Full ADR text | ARCHITECTURE.md §7 |
| ADR index + product-scope decisions | DECISIONS.md |
| Phase timing + completion gates + F-IDs | ROADMAP.md |
| Vocabulary definitions | GLOSSARY.md |

---

_Maintainer: xzawed | Last updated: 2026-04-19_
