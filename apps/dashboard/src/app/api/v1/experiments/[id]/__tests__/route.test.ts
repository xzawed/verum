jest.mock("@/lib/api/handlers", () => ({ getAuthUserId: jest.fn() }));
jest.mock("@/lib/db/queries", () => ({ getExperiment: jest.fn() }));

import { GET } from "../route";
import { getAuthUserId } from "@/lib/api/handlers";
import { getExperiment } from "@/lib/db/queries";

const mockGetAuthUserId = getAuthUserId as jest.Mock;
const mockGetExperiment = getExperiment as jest.Mock;

function makeParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

beforeEach(() => {
  jest.resetAllMocks();
});

describe("GET /api/v1/experiments/[id]", () => {
  it("returns 401 when unauthenticated", async () => {
    mockGetAuthUserId.mockResolvedValue(null);
    const res = await GET(new Request("http://localhost"), makeParams("exp-1"));
    expect(res.status).toBe(401);
  });

  it("returns 404 when experiment not found", async () => {
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockGetExperiment.mockResolvedValue(null);
    const res = await GET(new Request("http://localhost"), makeParams("exp-999"));
    expect(res.status).toBe(404);
  });

  it("returns 200 with experiment data on success", async () => {
    const experiment = { id: "exp-1", name: "prompt-ab-test", status: "running" };
    mockGetAuthUserId.mockResolvedValue("user-1");
    mockGetExperiment.mockResolvedValue(experiment);
    const res = await GET(new Request("http://localhost"), makeParams("exp-1"));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual(experiment);
  });
});
