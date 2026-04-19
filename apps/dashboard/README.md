# apps/dashboard

Next.js 16 App Router dashboard for Verum — the control plane for The Verum Loop.

**Status:** Phase 0 stub. No pages implemented yet.

## Tech stack

- Next.js 16 (App Router)
- React 19
- TypeScript strict
- Tailwind CSS v4
- Recharts (charts)
- Zustand (state)
- NextAuth (GitHub OAuth)

## Running locally

```bash
make dashboard-dev
# or
cd apps/dashboard && npm run dev
```

## Page plan (per phase)

| Phase | Pages |
|---|---|
| Phase 0 | Health check page |
| Phase 1 | Repo connection + ANALYZE result viewer |
| Phase 2 | INFER result + HARVEST progress + chunk search |
| Phase 3 | GENERATE proposal review + DEPLOY traffic controls |
| Phase 4 | Trace list + span waterfall + experiment results + evolution history |
| Phase 5 | Public landing page + docs |
