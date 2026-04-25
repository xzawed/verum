jest.mock("@/auth", () => ({
  auth: jest.fn(),
}));

jest.mock("@/lib/db/client", () => ({
  db: {
    select: jest.fn(),
    execute: jest.fn(),
  },
}));

jest.mock("@/lib/db/queries", () => ({
  getLatestAnalysis: jest.fn(),
  getLatestInference: jest.fn(),
  countChunks: jest.fn(),
}));

import { GET } from "../route";
import { auth } from "@/auth";
import { db } from "@/lib/db/client";
import { getLatestAnalysis, getLatestInference, countChunks } from "@/lib/db/queries";

const mockAuth = auth as jest.MockedFunction<typeof auth>;
const mockDb = db as jest.Mocked<typeof db>;
const mockGetLatestAnalysis = getLatestAnalysis as jest.MockedFunction<typeof getLatestAnalysis>;
const mockGetLatestInference = getLatestInference as jest.MockedFunction<typeof getLatestInference>;
const mockCountChunks = countChunks as jest.MockedFunction<typeof countChunks>;

function makeParams(repoId: string): { params: Promise<{ repoId: string }> } {
  return { params: Promise.resolve({ repoId }) };
}

function makeSelectChain(rows: unknown[]) {
  const chain: Record<string, jest.Mock> = {};
  (["from", "where", "orderBy"] as const).forEach((m) => {
    chain[m] = jest.fn().mockReturnValue(chain);
  });
  chain["limit"] = jest.fn().mockResolvedValue(rows);
  return chain;
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("GET /api/v1/activation/[repoId]", () => {
  it("returns 401 when auth() returns null", async () => {
    mockAuth.mockResolvedValue(null as any);

    const res = await GET(new Request("http://localhost/api/v1/activation/repo-1"), makeParams("repo-1"));

    expect(res.status).toBe(401);
  });

  it("returns 404 when repo is not found for the user", async () => {
    mockAuth.mockResolvedValue({ user: { id: "user-1" } } as any);

    // db.select().from().where().limit() chain returns []
    const limitMock = jest.fn().mockResolvedValue([]);
    const whereMock = jest.fn().mockReturnValue({ limit: limitMock });
    const fromMock = jest.fn().mockReturnValue({ where: whereMock });
    mockDb.select.mockReturnValue({ from: fromMock } as any);

    const res = await GET(new Request("http://localhost/api/v1/activation/repo-99"), makeParams("repo-99"));

    expect(res.status).toBe(404);
  });

  it("returns 200 with ActivationResponse when all DB calls succeed (all-null sections)", async () => {
    mockAuth.mockResolvedValue({ user: { id: "user-1" } } as any);

    // Owner check returns a repo row
    const limitMock = jest.fn().mockResolvedValue([{ id: "repo-1" }]);
    const whereMock = jest.fn().mockReturnValue({ limit: limitMock });
    const fromMock = jest.fn().mockReturnValue({ where: whereMock });
    mockDb.select.mockReturnValue({ from: fromMock } as any);

    // No analysis, no inference → harvest/generation/deployment sections are null
    mockGetLatestAnalysis.mockResolvedValue(null);
    mockGetLatestInference.mockResolvedValue(null);
    mockCountChunks.mockResolvedValue(0);

    // db.execute should not be called (no inference → no generation SQL), but mock it anyway
    mockDb.execute.mockResolvedValue({ rows: [] } as any);

    const res = await GET(new Request("http://localhost/api/v1/activation/repo-1"), makeParams("repo-1"));

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toMatchObject({
      inference: null,
      analysis: null,
      harvest: null,
      generation: null,
      deployment: null,
    });
  });

  it("returns 200 with fully populated ActivationResponse (full DAG)", async () => {
    mockAuth.mockResolvedValue({ user: { id: "user-1" } } as any);

    // db.select is called 3 times: owner check → rag_configs → deployments
    mockDb.select
      .mockReturnValueOnce(makeSelectChain([{ id: "repo-1" }]) as any)
      .mockReturnValueOnce(
        makeSelectChain([
          {
            chunking_strategy: "recursive",
            chunk_size: 512,
            chunk_overlap: 50,
            top_k: 5,
            hybrid_alpha: 0.5,
          },
        ]) as any,
      )
      .mockReturnValueOnce(
        makeSelectChain([
          {
            id: "dep-1",
            traffic_split: { baseline: 0.9, variant: 0.1 },
          },
        ]) as any,
      );

    mockGetLatestAnalysis.mockResolvedValue({
      id: "analysis-1",
      call_sites: [{ id: "cs-1" }, { id: "cs-2" }],
    } as any);
    mockGetLatestInference.mockResolvedValue({
      id: "inference-1",
      domain: "tarot",
      tone: "mystical",
      summary: "A tarot reading service",
      confidence: 0.95,
    } as any);
    mockCountChunks.mockResolvedValue(42);
    mockDb.execute.mockResolvedValue({
      rows: [{ id: "gen-1", variant_count: 3, eval_count: 10 }],
    } as any);

    const res = await GET(
      new Request("http://localhost/api/v1/activation/repo-1"),
      makeParams("repo-1"),
    );

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.inference).toMatchObject({
      domain: "tarot",
      tone: "mystical",
      confidence: 0.95,
    });
    expect(body.analysis).toEqual({ call_sites_count: 2 });
    expect(body.harvest).toEqual({ chunks_count: 42 });
    expect(body.generation).toMatchObject({
      id: "gen-1",
      variants_count: 3,
      eval_pairs_count: 10,
    });
    expect(body.generation.rag_config).toMatchObject({
      chunking_strategy: "recursive",
      chunk_size: 512,
    });
    expect(body.deployment).toEqual({ id: "dep-1", traffic_split: 0.1 });
  });

  it("returns 500 when an unexpected error is thrown inside try block", async () => {
    mockAuth.mockResolvedValue({ user: { id: "user-1" } } as any);

    // Owner check succeeds
    mockDb.select.mockReturnValueOnce(makeSelectChain([{ id: "repo-1" }]) as any);

    // getLatestAnalysis throws an unexpected error
    mockGetLatestAnalysis.mockRejectedValue(new Error("DB connection lost"));

    const res = await GET(
      new Request("http://localhost/api/v1/activation/repo-1"),
      makeParams("repo-1"),
    );
    expect(res.status).toBe(500);
  });
});
