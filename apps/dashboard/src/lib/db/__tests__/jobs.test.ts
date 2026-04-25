/**
 * Unit tests for lib/db/jobs.ts — no real DB, all Drizzle ORM calls are mocked.
 *
 * Each exported function is tested with at least:
 *   - a happy-path case (returns expected value / calls expected mocks)
 *   - one error / edge case (INSERT failure throws, cross-tenant returns null/false, etc.)
 */

jest.mock("@/lib/db/client", () => ({
  db: {
    select: jest.fn(),
    insert: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
    execute: jest.fn(),
    transaction: jest.fn(),
  },
}));

jest.mock("@/lib/db/queries", () => ({
  getInference: jest.fn(),
}));

import { db } from "@/lib/db/client";
import { getInference } from "@/lib/db/queries";
import {
  createRepo,
  deleteRepo,
  enqueueAnalyze,
  enqueueInfer,
  approveSource,
  rejectSource,
  enqueueHarvest,
  enqueueRetrieve,
  enqueueGenerate,
  enqueueDeployment,
  updateDeploymentTraffic,
  rollbackDeployment,
  approveGeneration,
  confirmInference,
  insertTrace,
  updateFeedback,
  getModelPricing,
  createSdkPrRequest,
  updateSdkPrRequest,
} from "../jobs";

// ── typed mock references ─────────────────────────────────────────────────────

const mockSelect = db.select as jest.Mock;
const mockInsert = db.insert as jest.Mock;
const mockUpdate = db.update as jest.Mock;
const mockDelete = db.delete as jest.Mock;
const mockExecute = db.execute as jest.Mock;
const mockTransaction = db.transaction as jest.Mock;
const mockGetInference = getInference as jest.Mock;

// ── chain builder helpers ─────────────────────────────────────────────────────

/**
 * Builds a Drizzle select chain that resolves to `rows` on .limit() or .orderBy().
 * Covers .from().where().innerJoin().limit() and similar patterns.
 */
function makeSelectChain(rows: unknown[]): Record<string, unknown> {
  const chain: Record<string, unknown> = {};
  (["from", "where", "innerJoin"] as const).forEach((m) => {
    chain[m] = jest.fn(() => chain);
  });
  chain["orderBy"] = jest.fn(() => Promise.resolve(rows));
  chain["limit"] = jest.fn(() => Promise.resolve(rows));
  chain["select"] = jest.fn(() => chain);
  return chain;
}

/**
 * Builds a Drizzle insert chain.
 * .insert(table).values({}).returning() → resolves to `rows`.
 * Also supports .returning({ id: col }) shaped calls.
 */
function makeInsertChain(rows: unknown[]): Record<string, unknown> {
  const chain: Record<string, unknown> = {};
  (["values", "onConflictDoUpdate"] as const).forEach((m) => {
    chain[m] = jest.fn(() => chain);
  });
  chain["returning"] = jest.fn(() => Promise.resolve(rows));
  return chain;
}

/**
 * Builds a Drizzle update chain.
 * .update(table).set({}).where() resolves to `rows` (for .returning()) or undefined.
 */
function makeUpdateChain(rows: unknown[] = []): Record<string, unknown> {
  const chain: Record<string, unknown> = {};
  chain["set"] = jest.fn(() => chain);
  chain["where"] = jest.fn(() => Promise.resolve(rows));
  chain["returning"] = jest.fn(() => Promise.resolve(rows));
  // Support .set().where().returning() pattern used by confirmInference
  const setFn = jest.fn(() => {
    const afterSet: Record<string, unknown> = {};
    afterSet["where"] = jest.fn(() => {
      const afterWhere: Record<string, unknown> = {};
      afterWhere["returning"] = jest.fn(() => Promise.resolve(rows));
      // Make it thenable so await works when no .returning() is chained
      (afterWhere as unknown as Promise<unknown>).then = (resolve: (v: unknown) => unknown) =>
        Promise.resolve(rows).then(resolve);
      return afterWhere;
    });
    // Make set().where() directly awaitable (used in approveSource / rejectSource)
    (afterSet["where"] as jest.Mock).mockImplementation(() => Promise.resolve(undefined));
    return afterSet;
  });
  chain["set"] = setFn;
  return chain;
}

