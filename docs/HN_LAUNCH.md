# Hacker News Launch Kit — Verum

This document is a preparation guide for the Verum Show HN post. It is not the post itself — it is a checklist, draft text, and response playbook for the author (xzawed) to execute at launch time.

---

## 1. Launch Prerequisites Checklist

Do not post until every box is checked.

- [ ] GitHub repo `github.com/xzawed/verum` is public
- [ ] `docker compose up` flow in README is verified against a fresh environment (not the dev machine)
- [ ] `QUICKSTART.md` is complete and tested end-to-end by someone other than xzawed
- [ ] Demo environment is live at `demo.verum.dev` with real seed data — EXPERIMENT results visible, not just screenshots
- [ ] F-4.11 (ArcanaInsight auto-evolution) has produced at least one real before/after result with measurable metric improvement
- [ ] Blog post "Why not LangChain" is published on dev.to (publish 2 days before the HN post)
- [ ] README includes honest limitations section (not just features)
- [ ] `/health` endpoint returns 200 with <100ms p99 on demo environment
- [ ] All CI checks pass on `main`
- [ ] COMPARISON.md (Langfuse vs Verum honest comparison) is linked from README

---

## 2. Recommended Timing

**Do not post on Friday or Saturday.** HN traffic drops sharply on weekends and posts that catch momentum on a Friday evening often fall off the front page before the US West Coast wakes up Saturday.

**Best days:** Tuesday or Wednesday

**Best window:** 8:00–11:00am US Eastern (ET)

- This hits the US East Coast start of workday, which is when HN's upvote density is highest.
- It also gives UK/European readers a chance to upvote in the afternoon before US readers log off.
- Avoid posting after noon ET — by then the front page is already crowded with posts that have a head start.

**Recommended specific target:** Wednesday 9:00am ET

Rationale: Tuesday has slightly higher competition from weekend-recharged content. Wednesday is reliably high-traffic with lower initial competition. Do not overthink this — content quality matters more than timing, but timing is the one free variable you control.

---

## 3. The Submission

### Title

```
Show HN: Verum – connect your repo, auto-generate prompts/RAG/evals, and A/B test them (open source)
```

Character count: 101 characters. Trim to: `Show HN: Verum – connect your repo, auto-generate prompts/RAG/evals and A/B test them (open source)` (100 chars) if HN enforces a hard limit at submission time. The meaning is identical.

### URL

```
https://github.com/xzawed/verum
```

### Submission Text (paste into the "text" field)

```
I built Verum because I kept manually writing and tweaking prompts for my AI services, guessing whether RAG was helping, and running informal A/B tests I couldn't measure. The loop felt broken. Verum is an attempt to close it automatically.

The flow: connect a GitHub repo → Verum statically analyzes it (no service execution required) to find every LLM call site, extract prompt templates, and record model/parameter configuration → a Claude inference step classifies the service domain (e.g., "tarot_divination", "code_review", "legal_qa") → it then crawls authoritative sources for that domain and builds a pgvector knowledge base → generates five prompt variants (Chain-of-Thought, Few-shot, Role-play, etc.) plus a RAG config and an eval dataset of 30–50 synthetic question/answer pairs → deploys via a thin SDK wrapper that handles traffic splitting → collects traces with LLM-as-Judge scoring → runs Bayesian A/B experiments → auto-promotes the winning variant and archives the losers.

What's live: I've been running this against ArcanaInsight, a Korean tarot reading app. The ANALYZE stage detected 8 LLM call sites, extracted 238 prompt templates, and classified it as `{"domain": "tarot_divination", "tone": "mystical", "language": "ko"}`. GENERATE produced five prompt variants; EXPERIMENT is running and has one complete auto-promotion cycle with a measurable improvement in LLM-as-Judge scores.

What's not done: RAGAS integration is partial (eval dataset generation works, RAGAS scoring pipeline is stubbed). Team/multi-user features don't exist yet. The only service tested is ArcanaInsight — I haven't validated the domain classifier on more than one type of service. Self-hosted deployments need at least 100 traces per prompt variant before the Bayesian test reaches confidence, which is a real constraint for low-traffic apps.

Tech: Python 3.13, Next.js 16, PostgreSQL 16 + pgvector (no external vector DB), MIT license. Self-host with `docker compose up`.

If you run it against your own repo, open an issue with what the domain classifier got wrong — that's the part most likely to break on unfamiliar service types.
```

---

## 4. Anticipated Questions and Answers

These are the comments most likely to appear in the first two hours. Read them the night before. Respond within 15 minutes of each comment if possible — early engagement materially affects HN ranking.

**Q1: "How is this different from Langfuse/LangSmith?"**

Langfuse and LangSmith are excellent observability tools — they record what your LLM calls do. Verum starts with that but tries to close the loop: the observation data feeds back into automatic prompt optimization and A/B experiments. The bigger difference is the ANALYZE stage: Verum reads your repo statically without requiring you to instrument anything first. You connect a repo, not a running service. Langfuse requires you to add SDK calls to your code before you see any data.

**Q2: "Why not use LangChain's built-in prompt optimization?"**

LangChain's LCEL and DSPy-style optimizers require you to be inside the LangChain abstraction. Verum is designed to work with services that use the raw OpenAI/Anthropic SDK directly — which is most production code I've seen. Also, Verum's optimization loop is tied to real production traffic and user feedback, not just offline eval sets. That said, if you're already on LangChain, Verum's ANALYZE stage won't be as useful since the call patterns are abstracted.

**Q3: "Does it work without pgvector? Can I use Pinecone?"**

