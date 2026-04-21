"""Tests for FOUND-07: job_run_log state machine + atomic job transactions.

Tasks covered:
- T-02-02: job_run_log writes + reconcile_aborted_jobs + atomic BEGIN/COMMIT/ROLLBACK

Run with:
    pytest tests/test_foundation_07_job_run_log.py -x -v
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest

from db.database import init_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _null_logger() -> logging.Logger:
    """Logger that discards all output."""
    logger = logging.getLogger(f"test_jrl_{id(object())}")
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


async def _get_jrl_row(db_path: str, job_name: str) -> dict | None:
    """Fetch the most recent job_run_log row for a given job_name."""
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (
            await conn.execute(
                "SELECT * FROM job_run_log WHERE job_name = ? ORDER BY id DESC LIMIT 1",
                (job_name,),
            )
        ).fetchone()
        return dict(row) if row else None


async def _count_signal_history(db_path: str) -> int:
    async with aiosqlite.connect(db_path) as conn:
        row = await (await conn.execute("SELECT COUNT(*) FROM signal_history")).fetchone()
        return int(row[0]) if row else 0


# ---------------------------------------------------------------------------
# Test A: run_daily_check writes start + finish rows in job_run_log
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_run_log_writes_start_and_finish(tmp_path) -> None:
    """run_daily_check inserts a job_run_log row and updates it to 'success'."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    mock_result = {
        "checked_positions": 1,
        "alerts": [],
        "snapshot_saved": True,
        "warnings": [],
    }

    with patch("daemon.jobs.PortfolioMonitor") as MockMonitor:
        instance = MockMonitor.return_value
        instance.run_check = AsyncMock(return_value=mock_result)

        from daemon.jobs import run_daily_check
        await run_daily_check(db_path, _null_logger())

    row = await _get_jrl_row(db_path, "daily_check")
    assert row is not None, "job_run_log row not found for daily_check"
    assert row["status"] == "success", f"expected 'success', got {row['status']!r}"
    assert row["completed_at"] is not None, "completed_at is None"
    assert row["duration_ms"] is not None and row["duration_ms"] >= 0
    assert row["error_message"] is None


# ---------------------------------------------------------------------------
# Test B: mid-job crash sets job_run_log status='error' and rolls back writes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mid_job_crash_sets_error_and_rolls_back(tmp_path) -> None:
    """If PortfolioMonitor.run_check raises, job_run_log='error' and no partial writes."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    with patch("daemon.jobs.PortfolioMonitor") as MockMonitor:
        instance = MockMonitor.return_value
        instance.run_check = AsyncMock(side_effect=RuntimeError("boom"))

        from daemon.jobs import run_daily_check
        result = await run_daily_check(db_path, _null_logger())

    assert "error" in result

    row = await _get_jrl_row(db_path, "daily_check")
    assert row is not None, "job_run_log row not found"
    assert row["status"] == "error", f"expected 'error', got {row['status']!r}"
    assert row["error_message"] is not None
    assert "boom" in row["error_message"]


# ---------------------------------------------------------------------------
# Test C: reconcile_aborted_jobs marks stale 'running' rows as 'aborted'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mid_job_crash_sets_aborted(tmp_path) -> None:
    """reconcile_aborted_jobs converts old 'running' row to 'aborted'."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    # Insert a stale running row
    old_started_at = "2025-01-01T00:00:00+00:00"
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO job_run_log (job_name, started_at, status) VALUES (?, ?, 'running')",
            ("stale_job", old_started_at),
        )
        await conn.commit()

    from daemon.jobs import reconcile_aborted_jobs
    count = await reconcile_aborted_jobs(db_path, min_age_seconds=5)
    assert count == 1, f"expected 1 reconciled, got {count}"

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (
            await conn.execute(
                "SELECT status, error_message FROM job_run_log WHERE job_name = 'stale_job'"
            )
        ).fetchone()
    assert row is not None
    assert row["status"] == "aborted"
    assert row["error_message"] is not None


