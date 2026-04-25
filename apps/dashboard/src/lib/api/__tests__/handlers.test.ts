jest.mock("@/auth", () => ({
  auth: jest.fn(),
}));

jest.mock("@/lib/rateLimit", () => ({
  checkRateLimitDual: jest.fn(),
  getClientIp: jest.fn(),
}));

import { getAuthUserId, createGetByIdHandler } from "../handlers";
import { auth } from "@/auth";
import { checkRateLimitDual, getClientIp } from "@/lib/rateLimit";

const mockAuth = auth as jest.MockedFunction<typeof auth>;
const mockCheckRateLimitDual = checkRateLimitDual as jest.MockedFunction<
  typeof checkRateLimitDual
>;
const mockGetClientIp = getClientIp as jest.MockedFunction<typeof getClientIp>;

function makeRequest(url = "http://localhost/api/v1/resource"): Request {
  return new Request(url, { method: "GET" });
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("getAuthUserId", () => {
  it("returns null when auth returns no session", async () => {
    mockAuth.mockResolvedValue(null as never);
    expect(await getAuthUserId()).toBeNull();
  });

  it("returns null when session has no user", async () => {
    mockAuth.mockResolvedValue({ user: undefined } as never);
    expect(await getAuthUserId()).toBeNull();
  });

  it("returns userId string when session has a user with id", async () => {
    mockAuth.mockResolvedValue({ user: { id: "user-123" } } as never);
    expect(await getAuthUserId()).toBe("user-123");
  });

  it("returns null when session user id is empty string", async () => {
    mockAuth.mockResolvedValue({ user: { id: "" } } as never);
    expect(await getAuthUserId()).toBeNull();
  });
});

describe("createGetByIdHandler", () => {
  it("returns 401 when not authenticated", async () => {
    mockAuth.mockResolvedValue(null as never);
    const handler = createGetByIdHandler(jest.fn());
    const res = await handler(makeRequest(), { params: Promise.resolve({ id: "abc" }) });
    expect(res.status).toBe(401);
  });

  it("returns rate limit response when rate limited", async () => {
    mockAuth.mockResolvedValue({ user: { id: "user-1" } } as never);
    mockGetClientIp.mockReturnValue("1.2.3.4");
    const limitResponse = new Response("Too Many Requests", { status: 429 });
    mockCheckRateLimitDual.mockResolvedValue(limitResponse);

    const handler = createGetByIdHandler(jest.fn());
    const res = await handler(makeRequest(), { params: Promise.resolve({ id: "abc" }) });
    expect(res.status).toBe(429);
  });

  it("returns 404 when queryFn returns null", async () => {
    mockAuth.mockResolvedValue({ user: { id: "user-1" } } as never);
    mockGetClientIp.mockReturnValue("1.2.3.4");
    mockCheckRateLimitDual.mockResolvedValue(null);

    const queryFn = jest.fn().mockResolvedValue(null);
    const handler = createGetByIdHandler(queryFn);
    const res = await handler(makeRequest(), { params: Promise.resolve({ id: "item-1" }) });
    expect(res.status).toBe(404);
    expect(queryFn).toHaveBeenCalledWith("user-1", "item-1");
  });

  it("returns 200 JSON when queryFn returns data", async () => {
    mockAuth.mockResolvedValue({ user: { id: "user-1" } } as never);
    mockGetClientIp.mockReturnValue("1.2.3.4");
    mockCheckRateLimitDual.mockResolvedValue(null);

    const data = { id: "item-1", name: "Test" };
    const queryFn = jest.fn().mockResolvedValue(data);
    const handler = createGetByIdHandler(queryFn);
    const res = await handler(makeRequest(), { params: Promise.resolve({ id: "item-1" }) });

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json).toEqual(data);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
  });
});