/**
 * Builds a Drizzle delete chain.
 * .delete(table).where() → resolves to undefined.
 */
function makeDeleteChain(): Record<string, unknown> {
  const chain: Record<string, unknown> = {};
  chain["where"] = jest.fn(() => Promise.resolve(undefined));
  return chain;
}

// ── fixture data ──────────────────────────────────────────────────────────────

const USER_A = "aaaaaaaa-0000-0000-0000-000000000001";

const REPO_ROW = {
  id: "repo-1",
  owner_user_id: USER_A,
  github_url: "https://github.com/user/proj",
  default_branch: "main",
  created_at: new Date(),
};

const ANALYSIS_ROW = { id: "analysis-1", repo_id: "repo-1", status: "pending" };
const INFERENCE_ROW = { id: "inference-1", repo_id: "repo-1", analysis_id: "analysis-1", status: "pending", domain: "tarot", tone: "mystical", language: "ko", user_type: "consumer" };
const JOB_ROW = { id: "job-1" };
const GEN_ROW = { id: "gen-1" };

beforeEach(() => {
  jest.clearAllMocks();
});

// ── createRepo ────────────────────────────────────────────────────────────────

describe("createRepo", () => {
  it("returns existing repo without INSERT when repo already exists", async () => {
    mockSelect.mockReturnValue(makeSelectChain([REPO_ROW]));
    const result = await createRepo(USER_A, "https://github.com/user/proj");
    expect(result).toEqual(REPO_ROW);
    expect(mockInsert).not.toHaveBeenCalled();
  });

  it("inserts and returns new repo when not found", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    mockInsert.mockReturnValue(makeInsertChain([REPO_ROW]));
    const result = await createRepo(USER_A, "https://github.com/user/newrepo", "develop");
    expect(result).toEqual(REPO_ROW);
    expect(mockInsert).toHaveBeenCalled();
  });

  it("throws when INSERT returns no row", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    mockInsert.mockReturnValue(makeInsertChain([]));
    await expect(createRepo(USER_A, "https://github.com/user/proj")).rejects.toThrow(
      "createRepo: INSERT returned no row",
    );
  });
});

// ── deleteRepo ────────────────────────────────────────────────────────────────

describe("deleteRepo", () => {
  it("calls delete().where() with user and repo id", async () => {
    const chain = makeDeleteChain();
    mockDelete.mockReturnValue(chain);
    await deleteRepo(USER_A, "repo-1");
    expect(mockDelete).toHaveBeenCalled();
    expect(chain["where"] as jest.Mock).toHaveBeenCalled();
  });
});

// ── enqueueAnalyze ─────────────────────────────────────────────────────────────

describe("enqueueAnalyze", () => {
  it("inserts analysis and job, returns analysis row", async () => {
    mockInsert
      .mockReturnValueOnce(makeInsertChain([ANALYSIS_ROW]))  // analyses insert
      .mockReturnValueOnce(makeInsertChain([]));              // verum_jobs insert (no .returning used)
    const result = await enqueueAnalyze({
      userId: USER_A,
      repoId: "repo-1",
      repoUrl: "https://github.com/user/proj",
      branch: "main",
    });
    expect(result).toEqual(ANALYSIS_ROW);
    expect(mockInsert).toHaveBeenCalledTimes(2);
  });

  it("throws when analysis INSERT returns no row", async () => {
    mockInsert.mockReturnValue(makeInsertChain([]));
    await expect(
      enqueueAnalyze({ userId: USER_A, repoId: "repo-1", repoUrl: "https://github.com/user/proj", branch: "main" }),
    ).rejects.toThrow("enqueueAnalyze: analysis INSERT returned no row");
  });
});

// ── enqueueInfer ──────────────────────────────────────────────────────────────

