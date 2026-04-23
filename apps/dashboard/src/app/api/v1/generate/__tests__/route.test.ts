jest.mock("@/lib/api/handlers", () => ({
  getAuthUserId: jest.fn(),
  createGetByIdHandler: jest.fn(),
}));
jest.mock("@/lib/db/queries", () => ({
  getInference: jest.fn(),
}));
jest.mock("@/lib/db/jobs", () => ({
  enqueueGenerate: jest.fn(),
}));

import { POST } from "../route";
import { getAuthUserId } from "@/lib/api/handlers";
import { getInference } from "@/lib/db/queries";
import { enqueueGenerate } from "@/lib/db/jobs";

const mockGetAuthUserId = getAuthUserId as jest.MockedFunction<typeof getAuthUserId>;
const mockGetInference = getInference as jest.MockedFunction<typeof getInference>;
const mockEnqueueGenerate = enqueueGenerate as jest.MockedFunction<typeof enqueueGenerate>;

function makeRequest(body: unknown): Request {
  return new Request("http://localhost/api/v1/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("POST /api/v1/generate", () => {
  it("returns 401 when not authenticated", async () => {
    mockGetAuthUserId.mockResolvedValue(null);

    const res = await POST(makeRequest({ inference_id: "inf-1" }));

    expect(res.status).toBe(401);
  });

  it("returns 400 when inference_id is missing", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");

    const res = await POST(makeRequest({}));

    expect(res.status).toBe(400);
  });

  it("returns 404 when inference is not found", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockGetInference.mockResolvedValue(null);

    const res = await POST(makeRequest({ inference_id: "inf-missing" }));

    expect(res.status).toBe(404);
  });

  it("returns 202 with generation_id and job_id on success", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockGetInference.mockResolvedValue({ id: "inf-1", status: "done" } as any);
    mockEnqueueGenerate.mockResolvedValue({ generationId: "gen-1", jobId: "job-gen-1" });

    const res = await POST(makeRequest({ inference_id: "inf-1" }));

    expect(res.status).toBe(202);
    const json = await res.json();
    expect(json).toEqual({ generation_id: "gen-1", job_id: "job-gen-1" });
  });
});
