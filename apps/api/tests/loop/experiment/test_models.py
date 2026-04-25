import uuid

import pytest
from src.loop.experiment.models import ExperimentResult, VariantStats


def test_variant_stats_win_rate_no_division_by_zero():
    stats = VariantStats(variant="original", wins=0, n=0, avg_winner_score=0.0)
    assert stats.win_rate == pytest.approx(0.0)


def test_variant_stats_win_rate_normal():
    stats = VariantStats(variant="cot", wins=70, n=100, avg_winner_score=0.75)
    assert stats.win_rate == pytest.approx(0.70)


def test_experiment_result_fields():
    exp = ExperimentResult(
        experiment_id=uuid.uuid4(),
        deployment_id=uuid.uuid4(),
        baseline=VariantStats(variant="original", wins=40, n=100, avg_winner_score=0.6),
        challenger=VariantStats(variant="cot", wins=70, n=100, avg_winner_score=0.75),
        confidence=0.97,
        converged=True,
        winner_variant="cot",
    )
    assert exp.winner_variant == "cot"
    assert exp.converged is True