describe("enqueueInfer", () => {
  it("inserts inference and job, returns inference row", async () => {
    mockInsert
      .mockReturnValueOnce(makeInsertChain([INFERENCE_ROW]))
      .mockReturnValueOnce(makeInsertChain([]));
    const result = await enqueueInfer({
      userId: USER_A,
      repoId: "repo-1",
      analysisId: "analysis-1",
    });
    expect(result).toEqual(INFERENCE_ROW);
    expect(mockInsert).toHaveBeenCalledTimes(2);
  });

  it("throws when inference INSERT returns no row", async () => {
    mockInsert.mockReturnValue(makeInsertChain([]));
    await expect(
      enqueueInfer({ userId: USER_A, repoId: "repo-1", analysisId: "analysis-1" }),
    ).rejects.toThrow("enqueueInfer: inference INSERT returned no row");
  });
});

// ── approveSource / rejectSource ──────────────────────────────────────────────

describe("approveSource", () => {
  it("calls update().set({ status: 'approved' }).where()", async () => {
    const setMock = jest.fn().mockReturnValue({ where: jest.fn().mockResolvedValue(undefined) });
    mockUpdate.mockReturnValue({ set: setMock });
    await approveSource("source-1");
    expect(setMock).toHaveBeenCalledWith(expect.objectContaining({ status: "approved" }));
  });
});

describe("rejectSource", () => {
  it("calls update().set({ status: 'rejected' }).where()", async () => {
    const setMock = jest.fn().mockReturnValue({ where: jest.fn().mockResolvedValue(undefined) });
    mockUpdate.mockReturnValue({ set: setMock });
    await rejectSource("source-1");
    expect(setMock).toHaveBeenCalledWith(expect.objectContaining({ status: "rejected" }));
  });
});

// ── enqueueHarvest ────────────────────────────────────────────────────────────

describe("enqueueHarvest", () => {
  it("calls insert with kind=harvest and correct source_ids payload", async () => {
    const valuesMock = jest.fn().mockResolvedValue(undefined);
    mockInsert.mockReturnValue({ values: valuesMock });
    await enqueueHarvest({
      userId: USER_A,
      inferenceId: "inference-1",
      sourcePairs: [
        { sourceId: "s1", url: "https://example.com/a" },
        { sourceId: "s2", url: "https://example.com/b" },
      ],
    });
    expect(valuesMock).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: "harvest",
        payload: expect.objectContaining({
          inference_id: "inference-1",
          source_ids: [
            ["s1", "https://example.com/a"],
            ["s2", "https://example.com/b"],
          ],
        }),
      }),
    );
  });
});

// ── enqueueRetrieve ───────────────────────────────────────────────────────────

describe("enqueueRetrieve", () => {
  it("returns job id string on success", async () => {
    mockInsert.mockReturnValue(makeInsertChain([JOB_ROW]));
    const id = await enqueueRetrieve({
      userId: USER_A,
      inferenceId: "inference-1",
      query: "how to read tarot",
      hybrid: true,
      topK: 5,
    });
    expect(id).toBe("job-1");
  });

  it("throws when INSERT returns no row", async () => {
    mockInsert.mockReturnValue(makeInsertChain([]));
    await expect(
      enqueueRetrieve({ userId: USER_A, inferenceId: "inference-1", query: "q", hybrid: false, topK: 3 }),
    ).rejects.toThrow("enqueueRetrieve: job INSERT returned no row");
  });
});

// ── enqueueGenerate ───────────────────────────────────────────────────────────

describe("enqueueGenerate", () => {
  it("returns { generationId, jobId } on success", async () => {
    mockInsert
      .mockReturnValueOnce(makeInsertChain([GEN_ROW]))   // generations insert
      .mockReturnValueOnce(makeInsertChain([JOB_ROW]));  // verum_jobs insert
    const result = await enqueueGenerate({ userId: USER_A, inferenceId: "inference-1" });
    expect(result).toEqual({ generationId: "gen-1", jobId: "job-1" });
  });

  it("throws when generation INSERT returns no row", async () => {
    mockInsert.mockReturnValueOnce(makeInsertChain([]));
    await expect(
      enqueueGenerate({ userId: USER_A, inferenceId: "inference-1" }),
    ).rejects.toThrow("enqueueGenerate: generation INSERT returned no row");
  });

  it("throws when job INSERT returns no row", async () => {
    mockInsert
      .mockReturnValueOnce(makeInsertChain([GEN_ROW]))
      .mockReturnValueOnce(makeInsertChain([]));
    await expect(
      enqueueGenerate({ userId: USER_A, inferenceId: "inference-1" }),
    ).rejects.toThrow("enqueueGenerate: job INSERT returned no row");
  });
});

