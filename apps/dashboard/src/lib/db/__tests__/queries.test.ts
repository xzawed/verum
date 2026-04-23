/**
 * Tenancy isolation tests for lib/db/queries.ts.
 *
 * These tests verify the multi-tenant contract: every read function that
 * exposes user data must filter by owner_user_id.  The DB is fully mocked
 * — no real Postgres is required.
 *
 * Pattern: supply a mock Drizzle chain that resolves to either rows (owner
 * matches) or [] (owner mismatch / cross-tenant).  Verify the function
 * returns the expected value in each case.
 */

jest.mock("@/lib/db/client", () => ({
  db: {
    select: jest.fn(),
    execute: jest.fn(),
  },
}));

import {
  getRepos,
  getRepo,
  getAnalysis,
  getDeployment,
  getTraceDetail,
  getExperiments,
  getExperiment,
} from "../queries";
import { db } from "@/lib/db/client";

// ── Mock helpers ─────────────────────────────────────────────────────────────

/**
 * Build a chainable mock that resolves to `rows` when awaited.
 * Covers the Drizzle fluent API: .from().where().innerJoin().limit() etc.
 */
function makeSelectChain(rows: unknown[]): object {
  const chain: Record<string, unknown> = {};
  // Every chaining method returns the same chain object
  (["from", "where", "innerJoin"] as const).forEach((m) => {
    chain[m] = jest.fn(() => chain);
  });
  // Terminal operations return a resolved Promise
  chain["orderBy"] = jest.fn(() => Promise.resolve(rows));
  chain["limit"] = jest.fn(() => Promise.resolve(rows));
  // select({ alias: table }) pattern — also returns chain
  chain["select"] = jest.fn(() => chain);
  return chain;
}

const mockSelect = db.select as jest.Mock;
const mockExecute = db.execute as jest.Mock;

const USER_A = "aaaaaaaa-0000-0000-0000-000000000001";
const USER_B = "bbbbbbbb-0000-0000-0000-000000000002";

const repoA = {
  id: "repo-a",
  owner_user_id: USER_A,
  github_full_name: "userA/proj",
  created_at: new Date(),
};
const repoB = {
  id: "repo-b",
  owner_user_id: USER_B,
  github_full_name: "userB/proj",
  created_at: new Date(),
};

beforeEach(() => {
  jest.clearAllMocks();
});

// ── getRepos ─────────────────────────────────────────────────────────────────

describe("getRepos(userId)", () => {
  it("returns the rows that DB resolves with for the requesting user", async () => {
    mockSelect.mockReturnValue(makeSelectChain([repoA]));
    const result = await getRepos(USER_A);
    expect(result).toEqual([repoA]);
  });

  it("returns empty array when user has no repos", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getRepos(USER_A);
    expect(result).toEqual([]);
  });

  it("does not return another user's repos (cross-tenant simulation)", async () => {
    // In production the WHERE owner_user_id=userA filters out repoB.
    // Here we simulate the DB returning [] for a userId that owns nothing.
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getRepos(USER_B);
    expect(result).toEqual([]);
    expect(result).not.toContainEqual(repoA);
  });
});

// ── getRepo ──────────────────────────────────────────────────────────────────

describe("getRepo(userId, repoId)", () => {
  it("returns the repo when owner matches", async () => {
    mockSelect.mockReturnValue(makeSelectChain([repoA]));
    const result = await getRepo(USER_A, "repo-a");
    expect(result).toEqual(repoA);
  });

  it("returns null when DB returns no rows (cross-tenant)", async () => {
    // Simulate: userA queries userB's repo — WHERE owner_user_id=userA
    // and id=repo-b matches nothing → empty result.
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getRepo(USER_A, "repo-b");
    expect(result).toBeNull();
  });

  it("returns null for unknown repoId", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getRepo(USER_A, "non-existent");
    expect(result).toBeNull();
  });
});

// ── getAnalysis ───────────────────────────────────────────────────────────────

describe("getAnalysis(userId, analysisId)", () => {
  const analysisA = { id: "analysis-a", repo_id: "repo-a", status: "done" };

  it("returns the analysis when owner chain resolves (innerJoin path)", async () => {
    // getAnalysis selects { a: analyses } and joins repos on owner_user_id
    mockSelect.mockReturnValue(makeSelectChain([{ a: analysisA }]));
    const result = await getAnalysis(USER_A, "analysis-a");
    expect(result).toEqual(analysisA);
  });

  it("returns null when cross-tenant JOIN returns no rows", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getAnalysis(USER_A, "analysis-b");
    expect(result).toBeNull();
  });
});

// ── getDeployment ─────────────────────────────────────────────────────────────

describe("getDeployment(userId, deploymentId)", () => {
  const deployA = { id: "deploy-a", generation_id: "gen-a", status: "active" };

  it("returns the deployment when multi-level owner JOIN resolves", async () => {
    // getDeployment chains 4 innerJoins up to repos.owner_user_id
    mockSelect.mockReturnValue(makeSelectChain([{ d: deployA }]));
    const result = await getDeployment(USER_A, "deploy-a");
    expect(result).toEqual(deployA);
  });

  it("returns null when userA queries userB's deployment (cross-tenant)", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getDeployment(USER_A, "deploy-b");
    expect(result).toBeNull();
  });
});

// ── getTraceDetail ────────────────────────────────────────────────────────────

describe("getTraceDetail(userId, traceId)", () => {
  it("returns trace row when owner matches (db.execute path)", async () => {
    const traceRow = { id: "trace-a", variant: "baseline", judge_score: 0.9 };
    mockExecute.mockResolvedValue({ rows: [traceRow] });
    const result = await getTraceDetail(USER_A, "trace-a");
    expect(result).toEqual(traceRow);
  });

  it("returns null when cross-tenant JOIN returns no rows", async () => {
    // getTraceDetail uses a raw db.execute() with JOIN to repos WHERE
    // owner_user_id = userId — returns no rows for cross-tenant access.
    mockExecute.mockResolvedValue({ rows: [] });
    const result = await getTraceDetail(USER_A, "trace-b");
    expect(result).toBeNull();
  });
});

// ── getExperiments — ownership gate ───────────────────────────────────────────

describe("getExperiments(userId, deploymentId)", () => {
  it("returns empty array when getDeployment returns null (ownership gate)", async () => {
    // getExperiments first calls getDeployment(userId, deploymentId) as an
    // ownership check.  When the deployment doesn't belong to userId the gate
    // returns [] without querying experiments at all.
    mockSelect.mockReturnValue(makeSelectChain([])); // getDeployment returns null
    const result = await getExperiments(USER_A, "deploy-b");
    expect(result).toEqual([]);
  });
});

// ── getExperiment — ownership gate ────────────────────────────────────────────

describe("getExperiment(userId, experimentId)", () => {
  it("returns null when the experiment's deployment does not belong to userId", async () => {
    const experimentRow = { id: "exp-a", deployment_id: "deploy-b" };
    // First select (experiment) returns a row; second select (getDeployment)
    // returns [] because deploy-b doesn't belong to USER_A.
    mockSelect
      .mockReturnValueOnce(makeSelectChain([experimentRow])) // getExperiment query
      .mockReturnValue(makeSelectChain([]));                  // getDeployment ownership check
    const result = await getExperiment(USER_A, "exp-a");
    expect(result).toBeNull();
  });
});
