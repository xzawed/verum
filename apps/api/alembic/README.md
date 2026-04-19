# alembic/

Alembic database migrations for Verum's PostgreSQL schema.

**Status:** Phase 0 — no migrations yet. The first migration (create `repos`, `analyses`, `inferences` tables) ships in Phase 1 (F-1.7).

Run migrations: `make db-migrate`
Create a new migration: `make db-revision m="describe the change"`

See [docs/ARCHITECTURE.md §4](../../docs/ARCHITECTURE.md#4-data-models) for the full schema specification.
