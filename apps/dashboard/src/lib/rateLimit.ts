/**
 * Sliding-window rate limiter: Redis-first with in-memory fallback.
 *
 * When REDIS_URL is set and Redis is reachable, all counters are stored in Redis
 * so limits are shared across multiple Next.js instances. When Redis is
 * unavailable, the in-memory store is used transparently — per-instance limits,
 * but never a hard failure.
 *
 * In-memory store is safe for single-instance (Railway free tier / local dev).
 */
import { checkRateLimitRedis } from "./rateLimitRedis";

interface Window {
  timestamps: number[];
}

const store = new Map<string, Window>();

// Evict entries whose last activity is older than 2× the default window (2 min).
// Called on 1% of requests to bound Map size without per-request overhead.
function _maybeEvict(): void {
  if (Math.random() > 0.01) return;
  const staleAfter = Date.now() - 120_000;
  for (const [key, entry] of store) {
    const last = entry.timestamps[entry.timestamps.length - 1];
    if (last === undefined || last < staleAfter) store.delete(key);
  }
}

function _buildResponse(
  limit: number,
  retryAfterMs: number,
  resetAtMs: number,
): Response {
  const retryAfterSec = Math.ceil(retryAfterMs / 1000);
  return Response.json(
    { error: "Too many requests" },
    {
      status: 429,
      headers: {
        "Retry-After": String(retryAfterSec),
        "X-RateLimit-Limit": String(limit),
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": String(Math.ceil(resetAtMs / 1000)),
      },
    },
  );
}

/**
 * Check rate limit for a given key (sliding window).
 *
 * @param key      Unique identifier (user ID, deployment ID, or IP address)
 * @param limit    Maximum requests allowed in the window
 * @param windowMs Window size in milliseconds (default: 60_000 = 1 minute)
 * @returns null if allowed, or a 429 Response if rate-limited
 */
export async function checkRateLimit(
  key: string,
  limit: number,
  windowMs = 60_000,
): Promise<Response | null> {
  // ── Redis path ────────────────────────────────────────────────────────────
  const redisResult = await checkRateLimitRedis(key, limit, windowMs);
  if (redisResult !== null) {
    if (!redisResult.allowed) {
      return _buildResponse(
        limit,
        redisResult.retryAfterMs,
        Date.now() + redisResult.retryAfterMs,
      );
    }
    return null;
  }

  // ── In-memory fallback ────────────────────────────────────────────────────
  const now = Date.now();
  const cutoff = now - windowMs;

  _maybeEvict();

  let entry = store.get(key);
  if (!entry) {
    entry = { timestamps: [] };
    store.set(key, entry);
  }

  entry.timestamps = entry.timestamps.filter((t) => t > cutoff);

  if (entry.timestamps.length >= limit) {
    const oldest = entry.timestamps[0];
    const retryAfterMs = oldest + windowMs - now;
    return _buildResponse(limit, retryAfterMs, oldest + windowMs);
  }

  entry.timestamps.push(now);
  return null;
}

/**
 * Apply two rate limit tiers in one call: user/key tier first, then IP tier.
 *
 * Either tier can independently reject the request.
 *
 * @param userKey   User ID or deployment/API key identifier
 * @param userLimit Max requests per user per window
 * @param ip        Client IP address (from getClientIp)
 * @param ipLimit   Max requests per IP per window
 * @param windowMs  Shared window size for both tiers
 */
export async function checkRateLimitDual(
  userKey: string,
  userLimit: number,
  ip: string,
  ipLimit: number,
  windowMs = 60_000,
): Promise<Response | null> {
  const userResult = await checkRateLimit(`u:${userKey}`, userLimit, windowMs);
  if (userResult) return userResult;
  // Skip IP tier for loopback addresses to avoid blocking local dev/tests.
  if (ip && ip !== "unknown" && ip !== "127.0.0.1" && ip !== "::1") {
    return checkRateLimit(`ip:${ip}`, ipLimit, windowMs);
  }
  return null;
}

/** Extract best-effort client IP from a Next.js Request. */
export function getClientIp(req: Request): string {
  const headers = (req as unknown as { headers: Headers }).headers;
  // Railway / Cloudflare set CF-Connecting-IP; fall back to x-forwarded-for.
  const cf = headers.get("cf-connecting-ip");
  if (cf) return cf.trim();
  const forwarded = headers.get("x-forwarded-for");
  return forwarded ? forwarded.split(",")[0].trim() : "unknown";
}
