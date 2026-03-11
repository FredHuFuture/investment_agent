"""Tests for Task 021: Batch Backtest Runner.

All tests use synthetic OHLCV data and mock agents -- no network calls.
"""
from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from agents.models import AgentOutput, Signal
from backtesting.batch_runner import (
    BatchConfig,
    BatchResult,
    BatchRunner,
    _detect_asset_type,
    _map_ticker,
    combo_key_from_agents,
)
from backtesting.models import BacktestConfig, BacktestResult, SimulatedTrade
from db.database import init_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(
    n: int = 60,
    start_price: float = 100.0,
    price_step: float = 0.5,
    start_date: str = "2024-01-02",
) -> pd.DataFrame:
    """Synthetic OHLCV DataFrame with n business-day rows."""
    dates = pd.bdate_range(start=start_date, periods=n)
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


def _mock_backtest_result(
    ticker: str = "TEST",
    agents: list[str] | None = None,
    total_return: float = 10.0,
    sharpe: float = 1.5,
    max_dd: float = -5.0,
    win_rate: float = 0.6,
    trades_count: int = 3,
) -> BacktestResult:
    """Create a synthetic BacktestResult for testing serialization."""
    cfg = BacktestConfig(
        ticker=ticker,
        start_date="2024-01-01",
        end_date="2024-12-31",
        agents=agents or ["TechnicalAgent"],
    )
    trades = [
        SimulatedTrade(
            entry_date="2024-01-10",
            entry_price=100.0,
            signal="BUY",
            confidence=70.0,
            shares=10.0,
            exit_date="2024-02-10",
            exit_price=110.0,
            exit_reason="signal_sell",
            pnl=100.0,
            pnl_pct=0.10,
            holding_days=31,
        )
    ]
    return BacktestResult(
        config=cfg,
        trades=trades[:trades_count],
        equity_curve=[
            {"date": "2024-01-01", "equity": 100_000},
            {"date": "2024-06-01", "equity": 105_000},
            {"date": "2024-12-31", "equity": 100_000 * (1 + total_return / 100)},
        ],
        metrics={
            "total_return_pct": total_return,
            "annualized_return_pct": total_return * 0.8,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sharpe * 1.2,
            "max_drawdown_pct": max_dd,
            "calmar_ratio": 2.0,
            "win_rate": win_rate,
            "profit_factor": 2.5,
            "total_trades": trades_count,
            "avg_holding_days": 30,
        },
        warnings=[],
    )


# ---------------------------------------------------------------------------
# 1. BatchConfig creation
# ---------------------------------------------------------------------------

def test_batch_config_creation() -> None:
    config = BatchConfig(
        tickers=["AAPL", "MSFT"],
        agent_combos=[["TechnicalAgent"]],
        start_date="2020-01-01",
        end_date="2025-12-31",
    )
    assert config.tickers == ["AAPL", "MSFT"]
    assert config.agent_combos == [["TechnicalAgent"]]
    assert config.initial_capital == 100_000.0
    assert config.position_size_pct == 1.0
    assert config.rebalance_frequency == "weekly"
    assert config.stop_loss_pct is None
    assert config.take_profit_pct is None


# ---------------------------------------------------------------------------
# 2. Single ticker, single combo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_runner_single_ticker_single_combo(tmp_path: Path) -> None:
    db_path = tmp_path / "batch1.db"
    await init_db(db_path)

    df = _make_ohlcv(30)
    start = str(df.index[0].date())
    end = str(df.index[-1].date())

    config = BatchConfig(
        tickers=["TEST"],
        agent_combos=[["TechnicalAgent"]],
        start_date=start,
        end_date=end,
    )

    mock_output = AgentOutput(
        agent_name="TechnicalAgent", ticker="TEST",
        signal=Signal.BUY, confidence=70.0, reasoning="mock",
    )

    with patch("backtesting.batch_runner.cache_price_data", new_callable=AsyncMock) as mock_cache, \
         patch("backtesting.engine._make_agent") as mock_make_agent:
        mock_cache.return_value = df
        mock_agent = AsyncMock()
        mock_agent.analyze = AsyncMock(return_value=mock_output)
        mock_make_agent.return_value = mock_agent

        runner = BatchRunner(config)
        result = await runner.run(db_path=str(db_path))

    assert "TEST" in result.results
    assert "TechnicalAgent" in result.results["TEST"]
    assert isinstance(result.results["TEST"]["TechnicalAgent"], BacktestResult)
    assert len(result.errors) == 0


