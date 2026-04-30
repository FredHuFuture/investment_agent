"""Tests for Phase 8 SIG-v2-01: reliability bins + adaptive bin count + Wilson CI.

Strategy:
- Adaptive bin count math is a pure function — exercise its edge cases directly.
- compute_reliability_bins is exercised via an in-process AsyncMock store for
  the fast assertions (HOLD exclusion, Wilson CI bounds, preliminary flag,
  ece sanity, provider filter routing).
- The dual-path store reader (Warning 6 fix) is exercised via tmp_path SQLite
  fixtures: one test for the module-level helper, one for the SignalStore method.
"""
from __future__ import annotations

import random
from pathlib import Path
from unittest.mock import AsyncMock

import aiosqlite
import pytest

from tracking.tracker import SignalTracker, _adaptive_bin_count


# ---------------------------------------------------------------------------
# Adaptive bin count: pure math edge cases
# ---------------------------------------------------------------------------


def test_adaptive_bin_count_below_threshold() -> None:
    assert _adaptive_bin_count(0) == 2
    assert _adaptive_bin_count(15) == 2
    assert _adaptive_bin_count(19) == 2


def test_adaptive_bin_count_at_threshold() -> None:
    assert _adaptive_bin_count(20) == 2
    assert _adaptive_bin_count(50) == 5
    assert _adaptive_bin_count(99) == 9
    assert _adaptive_bin_count(150) == 10  # capped at max_bins=10


def test_adaptive_bin_count_floor_and_cap() -> None:
    # Floor at 2
    assert _adaptive_bin_count(1) == 2
    # Cap at 10 even at huge N
    assert _adaptive_bin_count(10_000) == 10
    # Custom max_bins respected
    assert _adaptive_bin_count(150, max_bins=5) == 5
    # Custom min_per_bin respected
    assert _adaptive_bin_count(100, min_per_bin=20) == 5


# ---------------------------------------------------------------------------
# compute_reliability_bins via mocked store
# ---------------------------------------------------------------------------


def _mock_store(rows: list[dict]) -> AsyncMock:
    store = AsyncMock()
    store.get_backtest_signals_by_agent = AsyncMock(return_value=rows)
    return store


@pytest.mark.asyncio
async def test_compute_reliability_bins_excludes_hold() -> None:
    """HOLD signals must not contribute to n_samples (one-vs-rest binary)."""
    rows = (
        [
            {
                "signal": "BUY",
                "confidence": 70,
                "forward_return": 0.01,
                "forward_return_5d": 0.01,
            }
        ]
        * 50
        + [
            {
                "signal": "SELL",
                "confidence": 60,
                "forward_return": -0.01,
                "forward_return_5d": -0.01,
            }
        ]
        * 30
        + [
            {
                "signal": "HOLD",
                "confidence": 40,
                "forward_return": 0.01,
                "forward_return_5d": 0.01,
            }
        ]
        * 20
    )
    tracker = SignalTracker(store=_mock_store(rows))
    result = await tracker.compute_reliability_bins("TestAgent")
    assert result["n_samples"] == 80


@pytest.mark.asyncio
async def test_compute_reliability_bins_buy_sell_correctness() -> None:
    """BUY wins when forward_return > 0; SELL wins when forward_return < 0."""
    rows = (
        [
            {
                "signal": "BUY",
                "confidence": 80,
                "forward_return": 0.05,
                "forward_return_5d": 0.05,
            }
        ]
        * 30
        + [
            {
                "signal": "SELL",
                "confidence": 80,
                "forward_return": -0.05,
                "forward_return_5d": -0.05,
            }
        ]
        * 30
    )
    tracker = SignalTracker(store=_mock_store(rows))
    result = await tracker.compute_reliability_bins("TestAgent")
    # All wins: observed should be ~1.0 in every populated bin
    for b in result["bins"]:
        assert b["observed"] >= 0.95


@pytest.mark.asyncio
async def test_compute_reliability_bins_wilson_ci_within_bounds() -> None:
    """Wilson 95% CI bounds: [0,1], with observed inside the interval."""
    rng = random.Random(42)
    rows = [
        {
            "signal": "BUY",
            "confidence": rng.uniform(40, 90),
            "forward_return": rng.uniform(-0.05, 0.05),
            "forward_return_5d": rng.uniform(-0.05, 0.05),
        }
        for _ in range(150)
    ]
    tracker = SignalTracker(store=_mock_store(rows))
    result = await tracker.compute_reliability_bins("TestAgent")
    for b in result["bins"]:
        assert 0.0 <= b["ci_low"] <= 1.0
        assert 0.0 <= b["ci_high"] <= 1.0
        # Observed must lie within the 95% CI by construction
        assert b["ci_low"] - 1e-9 <= b["observed"] <= b["ci_high"] + 1e-9


@pytest.mark.asyncio
async def test_compute_reliability_bins_preliminary_calibration_at_low_n() -> None:
    """At n_samples=15 (< min_per_bin*2=20), result is preliminary."""
    rows = [
        {
            "signal": "BUY",
            "confidence": 60,
            "forward_return": 0.01,
            "forward_return_5d": 0.01,
        }
    ] * 15
    tracker = SignalTracker(store=_mock_store(rows))
    result = await tracker.compute_reliability_bins("TestAgent")
    assert result["preliminary_calibration"] is True


