"use client";

import { useState } from "react";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface RetrieveResult {
  content: string;
  score: number;
}

export default function RetrievePage() {
  const [inferenceId, setInferenceId] = useState("");
  const [query, setQuery] = useState("");
  const [hybrid, setHybrid] = useState(true);
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<RetrieveResult[]>([]);
  const [totalChunks, setTotalChunks] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const res = await fetch(`${apiBase}/v1/retrieve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ inference_id: inferenceId, query, hybrid, top_k: topK }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `HTTP ${res.status}`);
      }

      const data = await res.json();
      setResults(data.results ?? []);
      setTotalChunks(data.total_chunks ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <a href="/" style={{ fontSize: 12, color: "#666" }}>← Home</a>
      <h1 style={{ fontSize: 22, margin: "16px 0 20px" }}>RETRIEVE — Knowledge Search</h1>

      <form onSubmit={handleSubmit}>
        <label style={{ display: "block", marginBottom: 4, fontWeight: "bold" }}>Inference ID</label>
        <input
          type="text"
          value={inferenceId}
          onChange={(e) => setInferenceId(e.target.value)}
          placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
          required
          style={{ width: "100%", padding: "8px 12px", fontSize: 13, boxSizing: "border-box", marginBottom: 12 }}
        />

        <label style={{ display: "block", marginBottom: 4, fontWeight: "bold" }}>Query</label>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. What does the Tower card mean in a love reading?"
          required
          style={{ width: "100%", padding: "8px 12px", fontSize: 13, boxSizing: "border-box", marginBottom: 12 }}
        />

        <div style={{ display: "flex", gap: 24, marginBottom: 20, alignItems: "center" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
            <input type="checkbox" checked={hybrid} onChange={(e) => setHybrid(e.target.checked)} />
            Hybrid search (vector + BM25)
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
            Top K:
            <input
              type="number"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              min={1}
              max={20}
              style={{ width: 60, padding: "4px 8px" }}
            />
          </label>
        </div>

        {error && <p style={{ color: "red", marginBottom: 12 }}>Error: {error}</p>}

        <button
          type="submit"
          disabled={loading}
          style={{ padding: "8px 20px", fontWeight: "bold", cursor: loading ? "not-allowed" : "pointer" }}
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {totalChunks !== null && (
        <p style={{ marginTop: 20, fontSize: 12, color: "#888" }}>
          {results.length} result{results.length !== 1 ? "s" : ""} from {totalChunks.toLocaleString()} total chunks
        </p>
      )}

      {results.map((r, i) => (
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
