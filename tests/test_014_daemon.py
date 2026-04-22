"""Tests for Task 014: Monitoring Daemon.

All tests use tmp_path DBs and mock external I/O -- no network, no real scheduler.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest

from agents.models import Signal
from daemon.jobs import run_catalyst_scan, run_daily_check, run_weekly_revaluation
from daemon.signal_comparator import SignalComparison, compare_signals
from db.database import init_db
from engine.aggregator import AggregatedSignal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _null_logger() -> logging.Logger:
    """Logger that discards all output."""
    logger = logging.getLogger(f"test_daemon_{id(object())}")
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


async def _insert_position(db_path: str, ticker: str, asset_type: str, thesis_id: int | None) -> None:
    """Insert a position row into active_positions."""
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO active_positions (
                ticker, asset_type, quantity, avg_cost, entry_date,
                original_analysis_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ticker, asset_type, 10.0, 100.0, "2024-01-01", thesis_id),
        )
        await conn.commit()


async def _insert_thesis(
    db_path: str,
    thesis_id: int | None,
    ticker: str,
    expected_signal: str,
    expected_confidence: float,
) -> int:
    """Insert a thesis row and return its id."""
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            """
            INSERT INTO positions_thesis (
                ticker, asset_type, expected_signal, expected_confidence,
                expected_entry_price
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (ticker, "stock", expected_signal, expected_confidence, 100.0),
        )
        await conn.commit()
        return int(cursor.lastrowid)


def _make_aggregated_signal(
    ticker: str = "AAPL",
    signal: Signal = Signal.BUY,
    confidence: float = 70.0,
) -> AggregatedSignal:
    """Craft a minimal AggregatedSignal for testing."""
    return AggregatedSignal(
        ticker=ticker,
        asset_type="stock",
        final_signal=signal,
        final_confidence=confidence,
        regime=None,
        agent_signals=[],
        reasoning="mock",
        metrics={"raw_score": 0.5, "consensus_score": 1.0},
        warnings=[],
        ticker_info={"current_price": 105.0},
    )


# ---------------------------------------------------------------------------
# 1. Signal comparator -- BUY -> SELL reversal
# ---------------------------------------------------------------------------

def test_reversal_buy_to_sell() -> None:
    result = compare_signals("BUY", 70.0, "SELL", 65.0)
    assert isinstance(result, SignalComparison)
    assert result.direction_reversed is True
    assert abs(result.confidence_delta - (-5.0)) < 1e-6
    assert "REVERSAL" in result.summary


# ---------------------------------------------------------------------------
# 2. Signal comparator -- SELL -> BUY reversal
# ---------------------------------------------------------------------------

def test_reversal_sell_to_buy() -> None:
    result = compare_signals("SELL", 60.0, "BUY", 75.0)
    assert result.direction_reversed is True
    assert abs(result.confidence_delta - 15.0) < 1e-6


# ---------------------------------------------------------------------------
# 3. Signal comparator -- BUY -> HOLD (weakening, not reversal)
# ---------------------------------------------------------------------------

def test_no_reversal_buy_to_hold() -> None:
    result = compare_signals("BUY", 70.0, "HOLD", 50.0)
    assert result.direction_reversed is False
    assert "No change" in result.summary


# ---------------------------------------------------------------------------
# 4. Signal comparator -- BUY -> BUY (same signal)
# ---------------------------------------------------------------------------

def test_no_reversal_same_signal() -> None:
    result = compare_signals("BUY", 70.0, "BUY", 80.0)
    assert result.direction_reversed is False
    assert abs(result.confidence_delta - 10.0) < 1e-6


