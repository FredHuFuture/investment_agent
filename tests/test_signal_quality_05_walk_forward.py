"""Tests for SIG-05: Walk-forward window generation and Backtester.run_walk_forward.

Covers:
- generate_walk_forward_windows: window count, purge gap, no-overlap, step invariant
- WalkForwardResult default fields
- Backtester.run_walk_forward: returns BacktestResult with walk_forward_windows populated
- daemon.jobs.rebuild_signal_corpus: job_run_log audit, BLOCKER 2 dynamic dates,
  BLOCKER 3 atomic rollback on error
"""
from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
from typing import Any

import aiosqlite
import pandas as pd
import pytest

from backtesting.walk_forward import (
    WalkForwardResult,
    generate_walk_forward_windows,
)
from db.database import init_db


# ---------------------------------------------------------------------------
# Inline provider helper for walk-forward tests
# ---------------------------------------------------------------------------

class _MockProvider:
    """Minimal DataProvider for walk-forward + corpus tests."""

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
        return None

    async def get_news(self, ticker: str, limit: int = 10) -> list[dict]:
        return []

    async def get_fundamentals(self, ticker: str) -> dict | None:
        return None

    async def get_info(self, ticker: str) -> dict | None:
        return {"sector": "Technology", "industry": "Software"}


def _make_ohlcv(n: int = 400, start_price: float = 100.0) -> pd.DataFrame:
    """Synthetic OHLCV DataFrame with n rows using business-day index."""
    dates = pd.bdate_range("2023-01-02", periods=n)
    prices = [start_price + i * 0.05 for i in range(n)]
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


# ---------------------------------------------------------------------------
# generate_walk_forward_windows tests
# ---------------------------------------------------------------------------

def test_window_generation_30_10_1_over_1yr() -> None:
    """With 30-day train, 10-day OOS, 1-day purge over ~1 year → more than 20 windows."""
    windows = generate_walk_forward_windows(
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        train_days=30,
        oos_days=10,
        step_days=10,
        purge_days=1,
    )
    assert len(windows) > 20, f"Expected >20 windows over 1 year, got {len(windows)}"


def test_oos_start_strictly_after_train_end_with_purge() -> None:
    """Every window: oos_start is strictly after train_end and gap >= purge_days+1."""
    purge_days = 3
    windows = generate_walk_forward_windows(
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        train_days=30,
        oos_days=10,
        step_days=10,
        purge_days=purge_days,
    )
    assert len(windows) > 0, "No windows generated"
    for w in windows:
        assert w.oos_start > w.train_end, (
            f"window {w.window_idx}: oos_start {w.oos_start} not after train_end {w.train_end}"
        )
        gap = (w.oos_start - w.train_end).days
        assert gap >= purge_days + 1, (
            f"window {w.window_idx}: purge gap {gap} < {purge_days + 1}"
        )


def test_no_window_extends_past_end() -> None:
    """Every window's oos_end must be <= the supplied end date."""
    end = date(2024, 6, 30)
    windows = generate_walk_forward_windows(
        start=date(2024, 1, 1),
        end=end,
        train_days=30,
        oos_days=10,
        step_days=10,
        purge_days=1,
    )
    assert len(windows) > 0
    for w in windows:
        assert w.oos_end <= end, (
            f"window {w.window_idx}: oos_end {w.oos_end} exceeds end {end}"
        )


def test_window_step_advances_by_step_days() -> None:
    """Consecutive windows have train_start separated by exactly step_days."""
    step = 7
    windows = generate_walk_forward_windows(
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        train_days=30,
        oos_days=10,
        step_days=step,
        purge_days=1,
    )
    assert len(windows) >= 2
    for i in range(1, len(windows)):
        delta = (windows[i].train_start - windows[i - 1].train_start).days
        assert delta == step, (
            f"step between windows {i - 1} and {i} is {delta}, expected {step}"
        )


def test_walk_forward_result_has_preliminary_calibration_true() -> None:
    """WalkForwardResult defaults mark preliminary_calibration=True per 02-RESEARCH.md Q4."""
    windows = generate_walk_forward_windows(
        start=date(2024, 1, 1), end=date(2024, 3, 31)
    )
    result = WalkForwardResult(windows=windows)
    assert result.preliminary_calibration is True


def test_zero_windows_when_range_too_short() -> None:
    """start + train_days + purge + oos_days > end → empty list (no windows fit)."""
    # 30-day train + 2-day purge + 10-day OOS = minimum 42 calendar days needed
    windows = generate_walk_forward_windows(
        start=date(2024, 1, 1),
        end=date(2024, 1, 30),  # only 29 days — not enough for even one window
        train_days=30,
        oos_days=10,
        purge_days=1,
    )
    assert windows == [], f"Expected empty list for too-short range, got {windows}"


