import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

export interface McpServerContext {
  deploymentId: string;
  getExperiments: (deploymentId: string) => Promise<unknown[]>;
  getTraces: (deploymentId: string, limit?: number) => Promise<unknown[]>;
  getMetrics: (deploymentId: string) => Promise<Record<string, unknown>>;
  approveVariant: (deploymentId: string, variant: string) => Promise<Record<string, unknown>>;
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
