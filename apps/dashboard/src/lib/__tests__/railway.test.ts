import {
  listRailwayServices,
  upsertRailwayVariables,
  deleteRailwayVariables,
} from "../railway";

const mockFetch = jest.fn();
global.fetch = mockFetch as typeof fetch;

afterEach(() => mockFetch.mockReset());

const TOKEN = "railway_test_token";

describe("listRailwayServices", () => {
  it("returns flat list of services with project info", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: {
          projects: {
            edges: [
              {
                node: {
                  id: "proj1",
                  name: "MyProject",
                  environments: {
                    edges: [{ node: { id: "env1", name: "production" } }],
                  },
                  services: {
                    edges: [{ node: { id: "svc1", name: "ArcanaInsight" } }],
                  },
                },
              },
            ],
          },
        },
      }),
    });

    const result = await listRailwayServices(TOKEN);
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      id: "svc1",
      name: "ArcanaInsight",
      projectId: "proj1",
      projectName: "MyProject",
      environmentId: "env1",
    });
  });

  it("throws on Railway API error response", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 401 });
    await expect(listRailwayServices(TOKEN)).rejects.toThrow(
      "Railway API error: 401",
    );
  });

  it("throws on GraphQL-level error response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        errors: [{ message: "Unauthorized" }],
      }),
    });
    await expect(listRailwayServices(TOKEN)).rejects.toThrow(
      "Railway GraphQL error: Unauthorized",
    );
  });
});

describe("upsertRailwayVariables", () => {
  it("calls variableUpsert for each var", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ data: { variableUpsert: true } }),
    });

    await upsertRailwayVariables(TOKEN, "proj1", "svc1", "env1", {
      FOO: "bar",
      BAZ: "qux",
    });

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });
});

describe("deleteRailwayVariables", () => {
  it("calls variableDelete for each name", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ data: { variableDelete: true } }),
    });

    await deleteRailwayVariables(TOKEN, "proj1", "svc1", "env1", [
      "FOO",
      "BAR",
    ]);

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });
});
