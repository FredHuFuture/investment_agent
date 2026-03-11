"""Tests for Task 020: Adaptive Weight + Signal Threshold Optimization.

All tests use synthetic data and mock agents -- no network calls.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from agents.models import AgentOutput, Signal
from backtesting.models import BacktestConfig, BacktestResult, SimulatedTrade
from db.database import init_db
from engine.aggregator import SignalAggregator
from engine.weight_adapter import AdaptiveWeights, WeightAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_backtest_result(
    ticker: str = "TEST",
    agents: list[str] | None = None,
    sharpe: float = 1.5,
    total_return: float = 10.0,
    max_dd: float = -5.0,
    signals_log: list[dict] | None = None,
    trades: list[SimulatedTrade] | None = None,
    asset_type: str = "stock",
) -> BacktestResult:
    """Create a synthetic BacktestResult."""
    cfg = BacktestConfig(
        ticker=ticker,
        start_date="2024-01-01",
        end_date="2024-12-31",
        agents=agents or ["TechnicalAgent"],
        asset_type=asset_type,
    )
    default_trades = [
        SimulatedTrade(
            entry_date="2024-01-10", entry_price=100.0, signal="BUY",
            confidence=70.0, shares=10.0, exit_date="2024-02-10",
            exit_price=110.0, exit_reason="signal_sell",
            pnl=100.0, pnl_pct=0.10, holding_days=31,
        ),
        SimulatedTrade(
            entry_date="2024-03-01", entry_price=105.0, signal="BUY",
            confidence=60.0, shares=10.0, exit_date="2024-04-01",
            exit_price=100.0, exit_reason="signal_sell",
            pnl=-50.0, pnl_pct=-0.048, holding_days=31,
        ),
    ]
    default_signals = [
        {"date": "2024-01-10", "signal": "BUY", "confidence": 70.0, "raw_score": 0.45,
         "agent_signals": [{"agent": "TechnicalAgent", "signal": "BUY", "confidence": 70.0}]},
        {"date": "2024-02-10", "signal": "SELL", "confidence": 65.0, "raw_score": -0.35,
         "agent_signals": [{"agent": "TechnicalAgent", "signal": "SELL", "confidence": 65.0}]},
        {"date": "2024-03-01", "signal": "BUY", "confidence": 60.0, "raw_score": 0.32,
         "agent_signals": [{"agent": "TechnicalAgent", "signal": "BUY", "confidence": 60.0}]},
        {"date": "2024-04-01", "signal": "SELL", "confidence": 55.0, "raw_score": -0.40,
         "agent_signals": [{"agent": "TechnicalAgent", "signal": "SELL", "confidence": 55.0}]},
    ]
    return BacktestResult(
        config=cfg,
        trades=trades if trades is not None else default_trades,
        equity_curve=[
            {"date": "2024-01-01", "equity": 100_000},
            {"date": "2024-12-31", "equity": 100_000 * (1 + total_return / 100)},
        ],
        metrics={
            "total_return_pct": total_return,
            "sharpe_ratio": sharpe,
            "max_drawdown_pct": max_dd,
            "win_rate": 0.6,
            "total_trades": 2,
        },
        agent_signals_log=signals_log if signals_log is not None else default_signals,
    )


# ---------------------------------------------------------------------------
# 1. EWMA all correct -> ~1.0
# ---------------------------------------------------------------------------

def test_ewma_accuracy_all_correct() -> None:
    adapter = WeightAdapter()
    outcomes = [True] * 50
    acc = adapter._ewma_accuracy(outcomes)
    assert acc > 0.95


# ---------------------------------------------------------------------------
# 2. EWMA all wrong -> ~0.0
# ---------------------------------------------------------------------------

def test_ewma_accuracy_all_wrong() -> None:
    adapter = WeightAdapter()
    outcomes = [False] * 50
    acc = adapter._ewma_accuracy(outcomes)
    assert acc < 0.05


# ---------------------------------------------------------------------------
# 3. EWMA mixed -> ~0.5
# ---------------------------------------------------------------------------

def test_ewma_accuracy_mixed() -> None:
    adapter = WeightAdapter()
    # Alternating True/False
    outcomes = [i % 2 == 0 for i in range(100)]
    acc = adapter._ewma_accuracy(outcomes)
    assert 0.4 < acc < 0.6


# ---------------------------------------------------------------------------
# 4. EWMA recency bias
# ---------------------------------------------------------------------------

def test_ewma_recency_bias() -> None:
    adapter = WeightAdapter()
    # Many False followed by some True -- should be above 0.5 due to recency
    outcomes = [False] * 30 + [True] * 10
    acc = adapter._ewma_accuracy(outcomes)
    assert acc > 0.5


# ---------------------------------------------------------------------------
# 5. EWMA empty -> 0.5 prior
# ---------------------------------------------------------------------------

def test_ewma_accuracy_empty_returns_prior() -> None:
    adapter = WeightAdapter()
    acc = adapter._ewma_accuracy([])
    assert acc == 0.5


# ---------------------------------------------------------------------------
# 6. compute_weights_from_backtest -- better agent gets higher weight
# ---------------------------------------------------------------------------

def test_compute_weights_from_backtest() -> None:
    adapter = WeightAdapter()

    # TechnicalAgent with high Sharpe = 3.0
    tech_result = _mock_backtest_result(
        ticker="AAPL", agents=["TechnicalAgent"], sharpe=3.0,
    )
    # CryptoAgent with lower Sharpe = 1.0
    crypto_result = _mock_backtest_result(
        ticker="AAPL", agents=["CryptoAgent"], sharpe=1.0,
    )

    batch_results = {
        "AAPL": {
            "TechnicalAgent": tech_result,
            "CryptoAgent": crypto_result,
        }
    }

    weights = adapter.compute_weights_from_backtest(batch_results)

    assert weights.source == "backtest"
    assert "stock" in weights.weights
    stock_w = weights.weights["stock"]
    # TechnicalAgent should have higher weight than CryptoAgent
    assert stock_w["TechnicalAgent"] > stock_w["CryptoAgent"]
    # Weights should sum to ~1.0
    total = sum(stock_w.values())
    assert abs(total - 1.0) < 0.01


# ---------------------------------------------------------------------------
# 7. compute_weights insufficient signals -> default weights
# ---------------------------------------------------------------------------

def test_compute_weights_no_data_returns_defaults() -> None:
    adapter = WeightAdapter()
    # Empty batch results
    weights = adapter.compute_weights_from_backtest({})
    assert weights.source == "default"
    assert weights.sample_size == 0


# ---------------------------------------------------------------------------
# 8. threshold optimization finds a threshold
# ---------------------------------------------------------------------------

def test_threshold_optimization() -> None:
    adapter = WeightAdapter()
    result = _mock_backtest_result(
        signals_log=[
            {"date": "2024-01-10", "signal": "BUY", "confidence": 70, "raw_score": 0.45},
            {"date": "2024-02-10", "signal": "SELL", "confidence": 65, "raw_score": -0.35},
            {"date": "2024-03-01", "signal": "BUY", "confidence": 60, "raw_score": 0.32},
            {"date": "2024-04-01", "signal": "BUY", "confidence": 55, "raw_score": 0.50},
            {"date": "2024-05-01", "signal": "BUY", "confidence": 75, "raw_score": 0.60},
        ],
        trades=[
            SimulatedTrade("2024-01-10", 100.0, "BUY", 70.0, 10.0, "2024-02-10", 110.0, "signal_sell", pnl=100, pnl_pct=0.10, holding_days=31),
            SimulatedTrade("2024-03-01", 105.0, "BUY", 60.0, 10.0, "2024-04-01", 100.0, "signal_sell", pnl=-50, pnl_pct=-0.048, holding_days=31),
            SimulatedTrade("2024-04-01", 100.0, "BUY", 55.0, 10.0, "2024-05-01", 115.0, "signal_sell", pnl=150, pnl_pct=0.15, holding_days=30),
            SimulatedTrade("2024-05-01", 115.0, "BUY", 75.0, 10.0, "2024-06-01", 120.0, "signal_sell", pnl=50, pnl_pct=0.043, holding_days=31),
        ],
    )

    buy_thresh, sell_thresh = adapter.optimize_thresholds([result])
    # Should return a valid threshold in range
    assert 0.10 <= buy_thresh <= 0.50
    assert sell_thresh == -buy_thresh


# ---------------------------------------------------------------------------
# 9. save + load round-trip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_and_load_weights(tmp_path: Path) -> None:
    db_path = tmp_path / "weights.db"
    await init_db(db_path)

    adapter = WeightAdapter(db_path=str(db_path))

    original = AdaptiveWeights(
        weights={"stock": {"TechnicalAgent": 0.6, "FundamentalAgent": 0.4}},
        buy_threshold=0.25,
        sell_threshold=-0.25,
        source="backtest",
        computed_at=datetime.now(timezone.utc).isoformat(),
        sample_size=42,
    )

    await adapter.save_weights(original)
    loaded = await adapter.load_weights()

    assert loaded is not None
    assert loaded.source == "backtest"
    assert loaded.buy_threshold == 0.25
    assert loaded.sell_threshold == -0.25
    assert loaded.weights["stock"]["TechnicalAgent"] == 0.6
    assert loaded.weights["stock"]["FundamentalAgent"] == 0.4
    assert loaded.sample_size == 42


# ---------------------------------------------------------------------------
# 10. load staleness detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_weights_staleness(tmp_path: Path) -> None:
    import aiosqlite

    db_path = tmp_path / "stale.db"
    await init_db(db_path)

    # Manually insert a weight entry with old updated_at
    old_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    data = {
        "weights": {"stock": {"TechnicalAgent": 1.0}},
        "buy_threshold": 0.30,
        "sell_threshold": -0.30,
        "source": "backtest",
        "computed_at": old_time,
        "sample_size": 5,
    }
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO portfolio_meta (key, value, updated_at) VALUES (?, ?, ?)",
            ("adaptive_weights", json.dumps(data), old_time),
        )
        await conn.commit()

    adapter = WeightAdapter(db_path=str(db_path))
    loaded = await adapter.load_weights()

    assert loaded is not None
    assert loaded.staleness_days >= 9  # At least 9 days old


# ---------------------------------------------------------------------------
# 11. load missing -> None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_weights_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    await init_db(db_path)

    adapter = WeightAdapter(db_path=str(db_path))
    loaded = await adapter.load_weights()
    assert loaded is None


# ---------------------------------------------------------------------------
# 12. SignalAggregator with custom threshold
# ---------------------------------------------------------------------------

def test_aggregator_custom_threshold() -> None:
    # With default threshold 0.30, raw_score=0.25 would be HOLD
    # With custom threshold 0.20, raw_score=0.25 should be BUY
    agg_default = SignalAggregator()
    agg_custom = SignalAggregator(buy_threshold=0.20, sell_threshold=-0.20)

    output = AgentOutput(
        agent_name="TechnicalAgent",
        ticker="TEST",
        signal=Signal.BUY,
        confidence=55.0,  # This will give raw_score ~0.25 (between 0.20 and 0.30)
        reasoning="test",
    )

    # With stock weights (Tech=0.30, Fund=0.45, Macro=0.25), a single TechAgent BUY at 55%:
    # weighted_sum = 1.0 * 0.30 * 0.55 = 0.165
    # total_weight = 0.30 * 0.55 = 0.165
    # raw_score = 0.165 / 0.165 = 1.0
    # Actually raw_score=1.0 which is above both thresholds.
    # Let's use custom weights to get a controlled raw_score.

    # Use custom weights with single agent to get predictable raw_score
    custom_weights = {"stock": {"TechnicalAgent": 1.0}}
    agg_low_thresh = SignalAggregator(
        weights=custom_weights,
        buy_threshold=0.20,
        sell_threshold=-0.20,
    )
    agg_high_thresh = SignalAggregator(
        weights=custom_weights,
        buy_threshold=0.60,
        sell_threshold=-0.60,
    )

    # BUY with confidence=50 → raw_score = 1.0 * 1.0 * 0.5 / (1.0 * 0.5) = 1.0
    # That's too high. Use HOLD signal to get 0.0:
    hold_output = AgentOutput(
        agent_name="TechnicalAgent", ticker="TEST",
        signal=Signal.HOLD, confidence=50.0, reasoning="test",
    )
    # raw_score = 0.0 * 1.0 * 0.5 / (1.0 * 0.5) = 0.0 → HOLD for both thresholds ✓

    # Use two agents with conflicting signals to get raw_score between thresholds:
    mixed_weights = {
        "stock": {"AgentA": 0.5, "AgentB": 0.5},
    }
    buy_output = AgentOutput(
        agent_name="AgentA", ticker="TEST",
        signal=Signal.BUY, confidence=60.0, reasoning="bullish",
    )
    hold_output_b = AgentOutput(
        agent_name="AgentB", ticker="TEST",
        signal=Signal.HOLD, confidence=60.0, reasoning="neutral",
    )

    # raw_score = (1.0 * 0.5 * 0.6 + 0.0 * 0.5 * 0.6) / (0.5*0.6 + 0.5*0.6)
    #           = 0.3 / 0.6 = 0.5
    # 0.5 >= 0.20 → BUY (low threshold)
    # 0.5 < 0.60 → HOLD (high threshold)

    agg_low = SignalAggregator(weights=mixed_weights, buy_threshold=0.20, sell_threshold=-0.20)
    agg_high = SignalAggregator(weights=mixed_weights, buy_threshold=0.60, sell_threshold=-0.60)

    result_low = agg_low.aggregate([buy_output, hold_output_b], "TEST", "stock")
    result_high = agg_high.aggregate([buy_output, hold_output_b], "TEST", "stock")

    assert result_low.final_signal == Signal.BUY
    assert result_high.final_signal == Signal.HOLD


# ---------------------------------------------------------------------------
# 13. SignalAggregator default thresholds unchanged
# ---------------------------------------------------------------------------

def test_aggregator_default_thresholds_in_metrics() -> None:
    agg = SignalAggregator()

    output = AgentOutput(
        agent_name="TechnicalAgent", ticker="TEST",
        signal=Signal.BUY, confidence=70.0, reasoning="test",
    )
    result = agg.aggregate([output], "TEST", "stock")

    assert result.metrics["buy_threshold"] == 0.30
    assert result.metrics["sell_threshold"] == -0.30
