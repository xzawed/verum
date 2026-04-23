import { GET } from "../route";

jest.mock("@/auth", () => ({ auth: jest.fn() }));
jest.mock("@/lib/db/client", () => ({
  db: {
    execute: jest.fn(),
  },
}));
// drizzle-orm sql tag used in route
jest.mock("drizzle-orm", () => ({
  sql: jest.fn((...args: unknown[]) => args),
}));

import { auth } from "@/auth";
import { db } from "@/lib/db/client";

const mockAuth = auth as jest.MockedFunction<typeof auth>;
const mockDbExecute = db.execute as jest.MockedFunction<typeof db.execute>;

describe("GET /api/v1/quota", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns 401 if no session", async () => {
    mockAuth.mockResolvedValueOnce(null);
    const res = await GET();
    expect(res.status).toBe(401);
  });

  it("returns quota data for authenticated user with no existing row", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
    mockDbExecute.mockResolvedValueOnce({ rows: [] } as never);
    const res = await GET();
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toMatchObject({
      plan: "free",
      limits: { traces: 1000, chunks: 10000, repos: 3 },
      used: { traces: 0, chunks: 0, repos: 0 },
    });
    expect(body.period).toBeDefined();
  });

  it("returns quota data with actual usage when row exists", async () => {
    mockAuth.mockResolvedValueOnce({ user: { id: "user-1" } } as never);
    mockDbExecute.mockResolvedValueOnce({
      rows: [{ traces_used: 200, chunks_stored: 500, repos_connected: 1, plan: "free" }],
    } as never);
    const res = await GET();
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.used).toMatchObject({ traces: 200, chunks: 500, repos: 1 });
    expect(body.plan).toBe("free");
  });
});
