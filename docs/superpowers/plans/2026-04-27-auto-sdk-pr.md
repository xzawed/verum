# Auto SDK PR Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a "Create SDK PR" feature in the Verum dashboard that, after the ANALYZE pipeline completes for a connected repo, lets the user click a button to automatically open a GitHub PR on their repo containing the Verum inline client, `.env.example` additions, and `// TODO: [Verum]` comments on every detected LLM call site.

**Architecture:** All work happens in the Next.js dashboard — no new Python worker jobs. A new `sdk_pr_requests` table tracks request state. A `GitHubPrCreator` class reads repo files via GitHub Contents API, applies text transformations, and creates a PR using the GitHub Git Tree API using the user's `github_access_token` from the Auth.js JWT session. The transformer adds the inline Verum client, updates `.env.example`, and inserts `// TODO: [Verum]` comments above each detected LLM call site (line numbers from `analyses.call_sites` JSONB).

**Tech Stack:** Next.js App Router API routes, GitHub REST API (Contents v3 + Git Trees + Pulls), Drizzle ORM, Alembic migration 0019, TypeScript string manipulation, React client component with async state.

---

## File Map

**New files:**
- `apps/api/alembic/versions/0019_sdk_pr_requests.py`
- `apps/dashboard/src/lib/sdk-pr/verum-inline.ts`
- `apps/dashboard/src/lib/sdk-pr/transformer.ts`
- `apps/dashboard/src/lib/sdk-pr/__tests__/transformer.test.ts`
- `apps/dashboard/src/lib/github/pr-creator.ts`
- `apps/dashboard/src/lib/github/__tests__/pr-creator.test.ts`
- `apps/dashboard/src/app/api/repos/[id]/sdk-pr/route.ts`
- `apps/dashboard/src/app/api/repos/[id]/sdk-pr/[requestId]/route.ts`
- `apps/dashboard/src/app/api/repos/[id]/sdk-pr/__tests__/route.test.ts`
- `apps/dashboard/src/components/repos/SdkPrSection.tsx`

**Modified files:**
- `apps/dashboard/src/lib/db/schema.ts` — add `sdk_pr_requests` table
- `apps/dashboard/src/lib/db/jobs.ts` — add `createSdkPrRequest`, `updateSdkPrRequest`
- `apps/dashboard/src/lib/db/queries.ts` — add `getSdkPrRequest`, `getLatestSdkPrRequest`
- `apps/dashboard/src/app/repos/[id]/page.tsx` — add `SdkPrSection` after analysis complete

---

## Context

**Existing code to understand before starting:**

- `apps/dashboard/src/lib/db/queries.ts:76` — `getRepo(userId, repoId)` already exists, returns `Repo | null`
- `apps/dashboard/src/lib/db/queries.ts:85` — `getLatestAnalysis(repoId)` exists, returns `Analysis | null` with `call_sites: jsonb` field as `LLMCallSite[]`
- `apps/dashboard/src/lib/api/handlers.ts` — `getAuthUserId()` calls `auth()` internally; to get `github_access_token` call `auth()` directly: `(session?.user as Record<string, unknown>)?.github_access_token as string`
- `apps/dashboard/src/lib/db/jobs.ts` — pattern for all other job enqueue functions (insert + return id)
- `apps/api/alembic/versions/0018_chunks_inference_fk.py` — most recent migration (down_revision for 0019)
- `apps/api/src/loop/analyze/models.py` — `LLMCallSite` schema: `{ file_path, line, sdk, function, prompt_ref }`

---

## Task 1: Alembic Migration 0019 — sdk_pr_requests Table

**Files:**
- Create: `apps/api/alembic/versions/0019_sdk_pr_requests.py`
- Modify: `apps/dashboard/src/lib/db/schema.ts`

- [ ] **Step 1: Create the migration file**

```python
# apps/api/alembic/versions/0019_sdk_pr_requests.py
"""Add sdk_pr_requests table for Auto SDK PR Generation feature ([5] DEPLOY).

Revision ID: 0019_sdk_pr_requests
Revises: 0018_chunks_inference_fk
Create Date: 2026-04-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_sdk_pr_requests"
down_revision: str = "0018_chunks_inference_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sdk_pr_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "repo_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("repos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("pr_url", sa.Text(), nullable=True),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("branch_name", sa.String(255), nullable=True),
        sa.Column("files_changed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_sdk_pr_requests_repo_id", "sdk_pr_requests", ["repo_id"])
    op.create_index(
        "ix_sdk_pr_requests_owner_user_id", "sdk_pr_requests", ["owner_user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_sdk_pr_requests_owner_user_id", "sdk_pr_requests")
    op.drop_index("ix_sdk_pr_requests_repo_id", "sdk_pr_requests")
    op.drop_table("sdk_pr_requests")
```

- [ ] **Step 2: Run the migration**

```bash
cd apps/api
alembic upgrade head
```
Expected output includes: `Running upgrade 0018_chunks_inference_fk -> 0019_sdk_pr_requests`

- [ ] **Step 3: Sync Drizzle schema**

Run introspection to pull the new table into schema.ts:
```bash
cd apps/dashboard
npx drizzle-kit pull
```
Expected: `sdk_pr_requests` appears in `src/lib/db/schema.ts`.

If `drizzle-kit pull` is not configured for this (check `drizzle.config.ts`), manually add to `apps/dashboard/src/lib/db/schema.ts` after the `verum_jobs` table definition:

```typescript
export const sdk_pr_requests = pgTable("sdk_pr_requests", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  repo_id: uuid("repo_id")
    .notNull()
    .references(() => repos.id, { onDelete: "cascade" }),
  owner_user_id: uuid("owner_user_id")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  analysis_id: uuid("analysis_id")
    .notNull()
    .references(() => analyses.id, { onDelete: "cascade" }),
  status: varchar("status", { length: 32 }).notNull().default("pending"),
  pr_url: text("pr_url"),
  pr_number: integer("pr_number"),
  branch_name: varchar("branch_name", { length: 255 }),
  files_changed: integer("files_changed").notNull().default(0),
  error: text("error"),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updated_at: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd apps/dashboard
npx tsc --noEmit
```
Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add apps/api/alembic/versions/0019_sdk_pr_requests.py apps/dashboard/src/lib/db/schema.ts
git commit -m "feat(deploy): add sdk_pr_requests migration 0019 and Drizzle schema"
```

---

## Task 2: DB Query + Mutation Functions

**Files:**
- Modify: `apps/dashboard/src/lib/db/queries.ts` (add `getSdkPrRequest`, `getLatestSdkPrRequest`)
- Modify: `apps/dashboard/src/lib/db/jobs.ts` (add `createSdkPrRequest`, `updateSdkPrRequest`)
- Test: `apps/dashboard/src/lib/db/__tests__/sdk-pr-db.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `apps/dashboard/src/lib/db/__tests__/sdk-pr-db.test.ts`:

