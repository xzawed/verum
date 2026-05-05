jest.mock("@/lib/rateLimit", () => ({
  checkRateLimitDual: jest.fn().mockResolvedValue(null),
  getClientIp: jest.fn().mockReturnValue("127.0.0.1"),
}));
jest.mock("@/lib/api/validateApiKey", () => ({
  validateApiKey: jest.fn(),
}));
jest.mock("@/lib/db/jobs", () => ({
  updateFeedback: jest.fn(),
}));

import { POST } from "../route";
import { validateApiKey } from "@/lib/api/validateApiKey";
import { updateFeedback } from "@/lib/db/jobs";

const mockValidateApiKey = validateApiKey as jest.MockedFunction<typeof validateApiKey>;
const mockUpdateFeedback = updateFeedback as jest.MockedFunction<typeof updateFeedback>;

function makeRequest(
  body: unknown,
  headers: Record<string, string> = {},
): Request {
  return new Request("http://localhost/api/v1/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("POST /api/v1/feedback", () => {
  it("returns 401 when x-verum-api-key header is missing", async () => {
    const req = makeRequest({ trace_id: "trace-1", score: 1 });
    const res = await POST(req);
    expect(res.status).toBe(401);
    // validateApiKey should never be called — the route short-circuits on empty key
    expect(mockValidateApiKey).not.toHaveBeenCalled();
  });

  it("returns 400 when required fields are missing or score is invalid", async () => {
    mockValidateApiKey.mockResolvedValueOnce({
      deploymentId: "dep-1",
      userId: "user-1",
    });

    // score of 0 is neither 1 nor -1
    const req = makeRequest(
      { trace_id: "trace-1", score: 0 },
      { "x-verum-api-key": "a".repeat(41) },
    );
    const res = await POST(req);
    expect(res.status).toBe(400);
  });

  it("returns 204 on success", async () => {
    mockValidateApiKey.mockResolvedValueOnce({
      deploymentId: "dep-1",
      userId: "user-1",
    });
    mockUpdateFeedback.mockResolvedValueOnce(true as never);

    const req = makeRequest(
      { trace_id: "00000000-0000-4000-8000-000000000002", score: 1 },
      { "x-verum-api-key": "a".repeat(41) },
    );
    const res = await POST(req);
    expect(res.status).toBe(204);
    expect(mockUpdateFeedback).toHaveBeenCalledWith("dep-1", "00000000-0000-4000-8000-000000000002", 1);
  });
});
