import { z } from "zod";
import { getAuthUserId } from "@/lib/api/handlers";
import { checkRateLimitDual, getClientIp } from "@/lib/rateLimit";
import { createRepo } from "@/lib/db/jobs";
import { getRepos } from "@/lib/db/queries";

// Only GitHub HTTPS URLs are accepted — mirrors cloner.py _GITHUB_URL_RE.
const GITHUB_URL_RE = /^https:\/\/github\.com\/[\w.\-]+\/[\w.\-]+(\.git)?$/;

// In test mode the integration stack uses an internal git-http Docker service
// URL (e.g. http://git-http/...) — skip the github.com guard in that case.
/* istanbul ignore next */
const repoUrlSchema =
  process.env.VERUM_TEST_MODE === "1"
    ? z.string().url("repo_url must be a valid URL")
    : z
        .string()
        .url("repo_url must be a valid URL")
        .refine((v) => GITHUB_URL_RE.test(v), {
          message: "repo_url must be a github.com HTTPS URL",
        });

const CreateRepoSchema = z.object({
  repo_url: repoUrlSchema,
  branch: z
    .string()
    .regex(/^[a-zA-Z0-9._/\-]{1,200}$/, "branch contains invalid characters")
    .optional(),
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

  // 5 registrations per user per minute; 20 per IP per minute.
  // Bots registering many repos from the same IP hit the IP tier first.
  const ip = getClientIp(req);
  const rateLimitResponse = await checkRateLimitDual(uid, 5, ip, 20);
  if (rateLimitResponse) return rateLimitResponse;

  const parsed = CreateRepoSchema.safeParse(await req.json());
  if (!parsed.success) {
    return Response.json({ error: parsed.error.flatten() }, { status: 400 });
  }
  const body = parsed.data;
  const repo = await createRepo(uid, body.repo_url, body.branch);
  return Response.json(repo, { status: 201, headers: { "Cache-Control": "no-store" } });
}