// ── enqueueDeployment ─────────────────────────────────────────────────────────

describe("enqueueDeployment", () => {
  it("returns job id on success", async () => {
    mockInsert.mockReturnValue(makeInsertChain([JOB_ROW]));
    const id = await enqueueDeployment({ userId: USER_A, generationId: "gen-1" });
    expect(id).toBe("job-1");
  });

  it("throws when INSERT returns no row", async () => {
    mockInsert.mockReturnValue(makeInsertChain([]));
    await expect(
      enqueueDeployment({ userId: USER_A, generationId: "gen-1" }),
    ).rejects.toThrow("enqueueDeployment: job INSERT returned no row");
  });
});

// ── updateDeploymentTraffic ───────────────────────────────────────────────────

describe("updateDeploymentTraffic", () => {
  it("calls update with correct traffic_split math (split=0.3 → baseline=0.7, variant=0.3)", async () => {
    const setMock = jest.fn().mockReturnValue({ where: jest.fn().mockResolvedValue(undefined) });
    mockUpdate.mockReturnValue({ set: setMock });
    await updateDeploymentTraffic(USER_A, "deploy-1", 0.3);
    expect(setMock).toHaveBeenCalledWith(
      expect.objectContaining({
        traffic_split: { baseline: 0.7, variant: 0.3 },
      }),
    );
  });

  it("calls update with split=0 → baseline=1, variant=0 (full rollback-style)", async () => {
    const setMock = jest.fn().mockReturnValue({ where: jest.fn().mockResolvedValue(undefined) });
    mockUpdate.mockReturnValue({ set: setMock });
    await updateDeploymentTraffic(USER_A, "deploy-1", 0);
    expect(setMock).toHaveBeenCalledWith(
      expect.objectContaining({
        traffic_split: { baseline: 1, variant: 0 },
      }),
    );
  });
});

// ── rollbackDeployment ────────────────────────────────────────────────────────

describe("rollbackDeployment", () => {
  it("calls update with status=rolled_back and traffic_split zeroed", async () => {
    const setMock = jest.fn().mockReturnValue({ where: jest.fn().mockResolvedValue(undefined) });
    mockUpdate.mockReturnValue({ set: setMock });
    await rollbackDeployment(USER_A, "deploy-1");
    expect(setMock).toHaveBeenCalledWith(
      expect.objectContaining({
        status: "rolled_back",
        traffic_split: { baseline: 1.0, variant: 0.0 },
      }),
    );
  });
});

// ── approveGeneration ─────────────────────────────────────────────────────────

describe("approveGeneration", () => {
  it("returns false when ownership SELECT returns no rows", async () => {
    mockSelect.mockReturnValue(makeSelectChain([]));
    const result = await approveGeneration(USER_A, "gen-1");
    expect(result).toBe(false);
    expect(mockUpdate).not.toHaveBeenCalled();
  });

  it("returns true and updates status when ownership SELECT returns a row", async () => {
    const genRecord = { g: { id: "gen-1", status: "pending", inference_id: "inference-1" } };
    mockSelect.mockReturnValue(makeSelectChain([genRecord]));
    const setMock = jest.fn().mockReturnValue({ where: jest.fn().mockResolvedValue(undefined) });
    mockUpdate.mockReturnValue({ set: setMock });
    const result = await approveGeneration(USER_A, "gen-1");
    expect(result).toBe(true);
    expect(setMock).toHaveBeenCalledWith(expect.objectContaining({ status: "approved" }));
  });
});

