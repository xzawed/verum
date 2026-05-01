import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { db } from "@/lib/db/client";
import { sql } from "drizzle-orm";
import { FREE_LIMITS } from "@/lib/db/quota";

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const today = new Date();
  const periodStart = new Date(today.getFullYear(), today.getMonth(), 1)
    .toISOString()
    .split("T")[0];

  const rows = await db.execute(
    sql`SELECT traces_used, chunks_stored, repos_connected, plan
        FROM usage_quotas
        WHERE user_id = ${session.user.id}
          AND period_start = ${periodStart}::date
        LIMIT 1`
  );

  const quota = rows.rows[0] as
    | { traces_used: number; chunks_stored: number; repos_connected: number; plan: string }
    | undefined;

  return NextResponse.json({
    plan: quota?.plan ?? "free",
    period: periodStart,
    limits: FREE_LIMITS,
    used: {
      traces: quota?.traces_used ?? 0,
      chunks: quota?.chunks_stored ?? 0,
      repos: quota?.repos_connected ?? 0,
    },
  });
}
