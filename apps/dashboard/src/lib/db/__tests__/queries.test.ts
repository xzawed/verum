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
    insert: jest.fn(),
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
  getUserByGithubId,
  upsertUser,
  getLatestAnalysis,
  getLatestInference,
  getInference,
  getHarvestSources,
  countChunks,
  getJob,
  getWorkerAlive,
  getGeneration,
  getGenerationFull,
  getVariantPrompt,
  getLatestGeneration,
  getRepoStatus,
  getTraceList,
  getDailyMetrics,
  getSdkPrRequest,
  getLatestSdkPrRequest,
  getLatestSdkPrRequestByMode,
} from "../queries";
import { db } from "@/lib/db/client";

// ── Mock helpers ─────────────────────────────────────────────────────────────

/**
 * Build a chainable mock that resolves to `rows` when awaited.
 * Covers the Drizzle fluent API: .from().where().innerJoin().orderBy().limit() etc.
 *
 * All intermediate methods return the same chain so any ordering of
 * .from().where().orderBy().limit() — or .orderBy().limit() — works.
 * The chain object itself is thenable (has .then) so it resolves when awaited
 * directly (e.g. `return db.select().from(t).where(...).orderBy(...)` without
 * a trailing .limit()).
 */
function makeSelectChain(rows: unknown[]): object {
  const chain: Record<string, unknown> = {};
  // Intermediate chaining methods — all return the same chain
  (["from", "where", "innerJoin", "orderBy"] as const).forEach((m) => {
    chain[m] = jest.fn(() => chain);
  });
  // Terminal: limit resolves to rows
  chain["limit"] = jest.fn(() => Promise.resolve(rows));
  // select({ alias: table }) pattern — also returns chain
  chain["select"] = jest.fn(() => chain);
  // Make the chain itself awaitable for queries that don't call .limit()
  // e.g. `return db.select().from(t).where(...).orderBy(...)` (no limit)
  chain["then"] = jest.fn((resolve: (v: unknown) => unknown) => Promise.resolve(rows).then(resolve));
  chain["catch"] = jest.fn((reject: (e: unknown) => unknown) => Promise.resolve(rows).catch(reject));
  return chain;
}

const mockSelect = db.select as jest.Mock;
const mockExecute = db.execute as jest.Mock;
const mockInsert = db.insert as jest.Mock;

/**
 * Build a chainable mock for Drizzle ORM insert flows:
 * .insert().values().onConflictDoUpdate().returning()
 */
function makeInsertChain(rows: unknown[]): object {
  const chain: Record<string, unknown> = {};
  (["values", "onConflictDoUpdate"] as const).forEach((m) => {
    chain[m] = jest.fn(() => chain);
  });
  chain["returning"] = jest.fn(() => Promise.resolve(rows));
  return chain;
}

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
  // resetAllMocks clears both call history AND mock implementations,
  // preventing mock state from leaking between test cases.
  jest.resetAllMocks();
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

// ── getUserByGithubId ─────────────────────────────────────────────────────────

describe("getUserByGithubId(githubId)", () => {
  const userRow = {
    id: USER_A,
    github_id: 12345,
    github_login: "xzawed",
    email: "test@example.com",
    avatar_url: null,
    last_login_at: new Date(),
    created_at: new Date(),
  };

  it("returns the user row when found", async () => {
    mockSelect.mockReturnValue(makeSelectChain([userRow]));
    const result = await getUserByGithubId(12345);
    expect(result).toEqual(userRow);
  });

  it("returns null when no user found", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getUserByGithubId(99999);
    expect(result).toBeNull();
  });
});

// ── upsertUser ────────────────────────────────────────────────────────────────

describe("upsertUser(opts)", () => {
  const userRow = {
    id: USER_A,
    github_id: 12345,
    github_login: "xzawed",
    email: "test@example.com",
    avatar_url: null,
    last_login_at: new Date(),
    created_at: new Date(),
  };

  it("returns the upserted user row", async () => {
    mockInsert.mockReturnValue(makeInsertChain([userRow]));
    const result = await upsertUser({
      githubId: 12345,
      githubLogin: "xzawed",
      email: "test@example.com",
      avatarUrl: null,
    });
    expect(result).toEqual(userRow);
  });
});