@pytest.mark.asyncio
async def test_compute_reliability_bins_preliminary_calibration_at_high_n() -> None:
    """At n_samples=250 with diverse confidences, preliminary should be False."""
    rng = random.Random(1)
    rows = [
        {
            "signal": "BUY",
            "confidence": rng.uniform(40, 90),
            "forward_return": rng.uniform(-0.05, 0.05),
            "forward_return_5d": rng.uniform(-0.05, 0.05),
        }
        for _ in range(250)
    ]
    tracker = SignalTracker(store=_mock_store(rows))
    result = await tracker.compute_reliability_bins("TestAgent")
    assert result["preliminary_calibration"] is False
    assert result["n_bins_used"] >= 5


@pytest.mark.asyncio
async def test_compute_reliability_bins_zero_samples_returns_empty_with_preliminary() -> None:
    """Zero samples returns empty bins with preliminary=True and ece=None."""
    tracker = SignalTracker(store=_mock_store([]))
    result = await tracker.compute_reliability_bins("TestAgent")
    assert result["bins"] == []
    assert result["n_samples"] == 0
    assert result["n_bins_used"] == 0
    assert result["preliminary_calibration"] is True
    assert result["ece"] is None


@pytest.mark.asyncio
async def test_compute_reliability_bins_ece_sanity() -> None:
    """Sum of ece_contrib equals returned ece; ece in [0, 1]."""
    rng = random.Random(7)
    rows = [
        {
            "signal": "BUY" if rng.random() < 0.5 else "SELL",
            "confidence": rng.uniform(40, 90),
            "forward_return": rng.uniform(-0.05, 0.05),
            "forward_return_5d": rng.uniform(-0.05, 0.05),
        }
        for _ in range(200)
    ]
    tracker = SignalTracker(store=_mock_store(rows))
    result = await tracker.compute_reliability_bins("TestAgent")
    summed = sum(b["ece_contrib"] for b in result["bins"])
    assert result["ece"] == pytest.approx(summed, abs=1e-9)
    assert 0.0 <= result["ece"] <= 1.0


@pytest.mark.asyncio
async def test_compute_reliability_bins_filters_by_fundamentals_provider() -> None:
    """Provider kwarg is forwarded to the store; default is yfinance."""
    captured: dict[str, str | None] = {}

    async def fake_reader(
        agent_name: str,
        horizon: str = "5d",
        fundamentals_provider: str | None = "yfinance",
    ) -> list[dict]:
        captured["fundamentals_provider"] = fundamentals_provider
        if fundamentals_provider == "simfin":
            return []
        return [
            {
                "signal": "BUY",
                "confidence": 60,
                "forward_return": 0.01,
                "forward_return_5d": 0.01,
            }
        ] * 50

    store = AsyncMock()
    store.get_backtest_signals_by_agent = fake_reader
    tracker = SignalTracker(store=store)

    # Default reads yfinance corpus
    default = await tracker.compute_reliability_bins("TestAgent")
    assert default["n_samples"] == 50
    assert captured["fundamentals_provider"] == "yfinance"

    # Explicit simfin reads empty corpus
    simfin = await tracker.compute_reliability_bins(
        "TestAgent", fundamentals_provider="simfin"
    )
    assert simfin["n_samples"] == 0
    assert captured["fundamentals_provider"] == "simfin"


# ---------------------------------------------------------------------------
# Dual-path store reader tests (Warning 6 fix)
# ---------------------------------------------------------------------------


async def _seed_two_provider_rows(db_path: Path) -> None:
    """Insert one yfinance row + one simfin row for the same agent."""
    from db.database import init_db

    await init_db(str(db_path))
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute(
            """
            INSERT INTO backtest_signal_history
              (ticker, asset_type, signal_date, agent_name, raw_score, signal,
               confidence, forward_return_5d, fundamentals_provider, source)
            VALUES ('AAPL','stock','2024-06-30','A',0.5,'BUY',60,0.02,'yfinance','backtest')
            """
        )
        await conn.execute(
            """
            INSERT INTO backtest_signal_history
              (ticker, asset_type, signal_date, agent_name, raw_score, signal,
               confidence, forward_return_5d, fundamentals_provider, source)
            VALUES ('AAPL','stock','2024-07-30','A',0.5,'BUY',60,0.03,'simfin','backtest')
            """
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_module_level_helper_supports_fundamentals_provider_filter(
    tmp_path: Path,
) -> None:
    """tracking.store._get_backtest_signals_by_agent accepts the filter directly."""
    from tracking.store import _get_backtest_signals_by_agent

    db_path = tmp_path / "test_filter.db"
    await _seed_two_provider_rows(db_path)

    yfin = await _get_backtest_signals_by_agent(
        db_path, "A", "5d", fundamentals_provider="yfinance"
    )
    sim = await _get_backtest_signals_by_agent(
        db_path, "A", "5d", fundamentals_provider="simfin"
    )
    all_providers = await _get_backtest_signals_by_agent(
        db_path, "A", "5d", fundamentals_provider=None
    )

    assert len(yfin) == 1
    assert len(sim) == 1
    assert len(all_providers) == 2


@pytest.mark.asyncio
async def test_signalstore_method_threads_filter_to_module_helper(
    tmp_path: Path,
) -> None:
    """SignalStore.get_backtest_signals_by_agent forwards the kwarg."""
    from tracking.store import SignalStore

    db_path = tmp_path / "test_method.db"
    await _seed_two_provider_rows(db_path)

    store = SignalStore(str(db_path))
    sim = await store.get_backtest_signals_by_agent(
        "A", "5d", fundamentals_provider="simfin"
    )
    yfin = await store.get_backtest_signals_by_agent(
        "A", "5d", fundamentals_provider="yfinance"
    )
    assert len(sim) == 1
    assert len(yfin) == 1
