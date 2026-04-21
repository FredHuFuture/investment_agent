"""Tests for SIG-04: Transaction cost model in backtester.

Tests verify:
1. Asset-type defaults (equity=0.001, crypto=0.0025)
2. Cost strictly reduces total_return vs cost=0.0
3. Costs applied at BOTH entry AND exit (AP-06 guard)

_DFProvider is defined inline in this file — NOT imported from test_013_backtesting.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pandas as pd
import pytest

from backtesting.engine import Backtester
from backtesting.models import (
    BacktestConfig,
    COST_PER_TRADE_CRYPTO,
    COST_PER_TRADE_EQUITY,
    default_cost_per_trade,
)


# ---------------------------------------------------------------------------
# _DFProvider: inline DataProvider for backtester tests
# Matches the subset of the DataProvider interface that Backtester.run
# actually calls in provider-mode. Any method not used by the backtester
# either returns None (fundamentals, news) or raises NotImplementedError.
# ---------------------------------------------------------------------------

class _DFProvider:
    """Minimal DataProvider for backtester tests — reads prices from pre-built DataFrame.

    Matches the subset of the DataProvider interface that `Backtester.run` actually
    calls in backtest_mode. Any method not used by the backtester either returns
    None (fundamentals, news) or raises NotImplementedError (unused surfaces).
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df.copy()

    async def get_price_history(
        self,
        ticker: str,
        period: str = "max",
        interval: str = "1d",
    ) -> pd.DataFrame:
        return self._df.copy()

    async def get_current_price(self, ticker: str) -> float:
        return float(self._df["Close"].iloc[-1])

    async def get_key_stats(self, ticker: str) -> Any:
        return None  # FundamentalAgent returns HOLD in backtest_mode (FOUND-04)

    async def get_news(self, ticker: str, limit: int = 10) -> list[dict]:
        return []

    async def get_fundamentals(self, ticker: str) -> dict | None:
        return None

    async def get_info(self, ticker: str) -> dict | None:
        return {"sector": "Technology", "industry": "Consumer Electronics"}


# ---------------------------------------------------------------------------
# Deterministic price series that guarantees multiple round-trips
# (BLOCKER 5 fix: alternating ±5% cycles instead of noise+punch)
# ---------------------------------------------------------------------------