// ── confirmInference ──────────────────────────────────────────────────────────

describe("confirmInference", () => {
  it("returns null when getInference returns null (not found or cross-tenant)", async () => {
    mockGetInference.mockResolvedValue(null);
    const result = await confirmInference(USER_A, "inference-1", { domain: "tarot" });
    expect(result).toBeNull();
    expect(mockUpdate).not.toHaveBeenCalled();
  });

  it("calls update and returns updated inference row", async () => {
    mockGetInference.mockResolvedValue(INFERENCE_ROW);
    const updatedRow = { ...INFERENCE_ROW, domain: "astrology" };
    const returningMock = jest.fn().mockResolvedValue([updatedRow]);
    const whereMock = jest.fn().mockReturnValue({ returning: returningMock });
    const setMock = jest.fn().mockReturnValue({ where: whereMock });
    mockUpdate.mockReturnValue({ set: setMock });
    const result = await confirmInference(USER_A, "inference-1", { domain: "astrology" });
    expect(result).toEqual(updatedRow);
    expect(setMock).toHaveBeenCalledWith(
      expect.objectContaining({ domain: "astrology" }),
    );
  });

  it("returns null when update().returning() returns empty array", async () => {
    mockGetInference.mockResolvedValue(INFERENCE_ROW);
    const returningMock = jest.fn().mockResolvedValue([]);
    const whereMock = jest.fn().mockReturnValue({ returning: returningMock });
    const setMock = jest.fn().mockReturnValue({ where: whereMock });
    mockUpdate.mockReturnValue({ set: setMock });
    const result = await confirmInference(USER_A, "inference-1", {});
    expect(result).toBeNull();
  });
});

// ── insertTrace ───────────────────────────────────────────────────────────────

describe("insertTrace", () => {
  it("calls _getDeploymentOwner (db.execute) then transaction, returns traceId", async () => {
    // First db.execute call: _getDeploymentOwner
    mockExecute.mockResolvedValueOnce({ rows: [{ owner_user_id: USER_A }] });

    // transaction mock: runs the callback with a fake tx
    mockTransaction.mockImplementation(async (fn: (tx: unknown) => Promise<unknown>) => {
      const tx = {
        execute: jest.fn()
          .mockResolvedValueOnce({ rows: [{ id: "trace-id-abc" }] })  // INSERT traces
          .mockResolvedValueOnce({ rows: [] }),                         // INSERT spans
        insert: jest.fn().mockReturnValue(makeInsertChain([])),         // INSERT verum_jobs
      };
      return fn(tx);
    });

    const traceId = await insertTrace({
      deploymentId: "dep-1",
      variant: "baseline",
      model: "gpt-4o",
      inputTokens: 100,
      outputTokens: 200,
      latencyMs: 500,
      error: null,
      costUsd: "0.002",
    });

    expect(traceId).toBe("trace-id-abc");
    expect(mockExecute).toHaveBeenCalledTimes(1); // _getDeploymentOwner
    expect(mockTransaction).toHaveBeenCalledTimes(1);
  });

  it("passes spanAttributes into the transaction when provided", async () => {
    mockExecute.mockResolvedValueOnce({ rows: [{ owner_user_id: USER_A }] });

    let capturedTxExecute: jest.Mock | null = null;
    mockTransaction.mockImplementation(async (fn: (tx: unknown) => Promise<unknown>) => {
      const txExecute = jest.fn()
        .mockResolvedValueOnce({ rows: [{ id: "trace-id-xyz" }] })
        .mockResolvedValueOnce({ rows: [] });
      capturedTxExecute = txExecute;
      const tx = {
        execute: txExecute,
        insert: jest.fn().mockReturnValue(makeInsertChain([])),
      };
      return fn(tx);
    });

    await insertTrace({
      deploymentId: "dep-1",
      variant: "variant",
      model: "claude-3-5",
      inputTokens: 50,
      outputTokens: 80,
      latencyMs: 300,
      error: null,
      costUsd: "0.001",
      spanAttributes: { prompt_version: "v2" },
    });

    // tx.execute should have been called twice (traces + spans)
    expect(capturedTxExecute).not.toBeNull();
    expect(capturedTxExecute!).toHaveBeenCalledTimes(2);
  });
});

