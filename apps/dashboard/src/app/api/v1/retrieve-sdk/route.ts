import { NextResponse } from "next/server";
import { validateApiKey } from "@/lib/api/validateApiKey";
import { checkRateLimitDual, getClientIp } from "@/lib/rateLimit";
import { db } from "@/lib/db/client";
import { sql } from "drizzle-orm";

export async function POST(req: Request) {
  const apiKey = req.headers.get("x-verum-api-key") ?? "";

  // IP-level gate before expensive DB look-up: 60 retrievals/min per key, 100 per IP.
  const ip = getClientIp(req);
  const ipGate = await checkRateLimitDual(apiKey.slice(0, 16), 60, ip, 100);
  if (ipGate) return ipGate;

  const keyResult = await validateApiKey(apiKey);
  if (!keyResult) return new Response("unauthorized", { status: 401 });

  const body = await req.json() as {
    query?: unknown;
    collection_name?: unknown;
    top_k?: unknown;
  };

  if (typeof body.query !== "string" || !body.query) {
    return new Response("query required", { status: 400 });
  }
  if (body.query.length > 2000) {
    return new Response("query too long (max 2000 chars)", { status: 400 });
  }

  const topK = typeof body.top_k === "number" ? Math.min(body.top_k, 20) : 5;

  const embResp = await fetch("https://api.voyageai.com/v1/embeddings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.VOYAGE_API_KEY}`,
    },
    body: JSON.stringify({ input: [body.query], model: "voyage-3.5" }),
  });
  if (!embResp.ok) {
    return NextResponse.json({ error: "embedding failed" }, { status: 502 });
  }
  const embData = await embResp.json() as { data: { embedding: number[] }[] };
  const vec = embData.data[0]?.embedding;
  if (!vec) return new Response("embedding failed", { status: 500 });

  // vec is float[] (1024-dim voyage-3.5) — safe to stringify as a numeric literal list.
  const vecLiteral = `[${vec.map((v) => Number(v).toFixed(8)).join(",")}]`;

  const rows = await db.execute(
    sql`SELECT id, content, metadata,
               1 - (embedding_vec <=> ${vecLiteral}::vector) AS score
        FROM chunks
        WHERE embedding_vec IS NOT NULL
        ORDER BY embedding_vec <=> ${vecLiteral}::vector
        LIMIT ${topK}`
  );

  const chunks = (
    rows.rows as Array<{ id: string; content: string; metadata: unknown; score: number }>
  ).map((r) => ({ content: r.content, score: r.score, metadata: r.metadata ?? {} }));

  return NextResponse.json({ chunks }, { headers: { "Cache-Control": "no-store" } });
}
