# Bayesian A/B Testing for LLM Prompts: Why Frequentist Statistics Don't Work

*Published on dev.to / Medium*

---

## The Problem

You have two prompt variants for the same task. Variant A is your current production prompt. Variant B adds chain-of-thought reasoning. You want to know which one produces better responses.

The naive approach: run both for a week, count how many responses each one got rated highly, run a chi-squared test, check if p < 0.05. Ship the winner.

This approach has several problems that make it unreliable for LLM prompt testing specifically. Let's work through them, then look at what Verum uses instead.

---

## Why Frequentist Tests Fail Here

**The peeking problem.** Classic frequentist hypothesis testing assumes you decide on a sample size before the experiment, collect data, then test once. In practice, everyone checks results early. If you run a t-test after 20 calls and again after 40 calls and again after 100 calls, your false positive rate is no longer 5% — it's much higher. The math depends on how many times you peek, but peeking twice at p < 0.05 gives you roughly a 14% false positive rate.

LLM A/B tests run continuously by nature. You're not collecting a batch and then deciding — calls come in as real user traffic arrives, and you want to stop the experiment as soon as you have enough evidence. Frequentist tests don't support that.

**LLM output quality is not normally distributed.** The t-test assumes the underlying metric is approximately normal. A typical LLM quality score — especially from an LLM-as-Judge setup — is bounded between 0 and 1, skewed, and often bimodal (bad responses cluster near 0, good responses cluster near 0.8-1.0). Applying a t-test to this distribution gives you unreliable p-values.

**You can't easily incorporate prior knowledge.** You probably have intuitions before the experiment starts: "chain-of-thought prompts tend to do better on reasoning tasks" or "this specific service gets short, punchy questions where verbose CoT hurts latency." Frequentist tests have no mechanism for encoding that. Bayesian models do.

---

## The Beta-Bernoulli Model

We model each prompt variant's quality as a Bernoulli process: each call either "wins" (quality score above threshold) or "loses." The probability of winning is unknown but follows a Beta distribution — Beta(α, β), where α counts wins and β counts losses.

The Beta distribution is conjugate to the Bernoulli likelihood, which means the posterior after observing data has a clean closed form:

```
Prior:    Beta(α₀, β₀)
Observed: w wins, l losses
Posterior: Beta(α₀ + w, β₀ + l)
```

We start with a weakly informative prior of Beta(2, 2) — slightly favoring 0.5 win probability, encoding no strong belief about the variant. As calls accumulate, the posterior tightens around the observed win rate.

To compare champion vs challenger, we estimate P(challenger > champion) using Monte Carlo sampling:

```python
import numpy as np
from scipy import stats

def p_challenger_beats_champion(
    champion_wins: int,
    champion_losses: int,
    challenger_wins: int,
    challenger_losses: int,
    n_samples: int = 10_000,
) -> float:
    alpha0, beta0 = 2.0, 2.0  # weakly informative prior

    champion_samples = stats.beta.rvs(
        alpha0 + champion_wins,
        beta0 + champion_losses,
        size=n_samples,
    )
    challenger_samples = stats.beta.rvs(
        alpha0 + challenger_wins,
        beta0 + challenger_losses,
        size=n_samples,
    )

    return float(np.mean(challenger_samples > champion_samples))
```

This function returns the probability that the challenger's true win rate exceeds the champion's. If that probability exceeds 0.95, the challenger wins. If it drops below 0.05 (i.e., P(champion > challenger) > 0.95), the champion wins. Below those thresholds, we keep running.

---

## Sequential Pairwise Structure

Verum tests four challenger variants against the current champion in sequence:

1. Chain-of-thought (`cot`)
2. Few-shot examples (`few_shot`)
3. Role-play framing (`role_play`)
4. Concise / minimal (`concise`)

Each challenger runs as champion-vs-one-challenger. Once a challenger is decided (win or lose), the current champion (possibly updated) moves to the next round. This keeps the traffic split manageable: at any point, only two variants are live, not five.

The sequential structure also means we don't need to run all four challengers to full convergence simultaneously. If the chain-of-thought variant is clearly inferior after 40 calls, we move on. Total calls consumed is much lower than a full 4-way comparison.

---

## Scoring: What Counts as a Win

The win/loss binary is derived from a `winner_score` per call:

