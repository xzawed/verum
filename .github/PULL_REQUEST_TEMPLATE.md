## Summary

<!-- What does this PR do? Link relevant issues. -->

## Which loop stage does this belong to?

<!-- Every code change belongs to a stage. Cross-cutting concerns (auth, DB) are infrastructure. -->

- [ ] [1] ANALYZE
- [ ] [2] INFER
- [ ] [3] HARVEST
- [ ] [4] GENERATE
- [ ] [5] DEPLOY
- [ ] [6] OBSERVE
- [ ] [7] EXPERIMENT
- [ ] [8] EVOLVE
- [ ] Infrastructure / Dashboard / SDK

## F-ID reference

<!-- If this PR addresses a ROADMAP deliverable, list the F-ID(s): e.g. F-1.3 -->

## Checklist

- [ ] Tests pass (`make test`)
- [ ] Lint passes (`make lint` + `make type-check`)
- [ ] Loop stage is identified and documented in commit scope
- [ ] ArcanaInsight still works (or not yet connected — Phase 0 only)
- [ ] `docs/DECISIONS.md` updated if this PR makes a significant architectural decision
- [ ] No LangChain/LlamaIndex imports introduced
- [ ] No external vector DB introduced
- [ ] No hardcoded embedding dimensions introduced
- [ ] No `apps/api/src/loop/` directory structure changed without CLAUDE.md update