# ---------------------------------------------------------------------------
# Backtester.run_walk_forward integration test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_walk_forward_returns_per_window_sharpe() -> None:
    """Backtester.run_walk_forward returns BacktestResult with walk_forward_windows list."""
    from backtesting.engine import Backtester

    df = _make_ohlcv(n=400)
    provider = _MockProvider(df)

    start_date = str(df.index[0].date())
    end_date = str(df.index[-1].date())

    backtester = Backtester(provider)
    result = await backtester.run_walk_forward(
        ticker="TEST",
        asset_type="stock",
        start_date=start_date,
        end_date=end_date,
        train_days=30,
        oos_days=10,
        step_days=10,
        purge_days=1,
    )

    from backtesting.models import BacktestResult
    assert isinstance(result, BacktestResult)
    assert isinstance(result.walk_forward_windows, list)
    assert len(result.walk_forward_windows) > 0, (
        "Expected at least one walk-forward window for a 400-day series"
    )

    # Check required keys in each per-window metric entry
    required_keys = {"window_idx", "oos_start", "oos_end", "sharpe", "total_return", "n_trades"}
    for entry in result.walk_forward_windows:
        missing = required_keys - set(entry.keys())
        assert not missing, f"walk_forward_windows entry missing keys: {missing}. Entry: {entry}"


