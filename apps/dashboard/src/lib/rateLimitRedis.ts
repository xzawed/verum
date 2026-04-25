/**
 * Redis-backed sliding-window rate limiter.
 *
 * Uses an atomic Lua script to implement a precise sliding window:
 *   1. Remove entries older than (now - windowMs)
 *   2. Count remaining entries
 *   3. If under limit, add a new timestamped entry and return allowed
 *   4. If at/over limit, return denied with retry-after in ms
 *
 * Falls back to null (in-memory fallback activates) on any Redis error
 * or when REDIS_URL is not configured.
 */
import Redis from "ioredis";

const SLIDING_WINDOW_LUA = `
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local cutoff = now - window_ms

redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
local count = redis.call('ZCARD', key)

if count >= limit then
  local arr = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local oldest_score = tonumber(arr[2] or now)
  return {0, oldest_score + window_ms - now, count}
end

local t = redis.call('TIME')
redis.call('ZADD', key, now, t[1] .. '.' .. t[2])
redis.call('PEXPIRE', key, window_ms)
return {1, 0, count + 1}
`;

let _redis: Redis | null = null;
let _connected = false;

function getRedis(): Redis | null {
  const url = process.env.REDIS_URL;
  if (!url) return null;

  if (_redis) return _connected ? _redis : null;

  _redis = new Redis(url, {
    lazyConnect: true,
    enableOfflineQueue: false,
    maxRetriesPerRequest: 0,
    connectTimeout: 1000,
  });
  _redis.on("connect", () => {
    _connected = true;
  });
  _redis.on("error", () => {
    _connected = false;
  });
  // Fire-and-forget: first call always falls back to in-memory while connecting.
  _redis.connect().catch(() => {});
  return null;
}

export interface RedisRateLimitResult {
  allowed: boolean;
  retryAfterMs: number;
  count: number;
}

/**
 * Atomic sliding-window check via Redis Lua script.
 *
 * @returns Result object, or null if Redis is unavailable (caller should fall back).
 */
export async function checkRateLimitRedis(
  key: string,
  limit: number,
  windowMs: number,
): Promise<RedisRateLimitResult | null> {
  const redis = getRedis();
  if (!redis) return null;

  try {
    const raw = (await redis.eval(
      SLIDING_WINDOW_LUA,
      1,
      `rl:${key}`,
      String(Date.now()),
      String(windowMs),
      String(limit),
    )) as [number, number, number];

    return {
      allowed: raw[0] === 1,
      retryAfterMs: Math.max(0, raw[1]),
      count: raw[2],
    };
  } catch {
    return null;
  }
}
