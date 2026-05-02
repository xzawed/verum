const mockSelect = jest.fn();
const mockInsert = jest.fn();
const mockDelete = jest.fn();

jest.mock("@/auth", () => ({ auth: jest.fn() }));
jest.mock("@/lib/db/client", () => ({
  db: {
    select: () => ({ from: () => ({ where: mockSelect }) }),
    insert: () => ({ values: () => ({ returning: mockInsert }) }),
    delete: () => ({ where: () => ({ returning: mockDelete }) }),
  },
}));
jest.mock("drizzle-orm", () => ({
  eq: jest.fn((a: unknown, b: unknown) => ({ __eq: [a, b] })),
  and: jest.fn((...args: unknown[]) => ({ __and: args })),
}));
jest.mock("@/lib/db/schema", () => ({
  webhook_subscriptions: {
    id: "id",
    user_id: "user_id",
    deployment_id: "deployment_id",
    url: "url",
    events: "events",
    is_active: "is_active",
    signing_secret: "signing_secret",
    created_at: "created_at",
  },
}));

import { GET, POST } from "../route";
import { DELETE } from "../[id]/route";

const { auth } = require("@/auth") as { auth: jest.Mock };

afterEach(() => jest.clearAllMocks());

describe("GET /api/v1/webhooks", () => {
  it("returns 401 when not authenticated", async () => {
    auth.mockResolvedValueOnce(null);
    const resp = await GET(new Request("http://test/api/v1/webhooks"));
    expect(resp.status).toBe(401);
  });

  it("returns webhook list", async () => {
    auth.mockResolvedValueOnce({ user: { id: "user-1" } });
    mockSelect.mockResolvedValueOnce([
      { id: "sub-1", url: "https://example.com", events: ["experiment.winner_promoted"], is_active: true, created_at: new Date() },
    ]);
    const resp = await GET(new Request("http://test/api/v1/webhooks"));
    expect(resp.status).toBe(200);
    const data = await resp.json() as { webhooks: unknown[] };
    expect(data.webhooks).toHaveLength(1);
  });
});

describe("POST /api/v1/webhooks", () => {
  it("returns 401 when not authenticated", async () => {
    auth.mockResolvedValueOnce(null);
    const resp = await POST(
      new Request("http://test", { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } }),
    );
    expect(resp.status).toBe(401);
  });

  it("returns 400 for non-https URL", async () => {
    auth.mockResolvedValueOnce({ user: { id: "user-1" } });
    const resp = await POST(
      new Request("http://test", {
        method: "POST",
        body: JSON.stringify({ url: "http://example.com" }),
        headers: { "Content-Type": "application/json" },
      }),
    );
    expect(resp.status).toBe(400);
  });

  it("returns 400 for unknown event", async () => {
    auth.mockResolvedValueOnce({ user: { id: "user-1" } });
    const resp = await POST(
      new Request("http://test", {
        method: "POST",
        body: JSON.stringify({ url: "https://example.com", events: ["unknown.event"] }),
        headers: { "Content-Type": "application/json" },
      }),
    );
    expect(resp.status).toBe(400);
  });

  it("creates subscription and returns 201 with signing_secret", async () => {
    auth.mockResolvedValueOnce({ user: { id: "user-1" } });
    const created = {
      id: "sub-new",
      url: "https://example.com/hook",
      events: ["experiment.winner_promoted"],
      signing_secret: "abc123",
      created_at: new Date(),
    };
    mockInsert.mockResolvedValueOnce([created]);
    const resp = await POST(
      new Request("http://test", {
        method: "POST",
        body: JSON.stringify({ url: "https://example.com/hook" }),
        headers: { "Content-Type": "application/json" },
      }),
    );
    expect(resp.status).toBe(201);
    const data = await resp.json() as { webhook: { signing_secret: string } };
    expect(typeof data.webhook.signing_secret).toBe("string");
  });
});

describe("DELETE /api/v1/webhooks/[id]", () => {
  it("returns 401 when not authenticated", async () => {
    auth.mockResolvedValueOnce(null);
    const resp = await DELETE(new Request("http://test"), {
      params: Promise.resolve({ id: "sub-1" }),
    });
    expect(resp.status).toBe(401);
  });

  it("returns 404 when not found for user", async () => {
    auth.mockResolvedValueOnce({ user: { id: "user-1" } });
    mockDelete.mockResolvedValueOnce([]);
    const resp = await DELETE(new Request("http://test"), {
      params: Promise.resolve({ id: "sub-1" }),
    });
    expect(resp.status).toBe(404);
  });

  it("returns 204 on successful delete", async () => {
    auth.mockResolvedValueOnce({ user: { id: "user-1" } });
    mockDelete.mockResolvedValueOnce([{ id: "sub-1" }]);
    const resp = await DELETE(new Request("http://test"), {
      params: Promise.resolve({ id: "sub-1" }),
    });
    expect(resp.status).toBe(204);
  });
});
