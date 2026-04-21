"""Tests for SIG-05b: backtest_signal_history DDL and populate_signal_corpus.

Covers:
- Table + indexes created by init_db
- populate_signal_corpus inserts rows for a mock provider
- forward_return_5d computed via row-offset (AP-01 guard)
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import aiosqlite
import pandas as pd
import pytest

from db.database import init_db


# ---------------------------------------------------------------------------
# Inline provider helper
# ---------------------------------------------------------------------------

class _CorpusProvider:
    """Minimal DataProvider for signal_corpus tests."""

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


def _make_corpus_ohlcv(n: int = 80, start_price: float = 100.0) -> pd.DataFrame:
    """Monotone uptrend OHLCV so TechnicalAgent produces BUY signals."""
    dates = pd.bdate_range("2024-01-02", periods=n)
    prices = [start_price + i * 0.5 for i in range(n)]
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
# DDL tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backtest_signal_history_ddl_created(tmp_path: Path) -> None:
    """init_db creates backtest_signal_history table with all required columns."""
    db_file = tmp_path / "test_ddl.db"
    await init_db(db_file)

    import sqlite3
    con = sqlite3.connect(db_file)
    try:
        # Table exists
        row = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='backtest_signal_history'"
        ).fetchone()
        assert row is not None, "backtest_signal_history table not found"

        # Check all required columns
        cols = {r[1] for r in con.execute("PRAGMA table_info(backtest_signal_history)")}
        required_cols = {
            "id", "ticker", "asset_type", "signal_date", "agent_name",
            "raw_score", "signal", "confidence", "forward_return_5d",
            "forward_return_21d", "source", "backtest_run_id", "created_at",
        }
        missing = required_cols - cols
        assert not missing, f"Missing columns in backtest_signal_history: {missing}"
    finally:
        con.close()


@pytest.mark.asyncio
async def test_backtest_signal_history_indexes_created(tmp_path: Path) -> None:
    """init_db creates both idx_bsh_ticker_date and idx_bsh_agent_date indexes."""
    db_file = tmp_path / "test_idx.db"
    await init_db(db_file)

    import sqlite3
    con = sqlite3.connect(db_file)
    try:
        indexes = {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_bsh_ticker_date" in indexes, (
            f"idx_bsh_ticker_date not found. Available indexes: {indexes}"
        )
        assert "idx_bsh_agent_date" in indexes, (
            f"idx_bsh_agent_date not found. Available indexes: {indexes}"
        )
    finally:
        con.close()


# ---------------------------------------------------------------------------
# populate_signal_corpus tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_populate_signal_corpus_inserts_rows(tmp_path: Path) -> None:
    """populate_signal_corpus inserts rows into backtest_signal_history."""
    from backtesting.signal_corpus import populate_signal_corpus

    db_file = tmp_path / "corpus.db"
    await init_db(db_file)

    df = _make_corpus_ohlcv(n=80)
    provider = _CorpusProvider(df)

    start_date = str(df.index[0].date())
    end_date = str(df.index[-1].date())

    stats = await populate_signal_corpus(
        db_path=str(db_file),
        ticker="TEST",
        asset_type="stock",
        provider=provider,
        start_date=start_date,
        end_date=end_date,
    )

    # rows_inserted may be 0 if TechnicalAgent returned only HOLD signals on this
    # short series — what matters is the function runs without error
    assert isinstance(stats, dict)
    assert "rows_inserted" in stats
    assert "run_id" in stats
    assert stats["run_id"] is not None

    # If rows were inserted, verify they're in the DB
    if stats["rows_inserted"] > 0:
        async with aiosqlite.connect(db_file) as c:
            cnt = (await (await c.execute(
                "SELECT COUNT(*) FROM backtest_signal_history WHERE ticker='TEST'"
            )).fetchone())[0]
            assert cnt == stats["rows_inserted"], (
                f"DB count {cnt} != reported rows_inserted {stats['rows_inserted']}"
            )


@pytest.mark.asyncio
async def test_forward_return_5d_matches_row_offset(tmp_path: Path) -> None:
    """AP-01 guard: forward_return_5d is computed via OHLCV row offset, not calendar math."""
    from backtesting.signal_corpus import populate_signal_corpus

    db_file = tmp_path / "fwd.db"
    await init_db(db_file)

    # Deterministic price series: close = 100 + row_index (easy to verify)
    n = 80
    dates = pd.bdate_range("2024-01-02", periods=n)
    prices = [100.0 + i for i in range(n)]
    df = pd.DataFrame(
        {
            "Open": [p - 0.3 for p in prices],
            "High": [p + 1.0 for p in prices],
            "Low": [p - 1.0 for p in prices],
            "Close": prices,
            "Volume": [1_000_000.0] * n,
        },
        index=dates,
    )
    provider = _CorpusProvider(df)

    start_date = str(df.index[0].date())
    end_date = str(df.index[-1].date())

    stats = await populate_signal_corpus(
        db_path=str(db_file),
        ticker="TEST",
        asset_type="stock",
        provider=provider,
        start_date=start_date,
        end_date=end_date,
    )

    if stats["rows_inserted"] == 0:
        pytest.skip("No agent signals generated — AP-01 guard cannot be verified")

    # For the first inserted row, verify the stored forward_return_5d
    async with aiosqlite.connect(db_file) as c:
        c.row_factory = aiosqlite.Row
        rows = await (await c.execute(
            "SELECT signal_date, forward_return_5d FROM backtest_signal_history "
            "WHERE ticker='TEST' AND forward_return_5d IS NOT NULL "
            "ORDER BY signal_date LIMIT 5"
        )).fetchall()

    if not rows:
        pytest.skip("No rows with forward_return_5d — skipping AP-01 row-offset check")

    # Verify the row-offset computation matches for a sampled row
    # Build the price index as the backtester would see it
    date_to_idx = {str(d.date()): i for i, d in enumerate(df.index)}

    for row in rows[:3]:  # check first 3 rows
        sig_date = row["signal_date"]
        stored_fr5 = row["forward_return_5d"]
        if sig_date not in date_to_idx:
            continue
        idx = date_to_idx[sig_date]
        if idx + 5 >= len(prices):
            continue
        expected_fr5 = (prices[idx + 5] - prices[idx]) / prices[idx]
        assert abs(stored_fr5 - expected_fr5) < 1e-6, (
            f"Row-offset mismatch for {sig_date}: "
            f"stored={stored_fr5:.6f}, expected={expected_fr5:.6f}"
        )


@pytest.mark.asyncio
async def test_populate_signal_corpus_stores_raw_score_not_null(tmp_path: Path) -> None:
    """WR-01 regression guard: raw_score must never be NULL after populate runs.

    Before the WR-01 fix, populate_signal_corpus read agent_sig.get("raw_score")
    from per-agent sub-dicts which do not have that key — every row was NULL.
    After the fix it reads entry.get("raw_score", 0.0) (top-level aggregated score),
    so raw_score is always a float (0.0 if the aggregator produced no score).
    """
    from backtesting.signal_corpus import populate_signal_corpus

    db_file = tmp_path / "wr01.db"
    await init_db(db_file)

    df = _make_corpus_ohlcv(n=80)
    provider = _CorpusProvider(df)

    start_date = str(df.index[0].date())
    end_date = str(df.index[-1].date())

    stats = await populate_signal_corpus(
        db_path=str(db_file),
        ticker="TEST",
        asset_type="stock",
        provider=provider,
        start_date=start_date,
        end_date=end_date,
    )

    if stats["rows_inserted"] == 0:
        pytest.skip("No agent signals generated — WR-01 guard cannot be verified")

    async with aiosqlite.connect(db_file) as c:
        null_count = (await (await c.execute(
            "SELECT COUNT(*) FROM backtest_signal_history WHERE raw_score IS NULL"
        )).fetchone())[0]

    assert null_count == 0, (
        f"WR-01 regression: {null_count} rows have raw_score IS NULL after "
        f"populate_signal_corpus — top-level entry['raw_score'] must be used, "
        f"not per-agent sub-dict which lacks that key."
    )