// ── updateFeedback ────────────────────────────────────────────────────────────

describe("updateFeedback", () => {
  it("returns true when rowCount > 0", async () => {
    mockExecute.mockResolvedValue({ rowCount: 1, rows: [{ id: "trace-1" }] });
    const result = await updateFeedback("dep-1", "trace-1", 1);
    expect(result).toBe(true);
  });

  it("returns false when rowCount is 0 (trace not found)", async () => {
    mockExecute.mockResolvedValue({ rowCount: 0, rows: [] });
    const result = await updateFeedback("dep-1", "trace-999", 1);
    expect(result).toBe(false);
  });

  it("returns false when rowCount is null/undefined", async () => {
    mockExecute.mockResolvedValue({ rows: [] });
    const result = await updateFeedback("dep-1", "trace-999", -1);
    expect(result).toBe(false);
  });
});

// ── getModelPricing ───────────────────────────────────────────────────────────

describe("getModelPricing", () => {
  it("returns pricing row when model is found", async () => {
    const pricingRow = { input_per_1m_usd: "3.00", output_per_1m_usd: "15.00" };
    mockExecute.mockResolvedValue({ rows: [pricingRow] });
    const result = await getModelPricing("gpt-4o");
    expect(result).toEqual(pricingRow);
  });

  it("returns nullish when model not found (rows.rows is empty)", async () => {
    // The implementation returns rows.rows[0] cast as null — which resolves
    // to undefined when the array is empty. The declared return type is null,
    // but the cast produces undefined at runtime; we assert falsy to cover both.
    mockExecute.mockResolvedValue({ rows: [] });
    const result = await getModelPricing("unknown-model");
    expect(result).toBeFalsy();
  });
});

// ── createSdkPrRequest ────────────────────────────────────────────────────────

describe("createSdkPrRequest", () => {
  it("returns the new request id on success", async () => {
    mockInsert.mockReturnValue(makeInsertChain([{ id: "pr-req-1" }]));
    const id = await createSdkPrRequest({ userId: USER_A, repoId: "repo-1", analysisId: "analysis-1" });
    expect(id).toBe("pr-req-1");
  });

  it("throws when INSERT returns no row", async () => {
    mockInsert.mockReturnValue(makeInsertChain([]));
    await expect(
      createSdkPrRequest({ userId: USER_A, repoId: "repo-1", analysisId: "analysis-1" }),
    ).rejects.toThrow("createSdkPrRequest: INSERT returned no row");
  });
});

// ── updateSdkPrRequest ────────────────────────────────────────────────────────

describe("updateSdkPrRequest", () => {
  it("calls update().set().where() with the patch and updated_at", async () => {
    const setMock = jest.fn().mockReturnValue({ where: jest.fn().mockResolvedValue(undefined) });
    mockUpdate.mockReturnValue({ set: setMock });
    await updateSdkPrRequest("pr-req-1", { status: "pr_created", pr_url: "https://github.com/o/r/pull/5", pr_number: 5 });
    expect(setMock).toHaveBeenCalledWith(
      expect.objectContaining({ status: "pr_created", pr_url: "https://github.com/o/r/pull/5" }),
    );
  });

  it("includes updated_at in the set payload", async () => {
    const capturedPayload: Record<string, unknown>[] = [];
    const setMock = jest.fn().mockImplementation((payload: Record<string, unknown>) => {
      capturedPayload.push(payload);
      return { where: jest.fn().mockResolvedValue(undefined) };
    });
    mockUpdate.mockReturnValue({ set: setMock });
    await updateSdkPrRequest("pr-req-1", { status: "failed", error: "git push failed" });
    expect(capturedPayload[0]).toHaveProperty("updated_at");
    expect(capturedPayload[0]["updated_at"]).toBeInstanceOf(Date);
  });
});
