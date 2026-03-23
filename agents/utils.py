"""Shared utility helpers for agent modules."""
from __future__ import annotations

import math
from typing import Any

import pandas as pd


def _to_float(value: Any) -> float | None:
    """Convert *value* to float, returning None for non-numeric or NaN inputs."""
    if value is None:
        return None
    try:
        result = float(value)
        if math.isnan(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _clamp(value: float, lo: float = -100.0, hi: float = 100.0) -> float:
    """Clamp *value* to [lo, hi]."""
    return max(lo, min(hi, value))


def _safe_last(series: pd.Series | None) -> float | None:
    """Return the last non-NaN numeric value of *series*, or None."""
    if series is None or series.empty:
        return None
    value = series.iloc[-1]
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric):
        return None
    return numeric
