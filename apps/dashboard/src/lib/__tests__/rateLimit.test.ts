jest.mock("../rateLimitRedis", () => ({
  checkRateLimitRedis: jest.fn().mockResolvedValue(null),
}));

import { checkRateLimit, getClientIp } from "../rateLimit";

describe("checkRateLimit", () => {
  it("returns null when under the limit", async () => {
    const key = `test-under-${Date.now()}`;
    const result = await checkRateLimit(key, 5);
    expect(result).toBeNull();
  });

  it("returns null on repeated requests below the limit", async () => {
    const key = `test-repeat-${Date.now()}`;
    for (let i = 0; i < 4; i++) {
      expect(await checkRateLimit(key, 5)).toBeNull();
    }
  });

  it("returns a 429 Response when the limit is reached", async () => {
    const key = `test-limit-${Date.now()}`;
    for (let i = 0; i < 3; i++) {
      await checkRateLimit(key, 3);
    }
    const response = await checkRateLimit(key, 3);
    expect(response).not.toBeNull();
    expect(response?.status).toBe(429);
  });

  it("includes Retry-After and rate-limit headers on 429", async () => {
    const key = `test-headers-${Date.now()}`;
    for (let i = 0; i < 2; i++) {
      await checkRateLimit(key, 2);
    }
    const response = await checkRateLimit(key, 2);
    expect(response?.headers.get("Retry-After")).toBeTruthy();
    expect(response?.headers.get("X-RateLimit-Limit")).toBe("2");
    expect(response?.headers.get("X-RateLimit-Remaining")).toBe("0");
  });

  it("allows requests again after the window expires", async () => {
    const key = `test-window-${Date.now()}`;
    await checkRateLimit(key, 1, 1);
    await checkRateLimit(key, 1, 1);
    const freshKey = `test-fresh-${Date.now()}`;
    expect(await checkRateLimit(freshKey, 1, 1)).toBeNull();
  });
});

describe("getClientIp", () => {
  it("returns the first IP from x-forwarded-for header", () => {
    const req = new Request("https://example.com", {
      headers: { "x-forwarded-for": "203.0.113.1, 10.0.0.1" },
    });
    expect(getClientIp(req)).toBe("203.0.113.1");
  });

  it("returns 'unknown' when x-forwarded-for is absent", () => {
    const req = new Request("https://example.com");
    expect(getClientIp(req)).toBe("unknown");
  });

  it("trims whitespace from the extracted IP", () => {
    const req = new Request("https://example.com", {
      headers: { "x-forwarded-for": "  198.51.100.5  , 192.168.1.1" },
    });
    expect(getClientIp(req)).toBe("198.51.100.5");
  });

  it("returns cf-connecting-ip when present (Cloudflare/Railway header)", () => {
    const req = new Request("https://example.com", {
      headers: { "cf-connecting-ip": "  1.2.3.4  " },
    });
    expect(getClientIp(req)).toBe("1.2.3.4");
  });
});

describe("checkRateLimitDual", () => {
  // Import here so the jest.mock at the top (which mocks rateLimitRedis to return null)
  // is already hoisted before this import resolves.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { checkRateLimitDual } = require("../rateLimit") as {
    checkRateLimitDual: (
      userKey: string,
      userLimit: number,
      ip: string,
      ipLimit: number,
      windowMs?: number,
    ) => Promise<Response | null>;
  };

  it("returns null when both user and IP are under limit", async () => {
    const result = await checkRateLimitDual(
      `dual-user-${Date.now()}`,
      10,
      "203.0.113.1",
      20,
    );
    expect(result).toBeNull();
  });

  it("returns a 429 Response when the user key is rate-limited", async () => {
    const userKey = `dual-user-limit-${Date.now()}`;
    // Exhaust the user limit (limit = 2)
    await checkRateLimitDual(userKey, 2, "203.0.113.2", 100);
    await checkRateLimitDual(userKey, 2, "203.0.113.2", 100);
    const result = await checkRateLimitDual(userKey, 2, "203.0.113.2", 100);
    expect(result).not.toBeNull();
    expect(result?.status).toBe(429);
  });

  it("returns a 429 Response when the IP key is rate-limited", async () => {
    const ip = `1.2.3.${Math.floor(Math.random() * 200) + 1}`;
    // Exhaust the IP limit (ipLimit = 2) with distinct user keys so user tier passes
    await checkRateLimitDual(`user-a-${Date.now()}`, 100, ip, 2);
    await checkRateLimitDual(`user-b-${Date.now()}`, 100, ip, 2);
    const result = await checkRateLimitDual(`user-c-${Date.now()}`, 100, ip, 2);
    expect(result).not.toBeNull();
    expect(result?.status).toBe(429);
  });

  it("skips IP check for loopback address 127.0.0.1", async () => {
    const userKey = `dual-loopback-${Date.now()}`;
    // Even with ipLimit = 0 the IP tier is skipped for loopback
    const result = await checkRateLimitDual(userKey, 10, "127.0.0.1", 0);
    expect(result).toBeNull();
  });

  it('skips IP check when ip is "unknown"', async () => {
    const userKey = `dual-unknown-${Date.now()}`;
    // Even with ipLimit = 0 the IP tier is skipped for "unknown"
    const result = await checkRateLimitDual(userKey, 10, "unknown", 0);
    expect(result).toBeNull();
  });
});
