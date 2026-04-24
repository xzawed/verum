import { z } from "zod";
import { getAuthUserId } from "@/lib/api/handlers";
import { checkRateLimit } from "@/lib/rateLimit";
import { createRepo } from "@/lib/db/jobs";
import { getRepos } from "@/lib/db/queries";

const CreateRepoSchema = z.object({
  repo_url: z.string().url("repo_url must be a valid URL"),
  branch: z.string().optional(),
});

export async function GET() {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });
  const data = await getRepos(uid);
  return Response.json(data, { headers: { "Cache-Control": "no-store" } });
}

export async function POST(req: Request) {
  const uid = await getAuthUserId();
  if (!uid) return new Response("unauthorized", { status: 401 });
  const rateLimitResponse = checkRateLimit(uid, 20);
  if (rateLimitResponse) return rateLimitResponse;
  const parsed = CreateRepoSchema.safeParse(await req.json());
  if (!parsed.success) {
    return Response.json({ error: parsed.error.flatten() }, { status: 400 });
  }
  const body = parsed.data;
  const repo = await createRepo(uid, body.repo_url, body.branch);
  return Response.json(repo, { status: 201, headers: { "Cache-Control": "no-store" } });
}