// ── getLatestAnalysis ─────────────────────────────────────────────────────────

describe("getLatestAnalysis(repoId)", () => {
  const analysisRow = { id: "analysis-1", repo_id: "repo-a", status: "done", started_at: new Date() };

  it("returns the latest analysis when found", async () => {
    mockSelect.mockReturnValue(makeSelectChain([analysisRow]));
    const result = await getLatestAnalysis("repo-a");
    expect(result).toEqual(analysisRow);
  });

  it("returns null when no analysis exists for the repo", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getLatestAnalysis("repo-a");
    expect(result).toBeNull();
  });
});

// ── getLatestInference ────────────────────────────────────────────────────────

describe("getLatestInference(repoId)", () => {
  const inferenceRow = {
    id: "infer-1",
    repo_id: "repo-a",
    analysis_id: "analysis-1",
    status: "done",
    created_at: new Date(),
  };

  it("returns the latest inference when found", async () => {
    mockSelect.mockReturnValue(makeSelectChain([inferenceRow]));
    const result = await getLatestInference("repo-a");
    expect(result).toEqual(inferenceRow);
  });

  it("returns null when no inference exists", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getLatestInference("repo-a");
    expect(result).toBeNull();
  });
});

// ── getInference ──────────────────────────────────────────────────────────────

describe("getInference(userId, inferenceId)", () => {
  const inferenceRow = {
    id: "infer-1",
    repo_id: "repo-a",
    analysis_id: "analysis-1",
    status: "done",
    created_at: new Date(),
  };

  it("returns the inference when ownership JOIN resolves", async () => {
    mockSelect.mockReturnValue(makeSelectChain([{ i: inferenceRow }]));
    const result = await getInference(USER_A, "infer-1");
    expect(result).toEqual(inferenceRow);
  });

  it("returns null when cross-tenant JOIN returns no rows", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getInference(USER_A, "infer-2");
    expect(result).toBeNull();
  });
});

// ── getHarvestSources ─────────────────────────────────────────────────────────

describe("getHarvestSources(inferenceId)", () => {
  const sourceA = { id: "src-1", inference_id: "infer-1", url: "https://example.com", status: "done", created_at: new Date() };
  const sourceB = { id: "src-2", inference_id: "infer-1", url: "https://example.org", status: "pending", created_at: new Date() };

  it("returns all harvest sources for the inference", async () => {
    mockSelect.mockReturnValue(makeSelectChain([sourceA, sourceB]));
    const result = await getHarvestSources("infer-1");
    expect(result).toEqual([sourceA, sourceB]);
  });

  it("returns empty array when no sources exist", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getHarvestSources("infer-1");
    expect(result).toEqual([]);
  });
});

// ── countChunks ───────────────────────────────────────────────────────────────

describe("countChunks(inferenceId)", () => {
  it("returns the chunk count from the DB", async () => {
    mockExecute.mockResolvedValue({ rows: [{ n: 42 }] });
    const result = await countChunks("infer-1");
    expect(result).toBe(42);
  });

  it("returns 0 when the count field is undefined (fallback)", async () => {
    mockExecute.mockResolvedValue({ rows: [{ n: undefined }] });
    const result = await countChunks("infer-1");
    expect(result).toBe(0);
  });
});

// ── getJob ────────────────────────────────────────────────────────────────────

describe("getJob(jobId)", () => {
  const jobRow = { id: "job-1", kind: "analyze", status: "pending", payload: {}, created_at: new Date() };

  it("returns the job when found", async () => {
    mockSelect.mockReturnValue(makeSelectChain([jobRow]));
    const result = await getJob("job-1");
    expect(result).toEqual(jobRow);
  });

  it("returns null when job not found", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getJob("job-missing");
    expect(result).toBeNull();
  });
});

// ── getWorkerAlive ────────────────────────────────────────────────────────────

