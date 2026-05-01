import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { enqueueRetrieve } from "@/lib/db/jobs";
import { getJob } from "@/lib/db/queries";

interface RetrieveResult {
  content: string;
  score: number;
}

export default async function RetrievePage({
  searchParams,
}: {
  searchParams: Promise<{
    inference_id?: string;
    query?: string;
    hybrid?: string;
    top_k?: string;
    job_id?: string;
  }>;
}) {
  const session = await auth();
  if (!session?.user) redirect("/login");

  const userId = String((session.user as Record<string, unknown>).id ?? "");
  const sp = await searchParams;
  const inferenceId = sp.inference_id ?? "";
  const query = sp.query ?? "";
  const hybrid = sp.hybrid !== "false";
  const topK = Number(sp.top_k ?? "5") || 5;
  const jobId = sp.job_id ?? "";

  // Check job result if we have a job_id
  let results: RetrieveResult[] | null = null;
  let totalChunks = 0;
  let jobPending = false;

  if (jobId) {
    const job = await getJob(jobId);
    if (job?.status === "done" && job.result) {
      const r = job.result as { results: RetrieveResult[]; total_chunks: number };
      results = r.results;
      totalChunks = r.total_chunks;
    } else if (job && (job.status === "queued" || job.status === "running")) {
      jobPending = true;
    }
  }

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", fontFamily: "monospace", padding: "0 16px" }}>
      <a href="/repos" style={{ fontSize: 12, color: "#666" }}>← My Repos</a>
      <h1 style={{ fontSize: 22, margin: "16px 0 20px" }}>RETRIEVE — Knowledge Search</h1>

      <form
        action={async (formData: FormData) => {
          "use server";
          const s = await auth();
          if (!s?.user) redirect("/login");
          const uid = String((s.user as Record<string, unknown>).id ?? "");
          const infId = formData.get("inference_id");
          const q = formData.get("query");
          if (typeof infId !== "string" || typeof q !== "string" || !infId || !q) {
            return { error: "Missing required fields" };
          }
          const hyb = formData.get("hybrid") === "true";
          const k = Number(formData.get("top_k") ?? "5") || 5;
          const newJobId = await enqueueRetrieve({ userId: uid, inferenceId: infId, query: q, hybrid: hyb, topK: k });
          redirect(`/retrieve?inference_id=${infId}&query=${encodeURIComponent(q)}&hybrid=${hyb}&top_k=${k}&job_id=${newJobId}`);
        }}
      >
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
            <input name="top_k" type="number" defaultValue={topK} min={1} max={20} style={{ width: 60, padding: "4px 8px" }} />
          </label>
        </div>

        <button type="submit" style={{ padding: "8px 20px", fontWeight: "bold", cursor: "pointer" }}>
          Search
        </button>
      </form>

      {jobPending && (
        <p style={{ marginTop: 20, color: "#888" }}>
          Search in progress…{" "}
          <a href={`/retrieve?inference_id=${inferenceId}&query=${encodeURIComponent(query)}&hybrid=${hybrid}&top_k=${topK}&job_id=${jobId}`}>
            Refresh
          </a>
        </p>
      )}

      {results !== null && (
        <>
          <p style={{ marginTop: 20, fontSize: 12, color: "#888" }}>
            {results.length} result{results.length !== 1 ? "s" : ""} from {totalChunks.toLocaleString()} total chunks
          </p>
          {results.map((r, i) => (
            <div key={i} style={{ marginTop: 12, padding: "12px 14px", background: "#f9f9f9", border: "1px solid #ddd" }}>
              <div style={{ fontSize: 11, color: "#888", marginBottom: 6 }}>Score: {r.score.toFixed(4)}</div>
              <pre style={{ fontSize: 12, whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0 }}>{r.content}</pre>
            </div>
          ))}
        </>
      )}
    </main>
  );
}
