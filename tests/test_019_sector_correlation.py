from __future__ import annotations

"""Tests for Task 019 -- Sector Rotation & Correlation Module."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import numpy as np
import pandas as pd
import pytest

from agents.models import AgentOutput, Regime, Signal
from cli.report import format_analysis_report
from data_providers.base import DataProvider
from engine.aggregator import AggregatedSignal
from engine.correlation import calculate_portfolio_correlations
from engine.sector import SECTOR_ROTATION_MATRIX, get_sector_modifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_output(
    agent_name: str,
    signal: Signal,
    confidence: float,
    ticker: str = "AAPL",
    metrics: dict | None = None,
) -> AgentOutput:
    return AgentOutput(
        agent_name=agent_name,
        ticker=ticker,
        signal=signal,
        confidence=confidence,
        reasoning=f"{agent_name} says {signal.value}",
        metrics=metrics or {},
    )


class _FakeProvider(DataProvider):
    """Minimal DataProvider stub that returns pre-built price DataFrames."""

    def __init__(self, data: dict[str, pd.DataFrame]) -> None:
        self._data = data

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        if ticker in self._data:
            return self._data[ticker]
        raise ValueError(f"No data for {ticker}")

    async def get_current_price(self, ticker: str) -> float:
        if ticker in self._data:
            df = self._data[ticker]
            return float(df["Close"].iloc[-1])
        raise ValueError(f"No data for {ticker}")

    def is_point_in_time(self) -> bool:
        return False

    def supported_asset_types(self) -> list[str]:
        return ["stock"]


def _make_price_df(close_prices: list[float]) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame from a close price series."""
    n = len(close_prices)
    dates = pd.bdate_range(end="2026-03-10", periods=n)
    df = pd.DataFrame(
        {
            "Open": close_prices,
            "High": [p * 1.01 for p in close_prices],
            "Low": [p * 0.99 for p in close_prices],
            "Close": close_prices,
            "Volume": [1_000_000] * n,
        },
        index=dates,
    )
    return df


# ---------------------------------------------------------------------------
# Sector modifier tests
# ---------------------------------------------------------------------------

def test_sector_modifier_risk_on() -> None:
    """Technology in RISK_ON gets +20."""
    assert get_sector_modifier("Technology", "RISK_ON") == 20


def test_sector_modifier_risk_off() -> None:
    """Technology in RISK_OFF gets -15."""
    assert get_sector_modifier("Technology", "RISK_OFF") == -15


def test_sector_modifier_neutral() -> None:
    """Any sector in NEUTRAL gets 0."""
    assert get_sector_modifier("Technology", "NEUTRAL") == 0
    assert get_sector_modifier("Healthcare", "NEUTRAL") == 0
    assert get_sector_modifier("Utilities", "NEUTRAL") == 0


def test_sector_modifier_unknown_sector() -> None:
    """Unknown/None sector returns 0 regardless of regime."""
    assert get_sector_modifier(None, "RISK_ON") == 0
    assert get_sector_modifier("Alien Tech", "RISK_ON") == 0
    assert get_sector_modifier(None, "RISK_OFF") == 0
    assert get_sector_modifier("", "RISK_ON") == 0


def test_sector_modifier_unknown_regime() -> None:
    """Unknown regime returns 0."""
    assert get_sector_modifier("Technology", "UNKNOWN") == 0
    assert get_sector_modifier("Technology", "") == 0


def test_sector_modifier_confidence_clamp() -> None:
    """Modifier applied to confidence stays within [30, 90]."""
    # Simulate clamping logic: base confidence near max + big positive modifier
    base_confidence = 85.0
    modifier = get_sector_modifier("Technology", "RISK_ON")  # +20
    adjusted = max(30.0, min(90.0, base_confidence + modifier))
    assert adjusted == 90.0  # Clamped at 90

    # Low confidence + big negative modifier
    base_confidence = 35.0
    modifier = get_sector_modifier("Consumer Cyclical", "RISK_OFF")  # -20
    adjusted = max(30.0, min(90.0, base_confidence + modifier))
    assert adjusted == 30.0  # Clamped at 30


def test_sector_matrix_completeness() -> None:
    """All RISK_ON sectors have RISK_OFF counterparts and vice versa."""
    risk_on_sectors = set(SECTOR_ROTATION_MATRIX["RISK_ON"].keys())
    risk_off_sectors = set(SECTOR_ROTATION_MATRIX["RISK_OFF"].keys())
    assert risk_on_sectors == risk_off_sectors


# ---------------------------------------------------------------------------
# Correlation tests
# ---------------------------------------------------------------------------

def test_correlation_calculation() -> None:
    """Known return series produces expected correlation."""
    # Two tickers with perfectly correlated prices (both go up linearly)
    prices_a = [100.0 + i for i in range(30)]
    prices_b = [50.0 + i * 0.5 for i in range(30)]  # Same direction, different scale
    provider = _FakeProvider({
        "AAPL": _make_price_df(prices_a),
        "MSFT": _make_price_df(prices_b),
    })

    result = asyncio.run(
        calculate_portfolio_correlations(["AAPL", "MSFT"], provider)
    )

    assert ("AAPL", "MSFT") in result["correlation_matrix"]
    corr = result["correlation_matrix"][("AAPL", "MSFT")]
    # Both go up linearly, so correlation should be very high
    assert corr > 0.90


