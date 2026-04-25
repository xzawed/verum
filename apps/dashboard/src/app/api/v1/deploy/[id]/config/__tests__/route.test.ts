jest.mock("@/lib/api/validateApiKey", () => ({
  validateApiKey: jest.fn(),
}));
jest.mock("@/lib/db/client", () => ({
  db: {
    select: jest.fn().mockReturnThis(),
    from: jest.fn().mockReturnThis(),
    where: jest.fn().mockReturnThis(),
    orderBy: jest.fn().mockReturnThis(),
    limit: jest.fn().mockReturnThis(),
  },
}));
jest.mock("@/lib/db/schema", () => ({
  deployments: {},
  prompt_variants: {},
  rag_configs: {},
}));
jest.mock("@/lib/db/queries", () => ({
  getVariantPrompt: jest.fn(),
}));
jest.mock("drizzle-orm", () => ({
  eq: jest.fn(),
}));

import { GET } from "../route";
import { validateApiKey } from "@/lib/api/validateApiKey";
import { getVariantPrompt } from "@/lib/db/queries";
import { db } from "@/lib/db/client";

const mockValidateApiKey = validateApiKey as jest.MockedFunction<typeof validateApiKey>;
const mockGetVariantPrompt = getVariantPrompt as jest.MockedFunction<typeof getVariantPrompt>;
const mockDb = db as jest.Mocked<typeof db>;

function makeRequest(headers: Record<string, string> = {}): Request {
  return new Request("http://localhost/api/v1/deploy/dep-1/config", {
    headers,
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  // Reset the db chain mock to return empty by default
  (mockDb.select as jest.Mock).mockReturnValue(mockDb);
  (mockDb.from as jest.Mock).mockReturnValue(mockDb);
  (mockDb.where as jest.Mock).mockReturnValue(mockDb);
  (mockDb.limit as jest.Mock).mockResolvedValue([]);
});

describe("GET /api/v1/deploy/[id]/config", () => {
  it("returns 401 when no API key is provided", async () => {
    mockValidateApiKey.mockResolvedValueOnce(null);
    const req = makeRequest();
    const res = await GET(req, { params: Promise.resolve({ id: "dep-1" }) });
    expect(res.status).toBe(401);
  });

  it("returns 403 when API key belongs to a different deployment", async () => {
    mockValidateApiKey.mockResolvedValueOnce({
      deploymentId: "dep-OTHER",
      userId: "user-1",
    });
    const req = makeRequest({ "x-verum-api-key": "a".repeat(41) });
    const res = await GET(req, { params: Promise.resolve({ id: "dep-1" }) });
    expect(res.status).toBe(403);
  });

  it("returns 200 with config when deployment is found", async () => {
    mockValidateApiKey.mockResolvedValueOnce({
      deploymentId: "dep-1",
      userId: "user-1",
    });
    (mockDb.limit as jest.Mock)
      .mockResolvedValueOnce([
        {
          id: "dep-1",
          status: "active",
          traffic_split: { baseline: 0.8, variant: 0.2 },
          generation_id: "gen-1",
        },
      ])
      .mockResolvedValueOnce([
        {
          id: "var-1",
          variant_type: "chain_of_thought",
          content: "You are a helpful assistant.",
        },
        {
          id: "var-2",
          variant_type: "few_shot",
          content: "Here are some examples...",
        },
      ])
      .mockResolvedValueOnce([
        {
          chunking_strategy: "recursive",
          chunk_size: 512,
          chunk_overlap: 50,
          top_k: 5,
          hybrid_alpha: 0.7,
        },
      ]);
    mockGetVariantPrompt.mockResolvedValueOnce("You are a helpful assistant." as never);

    const req = makeRequest({ "x-verum-api-key": "a".repeat(41) });
    const res = await GET(req, { params: Promise.resolve({ id: "dep-1" }) });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toMatchObject({
      deployment_id: "dep-1",
      status: "active",
      traffic_split: 0.2,
      variant_prompt: "You are a helpful assistant.",
    });
    expect(body.prompt_variants).toHaveLength(2);
    expect(body.prompt_variants[0]).toMatchObject({
      id: "var-1",
      variant_type: "chain_of_thought",
      content: "You are a helpful assistant.",
    });
    expect(body.rag_config).toMatchObject({
      chunking_strategy: "recursive",
      chunk_size: 512,
      chunk_overlap: 50,
      top_k: 5,
      hybrid_alpha: 0.7,
    });
  });

  it("returns 200 with empty prompt_variants and null rag_config when none exist", async () => {
    mockValidateApiKey.mockResolvedValueOnce({
      deploymentId: "dep-1",
      userId: "user-1",
    });
    (mockDb.limit as jest.Mock)
      .mockResolvedValueOnce([
        {
          id: "dep-1",
          status: "active",
          traffic_split: { baseline: 0.8, variant: 0.2 },
          generation_id: "gen-1",
        },
      ])
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([]);
    mockGetVariantPrompt.mockResolvedValueOnce(null);

    const req = makeRequest({ "x-verum-api-key": "a".repeat(41) });
    const res = await GET(req, { params: Promise.resolve({ id: "dep-1" }) });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.prompt_variants).toEqual([]);
    expect(body.rag_config).toBeNull();
  });
});
