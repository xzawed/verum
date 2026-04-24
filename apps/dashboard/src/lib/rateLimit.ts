/**
 * In-memory sliding-window rate limiter.
 * For high-traffic deployments, replace with Redis-backed implementation.
 */

interface Window {
  timestamps: number[];
}

const store = new Map<string, Window>();

/**
 * Check rate limit for a given key.
 *
 * @param key     Unique identifier (user ID or IP address)
 * @param limit   Maximum requests allowed in the window
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

  // Slide: drop timestamps outside the window
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

/** Extract best-effort client IP from a Next.js Request. */
export function getClientIp(req: Request): string {
  const forwarded = (req as unknown as { headers: Headers }).headers.get(
    "x-forwarded-for",
  );
  return forwarded ? forwarded.split(",")[0].trim() : "unknown";
}
