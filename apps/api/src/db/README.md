# db/

SQLAlchemy 2 async models and session factory.

**Status:** Phase 0 stub — empty until Phase 1 adds the first Alembic migration.

All schema changes go through `alembic/` migrations. No raw SQL. See [docs/ARCHITECTURE.md §4](../../../docs/ARCHITECTURE.md#4-data-models) for the full schema.

The `FailoverSessionFactory` pattern from SCAManager is the reference implementation for the async session factory here.