# ---------------------------------------------------------------------------
# 3. Multiple tickers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_runner_multiple_tickers(tmp_path: Path) -> None:
    db_path = tmp_path / "batch2.db"
    await init_db(db_path)

    df = _make_ohlcv(30)
    start = str(df.index[0].date())
    end = str(df.index[-1].date())

    config = BatchConfig(
        tickers=["AAPL", "MSFT"],
        agent_combos=[["TechnicalAgent"]],
        start_date=start,
        end_date=end,
    )

    mock_output = AgentOutput(
        agent_name="TechnicalAgent", ticker="TEST",
        signal=Signal.BUY, confidence=70.0, reasoning="mock",
    )

    with patch("backtesting.batch_runner.cache_price_data", new_callable=AsyncMock) as mock_cache, \
         patch("backtesting.engine._make_agent") as mock_make_agent:
        mock_cache.return_value = df
        mock_agent = AsyncMock()
        mock_agent.analyze = AsyncMock(return_value=mock_output)
        mock_make_agent.return_value = mock_agent

        runner = BatchRunner(config)
        result = await runner.run(db_path=str(db_path))

    assert "AAPL" in result.results
    assert "MSFT" in result.results
    assert len(result.errors) == 0


# ---------------------------------------------------------------------------
# 4. Multiple combos per ticker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_runner_multiple_combos(tmp_path: Path) -> None:
    db_path = tmp_path / "batch3.db"
    await init_db(db_path)

    df = _make_ohlcv(30)
    start = str(df.index[0].date())
    end = str(df.index[-1].date())

    config = BatchConfig(
        tickers=["AAPL"],
        agent_combos=[["TechnicalAgent"], ["TechnicalAgent", "MacroAgent"]],
        start_date=start,
        end_date=end,
    )

    mock_output = AgentOutput(
        agent_name="TechnicalAgent", ticker="AAPL",
        signal=Signal.BUY, confidence=70.0, reasoning="mock",
    )

    with patch("backtesting.batch_runner.cache_price_data", new_callable=AsyncMock) as mock_cache, \
         patch("backtesting.engine._make_agent") as mock_make_agent:
        mock_cache.return_value = df
        mock_agent = AsyncMock()
        mock_agent.analyze = AsyncMock(return_value=mock_output)
        mock_make_agent.return_value = mock_agent

        runner = BatchRunner(config)
        result = await runner.run(db_path=str(db_path))

    assert "AAPL" in result.results
    assert "TechnicalAgent" in result.results["AAPL"]
    assert "MacroAgent+TechnicalAgent" in result.results["AAPL"]


# ---------------------------------------------------------------------------
# 5. Error isolation (one ticker fails, others succeed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_runner_error_isolation(tmp_path: Path) -> None:
    db_path = tmp_path / "batch4.db"
    await init_db(db_path)

    df = _make_ohlcv(30)
    start = str(df.index[0].date())
    end = str(df.index[-1].date())

    config = BatchConfig(
        tickers=["AAPL", "BADTICKER"],
        agent_combos=[["TechnicalAgent"]],
        start_date=start,
        end_date=end,
    )

    mock_output = AgentOutput(
        agent_name="TechnicalAgent", ticker="AAPL",
        signal=Signal.BUY, confidence=70.0, reasoning="mock",
    )

    async def _mock_cache(ticker, start, end, asset_type, db_path):
        if ticker == "BADTICKER":
            raise ValueError("No data for BADTICKER")
        return df

    with patch("backtesting.batch_runner.cache_price_data", side_effect=_mock_cache), \
         patch("backtesting.engine._make_agent") as mock_make_agent:
        mock_agent = AsyncMock()
        mock_agent.analyze = AsyncMock(return_value=mock_output)
        mock_make_agent.return_value = mock_agent

        runner = BatchRunner(config)
        result = await runner.run(db_path=str(db_path))

    # AAPL should succeed
    assert "AAPL" in result.results
    assert "TechnicalAgent" in result.results["AAPL"]
    # BADTICKER should have an error
    assert any("BADTICKER" in e for e in result.errors)


