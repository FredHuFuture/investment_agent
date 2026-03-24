"""VIX-scaled dynamic thresholds for signal aggregation.

In calm markets (low VIX) thresholds tighten to capture more opportunities.
In volatile markets (high VIX) thresholds widen to reduce false signals.
"""

from __future__ import annotations

# Long-run VIX average
VIX_BASELINE: float = 20.0

# Base aggregator thresholds
BASE_BUY: float = 0.30
BASE_SELL: float = -0.30

# How aggressively thresholds scale with VIX deviation.
# Each 1-point VIX deviation from baseline adjusts threshold by ~0.0075.
SCALE_FACTOR: float = 0.015

# Hard limits to prevent extreme thresholds
MIN_THRESHOLD: float = 0.15
MAX_THRESHOLD: float = 0.50


def compute_dynamic_thresholds(
    vix_current: float | None,
) -> tuple[float, float]:
    """Return (buy_threshold, sell_threshold) scaled by current VIX.

    Args:
        vix_current: Current VIX level. If *None*, returns base thresholds.

    Returns:
        Tuple of (buy_threshold, sell_threshold) where sell = -buy.
    """
    if vix_current is None:
        return (BASE_BUY, BASE_SELL)

    deviation = (vix_current - VIX_BASELINE) / VIX_BASELINE
    adjustment = deviation * SCALE_FACTOR * VIX_BASELINE

    buy_t = max(MIN_THRESHOLD, min(MAX_THRESHOLD, BASE_BUY + adjustment))
    sell_t = -buy_t
    return (buy_t, sell_t)
