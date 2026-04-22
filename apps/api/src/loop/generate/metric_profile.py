"""Metric profile auto-selection for the GENERATE stage ([4] of The Verum Loop).

Pure function — no LLM call, no DB I/O. Selects dashboard metrics based on
the service's user_type and domain inferred in the INFER stage.
"""
from __future__ import annotations

from pydantic import BaseModel


class MetricProfile(BaseModel):
    primary_metrics: list[str]
    secondary_metrics: list[str]
    profile_name: str


_CONSUMER_PRIMARY = ["latency_p95", "user_satisfaction", "response_length"]
_CONSUMER_SECONDARY = ["cost_per_call", "error_rate"]

_DEVELOPER_PRIMARY = ["accuracy", "latency_p95", "cost_per_call"]
_DEVELOPER_SECONDARY = ["token_count", "error_rate"]

_ENTERPRISE_PRIMARY = ["cost_per_call", "reliability", "throughput"]
_ENTERPRISE_SECONDARY = ["latency_p95", "error_rate"]


def select_metric_profile(user_type: str, domain: str) -> MetricProfile:
    """Return the recommended dashboard metric profile for this service.

    Args:
        user_type: From ServiceInference — "consumer", "developer", or "enterprise".
        domain: From ServiceInference — e.g. "divination/tarot", "code_review".

    Returns:
        MetricProfile with primary and secondary metric lists and a profile name.
    """
    domain_key = domain.split("/")[0] if "/" in domain else domain

    if user_type == "developer":
        primary = list(_DEVELOPER_PRIMARY)
        secondary = list(_DEVELOPER_SECONDARY)
    elif user_type == "enterprise":
        primary = list(_ENTERPRISE_PRIMARY)
        secondary = list(_ENTERPRISE_SECONDARY)
    else:
        primary = list(_CONSUMER_PRIMARY)
        secondary = list(_CONSUMER_SECONDARY)

    if domain_key == "divination" and "response_length" not in primary:
        primary.append("response_length")

    return MetricProfile(
        primary_metrics=primary,
        secondary_metrics=secondary,
        profile_name=f"{user_type}-{domain_key}",
    )
