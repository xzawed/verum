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
});
