# We Built an LLM Optimization Platform Without LangChain. Here's Why.

*Published on dev.to / Medium*

---

## What We're Building

Verum is an open-source platform that connects to a GitHub repo, statically analyzes how your service calls LLMs, and then auto-generates prompt variants, RAG indexes, and eval datasets — running Bayesian A/B tests to automatically promote the best-performing version. The entire thing runs as a closed loop: ANALYZE → INFER → HARVEST → GENERATE → DEPLOY → OBSERVE → EXPERIMENT → EVOLVE.

To do any of this well, we need to instrument LLM calls at a granular level: exact token counts, cost per call, model parameters, prompt version identifiers, and latency broken down by stage. That requirement is what drove us away from LangChain.

---

## What LangChain Is Good At

Let's be direct: LangChain is genuinely useful for a specific thing — getting a prototype working in an afternoon.

If you need to chain a retriever to a prompt to a model output parser, LangChain gives you that in 20 lines. If you're demoing a RAG system for the first time, or building a throwaway script that summarizes documents, LangChain's abstractions save real time. The ecosystem around it — integrations with dozens of vector stores, loaders for PDF/CSV/HTML, pre-built agent types — is legitimately impressive.

None of this is a knock. LangChain solved a real problem at a moment when there were no established patterns for working with LLMs in application code.

---

## What LangChain Makes Hard

The problems surface when you try to own what's happening underneath.

**Abstractions hide cost and latency attribution.** When you call a LangChain chain, tokens flow through multiple components. By default, the framework doesn't expose a clean breakdown of which step consumed what. You can attach a `CallbackHandler`, but the callback API has changed significantly across versions, and reconstructing a full cost breakdown per logical step requires writing substantial glue code anyway. At that point, you're paying the abstraction tax without getting the abstraction benefit.

**Deep instrumentation is an afterthought.** Verum needs to know, for every LLM call: the exact prompt string that was sent (not the template, the rendered string), the model name and parameters, the start and end timestamp with millisecond precision, the completion tokens, and the prompt version identifier we assigned. LangChain's tracing via LangSmith captures some of this, but it's tightly coupled to their platform. Extracting that data into our own PostgreSQL schema — in a format we control — required either forking callback internals or accepting an opaque blob we'd have to re-parse.

**Version instability has real costs.** Between LangChain 0.1 and 0.2 there were interface breaks that required code changes across a codebase. The `langchain-community` split added import path confusion. These are manageable for a team that's made LangChain a core dependency and tracks it closely. For a project where LangChain would be a transitive dependency of our core loop — one we don't control — version churn becomes a reliability risk.

**Magic is hard to own in production.** When something breaks in a LangChain chain at 2am, the stack trace leads through multiple layers of internal dispatch, callbacks, and retry logic. Debugging it requires understanding the framework's internals at roughly the same depth as understanding the raw API. We found that the cognitive overhead of knowing both the framework and the underlying API was higher than just knowing the underlying API.

---

## What We Chose Instead

We use the raw `anthropic` Python SDK directly, with no abstraction layer except what we write ourselves.

```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": rendered_prompt}],
)
```

That's the entire LLM call surface. Everything else — prompt rendering, retry logic, cost calculation, trace recording — is code we wrote and understand completely.

For our instrumentation, every call goes through a thin wrapper that records a row to our `llm_calls` table before returning:

```python
async def invoke_llm(
    *,
    prompt: str,
    model: str,
    temperature: float,
    prompt_version_id: str,
    job_id: str,
) -> LLMResult:
    start = time.monotonic()
    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    elapsed_ms = (time.monotonic() - start) * 1000

    await record_llm_call(
        job_id=job_id,
        prompt_version_id=prompt_version_id,
        model=model,
        prompt_tokens=response.usage.input_tokens,
        completion_tokens=response.usage.output_tokens,
        cost_usd=calculate_cost(model, response.usage),
        latency_ms=elapsed_ms,
        raw_response=response.content[0].text,
    )

    return LLMResult(text=response.content[0].text, usage=response.usage)
```

The entire call path is visible. There's no callback system, no dispatch chain, no magic retry interceptor. When something breaks, the stack trace leads directly to the line that broke.

Compare this to what LangChain's callback-based tracing looks like: you implement `on_llm_start`, `on_llm_end`, and `on_llm_error`, then pass the handler into the chain constructor. The handler receives a `LLMResult` object, but it's the framework's object — not your raw response. If the underlying API changes what it puts in `additional_kwargs`, your callback silently gets incomplete data.

---

## The Trade-off

We write more code. Every time we add a new provider (we currently support Anthropic; OpenAI and Grok are next), we write the integration from scratch rather than enabling a LangChain integration in one line.

We also don't get the pre-built loaders, parsers, and agent types. Our RAG pipeline — chunking, embedding via Voyage AI, storing in pgvector, retrieving with hybrid search — is code we wrote. It's around 400 lines in `apps/api/src/loop/harvest/` and `apps/api/src/loop/generate/`. LangChain could have given us that in 40 lines.

The bet we're making: for a system whose core value is *understanding LLM call behavior at depth*, the cost of maintaining 400 lines of retrieval code is lower than the cost of debugging behavior we don't own when something goes wrong at scale.

---

## Practical Guideline

Use LangChain when:
- You're prototyping and need to move fast
- You need breadth of integrations and don't need deep observability
- The team already knows it well and the cost of switching is real

Own your stack when:
- You're instrumenting LLM calls as a first-class concern
- You need portable traces in a schema you control
- You're building something whose correctness depends on understanding every layer

We're building Verum to be the system that other services plug into for optimization. Verum itself needs to be the kind of system where every call is fully auditable. That made the choice straightforward.

---

*Verum is open-source (MIT). Source: [github.com/xzawed/verum](https://github.com/xzawed/verum)*