# ---------------------------------------------------------------------------
# 6. Crypto auto-detect
# ---------------------------------------------------------------------------

def test_crypto_auto_detect() -> None:
    assert _detect_asset_type("BTC") == "btc"
    assert _detect_asset_type("BTC-USD") == "btc"
    assert _detect_asset_type("ETH") == "eth"
    assert _detect_asset_type("ETH-USD") == "eth"
    assert _detect_asset_type("AAPL") == "stock"
    assert _detect_asset_type("MSFT") == "stock"

    assert _map_ticker("BTC", "btc") == "BTC-USD"
    assert _map_ticker("ETH", "eth") == "ETH-USD"
    assert _map_ticker("AAPL", "stock") == "AAPL"


# ---------------------------------------------------------------------------
# 7. to_json() valid JSON round-trip
# ---------------------------------------------------------------------------

def test_batch_result_to_json() -> None:
    result = BatchResult()
    result.results["AAPL"] = {
        "TechnicalAgent": _mock_backtest_result("AAPL", total_return=15.0),
    }
    result.results["BTC"] = {
        "CryptoAgent": _mock_backtest_result("BTC-USD", ["CryptoAgent"], total_return=100.0),
    }

    json_str = result.to_json()
    data = json.loads(json_str)

    assert "results" in data
    assert "AAPL" in data["results"]
    assert "TechnicalAgent" in data["results"]["AAPL"]
    assert data["results"]["AAPL"]["TechnicalAgent"]["metrics"]["total_return_pct"] == 15.0
    assert "BTC" in data["results"]
    assert data["results"]["BTC"]["CryptoAgent"]["metrics"]["total_return_pct"] == 100.0


# ---------------------------------------------------------------------------
# 8. to_summary_dict() correct metrics
# ---------------------------------------------------------------------------

def test_batch_result_to_summary_dict() -> None:
    result = BatchResult()
    result.results["AAPL"] = {
        "TechnicalAgent": _mock_backtest_result("AAPL", total_return=15.0, sharpe=1.8),
    }

    summary = result.to_summary_dict()
    assert "AAPL" in summary
    assert "TechnicalAgent" in summary["AAPL"]
    m = summary["AAPL"]["TechnicalAgent"]
    assert m["total_return_pct"] == 15.0
    assert m["sharpe_ratio"] == 1.8
    assert m["win_rate"] == 0.6
    assert m["total_trades"] == 3


# ---------------------------------------------------------------------------
# 9. combo_key sorting determinism
# ---------------------------------------------------------------------------

def test_combo_key_sorting() -> None:
    key1 = combo_key_from_agents(["CryptoAgent", "TechnicalAgent"])
    key2 = combo_key_from_agents(["TechnicalAgent", "CryptoAgent"])
    assert key1 == key2
    assert key1 == "CryptoAgent+TechnicalAgent"

    # Single agent
    key3 = combo_key_from_agents(["TechnicalAgent"])
    assert key3 == "TechnicalAgent"


# ---------------------------------------------------------------------------
# 10. Shared price cache (one fetch per ticker)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_runner_shared_price_cache(tmp_path: Path) -> None:
    db_path = tmp_path / "batch5.db"
    await init_db(db_path)

    df = _make_ohlcv(30)
    start = str(df.index[0].date())
    end = str(df.index[-1].date())

    config = BatchConfig(
        tickers=["AAPL"],
        agent_combos=[["TechnicalAgent"], ["TechnicalAgent", "MacroAgent"]],
        start_date=start,
        end_date=end,
    )

    mock_output = AgentOutput(
        agent_name="TechnicalAgent", ticker="AAPL",
        signal=Signal.BUY, confidence=70.0, reasoning="mock",
    )

    with patch("backtesting.batch_runner.cache_price_data", new_callable=AsyncMock) as mock_cache, \
         patch("backtesting.engine._make_agent") as mock_make_agent:
        mock_cache.return_value = df
        mock_agent = AsyncMock()
        mock_agent.analyze = AsyncMock(return_value=mock_output)
        mock_make_agent.return_value = mock_agent

        runner = BatchRunner(config)
        result = await runner.run(db_path=str(db_path))

    # Price data should be fetched only ONCE for AAPL despite two combos
    assert mock_cache.call_count == 1
    # Both combos should have results
    assert len(result.results["AAPL"]) == 2