```typescript
// This file tests createSdkPrRequest, updateSdkPrRequest, getSdkPrRequest, getLatestSdkPrRequest.
// It follows the same mock pattern as queries.test.ts in this folder — mock @/lib/db/client.
import { createSdkPrRequest, updateSdkPrRequest } from "../jobs";
import { getSdkPrRequest, getLatestSdkPrRequest } from "../queries";

const mockInsertValues = jest.fn().mockReturnThis();
const mockInsertReturning = jest.fn().mockResolvedValue([{ id: "req-uuid-1", status: "pending" }]);
const mockUpdateSet = jest.fn().mockReturnThis();
const mockUpdateWhere = jest.fn().mockResolvedValue(undefined);
const mockSelectFrom = jest.fn().mockReturnThis();
const mockSelectWhere = jest.fn().mockReturnThis();
const mockSelectOrderBy = jest.fn().mockReturnThis();
const mockSelectLimit = jest.fn().mockResolvedValue([{
  id: "req-uuid-1",
  repo_id: "repo-1",
  owner_user_id: "user-1",
  analysis_id: "analysis-1",
  status: "pending",
  pr_url: null,
  pr_number: null,
  branch_name: null,
  files_changed: 0,
  error: null,
  created_at: new Date(),
  updated_at: new Date(),
}]);

jest.mock("@/lib/db/client", () => ({
  db: {
    insert: jest.fn(() => ({ values: mockInsertValues })),
    update: jest.fn(() => ({ set: mockUpdateSet })),
    select: jest.fn(() => ({ from: mockSelectFrom })),
  },
}));

// Wire up the mock chains
mockInsertValues.mockReturnValue({ returning: mockInsertReturning });
mockUpdateSet.mockReturnValue({ where: mockUpdateWhere });
mockSelectFrom.mockReturnValue({ where: mockSelectWhere });
mockSelectWhere.mockReturnValue({ limit: mockSelectLimit, orderBy: mockSelectOrderBy });
mockSelectOrderBy.mockReturnValue({ limit: mockSelectLimit });

describe("sdk_pr_requests DB helpers", () => {
  beforeEach(() => jest.clearAllMocks());

  it("createSdkPrRequest inserts and returns the new row id", async () => {
    const id = await createSdkPrRequest({ userId: "user-1", repoId: "repo-1", analysisId: "analysis-1" });
    expect(id).toBe("req-uuid-1");
    expect(mockInsertValues).toHaveBeenCalledWith(
      expect.objectContaining({ repo_id: "repo-1", owner_user_id: "user-1", status: "pending" }),
    );
  });

  it("updateSdkPrRequest sets status + updated_at", async () => {
    await updateSdkPrRequest("req-uuid-1", { status: "pr_created", pr_url: "https://github.com/o/r/pull/1", pr_number: 1, files_changed: 3 });
    expect(mockUpdateSet).toHaveBeenCalledWith(
      expect.objectContaining({ status: "pr_created", pr_url: "https://github.com/o/r/pull/1" }),
    );
  });

  it("getSdkPrRequest returns null on miss (empty array)", async () => {
    mockSelectLimit.mockResolvedValueOnce([]);
    const result = await getSdkPrRequest("user-1", "nonexistent");
    expect(result).toBeNull();
  });

  it("getLatestSdkPrRequest returns the most recent request", async () => {
    const result = await getLatestSdkPrRequest("user-1", "repo-1");
    expect(result).not.toBeNull();
    expect(result?.id).toBe("req-uuid-1");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/dashboard
npx jest src/lib/db/__tests__/sdk-pr-db.test.ts --no-coverage
```
Expected: FAIL — `createSdkPrRequest is not a function`

- [ ] **Step 3: Add `createSdkPrRequest` and `updateSdkPrRequest` to jobs.ts**

Add these two functions at the end of `apps/dashboard/src/lib/db/jobs.ts`. Also add `sdk_pr_requests` to the schema import at the top of the file.

**Import addition** (find the existing import line and extend it):
```typescript
// In the existing import from "./schema", add sdk_pr_requests:
import {
  analyses,
  deployments,
  generations,
  harvest_sources,
  inferences,
  repos,
  sdk_pr_requests,  // ADD THIS
  verum_jobs,
  type Inference,
} from "./schema";
```

**New functions at the end of jobs.ts:**
```typescript
// ── SDK PR ────────────────────────────────────────────────────

export async function createSdkPrRequest(opts: {
  userId: string;
  repoId: string;
  analysisId: string;
}): Promise<string> {
  const rows = await db
    .insert(sdk_pr_requests)
    .values({
      repo_id: opts.repoId,
      owner_user_id: opts.userId,
      analysis_id: opts.analysisId,
      status: "pending",
    })
    .returning({ id: sdk_pr_requests.id });
  const row = rows[0];
  if (!row) throw new Error("createSdkPrRequest: INSERT returned no row");
  return row.id;
}

export async function updateSdkPrRequest(
  requestId: string,
  patch: {
    status: string;
    pr_url?: string | null;
    pr_number?: number | null;
    branch_name?: string | null;
    files_changed?: number;
    error?: string | null;
  },
): Promise<void> {
  await db
    .update(sdk_pr_requests)
    .set({ ...patch, updated_at: new Date() })
    .where(eq(sdk_pr_requests.id, requestId));
}
```

- [ ] **Step 4: Add `getSdkPrRequest` and `getLatestSdkPrRequest` to queries.ts**

Add `sdk_pr_requests` to the existing schema import in `apps/dashboard/src/lib/db/queries.ts` (find the existing import and add `sdk_pr_requests`).

Add at the end of the file:
```typescript
// ── SDK PR ────────────────────────────────────────────────────

export async function getSdkPrRequest(userId: string, requestId: string) {
  const rows = await db
    .select()
    .from(sdk_pr_requests)
    .where(
      and(
        eq(sdk_pr_requests.id, requestId),
        eq(sdk_pr_requests.owner_user_id, userId),
      ),
    )
    .limit(1);
  return rows[0] ?? null;
}

export async function getLatestSdkPrRequest(userId: string, repoId: string) {
  const rows = await db
    .select()
    .from(sdk_pr_requests)
    .where(
      and(
        eq(sdk_pr_requests.repo_id, repoId),
        eq(sdk_pr_requests.owner_user_id, userId),
      ),
    )
    .orderBy(desc(sdk_pr_requests.created_at))
    .limit(1);
  return rows[0] ?? null;
}
```

Note: `desc` is already imported in queries.ts. Verify with `grep "import.*desc" apps/dashboard/src/lib/db/queries.ts`.

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd apps/dashboard
npx jest src/lib/db/__tests__/sdk-pr-db.test.ts --no-coverage
```
Expected: PASS — 4 tests

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/src/lib/db/jobs.ts apps/dashboard/src/lib/db/queries.ts apps/dashboard/src/lib/db/__tests__/sdk-pr-db.test.ts
git commit -m "feat(deploy): add sdk_pr_requests DB helpers — create, update, get"
```

