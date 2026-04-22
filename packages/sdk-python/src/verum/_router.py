"""Traffic split routing logic for the Verum SDK."""
from __future__ import annotations

import random


def choose_variant(split: float) -> str:
    """Return 'variant' or 'baseline' based on the given split fraction.

    Args:
        split: Fraction of traffic to route to the variant (0.0 to 1.0).

    Returns:
        'variant' if this call should use the variant prompt, 'baseline' otherwise.
    """
    return "variant" if random.random() < split else "baseline"
