import { NextResponse } from "next/server";
import { db } from "@/lib/db/client";
import { getWorkerAlive } from "@/lib/db/queries";
import { sql } from "drizzle-orm";

export const dynamic = "force-dynamic";

export async function GET() {
  let dbStatus = "disconnected";
  let workerAlive = false;

  try {
    await db.execute(sql`SELECT 1`);
    dbStatus = "connected";
    workerAlive = await getWorkerAlive();
  } catch {
    // fall through with defaults
  }

  const healthy = dbStatus === "connected";
  return NextResponse.json(
    { status: healthy ? "ok" : "degraded", db: dbStatus, worker: workerAlive ? "alive" : "unreachable" },
    { status: healthy ? 200 : 503 },
  );
}
