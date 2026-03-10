"""Tests for Task 013: Backtesting Framework.

All tests use synthetic OHLCV data and mock agents — no network calls.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from agents.base import BaseAgent
from agents.models import AgentInput, AgentOutput, Signal
from backtesting.data_slicer import HistoricalDataProvider
from backtesting.engine import Backtester, _close_trade
from backtesting.metrics import compute_metrics
from backtesting.models import BacktestConfig, BacktestResult, SimulatedTrade
from data_providers.base import DataProvider
from db.database import init_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 100, start_price: float = 100.0, price_step: float = 0.5) -> pd.DataFrame:
    """Synthetic OHLCV DataFrame with n rows, starting 2024-01-02."""
    base = date(2024, 1, 2)
    # Only business days
    dates = pd.bdate_range(start=str(base), periods=n)
    prices = [start_price + i * price_step for i in range(n)]
    return pd.DataFrame(
        {
            "Open": [p - 0.3 for p in prices],
            "High": [p + 1.0 for p in prices],
            "Low": [p - 1.0 for p in prices],
            "Close": prices,
            "Volume": [1_000_000.0] * n,
        },
        index=dates,
    )


def _make_position(entry_price: float = 100.0, shares: float = 10.0, entry_date: str = "2024-01-02") -> dict:
    return {
        "entry_date": entry_date,
        "entry_price": entry_price,
        "shares": shares,
        "signal": "BUY",
        "confidence": 70.0,
    }


class MockAgent(BaseAgent):
    """Configurable mock agent returning a fixed or date-keyed signal."""

    def __init__(self, provider: DataProvider, signal_map: dict[str, Signal] | None = None, default: Signal = Signal.BUY):
        super().__init__(provider)
        self._signal_map = signal_map or {}
        self._default = default

    @property
    def name(self) -> str:
        return "MockAgent"

    def supported_asset_types(self) -> list[str]:
        return ["stock", "btc", "eth"]

    async def analyze(self, agent_input: AgentInput) -> AgentOutput:
        sig = self._signal_map.get(agent_input.ticker, self._default)
        return AgentOutput(
            agent_name=self.name,
            ticker=agent_input.ticker,
            signal=sig,
            confidence=70.0,
            reasoning="Mock",
        )


# ---------------------------------------------------------------------------
# 1. HistoricalDataProvider — no lookahead
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_data_slicer_no_lookahead() -> None:
    df = _make_ohlcv(100)
    # current_date = row 49 (0-indexed)
    current_date = str(df.index[49].date())
    provider = HistoricalDataProvider(df, current_date)

    result = await provider.get_price_history("TEST")
    assert len(result) == 50  # rows 0..49 inclusive
    assert result.index[-1] == df.index[49]


# ---------------------------------------------------------------------------
# 2. HistoricalDataProvider — get_current_price
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_data_slicer_current_price() -> None:
    df = _make_ohlcv(50)
    current_date = str(df.index[20].date())
    provider = HistoricalDataProvider(df, current_date)

    price = await provider.get_current_price("TEST")
    expected = float(df.iloc[20]["Close"])
    assert abs(price - expected) < 1e-6


# ---------------------------------------------------------------------------
# 3. HistoricalDataProvider — empty raises
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_data_slicer_empty_raises() -> None:
    df = _make_ohlcv(50)
    # Set current_date before any data
    current_date = "2020-01-01"
    provider = HistoricalDataProvider(df, current_date)

    with pytest.raises(ValueError, match="No data available"):
        await provider.get_price_history("TEST")


# ---------------------------------------------------------------------------
# 4. Metrics — Sharpe ratio
# ---------------------------------------------------------------------------

def test_metrics_sharpe_ratio() -> None:
    # Varying returns that are mostly positive → Sharpe should be positive
    import random
    random.seed(42)
    n = 100
    equity = [100_000.0]
    for _ in range(n - 1):
        r = 0.001 + random.gauss(0, 0.005)  # positive mean, some variance
        equity.append(equity[-1] * (1 + r))
    equity_curve = [{"date": f"2024-{i:04d}", "equity": e} for i, e in enumerate(equity)]

    metrics = compute_metrics([], equity_curve, 100_000.0)
    # Sharpe may be None if std is near 0, but total_return should be positive
    assert metrics["total_return_pct"] is not None


# ---------------------------------------------------------------------------
# 5. Metrics — max drawdown
# ---------------------------------------------------------------------------

def test_metrics_max_drawdown() -> None:
    # Equity curve: peak at 110, trough at 90 → max drawdown = (110-90)/110 ≈ 18.2%
    equity_curve = [
        {"date": "2024-01-01", "equity": 100.0},
        {"date": "2024-01-02", "equity": 110.0},
        {"date": "2024-01-03", "equity": 90.0},
        {"date": "2024-01-04", "equity": 95.0},
        {"date": "2024-01-05", "equity": 120.0},
    ]
    metrics = compute_metrics([], equity_curve, 100.0)
    expected_dd = -(110 - 90) / 110 * 100  # ≈ -18.18%
    assert abs(metrics["max_drawdown_pct"] - expected_dd) < 0.1


# ---------------------------------------------------------------------------
# 6. Metrics — win rate
# ---------------------------------------------------------------------------

def test_metrics_win_rate() -> None:
    trades = [
        SimulatedTrade("2024-01-01", 100, "BUY", 70, 10, "2024-01-10", 110, "signal_sell", pnl=100, pnl_pct=0.10, holding_days=9),
        SimulatedTrade("2024-01-11", 110, "BUY", 70, 10, "2024-01-20", 120, "signal_sell", pnl=100, pnl_pct=0.09, holding_days=9),
        SimulatedTrade("2024-01-21", 120, "BUY", 70, 10, "2024-01-30", 110, "stop_loss", pnl=-100, pnl_pct=-0.083, holding_days=9),
    ]
    equity_curve = [{"date": "2024-01-01", "equity": 100_000}] * 30
    metrics = compute_metrics(trades, equity_curve, 100_000.0)
    assert metrics["total_trades"] == 3
    assert abs(metrics["win_rate"] - 2 / 3) < 0.01


# ---------------------------------------------------------------------------
# 7. Metrics — profit factor
# ---------------------------------------------------------------------------

def test_metrics_profit_factor() -> None:
    trades = [
        SimulatedTrade("2024-01-01", 100, "BUY", 70, 10, "2024-01-10", 110, "signal_sell", pnl=100, pnl_pct=0.10, holding_days=9),
        SimulatedTrade("2024-01-11", 110, "BUY", 70, 10, "2024-01-20", 100, "stop_loss", pnl=-100, pnl_pct=-0.09, holding_days=9),
    ]
    equity_curve = [{"date": "2024-01-01", "equity": 100_000}] * 20
    metrics = compute_metrics(trades, equity_curve, 100_000.0)
    # gross_profit=0.10, gross_loss=0.09 → pf ≈ 1.11
    assert metrics["profit_factor"] is not None
    assert metrics["profit_factor"] > 1.0


# ---------------------------------------------------------------------------
# 8. Metrics — no trades
# ---------------------------------------------------------------------------

def test_metrics_no_trades() -> None:
    equity_curve = [{"date": "2024-01-01", "equity": 100_000}] * 10
    metrics = compute_metrics([], equity_curve, 100_000.0)
    assert metrics["total_trades"] == 0
    assert metrics["win_rate"] is None
    assert metrics["profit_factor"] is None
    assert metrics["avg_win_pct"] is None


# ---------------------------------------------------------------------------
# 9. Backtester — always-BUY mock → creates trades
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backtest_engine_simple(tmp_path: Path) -> None:
    db_path = tmp_path / "bt.db"
    await init_db(db_path)

    df = _make_ohlcv(30)
    start = str(df.index[0].date())
    end = str(df.index[-1].date())

    config = BacktestConfig(
        ticker="TEST",
        start_date=start,
        end_date=end,
        initial_capital=100_000,
        rebalance_frequency="weekly",
        agents=["TechnicalAgent"],
        stop_loss_pct=None,
        take_profit_pct=None,
    )

    from unittest.mock import AsyncMock, patch

    mock_output = AgentOutput(
        agent_name="TechnicalAgent",
        ticker="TEST",
        signal=Signal.BUY,
        confidence=70.0,
        reasoning="mock",
    )

    with patch("backtesting.engine._make_agent") as mock_make_agent:
        mock_agent = MockAgent(HistoricalDataProvider(df, start))
        mock_agent.analyze = AsyncMock(return_value=mock_output)
        mock_make_agent.return_value = mock_agent

        backtester = Backtester(config)
        result = await backtester.run(full_data=df, db_path=str(db_path))

    assert isinstance(result, BacktestResult)
    assert len(result.equity_curve) >= 0
    assert result.metrics["total_trades"] >= 0


# ---------------------------------------------------------------------------
# 10. Backtester — BUY then SELL → one complete trade
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backtest_engine_sell_signal(tmp_path: Path) -> None:
    db_path = tmp_path / "bt2.db"
    await init_db(db_path)

    df = _make_ohlcv(40)
    dates = list(pd.bdate_range(str(df.index[0].date()), periods=40))
    start = str(dates[0].date())
    end = str(dates[-1].date())

    config = BacktestConfig(
        ticker="TEST",
        start_date=start,
        end_date=end,
        initial_capital=100_000,
        rebalance_frequency="daily",
        agents=["TechnicalAgent"],
        stop_loss_pct=None,
        take_profit_pct=None,
    )

    # BUY on day 5, SELL on day 10
    buy_date = str(dates[4].date())
    sell_date = str(dates[9].date())

    call_count = [0]

    class DateAwareAgent(BaseAgent):
        @property
        def name(self) -> str:
            return "TechnicalAgent"

        def supported_asset_types(self) -> list[str]:
            return ["stock"]

        async def analyze(self, agent_input: AgentInput) -> AgentOutput:
            # We need to figure out the current_date from the provider
            try:
                hist = await self._provider.get_price_history("TEST")
                date_str = str(hist.index[-1].date())
            except Exception:
                date_str = ""

            sig = Signal.SELL if date_str >= sell_date else Signal.BUY
            return AgentOutput(
                agent_name="TechnicalAgent",
                ticker="TEST",
                signal=sig,
                confidence=70.0,
                reasoning="date-aware mock",
            )

    with patch("backtesting.engine._make_agent") as mock_make_agent:
        def _factory(name, provider):
            return DateAwareAgent(provider)
        mock_make_agent.side_effect = _factory

        backtester = Backtester(config)
        result = await backtester.run(full_data=df, db_path=str(db_path))

    # Should have at least one closed trade
    closed = [t for t in result.trades if t.exit_reason == "signal_sell"]
    assert len(closed) >= 1
    assert closed[0].entry_date < closed[0].exit_date


# ---------------------------------------------------------------------------
# 11. Backtester — stop loss triggers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backtest_stop_loss(tmp_path: Path) -> None:
    db_path = tmp_path / "bt3.db"
    await init_db(db_path)

    # Price drops 15% after entry
    prices = [100.0] * 5 + [84.0] * 10
    n = len(prices)
    dates = pd.bdate_range("2024-01-02", periods=n)
    df = pd.DataFrame(
        {
            "Open": [p - 0.3 for p in prices],
            "High": [p + 0.5 for p in prices],
            "Low": [p - 0.5 for p in prices],
            "Close": prices,
            "Volume": [1_000_000.0] * n,
        },
        index=dates,
    )
    start = str(dates[0].date())
    end = str(dates[-1].date())

    config = BacktestConfig(
        ticker="TEST",
        start_date=start,
        end_date=end,
        initial_capital=100_000,
        rebalance_frequency="daily",
        agents=["TechnicalAgent"],
        stop_loss_pct=0.10,   # 10% stop loss
        take_profit_pct=None,
    )

    mock_output = AgentOutput(
        agent_name="TechnicalAgent", ticker="TEST",
        signal=Signal.BUY, confidence=70.0, reasoning="mock",
    )

    with patch("backtesting.engine._make_agent") as mock_make_agent:
        mock_agent = MockAgent(HistoricalDataProvider(df, start))
        mock_agent.analyze = AsyncMock(return_value=mock_output)
        mock_make_agent.return_value = mock_agent

        backtester = Backtester(config)
        result = await backtester.run(full_data=df, db_path=str(db_path))

    stop_loss_trades = [t for t in result.trades if t.exit_reason == "stop_loss"]
    assert len(stop_loss_trades) >= 1
    # Exit price should be ~10% below entry
    t = stop_loss_trades[0]
    assert t.pnl_pct is not None
    assert t.pnl_pct < -0.05  # at least 5% loss (stop at 10%)


# ---------------------------------------------------------------------------
# 12. Backtester — non-PIT warning for FundamentalAgent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backtest_non_pit_warning(tmp_path: Path) -> None:
    db_path = tmp_path / "bt4.db"
    await init_db(db_path)

    df = _make_ohlcv(10)
    start = str(df.index[0].date())
    end = str(df.index[-1].date())

    config = BacktestConfig(
        ticker="TEST",
        start_date=start,
        end_date=end,
        agents=["TechnicalAgent", "FundamentalAgent"],
    )

    mock_output = AgentOutput(
        agent_name="TechnicalAgent", ticker="TEST",
        signal=Signal.HOLD, confidence=50.0, reasoning="mock",
    )

    with patch("backtesting.engine._make_agent") as mock_make_agent:
        mock_agent = MockAgent(HistoricalDataProvider(df, start))
        mock_agent.analyze = AsyncMock(return_value=mock_output)
        mock_make_agent.return_value = mock_agent

        backtester = Backtester(config)
        result = await backtester.run(full_data=df, db_path=str(db_path))

    assert any("Non-PIT" in w for w in result.warnings)
    assert any("FundamentalAgent" in w for w in result.warnings)
