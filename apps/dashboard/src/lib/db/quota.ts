import { sql } from "drizzle-orm";
import { db } from "./client";

export const FREE_LIMITS = {
  traces: 1_000,
  chunks: 10_000,
  repos: 3,
} as const;

type QuotaRow = {
  traces_used: number;
  chunks_stored: number;
  repos_connected: number;
  plan: string;
};

function currentPeriod(): string {
  const today = new Date();
  return new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split("T")[0];
}

async function getOrCreateQuota(userId: string): Promise<QuotaRow> {
  const period = currentPeriod();
  const result = await db.execute(
    sql`INSERT INTO usage_quotas (user_id, period_start)
        VALUES (${userId}::uuid, ${period}::date)
        ON CONFLICT (user_id, period_start) DO UPDATE
          SET updated_at = now()
        RETURNING traces_used, chunks_stored, repos_connected, plan`
  );
  return result.rows[0] as QuotaRow;
}

export async function checkAndIncrementTraceQuota(
  userId: string
): Promise<{ status: "ok" | "exceeded" | "warning"; tracesUsed: number }> {
  const quota = await getOrCreateQuota(userId);

  if (quota.plan !== "free") {
    return { status: "ok", tracesUsed: quota.traces_used };
  }

  if (quota.traces_used >= FREE_LIMITS.traces) {
    return { status: "exceeded", tracesUsed: quota.traces_used };
  }

  const period = currentPeriod();
  await db.execute(
    sql`INSERT INTO usage_quotas (user_id, period_start, traces_used)
        VALUES (${userId}::uuid, ${period}::date, 1)
        ON CONFLICT (user_id, period_start) DO UPDATE
          SET traces_used = usage_quotas.traces_used + 1,
              updated_at = now()`
  );

  const newCount = quota.traces_used + 1;
  const pct = newCount / FREE_LIMITS.traces;
  return {
    status: pct >= 0.8 ? "warning" : "ok",
    tracesUsed: newCount,
  };
}