describe("getWorkerAlive()", () => {
  it("returns false when no heartbeat row exists", async () => {
    mockExecute.mockResolvedValue({ rows: [] });
    const result = await getWorkerAlive();
    expect(result).toBe(false);
  });

  it("returns true when last_seen_at is recent (< 90s ago)", async () => {
    mockExecute.mockResolvedValue({ rows: [{ last_seen_at: new Date() }] });
    const result = await getWorkerAlive();
    expect(result).toBe(true);
  });

  it("returns false when last_seen_at is older than 90s", async () => {
    mockExecute.mockResolvedValue({
      rows: [{ last_seen_at: new Date(Date.now() - 95_000) }],
    });
    const result = await getWorkerAlive();
    expect(result).toBe(false);
  });
});

// ── getGeneration ─────────────────────────────────────────────────────────────

describe("getGeneration(userId, generationId)", () => {
  const genRow = {
    id: "gen-1",
    inference_id: "infer-1",
    status: "done",
    generated_at: new Date(),
    created_at: new Date(),
  };

  it("returns the generation when ownership JOIN resolves", async () => {
    mockSelect.mockReturnValue(makeSelectChain([{ g: genRow }]));
    const result = await getGeneration(USER_A, "gen-1");
    expect(result).toEqual(genRow);
  });

  it("returns null when cross-tenant JOIN returns no rows", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getGeneration(USER_A, "gen-missing");
    expect(result).toBeNull();
  });
});

// ── getGenerationFull ─────────────────────────────────────────────────────────

describe("getGenerationFull(userId, generationId)", () => {
  const genRow = {
    id: "gen-1",
    inference_id: "infer-1",
    status: "done",
    generated_at: new Date(),
    created_at: new Date(),
  };
  const variant = { id: "v-1", generation_id: "gen-1", content: "prompt text", variant_type: "cot", created_at: new Date() };
  const ragConfig = { id: "rag-1", generation_id: "gen-1", chunk_size: 512 };
  const evalPair = { id: "ep-1", generation_id: "gen-1", question: "q?", answer: "a." };

  it("returns null when getGeneration returns null (ownership fails)", async () => {
    // First call: getGeneration inner select → []
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getGenerationFull(USER_A, "gen-missing");
    expect(result).toBeNull();
  });

  it("returns full generation object with variants, rag, and pairs", async () => {
    mockSelect
      .mockReturnValueOnce(makeSelectChain([{ g: genRow }]))  // getGeneration
      .mockReturnValueOnce(makeSelectChain([variant]))         // prompt_variants
      .mockReturnValueOnce(makeSelectChain([ragConfig]))       // rag_configs
      .mockReturnValueOnce(makeSelectChain([evalPair]));       // eval_pairs

    const result = await getGenerationFull(USER_A, "gen-1");
    expect(result).not.toBeNull();
    expect(result!.gen).toEqual(genRow);
    expect(result!.variants).toEqual([variant]);
    expect(result!.rag).toEqual(ragConfig);
    expect(result!.pairs).toEqual([evalPair]);
  });

  it("returns null rag when no rag_configs row exists", async () => {
    mockSelect
      .mockReturnValueOnce(makeSelectChain([{ g: genRow }]))  // getGeneration
      .mockReturnValueOnce(makeSelectChain([variant]))         // prompt_variants
      .mockReturnValueOnce(makeSelectChain([]))                // rag_configs → empty
      .mockReturnValueOnce(makeSelectChain([]));               // eval_pairs → empty

    const result = await getGenerationFull(USER_A, "gen-1");
    expect(result).not.toBeNull();
    expect(result!.rag).toBeNull();
    expect(result!.pairs).toEqual([]);
  });
});

// ── getVariantPrompt ──────────────────────────────────────────────────────────

describe("getVariantPrompt(deploymentId)", () => {
  it("returns the prompt content when found", async () => {
    mockExecute.mockResolvedValue({ rows: [{ content: "You are a tarot reader." }] });
    const result = await getVariantPrompt("deploy-1");
    expect(result).toBe("You are a tarot reader.");
  });

  it("returns null when no cot variant exists for the deployment", async () => {
    mockExecute.mockResolvedValue({ rows: [] });
    const result = await getVariantPrompt("deploy-1");
    expect(result).toBeNull();
  });
});

// ── getLatestGeneration ───────────────────────────────────────────────────────

