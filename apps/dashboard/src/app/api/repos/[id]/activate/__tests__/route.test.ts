jest.mock("@/auth", () => ({
  auth: jest.fn(),
}));

jest.mock("@/lib/db/client", () => ({
  db: {
    select: jest.fn(),
    insert: jest.fn(),
  },
}));

import { POST } from "../route";
import { NextRequest } from "next/server";
import { auth } from "@/auth";
import { db } from "@/lib/db/client";

const mockAuth = auth as jest.MockedFunction<typeof auth>;
const mockDb = db as jest.Mocked<typeof db>;

function makeRequest(url = "http://localhost/api/repos/repo-1/activate") {
  return new NextRequest(url, { method: "POST" });
}

function makeParams(id = "repo-1") {
  return { params: Promise.resolve({ id }) };
}

/** Chainable select mock that resolves to rows at .limit() */
function makeSelectChain(rows: unknown[]) {
  const chain: Record<string, jest.Mock> = {};
  (["from", "where", "innerJoin", "orderBy"] as const).forEach((m) => {
    chain[m] = jest.fn().mockReturnValue(chain);
  });
  chain.limit = jest.fn().mockResolvedValue(rows);
  return chain;
}

/** Insert mock that resolves returning rows */
function makeInsertChain(returning: unknown[]) {
  const chain: Record<string, jest.Mock> = {};
  chain.values = jest.fn().mockReturnValue(chain);
  chain.returning = jest.fn().mockResolvedValue(returning);
  // .values() alone (no .returning()) resolves undefined
  chain.values.mockReturnValue({
    ...chain,
    returning: chain.returning,
    then: undefined,
  });
  // Make the chain thenable for insert without returning()
  const plainInsert = { values: jest.fn().mockResolvedValue(undefined) };
  return { chain, plainInsert };
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("POST /api/repos/[id]/activate", () => {
  it("returns 401 when unauthenticated", async () => {
    mockAuth.mockResolvedValue(null as never);
    const res = await POST(makeRequest(), makeParams());
    expect(res.status).toBe(401);
  });

  it("returns 404 when repo not owned by user", async () => {
    mockAuth.mockResolvedValue({ user: { id: "user-1" } } as never);
    // owner check returns []
    mockDb.select.mockReturnValue(makeSelectChain([]) as never);
    const res = await POST(makeRequest(), makeParams());
    expect(res.status).toBe(404);
  });

  it("returns 422 when no ready generation exists", async () => {
    mockAuth.mockResolvedValue({ user: { id: "user-1" } } as never);

    let callCount = 0;
    mockDb.select.mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        // owner check → found
        return makeSelectChain([{ id: "repo-1" }]) as never;
      }
      // generation check → not found
      return makeSelectChain([]) as never;
    });

    const res = await POST(makeRequest(), makeParams());
    expect(res.status).toBe(422);
  });

  it("returns 409 when deployment already exists for this generation", async () => {
    mockAuth.mockResolvedValue({ user: { id: "user-1" } } as never);

    let callCount = 0;
    mockDb.select.mockImplementation(() => {
      callCount++;
      if (callCount === 1) return makeSelectChain([{ id: "repo-1" }]) as never;
      if (callCount === 2) return makeSelectChain([{ id: "gen-1" }]) as never;
      // existing deployment check → found
      return makeSelectChain([{ id: "dep-existing" }]) as never;
    });

    const res = await POST(makeRequest(), makeParams());
    expect(res.status).toBe(409);
    const body = await res.json() as Record<string, unknown>;
    expect(body.deployment_id).toBe("dep-existing");
  });

  it("returns 201 with deployment_id and api_key on success", async () => {
    mockAuth.mockResolvedValue({ user: { id: "user-1" } } as never);

    let callCount = 0;
    mockDb.select.mockImplementation(() => {
      callCount++;
      if (callCount === 1) return makeSelectChain([{ id: "repo-1" }]) as never;
      if (callCount === 2) return makeSelectChain([{ id: "gen-1" }]) as never;
      // no existing deployment
      return makeSelectChain([]) as never;
    });

    // insert deployment returns dep row
    let insertCount = 0;
    mockDb.insert.mockImplementation(() => {
      insertCount++;
      if (insertCount === 1) {
        // deployments insert with .returning()
        const chain = {
          values: jest.fn().mockReturnValue({
            returning: jest.fn().mockResolvedValue([{ id: "dep-new" }]),
          }),
        };
        return chain as never;
      }
      // experiments insert — no returning
      return { values: jest.fn().mockResolvedValue(undefined) } as never;
    });

    const res = await POST(makeRequest(), makeParams());
    expect(res.status).toBe(201);
    const body = await res.json() as Record<string, unknown>;
    expect(body.deployment_id).toBe("dep-new");
    expect(typeof body.api_key).toBe("string");
    expect(String(body.api_key)).toMatch(/^vk_[0-9a-f]{64}$/);
    expect(body.verum_api_url).toBe("http://localhost");
  });

  it("api_key differs between invocations (randomness)", async () => {
    mockAuth.mockResolvedValue({ user: { id: "user-1" } } as never);

    const makeSelects = () => {
      let c = 0;
      return () => {
        c++;
        if (c === 1) return makeSelectChain([{ id: "repo-1" }]) as never;
        if (c === 2) return makeSelectChain([{ id: "gen-1" }]) as never;
        return makeSelectChain([]) as never;
      };
    };

    const makeInserts = () => {
      let i = 0;
      return () => {
        i++;
        if (i === 1)
          return {
            values: jest.fn().mockReturnValue({
              returning: jest.fn().mockResolvedValue([{ id: "dep-new" }]),
            }),
          } as never;
        return { values: jest.fn().mockResolvedValue(undefined) } as never;
      };
    };

    mockDb.select.mockImplementation(makeSelects());
    mockDb.insert.mockImplementation(makeInserts());
    const res1 = await POST(makeRequest(), makeParams());
    const body1 = await res1.json() as Record<string, unknown>;

    mockDb.select.mockImplementation(makeSelects());
    mockDb.insert.mockImplementation(makeInserts());
    const res2 = await POST(makeRequest(), makeParams());
    const body2 = await res2.json() as Record<string, unknown>;

    expect(body1.api_key).not.toBe(body2.api_key);
  });
});
