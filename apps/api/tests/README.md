# tests/

pytest test suite for `apps/api`.

**Status:** Phase 0 — only a health check test exists. Coverage gate (≥ 80%) activates in Phase 2.

Run: `make test-api`

Conventions:
- Unit tests: test pure business logic with no I/O
- Integration tests: test against a real PostgreSQL database (not mocked — see CLAUDE.md §테스트)
- Files match `test_<module>.py` naming