# ---------------------------------------------------------------------------
# 5. Daily check -- wraps PortfolioMonitor, records success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_check_wraps_monitor(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    logger = _null_logger()

    mock_result = {
        "checked_positions": 2,
        "alerts": [],
        "snapshot_saved": True,
        "warnings": [],
    }

    with patch("daemon.jobs.PortfolioMonitor") as MockMonitor:
        instance = MockMonitor.return_value
        instance.run_check = AsyncMock(return_value=mock_result)

        result = await run_daily_check(db_path, logger)

    assert result["checked_positions"] == 2

    # Verify daemon_runs row
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT job_name, status FROM daemon_runs WHERE job_name = 'daily_check'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "daily_check"
    assert row[1] == "success"


# ---------------------------------------------------------------------------
# 6. Daily check -- records error when monitor raises
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_check_records_error(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    logger = _null_logger()

    with patch("daemon.jobs.PortfolioMonitor") as MockMonitor:
        instance = MockMonitor.return_value
        instance.run_check = AsyncMock(side_effect=RuntimeError("price feed down"))

        result = await run_daily_check(db_path, logger)

    assert "error" in result

    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT status, error_message FROM daemon_runs WHERE job_name = 'daily_check'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "error"
    assert "price feed down" in row[1]


# ---------------------------------------------------------------------------
# 7. Weekly revaluation -- detects signal reversal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weekly_detects_reversal(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    logger = _null_logger()

    # Insert thesis: BUY
    thesis_id = await _insert_thesis(db_path, None, "AAPL", "BUY", 70.0)
    # Insert position linked to thesis
    await _insert_position(db_path, "AAPL", "stock", thesis_id)

    # Mock pipeline to return SELL signal
    sell_signal = _make_aggregated_signal("AAPL", Signal.SELL, 58.0)

    with patch("daemon.jobs.AnalysisPipeline") as MockPipeline:
        instance = MockPipeline.return_value
        instance.analyze_ticker = AsyncMock(return_value=sell_signal)

        result = await run_weekly_revaluation(db_path, logger)

    # Signal reversal detected
    assert len(result["signal_reversals"]) == 1
    assert result["signal_reversals"][0]["ticker"] == "AAPL"
    assert result["signal_reversals"][0]["current_signal"] == "SELL"

    # SIGNAL_REVERSAL alert saved
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT alert_type, severity FROM monitoring_alerts WHERE ticker = 'AAPL'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "SIGNAL_REVERSAL"
    assert row[1] == "HIGH"

    # Signal saved to signal_history
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute("SELECT final_signal FROM signal_history WHERE ticker = 'AAPL'")
        ).fetchone()
    assert row is not None
    assert row[0] == "SELL"


# ---------------------------------------------------------------------------
# 8. Weekly revaluation -- no reversal when signal unchanged
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weekly_no_reversal(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    logger = _null_logger()

    thesis_id = await _insert_thesis(db_path, None, "AAPL", "BUY", 70.0)
    await _insert_position(db_path, "AAPL", "stock", thesis_id)

    # Same direction: still BUY
    buy_signal = _make_aggregated_signal("AAPL", Signal.BUY, 72.0)

    with patch("daemon.jobs.AnalysisPipeline") as MockPipeline:
        instance = MockPipeline.return_value
        instance.analyze_ticker = AsyncMock(return_value=buy_signal)

        result = await run_weekly_revaluation(db_path, logger)

    assert result["signal_reversals"] == []
    assert result["alerts_generated"] == 0

    # No SIGNAL_REVERSAL alert
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT COUNT(*) FROM monitoring_alerts WHERE alert_type = 'SIGNAL_REVERSAL'"
            )
        ).fetchone()
    assert row[0] == 0


