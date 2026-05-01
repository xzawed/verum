import { createSdkPrRequest, updateSdkPrRequest } from "../jobs";
import { getSdkPrRequest, getLatestSdkPrRequest } from "../queries";

const mockInsertValues = jest.fn().mockReturnThis();
const mockInsertReturning = jest.fn().mockResolvedValue([{ id: "req-uuid-1", status: "pending" }]);
const mockUpdateSet = jest.fn().mockReturnThis();
const mockUpdateWhere = jest.fn().mockResolvedValue(undefined);
const mockSelectFrom = jest.fn().mockReturnThis();
const mockSelectWhere = jest.fn().mockReturnThis();
const mockSelectOrderBy = jest.fn().mockReturnThis();
const mockSelectLimit = jest.fn().mockResolvedValue([{
  id: "req-uuid-1",
  repo_id: "repo-1",
  owner_user_id: "user-1",
  analysis_id: "analysis-1",
  status: "pending",
  pr_url: null,
  pr_number: null,
  branch_name: null,
  files_changed: 0,
  error: null,
  created_at: new Date(),
  updated_at: new Date(),
}]);

jest.mock("@/lib/db/client", () => ({
  db: {
    insert: jest.fn(() => ({ values: mockInsertValues })),
    update: jest.fn(() => ({ set: mockUpdateSet })),
    select: jest.fn(() => ({ from: mockSelectFrom })),
  },
}));

mockInsertValues.mockReturnValue({ returning: mockInsertReturning });
mockUpdateSet.mockReturnValue({ where: mockUpdateWhere });
mockSelectFrom.mockReturnValue({ where: mockSelectWhere });
mockSelectWhere.mockReturnValue({ limit: mockSelectLimit, orderBy: mockSelectOrderBy });
mockSelectOrderBy.mockReturnValue({ limit: mockSelectLimit });

describe("sdk_pr_requests DB helpers", () => {
  beforeEach(() => jest.clearAllMocks());

  it("createSdkPrRequest inserts and returns the new row id", async () => {
    const id = await createSdkPrRequest({ userId: "user-1", repoId: "repo-1", analysisId: "analysis-1", mode: "observe" });
    expect(id).toBe("req-uuid-1");
    expect(mockInsertValues).toHaveBeenCalledWith(
      expect.objectContaining({ repo_id: "repo-1", owner_user_id: "user-1", mode: "observe", status: "pending" }),
    );
  });

  it("updateSdkPrRequest sets status + updated_at", async () => {
    await updateSdkPrRequest("req-uuid-1", { status: "pr_created", pr_url: "https://github.com/o/r/pull/1", pr_number: 1, files_changed: 3 });
    expect(mockUpdateSet).toHaveBeenCalledWith(
      expect.objectContaining({ status: "pr_created", pr_url: "https://github.com/o/r/pull/1" }),
    );
  });

  it("getSdkPrRequest returns null on miss", async () => {
    mockSelectLimit.mockResolvedValueOnce([]);
    const result = await getSdkPrRequest("user-1", "nonexistent");
    expect(result).toBeNull();
  });

  it("getLatestSdkPrRequest returns the most recent request", async () => {
    const result = await getLatestSdkPrRequest("user-1", "repo-1");
    expect(result).not.toBeNull();
    expect(result?.id).toBe("req-uuid-1");
  });
});
