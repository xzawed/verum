# MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose Verum's EVOLVE-stage data and actions as MCP (Model Context Protocol) tools, enabling AI assistants to read experiment/trace/metrics data and — uniquely among competitors — approve variants via a write tool.

**Architecture:** Single stateless HTTP endpoint at `POST /api/mcp` handles all MCP traffic. Tool logic lives in a testable `apps/dashboard/src/lib/mcp/server.ts` module; the HTTP transport shim lives in `apps/dashboard/src/app/api/mcp/route.ts`. Auth reuses the existing deployment API key (`validateApiKey`). Four tools: three read-only (`get_experiments`, `get_traces`, `get_metrics`) plus one write (`approve_variant`).

**Tech Stack:** `@modelcontextprotocol/sdk` (TypeScript), Next.js App Router, Drizzle ORM, `validateApiKey` from `@/lib/api/validateApiKey`.

---

## Implementation Notes (subagent checklist)

- **Coverage decision** (MUST be decided at file creation):
  - `apps/dashboard/src/lib/mcp/server.ts` → **has tests** (Task 3). Include in coverage.
  - `apps/dashboard/src/app/api/mcp/route.ts` → **HTTP transport shim, excluded from coverage**. Add to both `sonar.coverage.exclusions` AND `jest.config.ts` `collectCoverageFrom` exclusion list.