# ---------------------------------------------------------------------------
# 9. Weekly revaluation -- handles per-position failure gracefully
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weekly_handles_analysis_failure(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    logger = _null_logger()

    # Insert two positions (no thesis needed for this test)
    await _insert_position(db_path, "AAPL", "stock", None)
    await _insert_position(db_path, "MSFT", "stock", None)

    msft_signal = _make_aggregated_signal("MSFT", Signal.BUY, 68.0)

    call_count = [0]

    async def _analyze_side_effect(ticker, asset_type, portfolio=None):
        call_count[0] += 1
        if ticker == "AAPL":
            raise RuntimeError("AAPL analysis failed")
        return msft_signal

    with patch("daemon.jobs.AnalysisPipeline") as MockPipeline:
        instance = MockPipeline.return_value
        instance.analyze_ticker = AsyncMock(side_effect=_analyze_side_effect)

        result = await run_weekly_revaluation(db_path, logger)

    # AAPL failed, MSFT succeeded
    assert result["positions_analyzed"] == 1
    assert len(result["errors"]) == 1
    assert result["errors"][0]["ticker"] == "AAPL"

    # MSFT signal was saved
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute("SELECT final_signal FROM signal_history WHERE ticker = 'MSFT'")
        ).fetchone()
    assert row is not None
    assert row[0] == "BUY"


# ---------------------------------------------------------------------------
# 10. Catalyst scan -- records skipped when no positions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_catalyst_scan_no_positions_records_skipped(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    logger = _null_logger()

    result = await run_catalyst_scan(db_path, logger)

    assert result["status"] == "skipped"
    assert "No open positions" in result["reason"]

    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT job_name, status FROM daemon_runs WHERE job_name = 'catalyst_scan'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "catalyst_scan"
    assert row[1] == "skipped"


# ---------------------------------------------------------------------------
# 11. WR-03: MonitoringDaemon.start() passes min_age_seconds=300 to
#     reconcile_aborted_jobs so that legitimately long-running jobs are not
#     falsely aborted on daemon restart.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daemon_start_reconcile_uses_300s_threshold(tmp_path: Path) -> None:
    """MonitoringDaemon.start() must call reconcile_aborted_jobs(min_age_seconds=300).

    Verifies that the WR-03 fix is in place: the start() call site passes
    min_age_seconds=300 so jobs running up to 5 minutes are not falsely aborted
    on daemon restart (aligns with /health STALE_RUNNING_SECONDS=300).
    """
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from daemon.config import DaemonConfig
    from daemon.scheduler import MonitoringDaemon

    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    config = DaemonConfig(db_path=db_path)
    daemon = MonitoringDaemon(config=config)

    # Capture kwargs forwarded to reconcile_aborted_jobs
    captured_kwargs: dict = {}

    async def _fake_reconcile(db_path_arg: str, min_age_seconds: int = 5) -> int:
        captured_kwargs["min_age_seconds"] = min_age_seconds
        return 0

    # Build a fake scheduler that satisfies scheduler.start() and scheduler.running
    fake_scheduler = MagicMock()
    fake_scheduler.running = False

    # Shutdown event that resolves immediately so start() doesn't block
    fake_event = MagicMock()
    fake_event.wait = AsyncMock(return_value=None)

    with (
        patch("daemon.scheduler.check_pid_file", return_value=("missing", None)),
        patch("daemon.scheduler.ensure_pid_file", return_value=99999),
        patch("daemon.scheduler.remove_pid_file"),
        patch("daemon.scheduler.atexit"),
        patch("daemon.scheduler.init_db", new_callable=AsyncMock),
        patch("daemon.scheduler.reconcile_aborted_jobs", side_effect=_fake_reconcile),
    ):
        # Inject fake scheduler before start() calls _setup_scheduler
        def _fake_setup_scheduler() -> None:
            daemon._scheduler = fake_scheduler

        daemon._setup_scheduler = _fake_setup_scheduler  # type: ignore[method-assign]

        # Inject fake shutdown event so start() returns after wait()
        original_event_class = asyncio.Event

        def _fake_event_ctor() -> MagicMock:
            return fake_event

        with patch("daemon.scheduler.asyncio.Event", side_effect=_fake_event_ctor):
            await daemon.start()

    assert "min_age_seconds" in captured_kwargs, (
        "reconcile_aborted_jobs was not called during daemon.start()"
    )
    assert captured_kwargs["min_age_seconds"] == 300, (
        f"Expected min_age_seconds=300 in start(), got {captured_kwargs['min_age_seconds']}"
    )
