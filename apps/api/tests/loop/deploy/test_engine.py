import pytest
from src.loop.deploy.engine import compute_traffic_split, should_auto_rollback


def test_compute_traffic_split_canary():
    split = compute_traffic_split(0.1)
    assert split == {"baseline": 0.9, "variant": 0.1}


def test_compute_traffic_split_full():
    split = compute_traffic_split(1.0)
    assert split == {"baseline": 0.0, "variant": 1.0}


def test_compute_traffic_split_clamps_to_zero_one():
    split = compute_traffic_split(1.5)
    assert split["variant"] == 1.0
    split2 = compute_traffic_split(-0.1)
    assert split2["variant"] == 0.0


def test_no_rollback_insufficient_calls():
    assert not should_auto_rollback(error_count=50, total_calls=50, threshold=5.0)


def test_rollback_triggered_when_error_rate_exceeds_threshold():
    # 100 calls, 10 errors = 10% error rate vs 1% baseline → 10× > 5× → rollback
    assert should_auto_rollback(error_count=10, total_calls=100, threshold=5.0)


def test_no_rollback_error_rate_within_threshold():
    # 100 calls, 3 errors = 3% vs 1% baseline → 3× < 5× → no rollback
    assert not should_auto_rollback(error_count=3, total_calls=100, threshold=5.0)
