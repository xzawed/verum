# Architecture of Verum: 8 Stages, One PostgreSQL Database, No Vector Database

*Published on dev.to / Medium*

---

## What Verum Does

Verum is an open-source platform that automatically optimizes LLM-powered services. You connect a GitHub repo, and Verum analyzes how your code calls LLMs, infers what the service is trying to do, harvests relevant domain knowledge, generates better prompt variants, runs A/B tests on real traffic, and promotes the winning prompts automatically.

The entire system runs as a closed loop:

```
  ┌──────────────────────────────────────────────────┐
  │                                                  │
  │  [1] ANALYZE     Static analysis of LLM calls   │
  │        ↓                                        │
  │  [2] INFER       Infer domain and intent        │
  │        ↓                                        │
  │  [3] HARVEST     Collect domain knowledge       │
  │        ↓                                        │
  │  [4] GENERATE    Generate prompt variants       │
  │        ↓                                        │
  │  [5] DEPLOY      Inject via SDK                 │
  │        ↓                                        │
  │  [6] OBSERVE     Trace calls in production      │
  │        ↓                                        │
  │  [7] EXPERIMENT  Bayesian A/B across variants   │
  │        ↓                                        │
  │  [8] EVOLVE      Promote winner, archive loser  │
  │        ↓                                        │
  └────────→  back to [1]  ─────────────────────────┘
```

This post covers the architectural decisions that make this work — and the ones we'd revisit with hindsight.

---

## One PostgreSQL Database for Everything

The most frequent question we get: "Why not use a dedicated vector database like Pinecone or Qdrant?"

The answer is operational simplicity. Verum is designed to be self-hostable with `docker compose up`. Every additional infrastructure component increases the surface area for things to go wrong during setup, increases the barrier to entry for self-hosters, and adds a dependency we don't control. pgvector handles vector similarity search directly inside PostgreSQL, with performance that's adequate for the scale Verum operates at in its early stages (tens of millions of vectors, not billions).

The concrete advantage is that we can join vector search results with relational data in a single query. For example, during HARVEST, we retrieve semantically similar document chunks while filtering by `repo_id` and `domain` — constraints that live in regular PostgreSQL columns:

```sql
SELECT chunk_id, content, embedding <=> $1 AS distance
FROM harvest_chunks
WHERE repo_id = $2
  AND domain = $3
ORDER BY embedding <=> $1
LIMIT 20;
```

Doing this with a separate vector DB would require fetching candidate IDs from the vector search, then querying PostgreSQL for the relational filters, then joining in application code. The performance overhead and code complexity aren't worth it at this scale.

The trade-off: pgvector's HNSW index performance degrades at hundreds of millions of vectors. When (if) Verum reaches that scale, adding a dedicated vector DB becomes the right call. We've deliberately not over-engineered for that now.

**Embeddings**: Voyage AI `voyage-3.5` (1024 dimensions). Stored as `vector(1024)` columns in PostgreSQL.

**Full-text search**: PostgreSQL `tsvector` for keyword search. We do hybrid retrieval — combine vector similarity score and BM25 keyword score with a weighted sum — without leaving the database.

---

## Node.js as PID 1, Python as Child Process

Verum runs as a single Docker container. Node.js is PID 1 and owns the HTTP server (Next.js). Python is spawned as a child process at boot time and handles all background job processing.

```
Container
├── Node.js (PID 1) — Next.js HTTP server, Auth.js, Drizzle ORM
│   └── instrumentation.ts → spawn.ts → python3 -m src.worker.main
└── Python (child) — asyncio worker, SQLAlchemy, LLM calls, AST analysis
```

This is not a microservices architecture. It's one process tree.

The reason: Railway (our deployment target) bills per service. Running two separate services (one Node.js, one Python) doubles the minimum cost and requires internal networking between them. A single container with an internal child process costs nothing extra and has zero network latency between the web layer and the job processor.

The Python worker communicates with the database directly over the shared PostgreSQL connection. Node.js hands off work by writing a job row to PostgreSQL. Python picks it up via the job queue. They never talk to each other directly.

The downside: if the Python worker crashes, it takes a restart of the entire container to bring it back. We handle this by having `spawn.ts` watch the child process and restart it automatically with exponential backoff. So far this has been reliable enough. A full microservices split would give better fault isolation, but the operational simplicity of one container wins at this stage.

---

## Job Queue in PostgreSQL, Not Redis

Background jobs (ANALYZE, INFER, HARVEST, GENERATE, EXPERIMENT cycles) are stored in a `verum_jobs` table in PostgreSQL. Python workers poll it with `SELECT FOR UPDATE SKIP LOCKED` to claim work without contention:

