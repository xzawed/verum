/**
 * Unit tests for apps/dashboard/src/app/repos/[id]/actions.ts
 * No real DB — all external modules are mocked.
 *
 * redirect() normally throws in Next.js. We simulate that by having the mock
 * throw a sentinel RedirectError so execution stops at the redirect point,
 * matching real runtime behaviour.
 */

jest.mock("next/navigation", () => ({
  redirect: jest.fn(),
}));
jest.mock("@/auth", () => ({
  auth: jest.fn(),
}));
jest.mock("@/lib/db/jobs", () => ({
  enqueueAnalyze: jest.fn(),
  enqueueInfer: jest.fn(),
  enqueueHarvest: jest.fn(),
  enqueueGenerate: jest.fn(),
}));
jest.mock("@/lib/db/queries", () => ({
  getHarvestSources: jest.fn(),
  getInference: jest.fn(),
}));

import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { enqueueAnalyze, enqueueInfer, enqueueHarvest, enqueueGenerate } from "@/lib/db/jobs";
import { getHarvestSources, getInference } from "@/lib/db/queries";

import {
  rerunAnalyze,
  rerunInfer,
  rerunHarvest,
  rerunGenerate,
} from "../actions";

const mockRedirect = redirect as jest.Mock;
const mockAuth = auth as jest.Mock;
const mockEnqueueAnalyze = enqueueAnalyze as jest.Mock;
const mockEnqueueInfer = enqueueInfer as jest.Mock;
const mockEnqueueHarvest = enqueueHarvest as jest.Mock;
const mockEnqueueGenerate = enqueueGenerate as jest.Mock;
const mockGetHarvestSources = getHarvestSources as jest.Mock;
const mockGetInference = getInference as jest.Mock;

const SESSION = { user: { id: "user-abc", name: "Test" } };

/** Sentinel thrown by our redirect mock — lets us assert and swallow it. */
class RedirectError extends Error {
  constructor(public readonly destination: string) {
    super(`REDIRECT:${destination}`);
    this.name = "RedirectError";
  }
}

/**
 * Invoke an async action and swallow any RedirectError (simulating Next.js
 * redirect internals). Re-throws genuine errors.
 */
async function runAction(fn: () => Promise<void>): Promise<void> {
  try {
    await fn();
  } catch (err) {
    if (err instanceof RedirectError) return;
    throw err;
  }
}

beforeEach(() => {
  jest.resetAllMocks();
  // Simulate Next.js: redirect() throws so execution stops at that call site.
  mockRedirect.mockImplementation((destination: string) => {
    throw new RedirectError(destination);
  });
});

// ---------------------------------------------------------------------------
// rerunAnalyze
// ---------------------------------------------------------------------------
describe("rerunAnalyze", () => {
  it("redirects to /login when unauthenticated", async () => {
    mockAuth.mockResolvedValue(null);
    await runAction(() => rerunAnalyze("repo-1", "https://github.com/a/b", "main"));
    expect(mockRedirect).toHaveBeenCalledWith("/login");
    expect(mockEnqueueAnalyze).not.toHaveBeenCalled();
  });

  it("enqueues analyze job and redirects to repo page", async () => {
    mockAuth.mockResolvedValue(SESSION);
    mockEnqueueAnalyze.mockResolvedValue({ id: "analysis-1" });
    await runAction(() => rerunAnalyze("repo-1", "https://github.com/a/b", "main"));
    expect(mockEnqueueAnalyze).toHaveBeenCalledWith({
      userId: "user-abc",
      repoId: "repo-1",
      repoUrl: "https://github.com/a/b",
      branch: "main",
    });
    expect(mockRedirect).toHaveBeenCalledWith("/repos/repo-1");
  });

  it("uses empty string for uid when session user has no id", async () => {
    mockAuth.mockResolvedValue({ user: { name: "No ID" } });
    mockEnqueueAnalyze.mockResolvedValue({ id: "analysis-2" });
    await runAction(() => rerunAnalyze("repo-2", "https://github.com/x/y", "develop"));
    expect(mockEnqueueAnalyze).toHaveBeenCalledWith(
      expect.objectContaining({ userId: "" })
    );
    expect(mockRedirect).toHaveBeenCalledWith("/repos/repo-2");
  });
});

// ---------------------------------------------------------------------------
// rerunInfer
// ---------------------------------------------------------------------------
describe("rerunInfer", () => {
  it("redirects to /login when unauthenticated", async () => {
    mockAuth.mockResolvedValue(null);
    await runAction(() => rerunInfer("repo-1", "analysis-1"));
    expect(mockRedirect).toHaveBeenCalledWith("/login");
    expect(mockEnqueueInfer).not.toHaveBeenCalled();
  });

  it("enqueues infer job and redirects to infer page with inference_id", async () => {
    mockAuth.mockResolvedValue(SESSION);
    mockEnqueueInfer.mockResolvedValue({ id: "inference-1" });
    await runAction(() => rerunInfer("repo-1", "analysis-1"));
    expect(mockEnqueueInfer).toHaveBeenCalledWith({
      userId: "user-abc",
      repoId: "repo-1",
      analysisId: "analysis-1",
    });
    expect(mockRedirect).toHaveBeenCalledWith(
      "/infer/analysis-1?inference_id=inference-1"
    );
  });
});

