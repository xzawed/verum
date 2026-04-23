import { validateApiKey } from "../validateApiKey";

jest.mock("@/lib/db/deploys", () => ({
  findDeploymentByApiKey: jest.fn(),
}));

import { findDeploymentByApiKey } from "@/lib/db/deploys";

const mockFind = findDeploymentByApiKey as jest.MockedFunction<typeof findDeploymentByApiKey>;

describe("validateApiKey", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns null for keys shorter than 40 chars", async () => {
    const result = await validateApiKey("short-key");
    expect(result).toBeNull();
  });

  it("does not call DB for short keys", async () => {
    await validateApiKey("tooshort");
    expect(mockFind).not.toHaveBeenCalled();
  });

  it("returns null when findDeploymentByApiKey returns null (hash not found)", async () => {
    mockFind.mockResolvedValueOnce(null);
    const validLengthKey = "a".repeat(40);
    const result = await validateApiKey(validLengthKey);
    expect(result).toBeNull();
    expect(mockFind).toHaveBeenCalledTimes(1);
  });

  it("returns deploymentId and userId when key is valid", async () => {
    mockFind.mockResolvedValueOnce({ id: "dep-1", userId: "user-1" } as never);
    const validLengthKey = "b".repeat(40);
    const result = await validateApiKey(validLengthKey);
    expect(result).toEqual({ deploymentId: "dep-1", userId: "user-1" });
  });
});