No, and intentionally. The entire stack runs on PostgreSQL 16 + pgvector. This is a deliberate constraint — it means `docker compose up` gives you the full system with no external service dependencies. Adding Pinecone/Weaviate/Qdrant would make self-hosting more complex for a capability PostgreSQL covers adequately at the scale Verum targets. If pgvector's performance ever becomes a bottleneck, I'll revisit — but that's a problem for after 10M+ vectors, which is not where this project is today.

**Q4: "100 traces per variant is a lot — what if my app is low-traffic?"**

It is a real limitation. The Bayesian stopping criterion needs enough data to distinguish signal from noise. For low-traffic apps, the current options are: (1) lower the confidence threshold and accept more false positives in winner selection, (2) run experiments for longer, (3) use synthetic traffic to warm up the eval pipeline. None of these are great. The right fix is probably a hierarchical model that shares priors across variants, which is on the roadmap but not built yet. I wanted to be upfront about this rather than hide it.

**Q5: "How do you ensure LLM-as-Judge isn't biased?"**

It isn't fully solved. Current mitigations: the judge model (Claude Sonnet 4.6) is different from the models being evaluated; scoring prompts are formatted to present variants in random order to reduce position bias; scores are normalized per-query before aggregating. Known gap: there's no cross-model judge ensemble yet, which would be the more robust approach. The eval dataset also includes human-labeled reference answers for ArcanaInsight, which gives a calibration signal, but that only works because I hand-labeled 50 examples. Generalizing that to new domains is unsolved.

**Q6: "Why Claude specifically for INFER/GENERATE?"**

Structured reasoning quality. The INFER step produces a JSON classification of the service's domain, tone, and language from unstructured code + docs. Early tests with GPT-4o and Sonnet 3.5 showed higher rates of hallucinated domain labels and malformed JSON on edge cases. Claude Sonnet 4.6 was more reliable on the structured output contract. That said, the LLM provider is configurable — Claude is the default, not a hard requirement.

**Q7: "What's the self-hosted cost?"**

The software is free (MIT). Infrastructure cost for self-hosting: PostgreSQL 16 instance + a server with enough RAM to run the Python worker alongside Next.js. The reference setup (Railway, single container) costs roughly $5–15/month depending on usage. The LLM API calls are your cost — INFER and GENERATE each make a handful of calls per repo analysis, so initial setup for one repo is typically under $1 in API fees. Ongoing costs depend on how many traces you collect and how many A/B experiments you run.

**Q8: "Is there a managed version?"**

Not yet. `demo.verum.dev` exists as a demo environment with seed data, but it is not a multi-tenant SaaS product. A cloud offering is planned for after the open-source version is stable and has been used by people other than me. The model will follow Langfuse's approach: identical features, hosted for you. No feature gating between open-source and cloud.

---

## 5. Cross-posting Plan

Execute in this order to avoid splitting the initial upvote momentum:

**Day -2 (before HN post):**
- Publish "Why not LangChain" blog post on dev.to. This is the technical companion piece. Link to the GitHub repo but do not announce the HN post yet.

**Day 0 (HN post day):**
- Post on HN at 9:00am ET.
- Within 1 hour of posting: post to Reddit r/MachineLearning. Frame it as a technical project post, not a launch announcement. Lead with the architecture, not the product.
- Within 2 hours: post to Reddit r/selfhosted. Focus entirely on the `docker compose up` angle and the PostgreSQL-only stack. That community cares about self-containment.
- Post X/Twitter thread: lead with the architecture diagram, include the ArcanaInsight before/after result (LLM-as-Judge score), link to HN post and GitHub. Keep to 4–5 tweets.

**Day +1:**
- Post to GeekNews (긱뉴스) in Korean. Write the submission in Korean — translate the HN submission text, not the English blog post. GeekNews readers are technical and will read both; a Korean-first post will be more appreciated.
- Post on Korean developer Twitter/X community (#개발 tag). Mention the ArcanaInsight dogfood since Korean readers will recognize the context.

**Day +3:**
- If the HN post gained traction, write a follow-up dev.to post: "What happened when I posted Verum on HN" — honest numbers, what broke, what questions came up. This tends to get its own traffic.

---

## 6. Metrics to Track

Track these daily for the first week after launch.

| Metric | Target (Week 1) | Where to check |
|--------|-----------------|----------------|
| GitHub stars | 100 | github.com/xzawed/verum |
| HN rank (peak) | Top 30 Show HN, ideally top 10 | news.ycombinator.com/show |
| HN comments | 20+ substantive comments | HN post page |
| Issues opened | 10+ (signal of real engagement) | GitHub Issues tab |
| Docker pulls | Any visible count | GitHub Container Registry or Docker Hub |
| Reddit upvotes (r/ML) | 50+ | Reddit post |
| Reddit upvotes (r/selfhosted) | 30+ | Reddit post |
| GeekNews reactions | 10+ | GeekNews post |
| Press/blog mentions | Note any; no target | Google Alerts on "Verum LLM" |

**What to do if HN ranking stalls below top 50 within the first 2 hours:**

Do not ask people to upvote — that violates HN rules and gets flagged. Instead: respond to every comment promptly and substantively. Engagement drives ranking more than initial upvotes. If the post doesn't catch in the first 4 hours, it probably won't — accept it, gather the feedback from comments, and plan a re-post with a revised angle in 3–4 months after meaningful new features ship.

**What "success" actually means:**

A top-10 Show HN with 100 stars and 10 real issues opened is more valuable than 500 stars from a viral tweet and zero GitHub engagement. The goal is users who self-host and report what breaks — not passive followers.
