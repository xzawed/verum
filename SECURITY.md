# Security Policy

## Supported Versions

Verum is currently in pre-release (alpha). Only the latest commit on `main` receives security fixes.

| Version | Supported |
|---|---|
| `main` (latest) | ✅ |
| Older commits | ❌ |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email: **xzawed31@gmail.com**  
Subject: `[Verum Security] <brief description>`

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fix (optional)

We will acknowledge receipt within **72 hours** and aim to release a fix within **14 days** for critical issues.

## Scope

In scope:
- `apps/api/src/` — Python worker and loop engine
- `apps/dashboard/src/` — Next.js API routes and authentication
- `packages/sdk-python/` and `packages/sdk-typescript/` — SDKs
- Authentication and authorization logic (GitHub OAuth, Auth.js session)
- SQL injection, IDOR, XSS, and other OWASP Top 10 issues

Out of scope:
- Theoretical vulnerabilities without a proof of concept
- Vulnerabilities in test fixtures or development-only configs
- Self-hosted deployments using non-default configurations

## Security Design Notes

- Browser-facing API routes require an Auth.js JWT session (GitHub OAuth)
- SDK-facing routes authenticate via `X-Verum-API-Key` header (= deployment UUID)
- All browser endpoints verify `repos.owner_user_id` via SQL JOIN chain to prevent IDOR
- Prompts sent to Claude and raw responses are stored in `judge_prompts` for auditability — no user PII is stored in this table
- Actual LLM call content (user queries, assistant responses) is **not** stored in `spans` — only token counts and latency

## Disclosure Policy

We follow coordinated disclosure. We will:
1. Confirm the report and assess severity
2. Develop and test a fix privately
3. Release the fix
4. Credit the reporter in the release notes (unless you prefer to remain anonymous)
