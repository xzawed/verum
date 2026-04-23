jest.mock("@/lib/db/deploys", () => ({
  findDeploymentByApiKey: jest.fn(),
}));

import { validateApiKey } from "../api/validateApiKey";
import { findDeploymentByApiKey } from "@/lib/db/deploys";

const mockFind = findDeploymentByApiKey as jest.MockedFunction<
  typeof findDeploymentByApiKey
>;

beforeEach(() => {
  mockFind.mockReset();
});

describe("validateApiKey()", () => {
  it("returns null for empty string without querying DB", async () => {
    expect(await validateApiKey("")).toBeNull();
    expect(mockFind).not.toHaveBeenCalled();
  });

  it("returns null for key shorter than 40 chars without querying DB", async () => {
    expect(await validateApiKey("short-key")).toBeNull();
    expect(mockFind).not.toHaveBeenCalled();
  });

  it("returns null when deployment is not found in DB", async () => {
    mockFind.mockResolvedValueOnce(null);
    expect(await validateApiKey("a".repeat(40))).toBeNull();
    expect(mockFind).toHaveBeenCalledTimes(1);
  });

  it("returns ApiKeyResult when deployment is found", async () => {
    mockFind.mockResolvedValueOnce({ id: "dep-123", userId: "user-456" });
    const result = await validateApiKey("a".repeat(40));
    expect(result).toEqual({ deploymentId: "dep-123", userId: "user-456" });
    expect(mockFind).toHaveBeenCalledTimes(1);
  });

  it("passes SHA-256 hash (64 hex chars) of the key to DB lookup", async () => {
    mockFind.mockResolvedValueOnce(null);
    const rawKey = "c".repeat(40);
    await validateApiKey(rawKey);
    const hashArg = mockFind.mock.calls[0]?.[0] as string;
    expect(hashArg).toMatch(/^[0-9a-f]{64}$/);
    expect(hashArg).not.toBe(rawKey);
  });

  it("returns null at exactly 39 chars (one below threshold)", async () => {
    expect(await validateApiKey("x".repeat(39))).toBeNull();
    expect(mockFind).not.toHaveBeenCalled();
  });

  it("queries DB at exactly 40 chars (threshold)", async () => {
    mockFind.mockResolvedValueOnce(null);
    await validateApiKey("x".repeat(40));
    expect(mockFind).toHaveBeenCalledTimes(1);
  });
});