def _make_price_df(start_price: float = 100.0, n_cycles: int = 6) -> pd.DataFrame:
    """Deterministic BUY/SELL-triggering OHLCV series (BLOCKER 5 fix).

    Constructs alternating 20-day +5%-uptrend + 20-day -5%-downtrend cycles.
    This guarantees:
        - TechnicalAgent RSI oscillates above 70 (SELL trigger) and below 30 (BUY trigger)
        - SMA20 crossovers happen at each cycle boundary (BUY/SELL trigger)
        - At least 2 round-trips (BUY → SELL) for n_cycles >= 2
    Avoids the previous noise+punch approach that could produce zero trades
    depending on threshold tuning.
    """
    prices: list[float] = [start_price]
    for _cycle in range(n_cycles):
        # 20 bars of +5% linear uptrend
        up_target = prices[-1] * 1.05
        up_step = (up_target - prices[-1]) / 20
        for _ in range(20):
            prices.append(prices[-1] + up_step)
        # 20 bars of -5% linear downtrend
        down_target = prices[-1] * 0.95
        down_step = (down_target - prices[-1]) / 20
        for _ in range(20):
            prices.append(prices[-1] + down_step)
    n_days = len(prices)
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    close = pd.Series(prices, index=dates)
    return pd.DataFrame(
        {
            "Open": close * 0.999,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": [1_000_000] * n_days,
        }
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_default_costs_per_asset_type() -> None:
    """SIG-04: default_cost_per_trade returns correct defaults for each asset class."""
    assert default_cost_per_trade("stock") == COST_PER_TRADE_EQUITY
    assert default_cost_per_trade("crypto") == COST_PER_TRADE_CRYPTO
    assert default_cost_per_trade("btc") == COST_PER_TRADE_CRYPTO
    assert default_cost_per_trade("eth") == COST_PER_TRADE_CRYPTO
    assert default_cost_per_trade("btc-usd") == COST_PER_TRADE_CRYPTO
    assert default_cost_per_trade("eth-usd") == COST_PER_TRADE_CRYPTO
    # Numeric checks
    assert abs(COST_PER_TRADE_EQUITY - 0.001) < 1e-9
    assert abs(COST_PER_TRADE_CRYPTO - 0.0025) < 1e-9


def test_cost_reduces_total_return() -> None:
    """SIG-04: backtest with cost_per_trade=0.001 has strictly lower total_return than cost=0.0."""
    df = _make_price_df(n_cycles=6)  # ~240 bars with guaranteed multiple round-trips
    end_date = df.index[-1].strftime("%Y-%m-%d")
    cfg_no_cost = BacktestConfig(
        ticker="AAPL",
        start_date="2024-01-01",
        end_date=end_date,
        initial_capital=100_000.0,
        cost_per_trade=0.0,
        rebalance_frequency="daily",
        stop_loss_pct=None,
        take_profit_pct=None,
    )
    cfg_with_cost = BacktestConfig(
        ticker="AAPL",
        start_date="2024-01-01",
        end_date=end_date,
        initial_capital=100_000.0,
        cost_per_trade=0.001,
        rebalance_frequency="daily",
        stop_loss_pct=None,
        take_profit_pct=None,
    )
    # Build two independent providers (each call consumes the DataFrame once)
    result_no_cost = asyncio.run(
        Backtester(_DFProvider(df)).run(cfg_no_cost)
    )
    result_with_cost = asyncio.run(
        Backtester(_DFProvider(df)).run(cfg_with_cost)
    )

    # Precondition guard (BLOCKER 5 fix): if synthetic series somehow produced
    # zero trades despite being designed to, skip with a clear message instead
    # of letting the monotonicity assertion pass vacuously.
    if result_no_cost.metrics["n_trades"] == 0 and result_with_cost.metrics["n_trades"] == 0:
        pytest.skip("Synthetic series produced no trades — adjust _make_price_df cycle shape")

    # Round-trip = BUY + SELL = 2 trade events; expect at least 2
    assert result_with_cost.metrics["n_trades"] >= 2, (
        f"expected >= 2 trades (one full round-trip), "
        f"got {result_with_cost.metrics['n_trades']}"
    )

    # SIG-04 primary success criterion: costs strictly reduce return
    total_return_no_cost = result_no_cost.metrics.get("total_return_pct", 0.0)
    total_return_with_cost = result_with_cost.metrics.get("total_return_pct", 0.0)
    delta = total_return_no_cost - total_return_with_cost
    assert delta > 0.0001, (
        f"cost-on total_return {total_return_with_cost} "
        f"should be strictly less than cost-off {total_return_no_cost}; "
        f"delta={delta}"
    )
    assert result_with_cost.metrics["total_costs_paid"] > 0.0
    assert "n_trades" in result_with_cost.metrics
    assert "cost_drag_pct" in result_with_cost.metrics
    assert "effective_cost_per_trade" in result_with_cost.metrics


def test_cost_applied_at_entry_and_exit_double() -> None:
    """AP-06 guard: total_costs_paid > single-side cost floor (exit cost also applied)."""
    df = _make_price_df(n_cycles=3)  # ~120 bars with at least 1 round-trip
    end_date = df.index[-1].strftime("%Y-%m-%d")
    cfg = BacktestConfig(
        ticker="AAPL",
        start_date="2024-01-01",
        end_date=end_date,
        initial_capital=100_000.0,
        cost_per_trade=0.002,  # 20 bps per side
        position_size_pct=0.10,
        rebalance_frequency="daily",
        stop_loss_pct=None,
        take_profit_pct=None,
    )
    result = asyncio.run(Backtester(_DFProvider(df)).run(cfg))
    if result.metrics["n_trades"] == 0:
        pytest.skip(
            "Synthetic series produced no trades — AP-06 guard cannot be tested"
        )
    # Per-trade cost floor: single-side cost = trade_value * cost_per_trade
    # If exit were NOT applied, per-trade average would equal the single-side floor.
    # With both sides applied, per-trade average should be ~2x single-side cost.
    single_side_cost = 100_000.0 * 0.10 * 0.002  # = 20.0
    per_trade_cost = (
        result.metrics["total_costs_paid"] / max(1, result.metrics["n_trades"])
    )
    assert per_trade_cost > single_side_cost * 0.9, (
        f"per-trade cost {per_trade_cost} is at or below single-side floor "
        f"{single_side_cost} — exit cost not applied (AP-06 violation)"
    )
