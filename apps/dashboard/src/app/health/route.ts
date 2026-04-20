import { NextResponse } from "next/server";

// Pure liveness probe — no DB or worker I/O.
// DB/worker health should be checked via a separate /api/status route with auth.
export async function GET() {
  return NextResponse.json({ status: "ok" }, { status: 200 });
}
