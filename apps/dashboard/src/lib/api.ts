/**
 * Server-side fetch helper for Verum API.
 *
 * FastAPI lives on Railway's internal network and is not reachable from the
 * public internet. This helper runs only in server components/actions, so the
 * shared INTERNAL token never leaves the dashboard server process.
 */
import { auth } from "@/auth";

const API_URL = process.env.VERUM_API_URL ?? "http://localhost:8000";
const INTERNAL_TOKEN = process.env.VERUM_INTERNAL_API_TOKEN ?? "";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const session = await auth();
  if (!session?.user) throw new ApiError(401, "Not authenticated");

  const u = session.user as Record<string, unknown>;
  const userId = String(u.id ?? "");
  if (!userId) throw new ApiError(401, "Session missing user id");

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Verum-Internal-Token": INTERNAL_TOKEN,
      "X-Verum-User-Id": userId,
      "X-Verum-User-Login": String(u.github_login ?? ""),
      "X-Verum-User-Email": session.user.email ?? "",
      ...init.headers,
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
