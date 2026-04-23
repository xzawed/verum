import { NextResponse } from "next/server";
import { validateApiKey } from "@/lib/api/validateApiKey";
import { db } from "@/lib/db/client";
import { sql } from "drizzle-orm";
import OpenAI from "openai";

let _openai: OpenAI | null = null;
function getOpenAI() {
  if (!_openai) _openai = new OpenAI();
  return _openai;
}

export async function POST(req: Request) {
  const apiKey = req.headers.get("x-verum-api-key") ?? "";
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

  const topK = typeof body.top_k === "number" ? Math.min(body.top_k, 20) : 5;

  const embeddingRes = await getOpenAI().embeddings.create({
    model: "text-embedding-3-small",
    input: body.query,
  });
  const vec = embeddingRes.data[0]?.embedding;
  if (!vec) return new Response("embedding failed", { status: 500 });

  // vec is float[] from OpenAI — safe to stringify as a numeric literal list.
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