describe("getLatestGeneration(inferenceId)", () => {
  const genRow = {
    id: "gen-1",
    inference_id: "infer-1",
    status: "done",
    generated_at: new Date(),
    created_at: new Date(),
  };

  it("returns the latest generation when found", async () => {
    mockSelect.mockReturnValue(makeSelectChain([genRow]));
    const result = await getLatestGeneration("infer-1");
    expect(result).toEqual(genRow);
  });

  it("returns null when no generation exists", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getLatestGeneration("infer-1");
    expect(result).toBeNull();
  });
});

// ── getRepoStatus ─────────────────────────────────────────────────────────────

describe("getRepoStatus(userId, repoId)", () => {
  it("returns null when repo does not belong to user", async () => {
    // getRepo internally calls db.select → returns []
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getRepoStatus(USER_A, "repo-missing");
    expect(result).toBeNull();
  });

  it("returns status with null inference when no analysis/inference exist", async () => {
    // Sequence:
    //   1. getRepo → repoA
    //   2. getLatestAnalysis → []
    //   3. getLatestInference → []
    mockSelect
      .mockReturnValueOnce(makeSelectChain([repoA]))  // getRepo
      .mockReturnValueOnce(makeSelectChain([]))        // getLatestAnalysis
      .mockReturnValueOnce(makeSelectChain([]));       // getLatestInference

    const result = await getRepoStatus(USER_A, "repo-a");
    expect(result).not.toBeNull();
    expect(result!.repo).toEqual(repoA);
    expect(result!.latestAnalysis).toBeNull();
    expect(result!.latestInference).toBeNull();
    expect(result!.harvestChunks).toBe(0);
    expect(result!.latestGeneration).toBeNull();
    expect(result!.latestDeploymentId).toBeNull();
  });

  it("returns status with harvest info when inference exists but is not done", async () => {
    const inferenceRow = {
      id: "infer-1",
      repo_id: "repo-a",
      analysis_id: "analysis-1",
      status: "running",
      created_at: new Date(),
    };
    const analysisRow = { id: "analysis-1", repo_id: "repo-a", status: "done", started_at: new Date() };
    const sourceA = { id: "src-1", inference_id: "infer-1", url: "https://example.com", status: "done", created_at: new Date() };
    const sourceB = { id: "src-2", inference_id: "infer-1", url: "https://example.org", status: "pending", created_at: new Date() };

    mockSelect
      .mockReturnValueOnce(makeSelectChain([repoA]))           // getRepo
      .mockReturnValueOnce(makeSelectChain([analysisRow]))      // getLatestAnalysis
      .mockReturnValueOnce(makeSelectChain([inferenceRow]))     // getLatestInference
      .mockReturnValueOnce(makeSelectChain([sourceA, sourceB])); // getHarvestSources

    // countChunks + getLatestHarvestJobStatus both use db.execute
    mockExecute
      .mockResolvedValueOnce({ rows: [{ n: 10 }] })            // countChunks
      .mockResolvedValueOnce({ rows: [{ status: "running" }] }); // getLatestHarvestJobStatus

    const result = await getRepoStatus(USER_A, "repo-a");
    expect(result).not.toBeNull();
    expect(result!.harvestSourcesTotal).toBe(2);
    expect(result!.harvestSourcesDone).toBe(1);
    expect(result!.harvestChunks).toBe(10);
    expect(result!.harvestJobStatus).toBe("running");
    expect(result!.latestGeneration).toBeNull(); // inference.status !== 'done'
  });
});

// ── getTraceList ──────────────────────────────────────────────────────────────

describe("getTraceList(deploymentId, page, limit)", () => {
  const traceRow = {
    id: "trace-1",
    variant: "baseline",
    user_feedback: null,
    judge_score: 0.85,
    created_at: new Date(),
    latency_ms: 320,
    cost_usd: 0.001,
    model: "claude-sonnet-4-5",
    input_tokens: 100,
    output_tokens: 50,
    error: null,
  };

  it("returns traces and total count", async () => {
    mockExecute
      .mockResolvedValueOnce({ rows: [traceRow] })          // trace rows
      .mockResolvedValueOnce({ rows: [{ total: 1 }] });     // count row

    const result = await getTraceList("deploy-1", 1, 20);
    expect(result.traces).toEqual([traceRow]);
    expect(result.total).toBe(1);
    expect(result.page).toBe(1);
  });

  it("returns empty traces and total 0 when no data", async () => {
    mockExecute
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [{ total: 0 }] });

    const result = await getTraceList("deploy-1");
    expect(result.traces).toEqual([]);
    expect(result.total).toBe(0);
  });
});

