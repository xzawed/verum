jest.mock("@/lib/api/handlers", () => ({ getAuthUserId: jest.fn() }));
jest.mock("@/lib/db/queries", () => ({ getTraceDetail: jest.fn() }));

import { GET } from "../route";
import { getAuthUserId } from "@/lib/api/handlers";
import { getTraceDetail } from "@/lib/db/queries";

const mockGetAuthUserId = getAuthUserId as jest.Mock;
const mockGetTraceDetail = getTraceDetail as jest.Mock;

function makeParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

beforeEach(() => {
  jest.resetAllMocks();
});

describe("GET /api/v1/traces/[id]", () => {
  it("returns 401 when unauthenticated", async () => {
    mockGetAuthUserId.mockResolvedValue(null);
    const res = await GET(new Request("http://localhost"), makeParams("trace-1"));
    expect(res.status).toBe(401);
  });

  it("returns 404 when trace not found", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockGetTraceDetail.mockResolvedValue(null);
    const res = await GET(new Request("http://localhost"), makeParams("trace-999"));
    expect(res.status).toBe(404);
  });

  it("returns 200 with trace data on success", async () => {
    const trace = { id: "trace-1", variant: "baseline", judge_score: 0.9 };
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockGetTraceDetail.mockResolvedValue(trace);
    const res = await GET(new Request("http://localhost"), makeParams("trace-1"));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual(trace);
  });
});