```
winner_score = judge_score - 0.1 × (cost_usd / max_cost_in_window)
```

Where:
- `judge_score` is the LLM-as-Judge rating (0.0–1.0)
- `cost_usd` is the actual spend for that call
- `max_cost_in_window` normalizes cost to [0, 1] relative to the most expensive call in the current experiment window

A call "wins" if `winner_score > 0.6`. This threshold is configurable.

The 0.1 coefficient on cost means quality dominates the score: a response needs to cost 10× more to lose by 1 point of judge score. This is intentional. In early experiments we weighted cost equally, which caused the concise variant to win by default not because it was better but because it was cheaper. The current weighting treats cost as a tiebreaker, not a primary signal.

---

## LLM-as-Judge as the Scoring Oracle

We score each response by sending it to a judge LLM (Claude Sonnet, the same model used for generation). The judge receives the original input, the response, and a rubric specific to the task type (e.g., for a tarot reading service: accuracy of card interpretation, consistency of tone, coherence of narrative arc).

One design decision worth calling out: we extract the score from the judge's **token metadata** (`usage.output_tokens` tells us if the response was truncated), not from parsing its response text. The actual numeric score comes from structured JSON output (`{"score": 0.82, "rationale": "..."}`), which we request via the API's response format parameter rather than prompt-instructing JSON.

This is more reliable than asking the judge to produce "a score between 0 and 10" in free text and then parsing it. Structured output prevents off-by-one errors in parsing and makes the score extraction deterministic.

---

## Convergence and Sample Size

The convergence condition is:

```
n ≥ 100  AND  (P(challenger > champion) ≥ 0.95  OR  P(challenger > champion) ≤ 0.05)
```

The minimum of 100 calls prevents early stopping due to random variance. With a Beta(2, 2) prior, after 10 calls the posterior is still quite wide — the Monte Carlo estimate of P(challenger > champion) swings dramatically with a few outlier responses. At 100 calls, the posterior is tight enough that the comparison is meaningful.

In practice, the 0.95 threshold is reachable in 80-150 calls for variants that differ substantially in quality. For variants that are close in performance, the experiment may run to the 1,000-call cap before a winner is declared — in which case we keep the champion by default.

**Cold start problem.** For a service with low traffic (< 50 LLM calls per day), convergence takes weeks. We handle this by allowing manual call injection during testing: if you have a held-out eval set of representative inputs, you can replay them through the experiment to accelerate convergence. This is opt-in and flagged explicitly in the dashboard so it's clear the sample isn't purely organic traffic.

**Cost of being wrong.** If the experiment declares a winner that's actually inferior (false positive), the cost is one round-trip to a worse prompt before the next EVOLVE cycle catches it. Because Verum runs EVOLVE continuously, a false promotion gets corrected in the next cycle rather than persisting indefinitely. The Bayesian model's 0.95 threshold keeps false positive rates low, and the sequential structure limits exposure time for any one bad decision.

---

## Practical Numbers

From our testing on ArcanaInsight (a tarot divination service):

- Median calls to convergence: 120
- Experiments where no variant beats champion at 1,000 calls: ~30% (current champion was already near-optimal)
- Cost of one full 4-variant experiment (including judge calls): $1.80–$4.20 depending on response length
- Net quality improvement per promotion cycle: +0.06–0.12 on the 0–1 judge scale

These numbers will vary significantly by domain and task complexity. Long-form generation tasks need more calls to converge than short classification tasks, because response quality variance is higher.

---

## Summary

Frequentist tests break on LLM prompt experiments because the peeking problem inflates false positives, LLM quality scores aren't normally distributed, and you can't encode prior knowledge. Beta-Bernoulli Bayesian testing handles all three: it's designed for sequential updating, it makes no normality assumption, and the prior is explicit. The trade-off is that you need to choose a convergence threshold (we use 0.95) and a minimum sample size (we use 100), both of which encode judgment calls that should be tuned for your specific domain.

The code is straightforward. The math is well-understood. The main work is building the infrastructure around it: running two variants in parallel, routing traffic consistently, collecting judge scores, and storing the Beta parameters in a way that survives service restarts.

---

*Verum is open-source (MIT). Source: [github.com/xzawed/verum](https://github.com/xzawed/verum)*
