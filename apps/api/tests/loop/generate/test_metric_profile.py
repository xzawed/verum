import pytest
from src.loop.generate.metric_profile import MetricProfile, select_metric_profile


def test_consumer_divination_primary():
    profile = select_metric_profile("consumer", "divination/tarot")
    assert "latency_p95" in profile.primary_metrics
    assert "user_satisfaction" in profile.primary_metrics
    assert "response_length" in profile.primary_metrics
    assert profile.profile_name == "consumer-divination"


def test_developer_code_review():
    profile = select_metric_profile("developer", "code_review")
    assert "accuracy" in profile.primary_metrics
    assert "cost_per_call" in profile.primary_metrics
    assert profile.profile_name == "developer-code_review"


def test_enterprise():
    profile = select_metric_profile("enterprise", "legal_qa")
    assert "cost_per_call" in profile.primary_metrics
    assert "reliability" in profile.primary_metrics
    assert profile.profile_name == "enterprise-legal_qa"


def test_unknown_user_type_defaults_to_consumer():
    profile = select_metric_profile("unknown_type", "other")
    assert len(profile.primary_metrics) >= 2
    assert isinstance(profile.profile_name, str)


def test_metric_profile_is_pydantic():
    profile = select_metric_profile("consumer", "divination/tarot")
    assert isinstance(profile, MetricProfile)
    data = profile.model_dump()
    assert "primary_metrics" in data
    assert "secondary_metrics" in data
    assert "profile_name" in data
