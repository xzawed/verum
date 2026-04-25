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
});