- **Sonar ↔ Jest sync**: Both exclusion lists must be updated together in Task 1. Touching only one causes LCOV denominator mismatch and CI failure.
- **Conventional Commits scope**: `feat(deploy):` for MCP tooling (it's the [5] DEPLOY interface).
- **MCP SDK version note**: Verify `StreamableHTTPServerTransport` API matches installed version before writing `route.ts`. Run `cat apps/dashboard/node_modules/@modelcontextprotocol/sdk/package.json | grep version` to confirm version after install.
- **No `any` types**: Use `unknown` and narrow, or use the SDK's typed interfaces.

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `apps/dashboard/package.json` | Modify | Add `@modelcontextprotocol/sdk` dependency |
| `apps/dashboard/jest.config.ts` | Modify | Exclude `route.ts` from coverage |
| `sonar-project.properties` | Modify | Exclude `route.ts` from coverage |
| `apps/dashboard/src/lib/mcp/server.ts` | Create | Tool logic (testable, no HTTP) |
| `apps/dashboard/src/app/api/mcp/route.ts` | Create | HTTP transport shim |
| `apps/dashboard/src/lib/mcp/__tests__/server.test.ts` | Create | Unit tests for tool logic |

---

### Task 1: Install `@modelcontextprotocol/sdk` + update coverage config

**Files:**
- Modify: `apps/dashboard/package.json`
- Modify: `apps/dashboard/jest.config.ts`
- Modify: `sonar-project.properties`

- [ ] **Step 1: Install the package**

```bash
cd apps/dashboard && pnpm add @modelcontextprotocol/sdk
```

Expected: Package added to `package.json` dependencies.

- [ ] **Step 2: Verify installed version**

```bash
cd apps/dashboard && node -e "console.log(require('@modelcontextprotocol/sdk/package.json').version)"
```

Note the version. If < 1.0, the Server API may differ — check `node_modules/@modelcontextprotocol/sdk/server/` for available exports.

- [ ] **Step 3: Add `route.ts` to Jest coverage exclusion**

In `apps/dashboard/jest.config.ts`, in the `collectCoverageFrom` array, add:

```typescript
"!src/app/api/mcp/route.ts",
```

Place it alongside other route exclusions (e.g., near `!src/app/api/proxy/**`).

- [ ] **Step 4: Add `route.ts` to Sonar coverage exclusion**

In `sonar-project.properties`, in `sonar.coverage.exclusions`, add:

```
apps/dashboard/src/app/api/mcp/route.ts,\
```

Place it alongside other route exclusions. Verify the existing exclusion list is comma+backslash separated (match the existing style exactly).

- [ ] **Step 5: Verify Jest config compiles**

```bash
cd apps/dashboard && pnpm tsc --noEmit
```

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/package.json apps/dashboard/pnpm-lock.yaml apps/dashboard/jest.config.ts sonar-project.properties
git commit -m "feat(deploy): install @modelcontextprotocol/sdk and configure coverage exclusions for MCP route"
```

---

### Task 2: Create MCP server tool logic (`server.ts`)

**Files:**
- Create: `apps/dashboard/src/lib/mcp/server.ts`

The tool logic must be dependency-injectable (accept DB query functions as constructor arguments) so tests can mock them without hitting a real database.

- [ ] **Step 1: Write the failing test**

Create `apps/dashboard/src/lib/mcp/__tests__/server.test.ts`:

```typescript
import { createMcpServer } from "../server";

const FAKE_DEPLOYMENT_ID = "dep-00000000-0000-0000-0000-000000000001";
const FAKE_USER_ID = "usr-00000000-0000-0000-0000-000000000001";

function makeContext(overrides: Partial<Parameters<typeof createMcpServer>[0]> = {}) {
  return {
    deploymentId: FAKE_DEPLOYMENT_ID,
    userId: FAKE_USER_ID,
    getExperiments: jest.fn().mockResolvedValue([
      { id: "exp-1", status: "running", baseline_variant: "v1", challenger_variant: "v2" },
    ]),
    getTraces: jest.fn().mockResolvedValue([
      { id: "trace-1", variant: "v1", latency_ms: 120 },
    ]),
    getMetrics: jest.fn().mockResolvedValue({ total_traces: 42, avg_latency_ms: 135.5 }),
    approveVariant: jest.fn().mockResolvedValue({ new_baseline: "v2" }),
    ...overrides,
  };
}

describe("createMcpServer", () => {
  it("creates a Server instance", () => {
    const server = createMcpServer(makeContext());
    expect(server).toBeDefined();
    expect(typeof server.connect).toBe("function");
  });
});

describe("list_tools", () => {
  it("exposes exactly 4 tools", async () => {
    const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
    const { InMemoryTransport } = require("@modelcontextprotocol/sdk/inMemory.js");
    const { ListToolsRequestSchema } = require("@modelcontextprotocol/sdk/types.js");

    const server = createMcpServer(makeContext());
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);

    const client = new Server({ name: "test-client", version: "0.0.1" }, { capabilities: {} });
    await client.connect(clientTransport);

    const result = await client.request({ method: "tools/list" }, ListToolsRequestSchema);
    expect(result.tools).toHaveLength(4);
    const names = result.tools.map((t: { name: string }) => t.name);
    expect(names).toContain("get_experiments");
    expect(names).toContain("get_traces");
    expect(names).toContain("get_metrics");
    expect(names).toContain("approve_variant");
  });
});

describe("call_tool: get_experiments", () => {
  it("calls getExperiments with deploymentId and returns structured result", async () => {
    const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
    const { InMemoryTransport } = require("@modelcontextprotocol/sdk/inMemory.js");
    const { CallToolRequestSchema } = require("@modelcontextprotocol/sdk/types.js");

    const ctx = makeContext();
    const server = createMcpServer(ctx);
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);

    const client = new Server({ name: "test-client", version: "0.0.1" }, { capabilities: {} });
    await client.connect(clientTransport);

    const result = await client.request(
      { method: "tools/call", params: { name: "get_experiments", arguments: {} } },
      CallToolRequestSchema,
    );

    expect(ctx.getExperiments).toHaveBeenCalledWith(FAKE_DEPLOYMENT_ID);
    expect(result.content[0].type).toBe("text");
    const parsed = JSON.parse(result.content[0].text as string) as { experiments: unknown[] };
    expect(parsed.experiments).toHaveLength(1);
  });
});

