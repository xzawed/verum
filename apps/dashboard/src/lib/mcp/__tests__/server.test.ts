import { createMcpServer } from "../server";

const FAKE_DEPLOYMENT_ID = "dep-00000000-0000-0000-0000-000000000001";

function makeContext(overrides: Partial<Parameters<typeof createMcpServer>[0]> = {}) {
  return {
    deploymentId: FAKE_DEPLOYMENT_ID,
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
    const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
    const { InMemoryTransport } = require("@modelcontextprotocol/sdk/inMemory.js");

    const server = createMcpServer(makeContext());
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);

    const client = new Client({ name: "test-client", version: "0.0.1" }, { capabilities: {} });
    await client.connect(clientTransport);

    const result = await client.listTools();
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
    const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
    const { InMemoryTransport } = require("@modelcontextprotocol/sdk/inMemory.js");

    const ctx = makeContext();
    const server = createMcpServer(ctx);
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);

    const client = new Client({ name: "test-client", version: "0.0.1" }, { capabilities: {} });
    await client.connect(clientTransport);

    const result = await client.callTool({ name: "get_experiments", arguments: {} });

    expect(ctx.getExperiments).toHaveBeenCalledWith(FAKE_DEPLOYMENT_ID);
    expect(result.content[0].type).toBe("text");
    const parsed = JSON.parse((result.content[0] as { type: string; text: string }).text) as { experiments: unknown[] };
    expect(parsed.experiments).toHaveLength(1);
  });
});

describe("call_tool: get_traces", () => {
  it("calls getTraces with deploymentId and returns structured result", async () => {
    const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
    const { InMemoryTransport } = require("@modelcontextprotocol/sdk/inMemory.js");

    const ctx = makeContext();
    const server = createMcpServer(ctx);
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);

    const client = new Client({ name: "test-client", version: "0.0.1" }, { capabilities: {} });
    await client.connect(clientTransport);

    const result = await client.callTool({ name: "get_traces", arguments: {} });

    expect(ctx.getTraces).toHaveBeenCalledWith(FAKE_DEPLOYMENT_ID, 20);
    expect(result.content[0].type).toBe("text");
    const parsed = JSON.parse((result.content[0] as { type: string; text: string }).text) as { traces: unknown[] };
    expect(parsed.traces).toHaveLength(1);
  });

  it("respects limit argument and caps at 100", async () => {
    const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
    const { InMemoryTransport } = require("@modelcontextprotocol/sdk/inMemory.js");

    const ctx = makeContext();
    const server = createMcpServer(ctx);
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);

    const client = new Client({ name: "test-client", version: "0.0.1" }, { capabilities: {} });
    await client.connect(clientTransport);

    await client.callTool({ name: "get_traces", arguments: { limit: 200 } });
    expect(ctx.getTraces).toHaveBeenCalledWith(FAKE_DEPLOYMENT_ID, 100);
  });
});

describe("call_tool: get_metrics", () => {
  it("calls getMetrics with deploymentId and returns structured result", async () => {
    const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
    const { InMemoryTransport } = require("@modelcontextprotocol/sdk/inMemory.js");

    const ctx = makeContext();
    const server = createMcpServer(ctx);
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);

    const client = new Client({ name: "test-client", version: "0.0.1" }, { capabilities: {} });
    await client.connect(clientTransport);

    const result = await client.callTool({ name: "get_metrics", arguments: {} });

    expect(ctx.getMetrics).toHaveBeenCalledWith(FAKE_DEPLOYMENT_ID);
    const parsed = JSON.parse((result.content[0] as { type: string; text: string }).text) as { metrics: Record<string, unknown> };
    expect(parsed.metrics.total_traces).toBe(42);
  });
});

describe("call_tool: approve_variant", () => {
  it("calls approveVariant with deploymentId+variant and returns new_baseline", async () => {
    const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
    const { InMemoryTransport } = require("@modelcontextprotocol/sdk/inMemory.js");

    const ctx = makeContext();
    const server = createMcpServer(ctx);
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);

    const client = new Client({ name: "test-client", version: "0.0.1" }, { capabilities: {} });
    await client.connect(clientTransport);

    const result = await client.callTool({ name: "approve_variant", arguments: { variant: "v2" } });

    expect(ctx.approveVariant).toHaveBeenCalledWith(FAKE_DEPLOYMENT_ID, "v2");
    const parsed = JSON.parse((result.content[0] as { type: string; text: string }).text) as { new_baseline: string };
    expect(parsed.new_baseline).toBe("v2");
  });

  it("returns error when variant argument is missing", async () => {
    const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
    const { InMemoryTransport } = require("@modelcontextprotocol/sdk/inMemory.js");

    const ctx = makeContext();
    const server = createMcpServer(ctx);
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);

    const client = new Client({ name: "test-client", version: "0.0.1" }, { capabilities: {} });
    await client.connect(clientTransport);

    const result = await client.callTool({ name: "approve_variant", arguments: {} });

    expect(result.isError).toBe(true);
    expect(ctx.approveVariant).not.toHaveBeenCalled();
  });

  it("returns error for unknown tool", async () => {
    const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
    const { InMemoryTransport } = require("@modelcontextprotocol/sdk/inMemory.js");

    const ctx = makeContext();
    const server = createMcpServer(ctx);
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);

    const client = new Client({ name: "test-client", version: "0.0.1" }, { capabilities: {} });
    await client.connect(clientTransport);

    const result = await client.callTool({ name: "nonexistent_tool", arguments: {} });

    expect(result.isError).toBe(true);
  });
});