// ---------------------------------------------------------------------------
// rerunHarvest
// ---------------------------------------------------------------------------
describe("rerunHarvest", () => {
  it("redirects to /login when unauthenticated", async () => {
    mockAuth.mockResolvedValue(null);
    await runAction(() => rerunHarvest("inference-1", "analysis-1"));
    expect(mockRedirect).toHaveBeenCalledWith("/login");
    expect(mockGetHarvestSources).not.toHaveBeenCalled();
  });

  it("redirects to infer page when there are no approved sources", async () => {
    mockAuth.mockResolvedValue(SESSION);
    mockGetHarvestSources.mockResolvedValue([
      { id: "src-1", status: "pending", url: "https://example.com" },
    ]);
    await runAction(() => rerunHarvest("inference-1", "analysis-1"));
    expect(mockRedirect).toHaveBeenCalledWith(
      "/infer/analysis-1?inference_id=inference-1"
    );
    expect(mockEnqueueHarvest).not.toHaveBeenCalled();
  });

  it("redirects to infer page when source list is empty", async () => {
    mockAuth.mockResolvedValue(SESSION);
    mockGetHarvestSources.mockResolvedValue([]);
    await runAction(() => rerunHarvest("inference-1", "analysis-1"));
    expect(mockRedirect).toHaveBeenCalledWith(
      "/infer/analysis-1?inference_id=inference-1"
    );
    expect(mockEnqueueHarvest).not.toHaveBeenCalled();
  });

  it("enqueues harvest with only approved sources and redirects to harvest page", async () => {
    mockAuth.mockResolvedValue(SESSION);
    mockGetHarvestSources.mockResolvedValue([
      { id: "src-1", status: "approved", url: "https://example.com" },
      { id: "src-2", status: "rejected", url: "https://other.com" },
      { id: "src-3", status: "pending", url: "https://pending.com" },
    ]);
    mockEnqueueHarvest.mockResolvedValue(undefined);
    await runAction(() => rerunHarvest("inference-1", "analysis-1"));
    expect(mockEnqueueHarvest).toHaveBeenCalledWith({
      userId: "user-abc",
      inferenceId: "inference-1",
      sourcePairs: [{ sourceId: "src-1", url: "https://example.com" }],
    });
    expect(mockRedirect).toHaveBeenCalledWith("/harvest/inference-1");
  });

  it("enqueues harvest with multiple approved sources", async () => {
    mockAuth.mockResolvedValue(SESSION);
    mockGetHarvestSources.mockResolvedValue([
      { id: "src-1", status: "approved", url: "https://a.com" },
      { id: "src-2", status: "approved", url: "https://b.com" },
    ]);
    mockEnqueueHarvest.mockResolvedValue(undefined);
    await runAction(() => rerunHarvest("inference-2", "analysis-2"));
    expect(mockEnqueueHarvest).toHaveBeenCalledWith({
      userId: "user-abc",
      inferenceId: "inference-2",
      sourcePairs: [
        { sourceId: "src-1", url: "https://a.com" },
        { sourceId: "src-2", url: "https://b.com" },
      ],
    });
    expect(mockRedirect).toHaveBeenCalledWith("/harvest/inference-2");
  });
});

// ---------------------------------------------------------------------------
// rerunGenerate
// ---------------------------------------------------------------------------
describe("rerunGenerate", () => {
  it("redirects to /login when unauthenticated", async () => {
    mockAuth.mockResolvedValue(null);
    await runAction(() => rerunGenerate("inference-1"));
    expect(mockRedirect).toHaveBeenCalledWith("/login");
    expect(mockEnqueueGenerate).not.toHaveBeenCalled();
  });

  it("enqueues generate job and redirects to repo page", async () => {
    mockAuth.mockResolvedValue(SESSION);
    mockEnqueueGenerate.mockResolvedValue(undefined);
    mockGetInference.mockResolvedValue({ id: "inference-1", repo_id: "repo-1" });
    await runAction(() => rerunGenerate("inference-1"));
    expect(mockEnqueueGenerate).toHaveBeenCalledWith({
      userId: "user-abc",
      inferenceId: "inference-1",
    });
    expect(mockRedirect).toHaveBeenCalledWith("/repos/repo-1");
  });

  it("redirects to /repos when inference has no repo_id", async () => {
    mockAuth.mockResolvedValue(SESSION);
    mockEnqueueGenerate.mockResolvedValue(undefined);
    mockGetInference.mockResolvedValue(null);
    await runAction(() => rerunGenerate("inference-missing"));
    expect(mockEnqueueGenerate).toHaveBeenCalledTimes(1);
    expect(mockRedirect).toHaveBeenCalledWith("/repos");
  });
});