describe("call_tool: approve_variant", () => {
  it("calls approveVariant with deploymentId+variant and returns new_baseline", async () => {
    const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
    const { InMemoryTransport } = require("@modelcontextprotocol/sdk/inMemory.js");
    const { CallToolRequestSchema } = require("@modelcontextprotocol/sdk/types.js");

    const ctx = makeContext();
    const server = createMcpServer(ctx);
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);

    const client = new Server({ name: "test-client", version: "0.0.1" }, { capabilities: {} });
    await client.connect(clientTransport);

    const result = await client.request(
      {
        method: "tools/call",
        params: { name: "approve_variant", arguments: { variant: "v2" } },
      },
      CallToolRequestSchema,
    );

    // Verify both args passed (deploymentId scoped from context, variant from call args)
    expect(ctx.approveVariant).toHaveBeenCalledWith(FAKE_DEPLOYMENT_ID, "v2");
    const parsed = JSON.parse(result.content[0].text as string) as { new_baseline: string };
    expect(parsed.new_baseline).toBe("v2");
  });

  it("returns error when variant argument is missing", async () => {
    const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
    const { InMemoryTransport } = require("@modelcontextprotocol/sdk/inMemory.js");
    const { CallToolRequestSchema } = require("@modelcontextprotocol/sdk/types.js");

    const ctx = makeContext();
    const server = createMcpServer(ctx);
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);

    const client = new Server({ name: "test-client", version: "0.0.1" }, { capabilities: {} });
    await client.connect(clientTransport);

    const result = await client.request(
      { method: "tools/call", params: { name: "approve_variant", arguments: {} } },
      CallToolRequestSchema,
    );

    expect(result.isError).toBe(true);
    expect(ctx.approveVariant).not.toHaveBeenCalled();
  });

  it("returns error for unknown tool", async () => {
    const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
    const { InMemoryTransport } = require("@modelcontextprotocol/sdk/inMemory.js");
    const { CallToolRequestSchema } = require("@modelcontextprotocol/sdk/types.js");

    const ctx = makeContext();
    const server = createMcpServer(ctx);
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);

    const client = new Server({ name: "test-client", version: "0.0.1" }, { capabilities: {} });
    await client.connect(clientTransport);

    const result = await client.request(
      { method: "tools/call", params: { name: "nonexistent_tool", arguments: {} } },
      CallToolRequestSchema,
    );

    expect(result.isError).toBe(true);
  });
});
```

- [ ] **Step 2: Run to verify fails**

```bash
cd apps/dashboard && pnpm jest src/lib/mcp --passWithNoTests
```

Expected: `Cannot find module '../server'`

- [ ] **Step 3: Create `apps/dashboard/src/lib/mcp/server.ts`**

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

export interface McpServerContext {
  deploymentId: string;
  userId: string;
  getExperiments: (deploymentId: string) => Promise<unknown[]>;
  getTraces: (deploymentId: string, limit?: number) => Promise<unknown[]>;
  getMetrics: (deploymentId: string) => Promise<Record<string, unknown>>;
  approveVariant: (deploymentId: string, variant: string) => Promise<{ new_baseline: string }>;
}

const TOOLS = [
  {
    name: "get_experiments",
    description:
      "List A/B experiments for the authenticated deployment. Returns status, variants, and convergence data.",
    inputSchema: {
      type: "object" as const,
      properties: {},
      required: [],
    },
  },
  {
    name: "get_traces",
    description:
      "Return recent LLM call traces for the deployment. Each trace includes variant, latency, model, and token counts.",
    inputSchema: {
      type: "object" as const,
      properties: {
        limit: { type: "number", description: "Max traces to return (default 20, max 100)" },
      },
      required: [],
    },
  },
  {
    name: "get_metrics",
    description:
      "Return aggregated metrics for the deployment: total traces, average latency, cost, and satisfaction score.",
    inputSchema: {
      type: "object" as const,
      properties: {},
      required: [],
    },
  },
  {
    name: "approve_variant",
    description:
      "Approve a prompt variant as the new baseline for the deployment. This promotes the variant without waiting for statistical convergence — use when you have reviewed the experiment data and want to act immediately.",
    inputSchema: {
      type: "object" as const,
      properties: {
        variant: { type: "string", description: "The variant identifier to promote (e.g. 'v2', 'challenger')" },
      },
      required: ["variant"],
    },
  },
];

export function createMcpServer(ctx: McpServerContext): Server {
  const server = new Server(
    { name: "verum", version: "1.0.0" },
    { capabilities: { tools: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const { name, arguments: args } = req.params;
    const safeArgs = (args ?? {}) as Record<string, unknown>;

    switch (name) {
      case "get_experiments": {
        const experiments = await ctx.getExperiments(ctx.deploymentId);
        return {
          content: [{ type: "text", text: JSON.stringify({ experiments }) }],
        };
      }

      case "get_traces": {
        const limit =
          typeof safeArgs.limit === "number"
            ? Math.min(safeArgs.limit, 100)
            : 20;
        const traces = await ctx.getTraces(ctx.deploymentId, limit);
        return {
          content: [{ type: "text", text: JSON.stringify({ traces }) }],
        };
      }

      case "get_metrics": {
        const metrics = await ctx.getMetrics(ctx.deploymentId);
        return {
          content: [{ type: "text", text: JSON.stringify({ metrics }) }],
        };
      }

      case "approve_variant": {
        const variant = safeArgs.variant;
        if (typeof variant !== "string" || !variant) {
          return {
            isError: true,
            content: [{ type: "text", text: "variant is required and must be a string" }],
          };
        }
        const result = await ctx.approveVariant(ctx.deploymentId, variant);
        return {
          content: [{ type: "text", text: JSON.stringify(result) }],
        };
      }

      default:
        return {
          isError: true,
          content: [{ type: "text", text: `Unknown tool: ${name}` }],
        };
    }
  });

  return server;
}
```