# ---------------------------------------------------------------------------
# daemon.jobs.rebuild_signal_corpus tests (BLOCKER 2 + BLOCKER 3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rebuild_signal_corpus_writes_job_run_log_success(
    tmp_path: Path,
) -> None:
    """BLOCKER 2: rebuild_signal_corpus derives date range from price_history_cache.

    Verifies:
    - No start_date/end_date passed → derived from MIN/MAX in price_history_cache
    - job_run_log status='success' after completion
    - backtest_signal_history has rows for the ticker
    """
    from unittest.mock import AsyncMock, patch

    db_file = tmp_path / "t.db"
    await init_db(db_file)

    # Seed price_history_cache for 'TEST' over Jan–Jun 2024
    n = 120
    dates_range = pd.bdate_range("2024-01-02", periods=n)
    async with aiosqlite.connect(db_file) as c:
        for i, d in enumerate(dates_range):
            await c.execute(
                """INSERT OR IGNORE INTO price_history_cache
                   (ticker, date, open, high, low, close, volume, asset_type)
                   VALUES (?,?,?,?,?,?,?,?)""",
                ("TEST", str(d.date()), 99.5 + i * 0.1, 101.0 + i * 0.1,
                 98.5 + i * 0.1, 100.0 + i * 0.1, 1_000_000.0, "stock"),
            )
        await c.commit()

    # Build a mock provider with matching data
    df = _make_ohlcv(n=n)
    provider = _MockProvider(df)

    # patch populate_signal_corpus to avoid a full backtester run in this integration test
    from backtesting import signal_corpus as sc_mod

    async def _mock_populate(db_path, ticker, asset_type, provider,
                              start_date, end_date, agents=None, run_id=None):
        # Insert a real row so the assertion below works
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute(
                """INSERT INTO backtest_signal_history
                   (ticker, asset_type, signal_date, agent_name, raw_score,
                    signal, confidence, forward_return_5d, forward_return_21d,
                    source, backtest_run_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (ticker, asset_type, start_date, "TechnicalAgent",
                 0.5, "BUY", 75.0, 0.01, 0.02, "backtest", run_id),
            )
            await conn.commit()
        return {"rows_inserted": 1, "n_bars": 1, "n_agents": 1, "run_id": run_id}

    with patch.object(sc_mod, "populate_signal_corpus", side_effect=_mock_populate):
        # Also patch in daemon.jobs namespace
        import daemon.jobs as djobs
        with patch.object(djobs, "populate_signal_corpus", side_effect=_mock_populate, create=True):
            from daemon.jobs import rebuild_signal_corpus
            stats = await rebuild_signal_corpus(
                db_path=str(db_file),
                tickers=[("TEST", "stock")],
                # No start_date/end_date → derived from cache (BLOCKER 2)
            )

    assert stats["rows_inserted"] >= 1

    async with aiosqlite.connect(db_file) as c:
        c.row_factory = aiosqlite.Row
        row = await (await c.execute(
            "SELECT status FROM job_run_log WHERE job_name='rebuild_signal_corpus' "
            "ORDER BY id DESC LIMIT 1"
        )).fetchone()
        assert row is not None, "No job_run_log row for rebuild_signal_corpus"
        assert row["status"] == "success", f"Expected success, got {row['status']}"

        cnt = (await (await c.execute(
            "SELECT COUNT(*) FROM backtest_signal_history WHERE ticker='TEST'"
        )).fetchone())[0]
        assert cnt >= 1, f"Expected >= 1 rows in backtest_signal_history, got {cnt}"


@pytest.mark.asyncio
async def test_rebuild_signal_corpus_logs_error_on_failure(
    tmp_path: Path,
) -> None:
    """rebuild_signal_corpus: exception propagates AND job_run_log shows 'error'."""
    from unittest.mock import patch

    db_file = tmp_path / "err.db"
    await init_db(db_file)

    # Seed minimal cache data so BLOCKER 2 date derivation has something
    async with aiosqlite.connect(db_file) as c:
        for i in range(5):
            d = f"2024-01-{i + 1:02d}"
            await c.execute(
                """INSERT OR IGNORE INTO price_history_cache
                   (ticker, date, open, high, low, close, volume, asset_type)
                   VALUES (?,?,?,?,?,?,?,?)""",
                ("TEST", d, 100.0, 101.0, 99.0, 100.0, 1_000_000.0, "stock"),
            )
        await c.commit()

    async def _failing_populate(*args, **kwargs):
        raise RuntimeError("simulated provider failure")

    from backtesting import signal_corpus as sc_mod
    import daemon.jobs as djobs

    with patch.object(sc_mod, "populate_signal_corpus", side_effect=_failing_populate):
        with patch.object(djobs, "populate_signal_corpus",
                          side_effect=_failing_populate, create=True):
            from daemon.jobs import rebuild_signal_corpus
            with pytest.raises(RuntimeError, match="simulated provider failure"):
                await rebuild_signal_corpus(
                    db_path=str(db_file),
                    tickers=[("TEST", "stock")],
                )

    async with aiosqlite.connect(db_file) as c:
        c.row_factory = aiosqlite.Row
        row = await (await c.execute(
            "SELECT status FROM job_run_log WHERE job_name='rebuild_signal_corpus' "
            "ORDER BY id DESC LIMIT 1"
        )).fetchone()
        assert row is not None, "Expected job_run_log row for failed rebuild_signal_corpus"
        assert row["status"] == "error", f"Expected error, got {row['status']}"


def test_rebuild_signal_corpus_rolls_back_partial_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLOCKER 3: partial rows from populate_signal_corpus are deleted on error.

    Monkey-patches populate_signal_corpus to insert 5 rows then raise.
    Asserts after the exception:
    (a) exception propagates (re-raised by daemon wrapper)
    (b) job_run_log shows 'error'
    (c) SELECT COUNT(*) FROM backtest_signal_history WHERE backtest_run_id = <jrl_id>
        returns 0 (DELETE rollback guard removed all partial rows)
    """
    async def _run() -> None:
        db_file = tmp_path / "rb.db"
        await init_db(db_file)

        # Seed price_history_cache so BLOCKER 2 derivation has data
        async with aiosqlite.connect(db_file) as c:
            for i in range(10):
                d = f"2024-01-{i + 1:02d}"
                await c.execute(
                    """INSERT OR IGNORE INTO price_history_cache
                       (ticker, date, open, high, low, close, volume, asset_type)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    ("TEST", d, 100.0, 101.0, 99.0, 100.0 + i * 0.5, 1_000_000.0, "stock"),
                )
            await c.commit()

        # Monkey-patch populate_signal_corpus to insert 5 rows then raise
        from backtesting import signal_corpus as sc_mod

        async def _partial_populate(
            db_path, ticker, asset_type, provider,
            start_date, end_date, agents=None, run_id=None,
        ):
            async with aiosqlite.connect(db_path) as conn:
                for j in range(5):
                    await conn.execute(
                        """INSERT INTO backtest_signal_history
                           (ticker, asset_type, signal_date, agent_name, raw_score,
                            signal, confidence, forward_return_5d, forward_return_21d,
                            source, backtest_run_id)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            ticker, asset_type, f"2024-01-{j + 1:02d}",
                            "TechnicalAgent", 0.5, "BUY", 75.0,
                            0.01, 0.02, "backtest", run_id,
                        ),
                    )
                await conn.commit()
            raise RuntimeError("simulated mid-insert failure")

        monkeypatch.setattr(sc_mod, "populate_signal_corpus", _partial_populate)
        # Also patch in daemon.jobs namespace if imported by name there
        import daemon.jobs as djobs
        monkeypatch.setattr(djobs, "populate_signal_corpus", _partial_populate, raising=False)

        from daemon.jobs import rebuild_signal_corpus
        with pytest.raises(RuntimeError, match="simulated mid-insert failure"):
            await rebuild_signal_corpus(
                db_path=str(db_file),
                tickers=[("TEST", "stock")],
            )

        # Locate the error job_run_log row and assert no backtest_signal_history
        # rows remain for its run_id (BLOCKER 3 guard)
        async with aiosqlite.connect(db_file) as c:
            r = await (await c.execute(
                "SELECT id, status FROM job_run_log "
                "WHERE job_name='rebuild_signal_corpus' ORDER BY id DESC LIMIT 1"
            )).fetchone()
            assert r is not None, "No job_run_log row found"
            jrl_id, status = r
            assert status == "error", f"Expected error status, got {status!r}"

            cnt = (await (await c.execute(
                "SELECT COUNT(*) FROM backtest_signal_history WHERE backtest_run_id = ?",
                (str(jrl_id),),
            )).fetchone())[0]
            assert cnt == 0, (
                f"Expected 0 partial rows after rollback, got {cnt} "
                f"(run_id={jrl_id!r})"
            )

    asyncio.run(_run())
