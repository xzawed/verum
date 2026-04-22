"""Pure functions for the DEPLOY stage ([5] of The Verum Loop)."""
from __future__ import annotations

_BASELINE_ERROR_RATE = 0.01  # 1% assumed baseline


def compute_traffic_split(variant_fraction: float) -> dict[str, float]:
    """Convert a variant fraction (0.0–1.0) to a traffic_split dict."""
    fraction = max(0.0, min(1.0, variant_fraction))
    variant = round(fraction, 10)
    return {"baseline": round(1.0 - variant, 10), "variant": variant}


def should_auto_rollback(
    error_count: int,
    total_calls: int,
    threshold: float = 5.0,
) -> bool:
    """Return True if the error rate exceeds threshold × baseline and calls ≥ 100."""
    if total_calls < 100:
        return False
    error_rate = error_count / total_calls
    return error_rate > _BASELINE_ERROR_RATE * threshold
