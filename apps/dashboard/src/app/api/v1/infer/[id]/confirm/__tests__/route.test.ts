jest.mock("@/lib/api/handlers", () => ({ getAuthUserId: jest.fn() }));
jest.mock("@/lib/db/jobs", () => ({
  confirmInference: jest.fn(),
}));

import { PATCH } from "../route";
import { getAuthUserId } from "@/lib/api/handlers";
import { confirmInference } from "@/lib/db/jobs";

const mockGetAuthUserId = getAuthUserId as jest.MockedFunction<typeof getAuthUserId>;
const mockConfirmInference = confirmInference as jest.MockedFunction<typeof confirmInference>;

function makeRequest(body: unknown): Request {
  return new Request("http://localhost/api/v1/infer/inf-1/confirm", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function makeParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("PATCH /api/v1/infer/[id]/confirm", () => {
  it("returns 401 when not authenticated", async () => {
    mockGetAuthUserId.mockResolvedValue(null);

    const res = await PATCH(makeRequest({}), makeParams("inf-1"));

    expect(res.status).toBe(401);
  });

  it("returns 401 when session has no user id", async () => {
    mockGetAuthUserId.mockResolvedValue(null);

    const res = await PATCH(makeRequest({}), makeParams("inf-1"));

    expect(res.status).toBe(401);
  });

  it("returns 404 when inference is not found", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockConfirmInference.mockResolvedValue(null);

    const res = await PATCH(makeRequest({}), makeParams("inf-missing"));

    expect(res.status).toBe(404);
  });

  it("returns 200 with updated inference on success", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");
    const updatedInference = {
      id: "inf-1",
      domain: "tarot_divination",
      tone: "mystical",
      language: "ko",
      user_type: "consumer",
      status: "confirmed",
    };
    mockConfirmInference.mockResolvedValue(updatedInference as any);

    const res = await PATCH(
      makeRequest({ domain: "tarot_divination", tone: "mystical" }),
      makeParams("inf-1"),
    );

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json).toMatchObject({ id: "inf-1", domain: "tarot_divination" });
  });

  it("passes overrides correctly to confirmInference", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockConfirmInference.mockResolvedValue({ id: "inf-1" } as any);

    await PATCH(
      makeRequest({ domain: "code_review", language: "en", user_type: null }),
      makeParams("inf-1"),
    );

    expect(mockConfirmInference).toHaveBeenCalledWith(
      "user-1",
      "inf-1",
      expect.objectContaining({ domain: "code_review", language: "en", user_type: null }),
    );
  });
});