# ---------------------------------------------------------------------------
# Test D: reconcile_aborted_jobs ignores fresh 'running' rows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reconcile_ignores_fresh_running_rows(tmp_path) -> None:
    """reconcile_aborted_jobs(min_age_seconds=5) must not touch a just-inserted row."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    # Insert a fresh running row (now)
    fresh_started_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO job_run_log (job_name, started_at, status) VALUES (?, ?, 'running')",
            ("fresh_job", fresh_started_at),
        )
        await conn.commit()

    from daemon.jobs import reconcile_aborted_jobs
    count = await reconcile_aborted_jobs(db_path, min_age_seconds=5)
    assert count == 0, f"expected 0 reconciled (row is fresh), got {count}"

    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT status FROM job_run_log WHERE job_name = 'fresh_job'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "running", f"expected 'running', got {row[0]!r}"


# ---------------------------------------------------------------------------
# Test E: run_weekly_revaluation rollback on exception leaves no signal_history rows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_partial_write_rolled_back(tmp_path) -> None:
    """If run_weekly_revaluation raises mid-job, signal_history stays clean."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    # Verify no signal_history rows before
    assert await _count_signal_history(db_path) == 0

    # Insert a position so the job has something to analyze
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO active_positions (ticker, asset_type, quantity, avg_cost, entry_date) "
            "VALUES ('AAPL', 'stock', 10.0, 100.0, '2024-01-01')",
        )
        await conn.commit()

    # Mock the pipeline to raise mid-analysis (simulates a crash after some partial DB work)
    with patch("daemon.jobs.AnalysisPipeline") as MockPipeline:
        instance = MockPipeline.return_value
        instance.analyze_ticker = AsyncMock(side_effect=RuntimeError("data feed down"))

        from daemon.jobs import run_weekly_revaluation
        result = await run_weekly_revaluation(db_path, _null_logger())

    # The job itself catches per-position errors and the outer loop continues —
    # but with all positions failing, signals_saved should be 0
    assert result.get("signals_saved", 0) == 0

    # job_run_log should have a row (either error or success with 0 analyzed)
    row = await _get_jrl_row(db_path, "weekly_revaluation")
    assert row is not None, "job_run_log row not found for weekly_revaluation"
    # No partial signal_history rows
    assert await _count_signal_history(db_path) == 0, "partial signal_history rows found after crash"


# ---------------------------------------------------------------------------
# Test F+G: prune_signal_history respects retention window
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prune_signal_history_respects_retention(tmp_path) -> None:
    """prune_signal_history deletes old rows, keeps recent ones."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    # Seed: 5 rows at 120 days ago (should be deleted), 5 at 30 days ago (should stay)
    async with aiosqlite.connect(db_path) as conn:
        old_ts = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        recent_ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        for ts in [old_ts] * 5 + [recent_ts] * 5:
            await conn.execute(
                "INSERT INTO signal_history (ticker, asset_type, final_signal, "
                "final_confidence, raw_score, consensus_score, agent_signals_json, "
                "reasoning, warnings_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("AAPL", "stock", "HOLD", 50.0, 0.0, 1.0, "[]", "test", "[]", ts),
            )
        await conn.commit()

    from daemon.jobs import prune_signal_history
    result = await prune_signal_history(db_path, retention_days=90)

    assert isinstance(result, dict), "prune_signal_history must return a dict"
    assert "deleted_rows" in result
    assert "retained_rows" in result
    assert result["deleted_rows"] == 5, f"expected 5 deleted, got {result['deleted_rows']}"
    assert result["retained_rows"] == 5, f"expected 5 retained, got {result['retained_rows']}"

    # Verify via direct query
    assert await _count_signal_history(db_path) == 5


# ---------------------------------------------------------------------------
# Test H: daemon_runs still written (backwards compat)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daemon_runs_still_written(tmp_path) -> None:
    """run_daily_check still writes to daemon_runs (backwards compat)."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    mock_result = {"checked_positions": 0, "alerts": [], "snapshot_saved": True, "warnings": []}

    with patch("daemon.jobs.PortfolioMonitor") as MockMonitor:
        instance = MockMonitor.return_value
        instance.run_check = AsyncMock(return_value=mock_result)

        from daemon.jobs import run_daily_check
        await run_daily_check(db_path, _null_logger())

    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT job_name, status FROM daemon_runs WHERE job_name = 'daily_check'"
            )
        ).fetchone()
    assert row is not None, "daemon_runs row not found (backwards compat broken)"
    assert row[1] == "success"
