"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const router = useRouter();
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${apiBase}/v1/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl, branch }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `HTTP ${res.status}`);
      }

      const data = await res.json();
      router.push(`/analyses/${data.analysis_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 600, margin: "80px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <h1 style={{ fontSize: 28, marginBottom: 8 }}>Verum</h1>
      <p style={{ color: "#666", marginBottom: 32 }}>
        Connect your repo. Verum learns how your AI behaves, then auto-builds and evolves everything around it.
      </p>

      <form onSubmit={handleSubmit}>
        <label style={{ display: "block", marginBottom: 4, fontWeight: "bold" }}>
          GitHub Repository URL
        </label>
        <input
          type="url"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          placeholder="https://github.com/owner/repo"
          required
          style={{ width: "100%", padding: "8px 12px", fontSize: 14, boxSizing: "border-box", marginBottom: 16 }}
        />

        <label style={{ display: "block", marginBottom: 4, fontWeight: "bold" }}>Branch</label>
        <input
          type="text"
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          placeholder="main"
          style={{ width: "100%", padding: "8px 12px", fontSize: 14, boxSizing: "border-box", marginBottom: 24 }}
        />

        {error && (
          <p style={{ color: "red", marginBottom: 16 }}>Error: {error}</p>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{
            padding: "10px 24px",
            fontSize: 14,
            fontWeight: "bold",
            cursor: loading ? "not-allowed" : "pointer",
            opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? "Submitting..." : "Analyze"}
        </button>
      </form>
    </main>
  );
}
