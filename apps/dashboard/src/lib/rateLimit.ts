/**
 * In-memory sliding-window rate limiter.
 *
 * Supports two independent limit tiers per request:
 *   1. Per-user or per-API-key limit (primary)
 *   2. Per-IP limit (secondary, bot / credential-stuffing guard)
 *
 * For high-traffic deployments, replace with a Redis-backed implementation.
 * The interface is identical — swap the store and the Map for a Redis client.
 */

interface Window {
  timestamps: number[];
}

const store = new Map<string, Window>();

/**
 * Check rate limit for a given key (sliding window).
 *
 * @param key      Unique identifier (user ID, deployment ID, or IP address)
 * @param limit    Maximum requests allowed in the window
 * @param windowMs Window size in milliseconds (default: 60_000 = 1 minute)
 * @returns null if allowed, or a 429 Response if rate-limited
 */
export function checkRateLimit(
  key: string,
  limit: number,
  windowMs = 60_000,
): Response | null {
  const now = Date.now();
  const cutoff = now - windowMs;

  let entry = store.get(key);
  if (!entry) {
    entry = { timestamps: [] };
    store.set(key, entry);
  }

  entry.timestamps = entry.timestamps.filter((t) => t > cutoff);

  if (entry.timestamps.length >= limit) {
    const oldest = entry.timestamps[0];
    const retryAfterMs = oldest + windowMs - now;
    const retryAfterSec = Math.ceil(retryAfterMs / 1000);
    return Response.json(
      { error: "Too many requests" },
      {
        status: 429,
        headers: {
          "Retry-After": String(retryAfterSec),
          "X-RateLimit-Limit": String(limit),
          "X-RateLimit-Remaining": "0",
          "X-RateLimit-Reset": String(Math.ceil((oldest + windowMs) / 1000)),
        },
      },
    );
  }

  entry.timestamps.push(now);
  return null;
}

/**
 * Apply two rate limit tiers in one call: user/key tier first, then IP tier.
 *
 * Use this for endpoints that need bot protection in addition to per-user limits.
 * Either tier can independently reject the request.
 *
 * @param userKey   User ID or deployment/API key identifier
 * @param userLimit Max requests per user per window
 * @param ip        Client IP address (from getClientIp)
 * @param ipLimit   Max requests per IP per window (should be larger than userLimit
 *                  to allow multiple users behind the same corporate NAT)
 * @param windowMs  Shared window size for both tiers
 */
export function checkRateLimitDual(
  userKey: string,
  userLimit: number,
  ip: string,
  ipLimit: number,
  windowMs = 60_000,
): Response | null {
  const userResult = checkRateLimit(`u:${userKey}`, userLimit, windowMs);
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
