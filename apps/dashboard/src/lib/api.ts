/**
 * Server-side fetch helper for Verum API.
 *
 * All calls go through server components / server actions so the JWT never
 * reaches the browser. CORS is not needed as a result.
 */
import { encode } from "next-auth/jwt";
import { auth } from "@/auth";

const API_URL = process.env.VERUM_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function getBearer(): Promise<string> {
  const session = await auth();
  if (!session?.user) throw new ApiError(401, "Not authenticated");

  // Re-encode the session claims as a JWE that FastAPI can verify with
  // the same NEXTAUTH_SECRET / AUTH_SECRET.
  const token = await encode({
    token: {
      sub: (session.user as { id?: string }).id ?? "",
      name: session.user.name ?? null,
      email: session.user.email ?? null,
      picture: session.user.image ?? null,
      github_login:
        (session.user as { github_login?: string }).github_login ?? null,
    },
    secret: process.env.AUTH_SECRET!,
    salt: "authjs.session-token",
  });
  return token;
}

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const bearer = await getBearer();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
      Authorization: `Bearer ${bearer}`,
    },
    cache: "no-store",
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore parse error
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}
