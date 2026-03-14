"""Tests for Sprint 11.2 -- Candidate correlation analysis (compute_correlations)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import numpy as np
import pandas as pd
import pytest

from engine.correlation import CorrelationResult, compute_correlations


# ---------------------------------------------------------------------------
# Helpers -- synthetic price data
# ---------------------------------------------------------------------------

_RNG = np.random.RandomState(42)  # deterministic for reproducibility


def _make_price_df(prices: pd.Series) -> pd.DataFrame:
    """Wrap a price series into a minimal OHLCV DataFrame."""
    dates = prices.index
    return pd.DataFrame(
        {
            "Open": prices.values,
            "High": prices.values * 1.01,
            "Low": prices.values * 0.99,
            "Close": prices.values,
            "Volume": [1_000_000] * len(dates),
        },
        index=dates,
    )


def _build_provider_mock(
    data_map: dict[str, pd.DataFrame],
    fail_tickers: set[str] | None = None,
) -> AsyncMock:
    """Create an AsyncMock provider whose get_price_history returns from data_map."""
    fail_tickers = fail_tickers or set()

    async def _get_price_history(ticker: str, period: str = "1y", interval: str = "1d"):
        if ticker in fail_tickers:
            raise RuntimeError(f"Simulated fetch failure for {ticker}")
        if ticker in data_map:
            return data_map[ticker]
        raise RuntimeError(f"No data for {ticker}")

    provider = AsyncMock()
    provider.get_price_history = AsyncMock(side_effect=_get_price_history)
    return provider


# Shared dates
_DATES = pd.date_range("2025-01-01", periods=120, freq="B")
_BASE_RETURNS = _RNG.randn(120) * 0.02

# Perfectly correlated: same returns + tiny noise
_CORRELATED_PRICES = pd.Series(
    100 * (1 + pd.Series(_BASE_RETURNS)).cumprod().values,
    index=_DATES,
)
_CORRELATED_NOISE_PRICES = pd.Series(
    100 * (1 + pd.Series(_BASE_RETURNS + _RNG.randn(120) * 0.001)).cumprod().values,
    index=_DATES,
)

# Uncorrelated: independent returns
_UNCORRELATED_PRICES = pd.Series(
    100 * (1 + pd.Series(_RNG.randn(120) * 0.02)).cumprod().values,
    index=_DATES,
)

# Negatively correlated: opposite returns
_NEGATIVE_PRICES = pd.Series(
    100 * (1 + pd.Series(-_BASE_RETURNS + _RNG.randn(120) * 0.001)).cumprod().values,
    index=_DATES,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_high_correlation_warning():
    """Two tickers with correlation > 0.8 should produce a warning."""
    data_map = {
        "AAPL": _make_price_df(_CORRELATED_PRICES),
        "MSFT": _make_price_df(_CORRELATED_NOISE_PRICES),
    }
    provider = _build_provider_mock(data_map)

    results = await compute_correlations(
        candidate_ticker="AAPL",
        existing_tickers=["MSFT"],
        provider=provider,
        period="6mo",
        threshold=0.80,
    )

    assert len(results) == 1
    r = results[0]
    assert r.ticker == "AAPL"
    assert r.existing_ticker == "MSFT"
    assert r.correlation > 0.80
    assert r.warning is not None
    assert "High correlation" in r.warning
    assert "portfolio diversification risk" in r.warning


@pytest.mark.asyncio
async def test_low_correlation_no_warning():
    """Correlation < 0.8 should not produce a warning."""
    data_map = {
        "AAPL": _make_price_df(_CORRELATED_PRICES),
        "XYZ": _make_price_df(_UNCORRELATED_PRICES),
    }
    provider = _build_provider_mock(data_map)

    results = await compute_correlations(
        candidate_ticker="AAPL",
        existing_tickers=["XYZ"],
        provider=provider,
        period="6mo",
        threshold=0.80,
    )

    assert len(results) == 1
    r = results[0]
    assert abs(r.correlation) < 0.80
    assert r.warning is None


@pytest.mark.asyncio
async def test_negative_correlation():
    """Negative correlation should work; abs() checked against threshold."""
    data_map = {
        "AAPL": _make_price_df(_CORRELATED_PRICES),
        "BEAR": _make_price_df(_NEGATIVE_PRICES),
    }
    provider = _build_provider_mock(data_map)

    results = await compute_correlations(
        candidate_ticker="AAPL",
        existing_tickers=["BEAR"],
        provider=provider,
        period="6mo",
        threshold=0.80,
    )

    assert len(results) == 1
    r = results[0]
    # Correlation should be strongly negative
    assert r.correlation < 0
    # The absolute value should be above threshold, so warning is set
    assert abs(r.correlation) > 0.80
    assert r.warning is not None
    assert "High correlation" in r.warning


@pytest.mark.asyncio
async def test_missing_price_data():
    """Provider raises exception for a ticker -- skip it gracefully."""
    data_map = {
        "AAPL": _make_price_df(_CORRELATED_PRICES),
        # "FAIL" is not in data_map -- will be in fail_tickers
    }
    provider = _build_provider_mock(data_map, fail_tickers={"FAIL"})

    results = await compute_correlations(
        candidate_ticker="AAPL",
        existing_tickers=["FAIL"],
        provider=provider,
        period="6mo",
        threshold=0.80,
    )

    # Should skip the failed ticker, returning empty
    assert len(results) == 0


@pytest.mark.asyncio
async def test_empty_portfolio():
    """No existing tickers should return empty results."""
    data_map = {
        "AAPL": _make_price_df(_CORRELATED_PRICES),
    }
    provider = _build_provider_mock(data_map)

    results = await compute_correlations(
        candidate_ticker="AAPL",
        existing_tickers=[],
        provider=provider,
        period="6mo",
        threshold=0.80,
    )

    assert results == []


@pytest.mark.asyncio
async def test_results_sorted_by_abs_correlation():
    """Results should be sorted by absolute correlation descending."""
    data_map = {
        "CANDIDATE": _make_price_df(_CORRELATED_PRICES),
        "HIGH_CORR": _make_price_df(_CORRELATED_NOISE_PRICES),
        "LOW_CORR": _make_price_df(_UNCORRELATED_PRICES),
        "NEG_CORR": _make_price_df(_NEGATIVE_PRICES),
    }
    provider = _build_provider_mock(data_map)

    results = await compute_correlations(
        candidate_ticker="CANDIDATE",
        existing_tickers=["HIGH_CORR", "LOW_CORR", "NEG_CORR"],
        provider=provider,
        period="6mo",
        threshold=0.80,
    )

    assert len(results) == 3
    abs_corrs = [abs(r.correlation) for r in results]
    assert abs_corrs == sorted(abs_corrs, reverse=True), (
        f"Results not sorted by |correlation| desc: {abs_corrs}"
    )


def test_correlation_result_to_dict():
    """Verify CorrelationResult serialisation."""
    r = CorrelationResult(
        ticker="AAPL",
        existing_ticker="MSFT",
        correlation=0.87654321,
        period_days=119,
        warning="High correlation (0.88) between AAPL and MSFT — portfolio diversification risk",
    )
    d = r.to_dict()
    assert d["ticker"] == "AAPL"
    assert d["existing_ticker"] == "MSFT"
    assert d["correlation"] == 0.8765  # rounded to 4 decimal places
    assert d["period_days"] == 119
    assert d["warning"] is not None
    assert "AAPL" in d["warning"]

    # Also test with no warning
    r2 = CorrelationResult(
        ticker="AAPL",
        existing_ticker="XYZ",
        correlation=0.1234,
        period_days=100,
    )
    d2 = r2.to_dict()
    assert d2["warning"] is None
    assert d2["correlation"] == 0.1234
