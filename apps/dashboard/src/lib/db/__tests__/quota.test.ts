/**
 * Unit tests for lib/db/quota.ts — no real DB, db.execute is mocked.
 *
 * Covers all 4 branches of checkAndIncrementTraceQuota:
 *   1. Paid plan  → status "ok", no second db.execute call
 *   2. Free plan, exceeded (>= 1000) → status "exceeded", no second db.execute call
 *   3. Free plan, >= 80% used but not exceeded (e.g. 800) → status "warning", increment called
 *   4. Free plan, < 80% used (e.g. 10) → status "ok", increment called
 */

jest.mock("@/lib/db/client", () => ({
  db: { execute: jest.fn() },
}));

import { checkAndIncrementTraceQuota, FREE_LIMITS } from "../quota";
import { db } from "@/lib/db/client";

const mockExecute = db.execute as jest.Mock;

beforeEach(() => {
  jest.resetAllMocks();
});

describe("checkAndIncrementTraceQuota", () => {
  it("paid plan: returns ok without incrementing", async () => {
    mockExecute.mockResolvedValue({
      rows: [
        {
          traces_used: 500,
          plan: "paid",
          chunks_stored: 0,
          repos_connected: 0,
        },
      ],
    });

    const result = await checkAndIncrementTraceQuota("user-1");

    expect(result).toEqual({ status: "ok", tracesUsed: 500 });
    // Only getOrCreateQuota is called — no increment execute
    expect(mockExecute).toHaveBeenCalledTimes(1);
  });

  it("free plan, exceeded: returns exceeded without incrementing", async () => {
    mockExecute.mockResolvedValue({
      rows: [
        {
          traces_used: FREE_LIMITS.traces, // 1000
          plan: "free",
          chunks_stored: 0,
          repos_connected: 0,
        },
      ],
    });

    const result = await checkAndIncrementTraceQuota("user-1");

    expect(result).toEqual({
      status: "exceeded",
      tracesUsed: FREE_LIMITS.traces,
    });
    expect(mockExecute).toHaveBeenCalledTimes(1);
  });

  it("free plan, 80% threshold: returns warning and increments", async () => {
    // traces_used = 800, newCount = 801, pct = 0.801 >= 0.8 → warning
    mockExecute
      .mockResolvedValueOnce({
        rows: [
          {
            traces_used: 800,
            plan: "free",
            chunks_stored: 0,
            repos_connected: 0,
          },
        ],
      })
      .mockResolvedValueOnce({ rows: [] }); // increment INSERT call

    const result = await checkAndIncrementTraceQuota("user-1");

    expect(result).toEqual({ status: "warning", tracesUsed: 801 });
    expect(mockExecute).toHaveBeenCalledTimes(2);
  });

  it("free plan, under 80%: returns ok and increments", async () => {
    // traces_used = 10, newCount = 11, pct = 0.011 < 0.8 → ok
    mockExecute
      .mockResolvedValueOnce({
        rows: [
          {
            traces_used: 10,
            plan: "free",
            chunks_stored: 0,
            repos_connected: 0,
          },
        ],
      })
      .mockResolvedValueOnce({ rows: [] }); // increment INSERT call

    const result = await checkAndIncrementTraceQuota("user-1");

    expect(result).toEqual({ status: "ok", tracesUsed: 11 });
    expect(mockExecute).toHaveBeenCalledTimes(2);
  });
});