```sql
SELECT * FROM verum_jobs
WHERE status = 'pending'
  AND next_run_at <= NOW()
ORDER BY priority DESC, created_at ASC
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

PostgreSQL sends `NOTIFY` on job insertion, and the Python worker uses `LISTEN` to wake up immediately rather than polling on a fixed interval. This gives sub-second job pickup latency without a separate message broker.

Why not Redis/Celery? Same answer as the vector DB question: operational simplicity. Redis is another infrastructure component, another thing to configure, another thing that can be out of sync with the database. Job creation in PostgreSQL is transactional — if a user action creates a job and the transaction rolls back, the job disappears automatically. With Redis, you'd need to coordinate the rollback manually.

The limitation: PostgreSQL-based queues don't scale to thousands of concurrent workers or millions of jobs per second. That's not a constraint for Verum's current workload. A single Python worker processes 20-50 jobs per minute, and jobs are coarse-grained (one ANALYZE job per repo, one EXPERIMENT cycle per service per day).

---

## ANALYZE: Static Analysis, No Runtime Required

The ANALYZE stage extracts LLM call patterns from source code without running the service. This is a deliberate design constraint: users shouldn't need to deploy or run their service to get value from Verum.

For Python repos, we use Python's `ast` module to parse source files and identify calls to `openai.chat.completions.create`, `anthropic.messages.create`, `client.messages.create`, and similar patterns. We extract the prompt strings (including f-strings and template literals with variable substitution), model names, and temperature settings.

For TypeScript/JavaScript repos, we use `tree-sitter` with the TypeScript grammar. The AST traversal logic is similar: find call expressions matching known SDK patterns, extract string arguments.

The output of ANALYZE is a structured JSON document: a list of call sites, each with the file path, line number, detected model, extracted prompt template, and identified input variables.

The limitation of static analysis: we can't know the runtime values of variables. If a prompt is built dynamically based on user input at runtime, we capture the template structure but not example instantiations. OBSERVE (stage 6) fills this gap by capturing actual rendered prompts from production traffic.

---

## INFER and GENERATE: Claude Sonnet 4.6

Both the INFER stage (determining domain and intent from extracted prompts) and the GENERATE stage (creating prompt variants) use Claude Sonnet 4.6 with structured JSON output.

INFER sends the extracted prompt templates, repo README, and type definitions to the model and asks for a domain classification:

```json
{
  "domain": "divination/tarot",
  "tone": "mystical",
  "language": "ko",
  "user_type": "consumer",
  "primary_task": "card_reading_interpretation"
}
```

GENERATE takes this domain context and the original prompts, then produces four variants (chain-of-thought, few-shot, role-play, concise) as structured JSON with the prompt text and rationale for each change.

We use structured output (via the `response_format` parameter) rather than asking the model to produce JSON in its response text and then parsing it. This eliminates a class of parsing failures that would otherwise require error handling and retries.

---

## Where We Made Trade-offs

**No streaming responses in GENERATE.** Claude's API supports streaming, which would let us show prompt generation progress in the UI. We use blocking requests instead because streaming complicates the job queue model — a streaming response doesn't fit neatly into "job starts, job completes, write result to DB." We'll add streaming in a later phase.

**Single-region PostgreSQL.** All data lives in one PostgreSQL instance on Railway. There's no read replica, no geographic distribution. For a product with users in one region (currently just us), this is fine. It will be the first thing to change if we see latency complaints from users in distant geographies.

**Synchronous embedding generation during HARVEST.** When we crawl and chunk domain knowledge, we generate embeddings synchronously in the same job. This means a HARVEST job that collects 500 documents blocks for however long it takes to embed 500 chunks via the Voyage AI API. We batch the embedding calls (100 chunks per request), but it's still the slowest part of the pipeline. An async queue for embedding jobs would speed this up.

**No horizontal scaling of the Python worker.** The `SKIP LOCKED` pattern supports multiple worker processes claiming different jobs. But right now we run exactly one Python worker per container. Scaling out requires either multiple containers (which requires coordination on the job queue) or threading within the single Python process (which conflicts with asyncio in non-obvious ways). This is a known gap for when job volume grows.

---

## What the Stack Actually Looks Like

```
┌─────────────────────────────────────┐
│  Next.js (App Router, standalone)   │
│  - Auth.js v5 (GitHub OAuth)        │
│  - Drizzle ORM (read-heavy queries) │
│  - API routes for SDK endpoints     │
└──────────────┬──────────────────────┘
               │ SQL (direct)
               ↓
┌─────────────────────────────────────┐
│  PostgreSQL 16                      │
│  - pgvector extension               │
│  - verum_jobs (job queue)           │
│  - harvest_chunks (embeddings)      │
│  - llm_calls (traces)               │
│  - prompt_versions (A/B variants)   │
└──────────────┬──────────────────────┘
               │ SQL (SQLAlchemy 2)
               ↓
┌─────────────────────────────────────┐
│  Python 3.13 (asyncio worker)       │
│  - AST analysis (ast + tree-sitter) │
│  - LLM calls (anthropic SDK)        │
│  - Embeddings (Voyage AI)           │
│  - Bayesian A/B (scipy + numpy)     │
└─────────────────────────────────────┘
```

The key architectural invariant: every service boundary goes through PostgreSQL. There's no direct HTTP between Node.js and Python. Jobs go in as rows, results come back as rows, and the job queue is the only coordination mechanism. This makes the system straightforward to reason about, easy to debug (just query the DB), and trivial to reset (truncate the jobs table and re-run).

---

## What We'd Do Differently

If we were starting today with the knowledge we have now:

1. **Separate the embedding pipeline into its own job type from the start.** Mixing crawl + chunk + embed into one HARVEST job made early iteration faster but now makes it hard to retry failed embeds without re-crawling.

2. **Build the streaming response path from day one.** Retrofitting streaming into a blocking job model is more work than designing for it initially.

3. **Use pgvector's HNSW index from the first migration.** We started with IVFFlat (faster to build, slower to query at scale) and migrated to HNSW later. The migration on a populated table was slower than expected.

Everything else — single PostgreSQL, child process architecture, no framework abstractions over LLM calls — we'd do the same way again.

---

*Verum is open-source (MIT). Source: [github.com/xzawed/verum](https://github.com/xzawed/verum)*
