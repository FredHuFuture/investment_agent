from __future__ import annotations

"""Sector rotation matrix -- maps macro regime to sector-level confidence modifiers.

The modifier adjusts the *aggregated* signal confidence (not direction).
A +20 means "this sector is favored in the current regime, increase conviction."
A -20 means "this sector faces headwinds, reduce conviction."
"""

# Modifier values: -30 to +30 (percentage points applied to confidence)
SECTOR_ROTATION_MATRIX: dict[str, dict[str, int]] = {
    "RISK_ON": {
        "Technology": +20,
        "Consumer Cyclical": +15,
        "Financial Services": +10,
        "Industrials": +10,
        "Communication Services": +10,
        "Basic Materials": +5,
        "Energy": +5,
        "Healthcare": 0,
        "Consumer Defensive": -10,
        "Utilities": -15,
        "Real Estate": -10,
    },
    "RISK_OFF": {
        "Technology": -15,
        "Consumer Cyclical": -20,
        "Financial Services": -10,
        "Industrials": -10,
        "Communication Services": -5,
        "Basic Materials": -10,
        "Energy": -5,
        "Healthcare": +10,
        "Consumer Defensive": +20,
        "Utilities": +15,
        "Real Estate": +5,
    },
    "NEUTRAL": {
        # All sectors get 0 modifier in neutral regime
    },
}


def get_sector_modifier(sector: str | None, regime: str) -> int:
    """Return sector rotation modifier in range [-30, +30].

    Args:
        sector: Sector name from yfinance (e.g., "Technology").
        regime: Macro regime from MacroAgent ("RISK_ON", "RISK_OFF", "NEUTRAL").

    Returns:
        Integer modifier to apply to signal confidence.
        Returns 0 if sector is None/unknown or regime is NEUTRAL/unknown.
    """
    if sector is None:
        return 0

    regime_map = SECTOR_ROTATION_MATRIX.get(regime)
    if regime_map is None:
        return 0

    return regime_map.get(sector, 0)
