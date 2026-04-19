import { apiFetch, ApiError } from "@/lib/api";

interface RetrieveResult {
  content: string;
  score: number;
}

interface RetrieveResponse {
  results: RetrieveResult[];
  total_chunks: number;
}

async function doRetrieve(
  inferenceId: string,
  query: string,
  hybrid: boolean,
  topK: number,
): Promise<RetrieveResponse | null> {
  if (!query) return null;
  try {
    return await apiFetch<RetrieveResponse>("/v1/retrieve", {
      method: "POST",
      body: JSON.stringify({ inference_id: inferenceId, query, hybrid, top_k: topK }),
    });
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw err;
  }
}

export default async function RetrievePage({
  searchParams,
}: {
  searchParams: Promise<{
    inference_id?: string;
    query?: string;
    hybrid?: string;
    top_k?: string;
  }>;
}) {
  const sp = await searchParams;
  const inferenceId = sp.inference_id ?? "";
  const query = sp.query ?? "";
  const hybrid = sp.hybrid !== "false";
  const topK = Number(sp.top_k ?? "5") || 5;

  let response: RetrieveResponse | null = null;
  let error: string | null = null;

  if (inferenceId && query) {
    try {
      response = await doRetrieve(inferenceId, query, hybrid, topK);
    } catch (err) {
      error = err instanceof ApiError ? err.message : String(err);
    }
  }

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <a href="/repos" style={{ fontSize: 12, color: "#666" }}>← My Repos</a>
      <h1 style={{ fontSize: 22, margin: "16px 0 20px" }}>RETRIEVE — Knowledge Search</h1>

      <form method="GET" action="/retrieve">
        <label style={{ display: "block", marginBottom: 4, fontWeight: "bold" }}>Inference ID</label>
        <input
          name="inference_id"
          type="text"
          defaultValue={inferenceId}
          placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
          required
          style={{ width: "100%", padding: "8px 12px", fontSize: 13, boxSizing: "border-box", marginBottom: 12 }}
        />

        <label style={{ display: "block", marginBottom: 4, fontWeight: "bold" }}>Query</label>
        <input
          name="query"
          type="text"
          defaultValue={query}
          placeholder="e.g. What does the Tower card mean in a love reading?"
          required
          style={{ width: "100%", padding: "8px 12px", fontSize: 13, boxSizing: "border-box", marginBottom: 12 }}
        />

        <div style={{ display: "flex", gap: 24, marginBottom: 20, alignItems: "center" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
            <input type="checkbox" name="hybrid" value="true" defaultChecked={hybrid} />
            Hybrid search (vector + BM25)
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
            Top K:
            <input
              name="top_k"
              type="number"
              defaultValue={topK}
              min={1}
              max={20}
              style={{ width: 60, padding: "4px 8px" }}
            />
          </label>
        </div>

        {error && <p style={{ color: "red", marginBottom: 12 }}>Error: {error}</p>}

        <button
          type="submit"
          style={{ padding: "8px 20px", fontWeight: "bold", cursor: "pointer" }}
        >
          Search
        </button>
      </form>

      {response && (
        <p style={{ marginTop: 20, fontSize: 12, color: "#888" }}>
          {response.results.length} result{response.results.length !== 1 ? "s" : ""} from{" "}
          {response.total_chunks.toLocaleString()} total chunks
        </p>
      )}

      {response?.results.map((r, i) => (
        <div
          key={i}
          style={{ marginTop: 12, padding: "12px 14px", background: "#f9f9f9", border: "1px solid #ddd" }}
        >
          <div style={{ fontSize: 11, color: "#888", marginBottom: 6 }}>
            Score: {r.score.toFixed(4)}
          </div>
          <pre style={{ fontSize: 12, whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0 }}>
            {r.content}
          </pre>
        </div>
      ))}
    </main>
  );
}