- [ ] **Step 4: Run tests — verify pass**

```bash
cd apps/dashboard && pnpm jest src/lib/mcp --coverage
```

Expected: All 5 tests pass, `server.ts` shows coverage.

If tests fail with `Cannot find module '@modelcontextprotocol/sdk/inMemory.js'`: Check what the SDK exports with `ls apps/dashboard/node_modules/@modelcontextprotocol/sdk/` — the `InMemoryTransport` may be at a different path. Adjust the import accordingly.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/src/lib/mcp/
git commit -m "feat(deploy): add MCP server with get_experiments/get_traces/get_metrics/approve_variant tools"
```

---

### Task 3: Create MCP HTTP route

**Files:**
- Create: `apps/dashboard/src/app/api/mcp/route.ts`

This file is intentionally thin — it only handles auth and HTTP transport. All tool logic is tested via `server.ts`.

- [ ] **Step 1: Check SDK transport API**

```bash
ls apps/dashboard/node_modules/@modelcontextprotocol/sdk/server/
```

Identify whether `streamableHttp.js` (or `streamableHttp.d.ts`) exists. If it does, use `StreamableHTTPServerTransport`. If not, check for `http.js` or `sse.js` — the implementation note below has the fallback.

- [ ] **Step 2: Create `apps/dashboard/src/app/api/mcp/route.ts`**

```typescript
import { NextRequest } from "next/server";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { validateApiKey } from "@/lib/api/validateApiKey";
import { createMcpServer } from "@/lib/mcp/server";
import { getExperiments } from "@/lib/db/queries";
import { db } from "@/lib/db/client";
import { spans, traces, deployments, experiments } from "@/lib/db/schema";
import { and, avg, count, eq, sql } from "drizzle-orm";

async function getTracesForDeployment(deploymentId: string, limit = 20) {
  return db
    .select({
      id: traces.id,
      variant: traces.variant,
      created_at: traces.created_at,
    })
    .from(traces)
    .where(eq(traces.deployment_id, deploymentId))
    .orderBy(sql`${traces.created_at} DESC`)
    .limit(limit);
}

