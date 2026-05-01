jest.mock("@/lib/rateLimit", () => ({
  checkRateLimitDual: jest.fn().mockResolvedValue(null),
  getClientIp: jest.fn().mockReturnValue("127.0.0.1"),
}));
jest.mock("@/lib/db/client", () => ({
  db: { execute: jest.fn() },
}));
jest.mock("@/lib/api/validateApiKey");

import { POST } from "../route";
import { db } from "@/lib/db/client";
import { validateApiKey } from "@/lib/api/validateApiKey";

const mockExecute = db.execute as jest.Mock;
const mockValidateApiKey = validateApiKey as jest.Mock;
const mockFetch = jest.fn();

function makeRequest(body: unknown, apiKey = "valid-key"): Request {
  return new Request("http://localhost/api/v1/retrieve-sdk", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-verum-api-key": apiKey,
    },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  mockValidateApiKey.mockResolvedValue({ userId: "user-1" });
  global.fetch = mockFetch;
});

describe("POST /api/v1/retrieve-sdk", () => {
  it("returns 401 when API key is invalid", async () => {
    mockValidateApiKey.mockResolvedValue(null);

    const res = await POST(makeRequest({ query: "tarot" }, "bad-key"));

    expect(res.status).toBe(401);
  });

  it("returns 400 when query is missing", async () => {
    const res = await POST(makeRequest({}));

    expect(res.status).toBe(400);
  });

  it("returns 502 when Voyage AI embedding call fails", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 500 });

    const res = await POST(makeRequest({ query: "tarot meaning" }));

    expect(res.status).toBe(502);
  });

  it("returns chunks on successful pgvector query", async () => {
    const fakeEmbedding = Array.from({ length: 1024 }, () => 0.1);
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: [{ embedding: fakeEmbedding }] }),
    });

    mockExecute.mockResolvedValue({
      rows: [
        { id: "c1", content: "Tarot card meanings", metadata: { source: "wiki" }, score: 0.92 },
        { id: "c2", content: "Major arcana overview", metadata: null, score: 0.87 },
      ],
    });

    const res = await POST(makeRequest({ query: "tarot meaning", top_k: 2 }));

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.chunks).toHaveLength(2);
    expect(json.chunks[0]).toMatchObject({ content: "Tarot card meanings", score: 0.92 });
    expect(json.chunks[1].metadata).toEqual({});
    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.voyageai.com/v1/embeddings",
      expect.objectContaining({ method: "POST" }),
    );
    expect(mockExecute).toHaveBeenCalledTimes(1);
  });
});