---

## Task 3: Verum Inline SDK Template

**Files:**
- Create: `apps/dashboard/src/lib/sdk-pr/verum-inline.ts`

This file holds the VerumClient TypeScript source as a template string that will be written verbatim into target repos. It matches the client created for ArcanaInsight in `f:\DEVELOPMENT\SOURCE\CLAUDE\ArcanaInsight\src\lib\verum\client.ts` but without ArcanaInsight-specific imports.

- [ ] **Step 1: Create the template file**

```typescript
// apps/dashboard/src/lib/sdk-pr/verum-inline.ts

export const VERUM_CLIENT_SOURCE = `interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

interface ChatResult {
  messages: ChatMessage[];
  routed_to: "variant" | "baseline";
  deployment_id: string;
}

interface RecordParams {
  deploymentId: string;
  variant: "variant" | "baseline";
  model: string;
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
}

export class VerumClient {
  private readonly apiUrl: string;
  private readonly apiKey: string;

  constructor(opts: { apiUrl: string; apiKey: string }) {
    this.apiUrl = opts.apiUrl.replace(/\\/$/, "");
    this.apiKey = opts.apiKey;
  }

  async chat(
    messages: ChatMessage[],
    deploymentId?: string,
  ): Promise<ChatResult> {
    if (!this.apiUrl || !this.apiKey || !deploymentId) {
      return { messages, routed_to: "baseline", deployment_id: deploymentId ?? "" };
    }
    const res = await fetch(\`\${this.apiUrl}/api/v1/sdk/chat\`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: \`Bearer \${this.apiKey}\`,
      },
      body: JSON.stringify({ messages, deployment_id: deploymentId }),
    });
    if (!res.ok) {
      throw new Error(\`Verum API error: \${res.status} \${res.statusText}\`);
    }
    return res.json() as Promise<ChatResult>;
  }

  async record(params: RecordParams): Promise<string> {
    const res = await fetch(\`\${this.apiUrl}/api/v1/sdk/record\`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: \`Bearer \${this.apiKey}\`,
      },
      body: JSON.stringify({
        deployment_id: params.deploymentId,
        variant: params.variant,
        model: params.model,
        input_tokens: params.inputTokens,
        output_tokens: params.outputTokens,
        latency_ms: params.latencyMs,
      }),
    });
    if (!res.ok) throw new Error(\`Verum record error: \${res.status}\`);
    const data = await res.json() as { trace_id: string };
    return data.trace_id;
  }
}
`;

export const VERUM_ENV_ADDITIONS = `
# Verum — connect to The Verum Loop for automatic prompt optimization
# Obtain VERUM_API_KEY and VERUM_DEPLOYMENT_ID from the Verum dashboard
# after running ANALYZE → INFER → HARVEST → GENERATE → DEPLOY for this repo.
# If not set, falls back to built-in local prompts (safe default).
VERUM_API_URL=https://verum-production.up.railway.app
VERUM_API_KEY=
VERUM_DEPLOYMENT_ID=
`.trimStart();
```

- [ ] **Step 2: Commit (no test needed for pure constants)**

```bash
git add apps/dashboard/src/lib/sdk-pr/verum-inline.ts
git commit -m "feat(deploy): add verum inline SDK template string for Auto SDK PR"
```

---

## Task 4: Code Transformer

**Files:**
- Create: `apps/dashboard/src/lib/sdk-pr/transformer.ts`
- Create: `apps/dashboard/src/lib/sdk-pr/__tests__/transformer.test.ts`

The transformer takes the `call_sites` array (from `analyses.call_sites`) and a map of `filePath → currentContent` (fetched from GitHub) and returns a `FileChange[]` list. Phase 1 strategy:
1. Always add `src/lib/verum/client.ts` with the inline VerumClient
2. Add/update `.env.example` with Verum env vars (append if already exists, skip if already has `VERUM_API_URL`)
3. For each TypeScript/JavaScript file that has call sites: insert a `// TODO: [Verum]` comment above the detected call site line (line numbers from `LLMCallSite.line`, 1-indexed)

- [ ] **Step 1: Write the failing tests**

Create `apps/dashboard/src/lib/sdk-pr/__tests__/transformer.test.ts`:

```typescript
import { buildPrFileChanges } from "../transformer";
import type { LLMCallSite } from "../transformer";

const oneCallSite: LLMCallSite[] = [
  { file_path: "src/services/ai.ts", line: 5, sdk: "openai", function: "chat.completions.create", prompt_ref: null },
];

const sampleFileContent = [
  "import OpenAI from 'openai';",       // line 1
  "const client = new OpenAI();",        // line 2
  "",                                    // line 3
  "async function call() {",             // line 4
  "  const res = await client.chat.completions.create({", // line 5
  "    model: 'gpt-4',",                 // line 6
  "    messages: [],",                   // line 7
  "  });",                               // line 8
  "}",                                   // line 9
].join("\n");

describe("buildPrFileChanges", () => {
  it("always includes src/lib/verum/client.ts", () => {
    const changes = buildPrFileChanges({ callSites: [], existingFiles: {}, repoFullName: "owner/repo" });
    const clientFile = changes.find((c) => c.path === "src/lib/verum/client.ts");
    expect(clientFile).toBeDefined();
    expect(clientFile!.content).toContain("class VerumClient");
  });

  it("creates .env.example when it does not exist", () => {
    const changes = buildPrFileChanges({ callSites: [], existingFiles: {}, repoFullName: "owner/repo" });
    const envFile = changes.find((c) => c.path === ".env.example");
    expect(envFile).toBeDefined();
    expect(envFile!.content).toContain("VERUM_API_URL");
    expect(envFile!.content).toContain("VERUM_DEPLOYMENT_ID");
  });

  it("appends Verum vars to existing .env.example", () => {
    const changes = buildPrFileChanges({
      callSites: [],
      existingFiles: { ".env.example": "DATABASE_URL=postgres://localhost/mydb\n" },
      repoFullName: "owner/repo",
    });
    const envFile = changes.find((c) => c.path === ".env.example");
    expect(envFile).toBeDefined();
    expect(envFile!.content).toContain("DATABASE_URL=postgres://localhost/mydb");
    expect(envFile!.content).toContain("VERUM_API_URL");
  });

  it("does NOT modify .env.example if VERUM_API_URL already present", () => {
    const changes = buildPrFileChanges({
      callSites: [],
      existingFiles: { ".env.example": "VERUM_API_URL=https://verum.dev\n" },
      repoFullName: "owner/repo",
    });
    const envFile = changes.find((c) => c.path === ".env.example");
    // No change needed — should not appear in changes
    expect(envFile).toBeUndefined();
  });

  it("inserts TODO comment above the detected call site line", () => {
    const changes = buildPrFileChanges({
      callSites: oneCallSite,
      existingFiles: { "src/services/ai.ts": sampleFileContent },
      repoFullName: "owner/repo",
    });
    const aiFile = changes.find((c) => c.path === "src/services/ai.ts");
    expect(aiFile).toBeDefined();
    const lines = aiFile!.content.split("\n");
    // The TODO comment should appear immediately before the original line 5
    const todoIdx = lines.findIndex((l) => l.includes("// TODO: [Verum]"));
    expect(todoIdx).toBeGreaterThanOrEqual(0);
    expect(lines[todoIdx + 1]).toContain("client.chat.completions.create");
  });

  it("does not insert duplicate TODO comments when called twice", () => {
    const firstPass = buildPrFileChanges({
      callSites: oneCallSite,
      existingFiles: { "src/services/ai.ts": sampleFileContent },
      repoFullName: "owner/repo",
    });
    const modified = firstPass.find((c) => c.path === "src/services/ai.ts")!.content;
    const secondPass = buildPrFileChanges({
      callSites: oneCallSite,
      existingFiles: { "src/services/ai.ts": modified },
      repoFullName: "owner/repo",
    });
    const finalFile = secondPass.find((c) => c.path === "src/services/ai.ts")!;
    const count = (finalFile.content.match(/\/\/ TODO: \[Verum\]/g) ?? []).length;
    expect(count).toBe(1);
  });

  it("skips non-TypeScript files in call_sites", () => {
    const changes = buildPrFileChanges({
      callSites: [{ file_path: "src/script.py", line: 3, sdk: "openai", function: "create", prompt_ref: null }],
      existingFiles: { "src/script.py": "import openai\nclient = openai.OpenAI()\nclient.chat.completions.create()\n" },
      repoFullName: "owner/repo",
    });
    const pyFile = changes.find((c) => c.path === "src/script.py");
    // Python files are not modified in Phase 1 (TypeScript-only transformer)
    expect(pyFile).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/dashboard
npx jest src/lib/sdk-pr/__tests__/transformer.test.ts --no-coverage
```
Expected: FAIL — `Cannot find module '../transformer'`

- [ ] **Step 3: Implement the transformer**

Create `apps/dashboard/src/lib/sdk-pr/transformer.ts`:

```typescript
import { VERUM_CLIENT_SOURCE, VERUM_ENV_ADDITIONS } from "./verum-inline";

export interface LLMCallSite {
  file_path: string;
  line: number;
  sdk: string;
  function: string;
  prompt_ref: string | null;
}

export interface FileChange {
  path: string;
  content: string;
}

const TS_EXTENSIONS = /\.(ts|tsx|js|jsx|mjs|cjs)$/;
const VERUM_TODO_MARKER = "// TODO: [Verum]";

function buildTodoComment(sdk: string, fn: string): string {
  return (
    `${VERUM_TODO_MARKER} Wrap this ${sdk} call (${fn}) with VerumClient for A/B prompt optimization.\n` +
    `// See integration guide: https://verum.dev/docs/sdk-integration`
  );
}

export function buildPrFileChanges(opts: {
  callSites: LLMCallSite[];
  existingFiles: Record<string, string>;
  repoFullName: string;
}): FileChange[] {
  const { callSites, existingFiles } = opts;
  const changes: FileChange[] = [];

  // 1. Always add the inline Verum client
  changes.push({ path: "src/lib/verum/client.ts", content: VERUM_CLIENT_SOURCE + "\n" });

  // 2. Add/update .env.example (skip if VERUM_API_URL already present)
  const existingEnv = existingFiles[".env.example"] ?? "";
  if (!existingEnv.includes("VERUM_API_URL")) {
    const newEnv = existingEnv
      ? existingEnv.trimEnd() + "\n\n" + VERUM_ENV_ADDITIONS
      : VERUM_ENV_ADDITIONS;
    changes.push({ path: ".env.example", content: newEnv });
  }

  // 3. Insert TODO comments in TypeScript files with detected call sites
  const fileCallSites = new Map<string, LLMCallSite[]>();
  for (const site of callSites) {
    if (!TS_EXTENSIONS.test(site.file_path)) continue;
    const existing = fileCallSites.get(site.file_path) ?? [];
    existing.push(site);
    fileCallSites.set(site.file_path, existing);
  }

  for (const [filePath, sites] of fileCallSites) {
    const original = existingFiles[filePath];
    if (!original) continue;

    // Sort descending by line so we insert from bottom up — preserves line numbers for earlier inserts
    const sorted = [...sites].sort((a, b) => b.line - a.line);
    const lines = original.split("\n");

    for (const site of sorted) {
      const insertAt = site.line - 1; // convert 1-indexed to 0-indexed
      if (insertAt < 0 || insertAt >= lines.length) continue;
      // Skip if a TODO comment already precedes this line (idempotent)
      if (lines[insertAt - 1]?.trimStart().startsWith(VERUM_TODO_MARKER)) continue;
      if (lines[insertAt]?.trimStart().startsWith(VERUM_TODO_MARKER)) continue;
      lines.splice(insertAt, 0, buildTodoComment(site.sdk, site.function));
    }

    changes.push({ path: filePath, content: lines.join("\n") });
  }

  return changes;
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/dashboard
npx jest src/lib/sdk-pr/__tests__/transformer.test.ts --no-coverage
```
Expected: PASS — 6 tests

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/src/lib/sdk-pr/
git commit -m "feat(deploy): add SDK PR file transformer — verum client + env + TODO comments"
```

---

## Task 5: GitHub Git Tree API Client

**Files:**
- Create: `apps/dashboard/src/lib/github/pr-creator.ts`
- Create: `apps/dashboard/src/lib/github/__tests__/pr-creator.test.ts`

The `GitHubPrCreator` creates a PR in 7 sequential GitHub API calls using the Git Trees API for an atomic multi-file commit (no separate blob creation per file — blobs are embedded in the tree).

- [ ] **Step 1: Write the failing tests**

Create `apps/dashboard/src/lib/github/__tests__/pr-creator.test.ts`:

```typescript
import { GitHubPrCreator } from "../pr-creator";

const mockFetch = jest.fn();
global.fetch = mockFetch;

const BASE_SHA = "aabbcc112233";
const TREE_SHA = "ddeeff445566";
const NEW_BLOB_SHA = "111bbb";
const NEW_TREE_SHA = "222ccc";
const NEW_COMMIT_SHA = "333ddd";

function mockGitHubResponses() {
  mockFetch
    // Step 1: get ref → base SHA
    .mockResolvedValueOnce({ ok: true, json: async () => ({ object: { sha: BASE_SHA } }) })
    // Step 2: get commit → tree SHA
    .mockResolvedValueOnce({ ok: true, json: async () => ({ tree: { sha: TREE_SHA } }) })
    // Step 3: create blob for each file (1 file in tests)
    .mockResolvedValueOnce({ ok: true, json: async () => ({ sha: NEW_BLOB_SHA }) })
    // Step 4: create tree
    .mockResolvedValueOnce({ ok: true, json: async () => ({ sha: NEW_TREE_SHA }) })
    // Step 5: create commit
    .mockResolvedValueOnce({ ok: true, json: async () => ({ sha: NEW_COMMIT_SHA }) })
    // Step 6: create branch ref
    .mockResolvedValueOnce({ ok: true, json: async () => ({}) })
    // Step 7: open PR
    .mockResolvedValueOnce({ ok: true, json: async () => ({ html_url: "https://github.com/owner/repo/pull/42", number: 42 }) });
}

describe("GitHubPrCreator", () => {
  beforeEach(() => mockFetch.mockReset());

  it("creates PR and returns pr_url + pr_number", async () => {
    mockGitHubResponses();
    const creator = new GitHubPrCreator({ accessToken: "ghp_test123", repoFullName: "owner/repo" });
    const result = await creator.createPr({
      branchName: "verum/sdk-integration",
      baseBranch: "main",
      title: "Add Verum SDK",
      body: "PR body",
      files: [{ path: "src/lib/verum/client.ts", content: "export class VerumClient {}" }],
    });
    expect(result.pr_url).toBe("https://github.com/owner/repo/pull/42");
    expect(result.pr_number).toBe(42);
    expect(result.branch_name).toBe("verum/sdk-integration");
    expect(mockFetch).toHaveBeenCalledTimes(7);
  });

  it("throws a descriptive error on 404 from GitHub", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: async () => ({}),
    });
    const creator = new GitHubPrCreator({ accessToken: "ghp_bad", repoFullName: "owner/repo" });
    await expect(
      creator.createPr({ branchName: "verum/x", baseBranch: "main", title: "t", body: "b", files: [] }),
    ).rejects.toThrow("GitHub API 404");
  });

  it("readFile returns null when file does not exist (404)", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404, statusText: "Not Found", json: async () => ({}) });
    const creator = new GitHubPrCreator({ accessToken: "ghp_test", repoFullName: "owner/repo" });
    const content = await creator.readFile(".env.example");
    expect(content).toBeNull();
  });

  it("readFile decodes base64 content", async () => {
    const encoded = Buffer.from("EXISTING_VAR=hello\n").toString("base64");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ content: encoded + "\n", encoding: "base64" }),
    });
    const creator = new GitHubPrCreator({ accessToken: "ghp_test", repoFullName: "owner/repo" });
    const content = await creator.readFile(".env.example");
    expect(content).toBe("EXISTING_VAR=hello\n");
  });

  it("throws on invalid repoFullName", () => {
    expect(() => new GitHubPrCreator({ accessToken: "x", repoFullName: "invalid-no-slash" })).toThrow(
      "Invalid repoFullName",
    );
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/dashboard
npx jest src/lib/github/__tests__/pr-creator.test.ts --no-coverage
```
Expected: FAIL — `Cannot find module '../pr-creator'`

- [ ] **Step 3: Implement `GitHubPrCreator`**

Create `apps/dashboard/src/lib/github/pr-creator.ts`:

```typescript
export interface PrFile {
  path: string;
  content: string;
}

export interface CreatePrOptions {
  branchName: string;
  baseBranch: string;
  title: string;
  body: string;
  files: PrFile[];
}

export interface CreatePrResult {
  pr_url: string;
  pr_number: number;
  branch_name: string;
}

export class GitHubPrCreator {
  private readonly token: string;
  private readonly owner: string;
  private readonly repo: string;
  private readonly base = "https://api.github.com";

  constructor(opts: { accessToken: string; repoFullName: string }) {
    this.token = opts.accessToken;
    const parts = opts.repoFullName.split("/");
    if (parts.length !== 2 || !parts[0] || !parts[1]) {
      throw new Error(`Invalid repoFullName: "${opts.repoFullName}" — expected "owner/repo"`);
    }
    this.owner = parts[0];
    this.repo = parts[1];
  }

  async createPr(opts: CreatePrOptions): Promise<CreatePrResult> {
    // Step 1: Get base branch HEAD SHA
    const refData = await this._request<{ object: { sha: string } }>(
      "GET",
      `/repos/${this.owner}/${this.repo}/git/ref/heads/${opts.baseBranch}`,
    );
    const baseSha = refData.object.sha;

    // Step 2: Get base commit's tree SHA
    const commitData = await this._request<{ tree: { sha: string } }>(
      "GET",
      `/repos/${this.owner}/${this.repo}/git/commits/${baseSha}`,
    );
    const baseTreeSha = commitData.tree.sha;

    // Step 3: Create a blob for each file
    const treeItems = await Promise.all(
      opts.files.map(async (file) => {
        const blob = await this._request<{ sha: string }>(
          "POST",
          `/repos/${this.owner}/${this.repo}/git/blobs`,
          { content: Buffer.from(file.content).toString("base64"), encoding: "base64" },
        );
        return { path: file.path, mode: "100644" as const, type: "blob" as const, sha: blob.sha };
      }),
    );

    // Step 4: Create new tree from base tree + modified blobs
    const newTree = await this._request<{ sha: string }>(
      "POST",
      `/repos/${this.owner}/${this.repo}/git/trees`,
      { base_tree: baseTreeSha, tree: treeItems },
    );

    // Step 5: Create commit pointing to new tree
    const newCommit = await this._request<{ sha: string }>(
      "POST",
      `/repos/${this.owner}/${this.repo}/git/commits`,
      { message: opts.title, tree: newTree.sha, parents: [baseSha] },
    );

    // Step 6: Create new branch pointing to the new commit
    await this._request(
      "POST",
      `/repos/${this.owner}/${this.repo}/git/refs`,
      { ref: `refs/heads/${opts.branchName}`, sha: newCommit.sha },
    );

    // Step 7: Open the PR
    const pr = await this._request<{ html_url: string; number: number }>(
      "POST",
      `/repos/${this.owner}/${this.repo}/pulls`,
      { title: opts.title, body: opts.body, head: opts.branchName, base: opts.baseBranch },
    );

    return { pr_url: pr.html_url, pr_number: pr.number, branch_name: opts.branchName };
  }

  async readFile(filePath: string): Promise<string | null> {
    try {
      const data = await this._request<{ content: string; encoding: string }>(
        "GET",
        `/repos/${this.owner}/${this.repo}/contents/${filePath}`,
      );
      if (data.encoding === "base64") {
        return Buffer.from(data.content.replace(/\n/g, ""), "base64").toString("utf-8");
      }
      return data.content;
    } catch {
      return null;
    }
  }

  private async _request<T = unknown>(method: string, path: string, body?: unknown): Promise<T> {
    const url = `${this.base}${path}`;
    const res = await fetch(url, {
      method,
      headers: {
        Authorization: `Bearer ${this.token}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    if (!res.ok) {
      throw new Error(`GitHub API ${res.status}: ${method} ${path} — ${res.statusText}`);
    }
    return res.json() as Promise<T>;
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/dashboard
npx jest src/lib/github/__tests__/pr-creator.test.ts --no-coverage
```
Expected: PASS — 5 tests

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/src/lib/github/pr-creator.ts apps/dashboard/src/lib/github/__tests__/pr-creator.test.ts
git commit -m "feat(deploy): add GitHubPrCreator using Git Trees API"
```

---

## Task 6: API Routes — /api/repos/[id]/sdk-pr

**Files:**
- Create: `apps/dashboard/src/app/api/repos/[id]/sdk-pr/route.ts`
- Create: `apps/dashboard/src/app/api/repos/[id]/sdk-pr/[requestId]/route.ts`
- Create: `apps/dashboard/src/app/api/repos/[id]/sdk-pr/__tests__/route.test.ts`

The POST handler orchestrates the entire flow:
1. Validates session + repo ownership
2. Gets `github_access_token` from Auth.js session
3. Reads latest analysis `call_sites` from DB via `getLatestAnalysis(repoId)`
4. Reads existing repo files via `GitHubPrCreator.readFile()`
5. Calls `buildPrFileChanges()` to compute file changes
6. Creates SDK PR request row via `createSdkPrRequest()`
7. Calls `GitHubPrCreator.createPr()`
8. Updates the request row with `pr_created` status + PR URL

- [ ] **Step 1: Write the failing tests**

Create `apps/dashboard/src/app/api/repos/[id]/sdk-pr/__tests__/route.test.ts`:

```typescript
import { POST, GET } from "../route";
import { NextRequest } from "next/server";

jest.mock("@/auth", () => ({
  auth: jest.fn().mockResolvedValue({
    user: {
      id: "user-1",
      github_access_token: "ghp_test_token",
    },
  }),
}));

jest.mock("@/lib/api/handlers", () => ({
  getAuthUserId: jest.fn().mockResolvedValue("user-1"),
}));

jest.mock("@/lib/db/queries", () => ({
  getRepo: jest.fn().mockResolvedValue({
    id: "repo-1",
    github_url: "https://github.com/owner/testrepo",
    default_branch: "main",
    owner_user_id: "user-1",
  }),
  getLatestAnalysis: jest.fn().mockResolvedValue({
    id: "analysis-1",
    status: "done",
    call_sites: [
      { file_path: "src/ai.ts", line: 10, sdk: "openai", function: "chat.completions.create", prompt_ref: null },
    ],
  }),
  getLatestSdkPrRequest: jest.fn().mockResolvedValue(null),
}));

jest.mock("@/lib/db/jobs", () => ({
  createSdkPrRequest: jest.fn().mockResolvedValue("sdk-req-1"),
  updateSdkPrRequest: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("@/lib/github/pr-creator", () => ({
  GitHubPrCreator: jest.fn().mockImplementation(() => ({
    readFile: jest.fn().mockResolvedValue(null),
    createPr: jest.fn().mockResolvedValue({
      pr_url: "https://github.com/owner/testrepo/pull/7",
      pr_number: 7,
      branch_name: "verum/sdk-integration-12345",
    }),
  })),
}));

jest.mock("@/lib/sdk-pr/transformer", () => ({
  buildPrFileChanges: jest.fn().mockReturnValue([
    { path: "src/lib/verum/client.ts", content: "export class VerumClient {}" },
    { path: ".env.example", content: "VERUM_API_URL=\n" },
    { path: "src/ai.ts", content: "// TODO: [Verum]\nconst res = await openai.create();\n" },
  ]),
}));

const makeRequest = (method = "POST") =>
  new NextRequest("http://localhost/api/repos/repo-1/sdk-pr", { method });
const makeParams = () => Promise.resolve({ id: "repo-1" });

describe("POST /api/repos/[id]/sdk-pr", () => {
  it("returns 201 with pr_url and files_changed on success", async () => {
    const res = await POST(makeRequest(), { params: makeParams() });
    expect(res.status).toBe(201);
    const body = await res.json() as Record<string, unknown>;
    expect(body.pr_url).toBe("https://github.com/owner/testrepo/pull/7");
    expect(body.pr_number).toBe(7);
    expect(body.files_changed).toBe(3);
    expect(body.request_id).toBe("sdk-req-1");
  });

  it("returns 401 when not authenticated", async () => {
    const { getAuthUserId } = await import("@/lib/api/handlers");
    (getAuthUserId as jest.Mock).mockResolvedValueOnce(null);
    const res = await POST(makeRequest(), { params: makeParams() });
    expect(res.status).toBe(401);
  });

  it("returns 401 when github_access_token is missing from session", async () => {
    const { auth } = await import("@/auth");
    (auth as jest.Mock).mockResolvedValueOnce({ user: { id: "user-1" } });
    const res = await POST(makeRequest(), { params: makeParams() });
    expect(res.status).toBe(401);
  });

  it("returns 404 when repo not found", async () => {
    const { getRepo } = await import("@/lib/db/queries");
    (getRepo as jest.Mock).mockResolvedValueOnce(null);
    const res = await POST(makeRequest(), { params: makeParams() });
    expect(res.status).toBe(404);
  });

  it("returns 409 when analysis is not done", async () => {
    const { getLatestAnalysis } = await import("@/lib/db/queries");
    (getLatestAnalysis as jest.Mock).mockResolvedValueOnce({ id: "a-1", status: "running", call_sites: [] });
    const res = await POST(makeRequest(), { params: makeParams() });
    expect(res.status).toBe(409);
  });
});

describe("GET /api/repos/[id]/sdk-pr", () => {
  it("returns 404 when no SDK PR request exists", async () => {
    const { getLatestSdkPrRequest } = await import("@/lib/db/queries");
    (getLatestSdkPrRequest as jest.Mock).mockResolvedValueOnce(null);
    const res = await GET(makeRequest("GET"), { params: makeParams() });
    expect(res.status).toBe(404);
  });

  it("returns 200 with the latest request when it exists", async () => {
    const { getLatestSdkPrRequest } = await import("@/lib/db/queries");
    (getLatestSdkPrRequest as jest.Mock).mockResolvedValueOnce({
      id: "req-1",
      status: "pr_created",
      pr_url: "https://github.com/o/r/pull/7",
      pr_number: 7,
    });
    const res = await GET(makeRequest("GET"), { params: makeParams() });
    expect(res.status).toBe(200);
    const body = await res.json() as Record<string, unknown>;
    expect(body.pr_url).toBe("https://github.com/o/r/pull/7");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/dashboard
npx jest "src/app/api/repos/\[id\]/sdk-pr/__tests__/route.test.ts" --no-coverage
```
Expected: FAIL — `Cannot find module '../route'`

- [ ] **Step 3: Implement `route.ts`**

Create `apps/dashboard/src/app/api/repos/[id]/sdk-pr/route.ts`:

```typescript
import { NextRequest } from "next/server";
import { auth } from "@/auth";
import { getAuthUserId } from "@/lib/api/handlers";
import { getRepo, getLatestAnalysis, getLatestSdkPrRequest } from "@/lib/db/queries";
import { createSdkPrRequest, updateSdkPrRequest } from "@/lib/db/jobs";
import { GitHubPrCreator } from "@/lib/github/pr-creator";
import { buildPrFileChanges } from "@/lib/sdk-pr/transformer";
import type { LLMCallSite } from "@/lib/sdk-pr/transformer";

const PR_BODY = `## Verum SDK Integration

This PR was automatically generated by [Verum](https://verum-production.up.railway.app) to integrate the Verum Loop into your AI service.

### What's included

- \`src/lib/verum/client.ts\` — inline Verum SDK client (no npm install required)
- \`.env.example\` — Verum environment variable templates
- \`// TODO: [Verum]\` comments on every detected LLM call site showing where to integrate

### Next steps

1. Set \`VERUM_API_URL\`, \`VERUM_API_KEY\`, and \`VERUM_DEPLOYMENT_ID\` in your environment (values from the Verum dashboard after DEPLOY completes)
2. Follow each \`TODO: [Verum]\` comment to wrap the call with \`VerumClient\`
3. Verum will then A/B test your prompts automatically and evolve them over time

> Not affiliated with Verum AI Platform (verumai.com).
`;

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const userId = await getAuthUserId();
  if (!userId) return new Response("unauthorized", { status: 401 });

  const session = await auth();
  const accessToken = (session?.user as Record<string, unknown> | undefined)
    ?.github_access_token as string | undefined;
  if (!accessToken) return new Response("github_access_token missing from session", { status: 401 });

  const { id: repoId } = await params;

  const repo = await getRepo(userId, repoId);
  if (!repo) return new Response("repo not found", { status: 404 });

  const analysis = await getLatestAnalysis(repoId);
  if (!analysis) return new Response("no analysis found for this repo", { status: 404 });
  if (analysis.status !== "done") return new Response("analysis not complete yet", { status: 409 });

  const callSites = (analysis.call_sites ?? []) as LLMCallSite[];
  const repoFullName = repo.github_url.replace("https://github.com/", "");

  const creator = new GitHubPrCreator({ accessToken, repoFullName });

  // Fetch existing files that the transformer might want to modify
  const filesToRead = [".env.example", ...callSites.map((s) => s.file_path)];
  const existingFiles: Record<string, string> = {};
  await Promise.all(
    filesToRead.map(async (path) => {
      const content = await creator.readFile(path);
      if (content !== null) existingFiles[path] = content;
    }),
  );

  const fileChanges = buildPrFileChanges({ callSites, existingFiles, repoFullName });
  const branchName = `verum/sdk-integration-${Date.now()}`;
  const requestId = await createSdkPrRequest({ userId, repoId, analysisId: analysis.id });

  try {
    const { pr_url, pr_number } = await creator.createPr({
      branchName,
      baseBranch: repo.default_branch,
      title: "Add Verum SDK integration",
      body: PR_BODY,
      files: fileChanges,
    });

    await updateSdkPrRequest(requestId, {
      status: "pr_created",
      pr_url,
      pr_number,
      branch_name: branchName,
      files_changed: fileChanges.length,
    });

    return Response.json(
      { request_id: requestId, pr_url, pr_number, files_changed: fileChanges.length },
      { status: 201 },
    );
  } catch (e) {
    const error = e instanceof Error ? e.message : String(e);
    await updateSdkPrRequest(requestId, { status: "error", error });
    return Response.json({ error }, { status: 502 });
  }
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const userId = await getAuthUserId();
  if (!userId) return new Response("unauthorized", { status: 401 });
  const { id: repoId } = await params;
  const request = await getLatestSdkPrRequest(userId, repoId);
  if (!request) return new Response("not found", { status: 404 });
  return Response.json(request);
}
```

- [ ] **Step 4: Implement `[requestId]/route.ts`**

Create `apps/dashboard/src/app/api/repos/[id]/sdk-pr/[requestId]/route.ts`:

```typescript
import { NextRequest } from "next/server";
import { getAuthUserId } from "@/lib/api/handlers";
import { getSdkPrRequest } from "@/lib/db/queries";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string; requestId: string }> },
) {
  const userId = await getAuthUserId();
  if (!userId) return new Response("unauthorized", { status: 401 });
  const { requestId } = await params;
  const request = await getSdkPrRequest(userId, requestId);
  if (!request) return new Response("not found", { status: 404 });
  return Response.json(request);
}
```

- [ ] **Step 5: Run the tests**

```bash
cd apps/dashboard
npx jest "src/app/api/repos/\[id\]/sdk-pr/__tests__/route.test.ts" --no-coverage
```
Expected: PASS — 7 tests

- [ ] **Step 6: Commit**

```bash
git add "apps/dashboard/src/app/api/repos/[id]/sdk-pr/"
git commit -m "feat(deploy): add /api/repos/[id]/sdk-pr POST+GET routes for Auto SDK PR"
```

---

## Task 7: Dashboard UI — SdkPrSection Component

**Files:**
- Create: `apps/dashboard/src/components/repos/SdkPrSection.tsx`

A client component that shows a "Create SDK PR" button and displays the PR status. No polling needed — the POST is synchronous (GitHub API calls complete in <10s for small repos).

- [ ] **Step 1: Implement the component**

Create `apps/dashboard/src/components/repos/SdkPrSection.tsx`:

```tsx
"use client";