def test_concentration_risk_high() -> None:
    """High avg correlation produces HIGH risk rating."""
    # Three tickers with highly correlated prices
    base = [100.0 + i * 2 for i in range(30)]
    prices_a = base
    prices_b = [p + 10 for p in base]
    prices_c = [p + 20 for p in base]

    provider = _FakeProvider({
        "AAA": _make_price_df(prices_a),
        "BBB": _make_price_df(prices_b),
        "CCC": _make_price_df(prices_c),
    })

    result = asyncio.run(
        calculate_portfolio_correlations(["AAA", "BBB", "CCC"], provider)
    )

    assert result["concentration_risk"] == "HIGH"
    assert result["avg_correlation"] > 0.70


def test_concentration_risk_low() -> None:
    """Diverse portfolio produces LOW risk rating."""
    np.random.seed(42)
    n = 60
    # Use uncorrelated random walks
    prices_a = list(np.cumsum(np.random.randn(n)) + 100)
    prices_b = list(np.cumsum(np.random.randn(n)) + 100)
    prices_c = list(np.cumsum(np.random.randn(n)) + 100)

    # Make sure prices are positive
    prices_a = [max(p, 1.0) for p in prices_a]
    prices_b = [max(p, 1.0) for p in prices_b]
    prices_c = [max(p, 1.0) for p in prices_c]

    provider = _FakeProvider({
        "AAA": _make_price_df(prices_a),
        "BBB": _make_price_df(prices_b),
        "CCC": _make_price_df(prices_c),
    })

    result = asyncio.run(
        calculate_portfolio_correlations(["AAA", "BBB", "CCC"], provider)
    )

    assert result["concentration_risk"] == "LOW"
    assert result["avg_correlation"] < 0.40


def test_correlation_missing_data() -> None:
    """Partial data handled gracefully -- tickers with no data are skipped."""
    prices_a = [100.0 + i for i in range(30)]
    # Only provide data for one ticker out of two requested
    provider = _FakeProvider({
        "AAPL": _make_price_df(prices_a),
    })

    result = asyncio.run(
        calculate_portfolio_correlations(["AAPL", "MISSING"], provider)
    )

    # Should return gracefully with LOW risk and a warning
    assert result["concentration_risk"] == "LOW"
    assert len(result["warnings"]) > 0


def test_correlation_single_ticker() -> None:
    """Single ticker returns empty correlation (need 2+ tickers)."""
    provider = _FakeProvider({
        "AAPL": _make_price_df([100.0 + i for i in range(30)]),
    })

    result = asyncio.run(
        calculate_portfolio_correlations(["AAPL"], provider)
    )

    assert result["concentration_risk"] == "LOW"
    assert result["avg_correlation"] == 0.0
    assert result["correlation_matrix"] == {}


# ---------------------------------------------------------------------------
# Report display tests
# ---------------------------------------------------------------------------

def test_sector_display_standard() -> None:
    """Standard report shows sector adjustment line when modifier is present."""
    signal = AggregatedSignal(
        ticker="AAPL",
        asset_type="stock",
        final_signal=Signal.BUY,
        final_confidence=72.0,
        regime=Regime.RISK_ON,
        agent_signals=[
            _make_output("TechnicalAgent", Signal.BUY, 72.0),
        ],
        reasoning="ok",
        metrics={
            "sector_modifier": 20,
            "sector_name": "Technology",
            "pre_sector_confidence": 52.0,
        },
        warnings=[],
    )

    output = format_analysis_report(signal)

    assert "Sector Adj: +20" in output
    assert "Technology" in output
    assert "RISK_ON" in output


def test_sector_display_detail() -> None:
    """Detail mode shows full SECTOR ADJUSTMENT block."""
    signal = AggregatedSignal(
        ticker="AAPL",
        asset_type="stock",
        final_signal=Signal.BUY,
        final_confidence=72.0,
        regime=Regime.RISK_ON,
        agent_signals=[
            _make_output(
                "TechnicalAgent",
                Signal.BUY,
                72.0,
                metrics={"trend_score": 10},
            ),
        ],
        reasoning="ok",
        metrics={
            "raw_score": 0.5,
            "consensus_score": 1.0,
            "buy_count": 1,
            "sell_count": 0,
            "hold_count": 0,
            "weights_used": {"TechnicalAgent": 1.0},
            "agent_contributions": {
                "TechnicalAgent": {
                    "signal": "BUY",
                    "confidence": 72.0,
                    "weighted_contribution": 0.72,
                },
            },
            "sector_modifier": 20,
            "sector_name": "Technology",
            "pre_sector_confidence": 52.0,
        },
        warnings=[],
    )

    output = format_analysis_report(signal, detail=True)

    assert "SECTOR ADJUSTMENT" in output
    assert "Technology" in output
    assert "RISK_ON" in output
    assert "+20" in output
    assert "52%" in output
    assert "72%" in output
    assert "sector favored" in output


def test_no_sector_display_without_modifier() -> None:
    """Report does not show sector section when no modifier was applied."""
    signal = AggregatedSignal(
        ticker="AAPL",
        asset_type="stock",
        final_signal=Signal.BUY,
        final_confidence=72.0,
        regime=Regime.RISK_ON,
        agent_signals=[
            _make_output("TechnicalAgent", Signal.BUY, 72.0),
        ],
        reasoning="ok",
        metrics={},
        warnings=[],
    )

    output = format_analysis_report(signal)

    assert "Sector Adj" not in output
    assert "SECTOR ADJUSTMENT" not in output