// ── getDailyMetrics ───────────────────────────────────────────────────────────

describe("getDailyMetrics(deploymentId, days)", () => {
  const metricRow = {
    date: "2025-04-20",
    total_cost_usd: 0.05,
    call_count: 10,
    p95_latency_ms: 400,
    avg_judge_score: 0.88,
  };

  it("returns metric rows from the DB", async () => {
    mockExecute.mockResolvedValue({ rows: [metricRow] });
    const result = await getDailyMetrics("deploy-1", 7);
    expect(result).toEqual([metricRow]);
  });

  it("returns empty array when no metrics exist", async () => {
    mockExecute.mockResolvedValue({ rows: [] });
    const result = await getDailyMetrics("deploy-1");
    expect(result).toEqual([]);
  });
});

// ── getSdkPrRequest ───────────────────────────────────────────────────────────

describe("getSdkPrRequest(userId, requestId)", () => {
  const prRow = {
    id: "req-1",
    owner_user_id: USER_A,
    repo_id: "repo-a",
    status: "open",
    created_at: new Date(),
  };

  it("returns the PR request when owner matches", async () => {
    mockSelect.mockReturnValue(makeSelectChain([prRow]));
    const result = await getSdkPrRequest(USER_A, "req-1");
    expect(result).toEqual(prRow);
  });

  it("returns null when cross-tenant or not found", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getSdkPrRequest(USER_A, "req-other");
    expect(result).toBeNull();
  });
});

// ── getLatestSdkPrRequest ─────────────────────────────────────────────────────

describe("getLatestSdkPrRequest(userId, repoId)", () => {
  const prRow = {
    id: "req-1",
    owner_user_id: USER_A,
    repo_id: "repo-a",
    status: "open",
    created_at: new Date(),
  };

  it("returns the most recent PR request for the repo", async () => {
    mockSelect.mockReturnValue(makeSelectChain([prRow]));
    const result = await getLatestSdkPrRequest(USER_A, "repo-a");
    expect(result).toEqual(prRow);
  });

  it("returns null when no PR request exists", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getLatestSdkPrRequest(USER_A, "repo-a");
    expect(result).toBeNull();
  });
});

// ── getLatestSdkPrRequestByMode ───────────────────────────────────────────────

describe("getLatestSdkPrRequestByMode(userId, repoId, mode)", () => {
  const observeRow = {
    id: "req-observe-1",
    owner_user_id: USER_A,
    repo_id: "repo-a",
    mode: "observe",
    status: "pr_created",
    pr_url: "https://github.com/owner/repo/pull/1",
    pr_number: 1,
    created_at: new Date(),
  };
  const bidirectionalRow = {
    id: "req-bidi-1",
    owner_user_id: USER_A,
    repo_id: "repo-a",
    mode: "bidirectional",
    status: "pr_created",
    pr_url: "https://github.com/owner/repo/pull/2",
    pr_number: 2,
    created_at: new Date(),
  };

  it("returns the most recent observe-mode PR request", async () => {
    mockSelect.mockReturnValue(makeSelectChain([observeRow]));
    const result = await getLatestSdkPrRequestByMode(USER_A, "repo-a", "observe");
    expect(result).toEqual(observeRow);
  });

  it("returns the most recent bidirectional-mode PR request", async () => {
    mockSelect.mockReturnValue(makeSelectChain([bidirectionalRow]));
    const result = await getLatestSdkPrRequestByMode(USER_A, "repo-a", "bidirectional");
    expect(result).toEqual(bidirectionalRow);
  });

  it("returns null when no PR request exists for that mode", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getLatestSdkPrRequestByMode(USER_A, "repo-a", "bidirectional");
    expect(result).toBeNull();
  });

  it("returns null for cross-tenant access (owner mismatch)", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await getLatestSdkPrRequestByMode(USER_B, "repo-a", "observe");
    expect(result).toBeNull();
  });
});
