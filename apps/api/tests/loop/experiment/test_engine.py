import pytest
from src.loop.experiment.engine import (
    compute_winner_score,
    bayesian_confidence,
    check_experiment,
)
import uuid


# ── compute_winner_score ──────────────────────────────────────────────────────

def test_winner_score_no_cost():
    score = compute_winner_score(judge_score=0.8, cost_usd=0.01, max_cost_in_window=0.0)
    assert score == pytest.approx(0.8)


def test_winner_score_full_cost_penalty():
    score = compute_winner_score(judge_score=0.8, cost_usd=1.0, max_cost_in_window=1.0)
    assert score == pytest.approx(0.7)


def test_winner_score_partial_penalty():
    score = compute_winner_score(judge_score=0.75, cost_usd=0.5, max_cost_in_window=1.0, cost_weight=0.1)
    assert score == pytest.approx(0.70)


# ── bayesian_confidence ───────────────────────────────────────────────────────

def test_bayesian_confidence_challenger_dominates():
    conf = bayesian_confidence(b_wins=10, b_n=100, c_wins=90, c_n=100, samples=20_000)
    assert conf > 0.95


def test_bayesian_confidence_baseline_dominates():
    conf = bayesian_confidence(b_wins=90, b_n=100, c_wins=10, c_n=100, samples=20_000)
    assert conf < 0.05


def test_bayesian_confidence_uncertain():
    conf = bayesian_confidence(b_wins=50, b_n=100, c_wins=52, c_n=100, samples=20_000)
    assert 0.05 < conf < 0.95


# ── check_experiment ─────────────────────────────────────────────────────────

def make_experiment_dict(b_wins=0, b_n=0, c_wins=0, c_n=0):
    return {
        "id": str(uuid.uuid4()),
        "deployment_id": str(uuid.uuid4()),
        "baseline_variant": "original",
        "challenger_variant": "cot",
        "baseline_wins": b_wins,
        "baseline_n": b_n,
        "challenger_wins": c_wins,
        "challenger_n": c_n,
        "win_threshold": 0.6,
        "cost_weight": 0.1,
    }


def test_check_experiment_not_converged_insufficient_samples():
    exp_row = make_experiment_dict(b_wins=80, b_n=99, c_wins=90, c_n=99)
    result = check_experiment(exp_row, max_cost_in_window=1.0)
    assert result.converged is False


def test_check_experiment_converged_challenger_wins():
    exp_row = make_experiment_dict(b_wins=10, b_n=100, c_wins=90, c_n=100)
    result = check_experiment(exp_row, max_cost_in_window=1.0)
    assert result.converged is True
    assert result.winner_variant == "cot"
    assert result.confidence >= 0.95


def test_check_experiment_converged_baseline_holds():
    exp_row = make_experiment_dict(b_wins=90, b_n=100, c_wins=10, c_n=100)
    result = check_experiment(exp_row, max_cost_in_window=1.0)
    assert result.converged is True
    assert result.winner_variant == "original"
    assert result.confidence <= 0.05