import { useState } from "react";

interface SdkPrSectionProps {
  repoId: string;
  existingPrUrl?: string | null;
  existingPrNumber?: number | null;
}

type State =
  | { type: "idle" }
  | { type: "loading" }
  | { type: "done"; prUrl: string; prNumber: number; filesChanged: number }
  | { type: "error"; message: string };

export function SdkPrSection({ repoId, existingPrUrl, existingPrNumber }: SdkPrSectionProps) {
  const [state, setState] = useState<State>(
    existingPrUrl && existingPrNumber
      ? { type: "done", prUrl: existingPrUrl, prNumber: existingPrNumber, filesChanged: 0 }
      : { type: "idle" },
  );

  async function handleCreate() {
    setState({ type: "loading" });
    try {
      const res = await fetch(`/api/repos/${repoId}/sdk-pr`, { method: "POST" });
      const data = (await res.json()) as {
        pr_url?: string;
        pr_number?: number;
        files_changed?: number;
        error?: string;
      };
      if (!res.ok || !data.pr_url || !data.pr_number) {
        setState({ type: "error", message: data.error ?? `HTTP ${res.status}` });
        return;
      }
      setState({
        type: "done",
        prUrl: data.pr_url,
        prNumber: data.pr_number,
        filesChanged: data.files_changed ?? 0,
      });
    } catch (e) {
      setState({ type: "error", message: e instanceof Error ? e.message : "Unknown error" });
    }
  }

  return (
    <section className="rounded-lg border border-neutral-200 p-6 dark:border-neutral-800">
      <h2 className="mb-1 text-lg font-semibold">SDK Integration PR</h2>
      <p className="mb-4 text-sm text-neutral-500 dark:text-neutral-400">
        Automatically create a GitHub PR that adds the Verum inline client and marks every LLM call
        site with integration instructions.
      </p>

      {state.type === "idle" && (
        <button
          onClick={() => void handleCreate()}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          Create SDK PR
        </button>
      )}

      {state.type === "loading" && (
        <div className="flex items-center gap-2 text-sm text-neutral-500">
          <span
            aria-label="loading"
            className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"
          />
          Creating PR on GitHub…
        </div>
      )}

      {state.type === "done" && (
        <div className="rounded-md bg-green-50 p-4 dark:bg-green-950">
          <p className="text-sm font-medium text-green-800 dark:text-green-200">
            PR #{state.prNumber} opened
            {state.filesChanged > 0 && (
              <span className="ml-2 font-normal text-green-600 dark:text-green-400">
                ({state.filesChanged} files)
              </span>
            )}
          </p>
          <a
            href={state.prUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1 inline-block text-sm text-blue-600 underline hover:text-blue-800 dark:text-blue-400"
          >
            View PR on GitHub →
          </a>
        </div>
      )}

      {state.type === "error" && (
        <div className="rounded-md bg-red-50 p-4 dark:bg-red-950">
          <p className="text-sm text-red-800 dark:text-red-200">Failed: {state.message}</p>
          <button
            onClick={() => setState({ type: "idle" })}
            className="mt-2 text-xs text-red-600 underline hover:text-red-800 dark:text-red-400"
          >
            Try again
          </button>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/dashboard/src/components/repos/SdkPrSection.tsx
git commit -m "feat(deploy): add SdkPrSection React component for SDK PR creation"
```

---

## Task 8: Wire Up to Repo Detail Page

**Files:**
- Modify: `apps/dashboard/src/app/repos/[id]/page.tsx`

- [ ] **Step 1: Read the current page file**

```bash
cat apps/dashboard/src/app/repos/[id]/page.tsx
```

Identify:
- Where `userId` and `repoId` are fetched
- Where the page returns JSX (look for the deploy/experiment section to place `SdkPrSection` after it)

- [ ] **Step 2: Add the import**

At the top of `apps/dashboard/src/app/repos/[id]/page.tsx`, add:

```typescript
import { SdkPrSection } from "@/components/repos/SdkPrSection";
```

- [ ] **Step 3: Fetch the latest SDK PR request in the server component**

Inside the async server component function body, after the existing DB queries, add:

```typescript
const { getLatestSdkPrRequest } = await import("@/lib/db/queries");
// Note: getLatestSdkPrRequest is also exported statically — you can use a static import at the top instead
const sdkPrRequest = latestAnalysis?.status === "done"
  ? await getLatestSdkPrRequest(userId, repoId)
  : null;
```

If the function already imports from `@/lib/db/queries` statically, add `getLatestSdkPrRequest` to that import instead of using dynamic import.

- [ ] **Step 4: Render `SdkPrSection` in the JSX**

Find the section at the bottom of the page (after the deploy/experiment/evolve status sections) and add:

```tsx
{latestAnalysis?.status === "done" && (
  <SdkPrSection
    repoId={repoId}
    existingPrUrl={sdkPrRequest?.pr_url ?? null}
    existingPrNumber={sdkPrRequest?.pr_number ?? null}
  />
)}
```

- [ ] **Step 5: Run TypeScript check**

```bash
cd apps/dashboard
npx tsc --noEmit
```
Expected: 0 errors. If there are type errors around `getLatestSdkPrRequest` return type or `sdkPrRequest`, check that `sdk_pr_requests` was correctly added to `schema.ts` and the import in `queries.ts` is correct.

- [ ] **Step 6: Commit**

```bash
git add "apps/dashboard/src/app/repos/[id]/page.tsx"
git commit -m "feat(deploy): add SdkPrSection to repo detail page (visible after ANALYZE done)"
```

---

## Task 9: Final Checks

- [ ] **Step 1: Run the full test suite**

```bash
cd apps/dashboard
npx jest --coverage
```
Expected: all existing tests pass + all new tests pass (≥ 18 new test cases added)

- [ ] **Step 2: Run TypeScript strict check**

```bash
cd apps/dashboard
npx tsc --noEmit
```
Expected: 0 errors

- [ ] **Step 3: Run the Python API tests (migration smoke)**

```bash
cd apps/api
pytest tests/ -x --tb=short -q
```
Expected: all tests pass (the migration itself doesn't break anything)

- [ ] **Step 4: Run lint**

```bash
cd apps/dashboard
npx eslint src/ --max-warnings 0
```
Fix any warnings, then:

```bash
cd apps/api
ruff check src/ --fix
```

- [ ] **Step 5: Final commit for any lint/type fixes**

```bash
git add -p
git commit -m "fix(deploy): lint and type fixes for Auto SDK PR feature"
```

- [ ] **Step 6: Verify the feature end-to-end (manual)**

1. Start the dev stack: `make dev`
2. Log in with GitHub OAuth
3. Connect a repo that has at least one TypeScript LLM call
4. Wait for ANALYZE to complete
5. Navigate to the repo detail page
6. Verify the "SDK Integration PR" section appears below the analysis results
7. Click "Create SDK PR"
8. Verify the loading spinner appears
9. Verify the success card with PR link appears
10. Follow the PR link — confirm the PR was actually created on GitHub with the expected files

---

## Out of Scope (Phase 2)

The following are NOT in this plan and should NOT be implemented:

- Python repo support (libcst-based transformer) — separate plan
- Actual LLM call site code transformation (wrapping calls with VerumClient) — separate plan
- PR preview step before creation — separate plan
- Private repo support (needs `repo` OAuth scope upgrade) — separate plan
- Automatic trigger after DEPLOY (currently user-triggered) — separate plan
- Duplicate PR guard (currently allows multiple PRs for same repo) — add `UNIQUE(repo_id, status)` constraint in Phase 2