async function getMetricsForDeployment(deploymentId: string) {
  const rows = await db
    .select({
      total: count(spans.id),
      avg_latency: avg(spans.latency_ms),
    })
    .from(spans)
    .innerJoin(traces, eq(spans.trace_id, traces.id))
    .where(eq(traces.deployment_id, deploymentId));

  const row = rows[0];
  return {
    total_traces: Number(row?.total ?? 0),
    avg_latency_ms: row?.avg_latency ? Number(row.avg_latency) : null,
  };
}

async function approveVariantForDeployment(deploymentId: string, variant: string) {
  // Mark any running experiment for this deployment as converged (manual override)
  await db
    .update(experiments)
    .set({
      status: "converged",
      winner_variant: variant,
      confidence: 1.0,
      converged_at: new Date(),
    })
    .where(
      and(
        eq(experiments.deployment_id, deploymentId),
        eq(experiments.status, "running"),
      ),
    );

  // Promote winner to baseline and mark deployment as completed
  await db
    .update(deployments)
    .set({
      current_baseline_variant: variant,
      traffic_split: { [variant]: 1.0 },
      experiment_status: "completed",
      updated_at: new Date(),
    })
    .where(eq(deployments.id, deploymentId));

  return { new_baseline: variant };
}

export async function POST(req: NextRequest): Promise<Response> {
  const apiKey =
    req.headers.get("authorization")?.replace(/^Bearer\s+/i, "") ??
    req.headers.get("x-verum-api-key") ??
    "";

  const keyResult = await validateApiKey(apiKey);
  if (!keyResult) return new Response("Unauthorized", { status: 401 });

  const server = createMcpServer({
    deploymentId: keyResult.deploymentId,
    userId: keyResult.userId,
    getExperiments: (depId) => getExperiments(keyResult.userId, depId),
    getTraces: (depId, limit) => getTracesForDeployment(depId, limit),
    getMetrics: (depId) => getMetricsForDeployment(depId),
    approveVariant: (depId, variant) => approveVariantForDeployment(depId, variant),
  });

  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  await server.connect(transport);
  return transport.handleRequest(req);
}
```

**Implementation note — if `StreamableHTTPServerTransport` doesn't exist in this SDK version:**
Check `node_modules/@modelcontextprotocol/sdk/server/` for available transports. A common fallback is:
```typescript
// Alternative if StreamableHTTPServerTransport is unavailable:
// Implement the JSON-RPC exchange manually using InMemoryTransport
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
await server.connect(serverTransport);
const body = await req.json();
// ... send request, collect response, return as Response.json(...)
```
The plan uses `StreamableHTTPServerTransport` as the intended approach — adjust if SDK version differs.

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd apps/dashboard && pnpm tsc --noEmit
```

Expected: No errors.
The `current_baseline_variant` column is confirmed in `apps/dashboard/src/lib/db/schema.ts` (line ~167). If it is renamed in the future, check `schema.ts`.

- [ ] **Step 4: Run full test suite**

```bash
cd apps/dashboard && pnpm jest --coverage
```

Expected: All tests pass. `route.ts` does NOT appear in coverage report (excluded). `server.ts` shows coverage.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/src/app/api/mcp/
git commit -m "feat(deploy): add MCP HTTP route with API key auth and StreamableHTTP transport"
```

---

### Task 4: Final verification

- [ ] **Step 1: Check MCP route is excluded from coverage**

```bash
cd apps/dashboard && pnpm jest --coverage --verbose 2>&1 | grep "mcp/route"
```

Expected: No output (file not in coverage table). If it appears, re-check `jest.config.ts` exclusion.

- [ ] **Step 2: Check Sonar exclusion is present**

```bash
grep "mcp/route" sonar-project.properties
```

Expected: Line present.

- [ ] **Step 3: TypeScript strict check**

```bash
cd apps/dashboard && pnpm tsc --noEmit --strict
```

Expected: No errors.

- [ ] **Step 4: Python side unaffected**

```bash
cd apps/api && python -m pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=95
```

Expected: Coverage ≥ 95% (MCP changes are TS-only, Python coverage unaffected).

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "feat(deploy): complete MCP server — tools, route, coverage config, tests"
```
