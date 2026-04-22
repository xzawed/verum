import { auth } from "@/auth";
import { confirmInference } from "@/lib/db/jobs";
import { NextRequest, NextResponse } from "next/server";

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const session = await auth();
  if (!session?.user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const uid = String((session.user as Record<string, unknown>).id ?? "");
  if (!uid) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  let body: Record<string, unknown> = {};
  try {
    body = await req.json();
  } catch {
    // empty body is fine — no overrides
  }

  const overrides: {
    domain?: string | null;
    tone?: string | null;
    language?: string | null;
    user_type?: string | null;
  } = {};
  if (typeof body.domain === "string" || body.domain === null) overrides.domain = body.domain as string | null;
  if (typeof body.tone === "string" || body.tone === null) overrides.tone = body.tone as string | null;
  if (typeof body.language === "string" || body.language === null) overrides.language = body.language as string | null;
  if (typeof body.user_type === "string" || body.user_type === null) overrides.user_type = body.user_type as string | null;

  const updated = await confirmInference(uid, params.id, overrides);
  if (!updated) return NextResponse.json({ error: "Not found" }, { status: 404 });

  return NextResponse.json(updated);
}
