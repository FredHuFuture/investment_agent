"""Tests for FOUND-06: WAL mode, covering indexes, pruning job.

Tasks covered:
- T-02-01: WAL PRAGMA in init_db + composite indexes + job_run_log schema
- T-02-03: 50k-row analytics timing + concurrency soak

Run with:
    pytest tests/test_foundation_06_db_wal_indexes.py -x -v
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone

import aiosqlite
import pytest

from db.database import init_db


# ---------------------------------------------------------------------------
# Test A: WAL mode after init_db
# ---------------------------------------------------------------------------

def test_wal_mode_enabled(tmp_path: pytest.TempPathFactory) -> None:
    """After init_db, a fresh connection reports journal_mode=wal."""
    async def _run() -> None:
        db = str(tmp_path / "wal.db")
        await init_db(db)
        async with aiosqlite.connect(db) as conn:
            row = await (await conn.execute("PRAGMA journal_mode;")).fetchone()
            assert row is not None
            assert row[0].lower() == "wal", f"expected wal, got {row[0]!r}"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test B: job_run_log table exists after init_db
# ---------------------------------------------------------------------------

def test_job_run_log_table_exists(tmp_path: pytest.TempPathFactory) -> None:
    """init_db creates the job_run_log table."""
    async def _run() -> None:
        db = str(tmp_path / "jrl.db")
        await init_db(db)
        async with aiosqlite.connect(db) as conn:
            row = await (
                await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='job_run_log'"
                )
            ).fetchone()
            assert row is not None, "job_run_log table not found"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test C: job_run_log schema columns and CHECK constraint
# ---------------------------------------------------------------------------

def test_job_run_log_schema(tmp_path: pytest.TempPathFactory) -> None:
    """job_run_log has the required columns and a CHECK on status."""
    async def _run() -> None:
        db = str(tmp_path / "schema.db")
        await init_db(db)
        async with aiosqlite.connect(db) as conn:
            cols = await (
                await conn.execute("PRAGMA table_info(job_run_log);")
            ).fetchall()
            col_names = {c[1] for c in cols}
            expected = {
                "id", "job_name", "started_at", "completed_at",
                "status", "error_message", "duration_ms", "created_at",
            }
            assert expected.issubset(col_names), f"missing columns: {expected - col_names}"

            # Verify CHECK constraint via sqlite_master
            sql_row = await (
                await conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='job_run_log'"
                )
            ).fetchone()
            assert sql_row is not None
            sql = sql_row[0].lower()
            for status in ("running", "success", "error", "aborted"):
                assert status in sql, f"status '{status}' not in CHECK constraint"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test D: idx_job_run_log_job_started index exists
# ---------------------------------------------------------------------------

def test_job_run_log_index_exists(tmp_path: pytest.TempPathFactory) -> None:
    """idx_job_run_log_job_started index exists on job_run_log."""
    async def _run() -> None:
        db = str(tmp_path / "idx.db")
        await init_db(db)
        async with aiosqlite.connect(db) as conn:
            row = await (
                await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND name='idx_job_run_log_job_started'"
                )
            ).fetchone()
            assert row is not None, "idx_job_run_log_job_started not found"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test E: idx_portfolio_snapshots_timestamp exists
# ---------------------------------------------------------------------------

def test_portfolio_snapshots_index_exists(tmp_path: pytest.TempPathFactory) -> None:
    """idx_portfolio_snapshots_timestamp index exists."""
    async def _run() -> None:
        db = str(tmp_path / "ps_idx.db")
        await init_db(db)
        async with aiosqlite.connect(db) as conn:
            row = await (
                await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND name='idx_portfolio_snapshots_timestamp'"
                )
            ).fetchone()
            assert row is not None, "idx_portfolio_snapshots_timestamp not found"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test F: idx_signal_history_ticker_created exists
# ---------------------------------------------------------------------------

def test_signal_history_index_used(tmp_path: pytest.TempPathFactory) -> None:
    """idx_signal_history_ticker_created index exists on signal_history."""
    async def _run() -> None:
        db = str(tmp_path / "sh_idx.db")
        await init_db(db)
        async with aiosqlite.connect(db) as conn:
            row = await (
                await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND name='idx_signal_history_ticker_created'"
                )
            ).fetchone()
            assert row is not None, "idx_signal_history_ticker_created not found"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test G: CHECK constraint rejects invalid status
# ---------------------------------------------------------------------------

def test_job_run_log_check_constraint(tmp_path: pytest.TempPathFactory) -> None:
    """Inserting an invalid status raises IntegrityError."""
    async def _run() -> None:
        db = str(tmp_path / "check.db")
        await init_db(db)
        async with aiosqlite.connect(db) as conn:
            with pytest.raises(aiosqlite.IntegrityError):
                await conn.execute(
                    "INSERT INTO job_run_log (job_name, started_at, status) "
                    "VALUES (?, ?, ?)",
                    ("test_job", "2026-01-01T00:00:00+00:00", "invalid"),
                )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test H: init_db is idempotent
# ---------------------------------------------------------------------------

def test_init_db_idempotent(tmp_path: pytest.TempPathFactory) -> None:
    """Calling init_db twice on the same path raises no exception."""
    async def _run() -> None:
        db = str(tmp_path / "idem.db")
        await init_db(db)
        await init_db(db)  # second call must not raise
        # Check no duplicate indexes
        async with aiosqlite.connect(db) as conn:
            rows = await (
                await conn.execute(
                    "SELECT name, COUNT(*) as cnt FROM sqlite_master "
                    "WHERE type='index' "
                    "GROUP BY name HAVING cnt > 1"
                )
            ).fetchall()
            assert len(rows) == 0, f"duplicate indexes found: {rows}"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test: pruning job deletes old rows
# ---------------------------------------------------------------------------

def test_pruning_deletes_old_rows(tmp_path: pytest.TempPathFactory) -> None:
    """prune_signal_history deletes rows older than retention_days."""
    async def _run() -> None:
        from daemon.jobs import prune_signal_history

        db = str(tmp_path / "prune_basic.db")
        await init_db(db)

        # Insert 5 old rows (120 days ago) and 5 fresh rows (1 day ago)
        async with aiosqlite.connect(db) as conn:
            old_ts = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
            fresh_ts = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            for ts in [old_ts] * 5 + [fresh_ts] * 5:
                await conn.execute(
                    "INSERT INTO signal_history (ticker, asset_type, final_signal, "
                    "final_confidence, raw_score, consensus_score, agent_signals_json, "
                    "reasoning, warnings_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("AAPL", "stock", "HOLD", 50.0, 0.0, 1.0, "[]", "seed", "[]", ts),
                )
            await conn.commit()

        result = await prune_signal_history(db, retention_days=90)
        assert result["deleted_rows"] == 5, f"expected 5 deleted, got {result['deleted_rows']}"
        assert result["retained_rows"] == 5, f"expected 5 retained, got {result['retained_rows']}"

    asyncio.run(_run())


# ===========================================================================
# Task 3: Performance + concurrency tests (added in T-02-03)
# ===========================================================================


async def _seed_signal_history(db_path: str, n_rows: int, span_days: int) -> None:
    """Insert n_rows into signal_history spanning the last span_days."""
    import random

    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
    async with aiosqlite.connect(db_path) as conn:
        now = datetime.now(timezone.utc)
        rows = []
        for i in range(n_rows):
            age_days = (i * span_days) // n_rows
            ts = (now - timedelta(days=age_days, seconds=random.randint(0, 86400))).isoformat()
            rows.append((
                random.choice(tickers), "stock", "HOLD", 50.0, None, 0.0, 1.0,
                "[]", "seed", "[]", None, "OPEN", None, None, ts,
            ))
        await conn.executemany(
            """
            INSERT INTO signal_history (
                ticker, asset_type, final_signal, final_confidence, regime,
                raw_score, consensus_score, agent_signals_json, reasoning,
                warnings_json, thesis_id, outcome, outcome_return_pct,
                outcome_resolved_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        await conn.commit()


def test_analytics_query_fast_on_50k_rows(tmp_path: pytest.TempPathFactory) -> None:
    """Analytics query on 50k rows completes in <1.0s using covering index."""
    async def _run() -> None:
        db = str(tmp_path / "perf.db")
        await init_db(db)
        await _seed_signal_history(db, n_rows=50_000, span_days=200)

        async with aiosqlite.connect(db) as conn:
            t0 = time.monotonic()
            rows = await (
                await conn.execute(
                    "SELECT * FROM signal_history WHERE ticker = ? ORDER BY created_at DESC LIMIT 100",
                    ("AAPL",),
                )
            ).fetchall()
            duration = time.monotonic() - t0
        assert duration < 1.0, f"analytics query took {duration:.3f}s on 50k rows (want <1.0s)"
        assert len(rows) > 0, "no rows returned for AAPL"

    asyncio.run(_run())


def test_explain_query_plan_uses_index(tmp_path: pytest.TempPathFactory) -> None:
    """EXPLAIN QUERY PLAN shows the covering index is used."""
    async def _run() -> None:
        db = str(tmp_path / "explain.db")
        await init_db(db)
        await _seed_signal_history(db, n_rows=1_000, span_days=30)
        async with aiosqlite.connect(db) as conn:
            plan = await (
                await conn.execute(
                    "EXPLAIN QUERY PLAN SELECT * FROM signal_history "
                    "WHERE ticker = ? ORDER BY created_at DESC LIMIT 100",
                    ("AAPL",),
                )
            ).fetchall()
            plan_text = " ".join(str(r) for r in plan).lower()
            assert "idx_signal_history_ticker" in plan_text, f"index not used: {plan}"

    asyncio.run(_run())


def test_concurrent_writes_and_reads_no_lock_error(tmp_path: pytest.TempPathFactory) -> None:
    """3 concurrent writers + 3 readers produce zero 'database is locked' errors."""
    async def _run() -> None:
        db = str(tmp_path / "concurrency.db")
        await init_db(db)

        errors: list[str] = []

        async def writer(kind: str, n: int) -> None:
            try:
                async with aiosqlite.connect(db) as conn:
                    await conn.execute("PRAGMA journal_mode=WAL;")
                    await conn.execute("PRAGMA busy_timeout=5000;")
                    for i in range(n):
                        if kind == "signal":
                            await conn.execute(
                                "INSERT INTO signal_history (ticker, asset_type, final_signal, "
                                "final_confidence, raw_score, consensus_score, agent_signals_json, "
                                "reasoning, warnings_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (f"W{i}", "stock", "HOLD", 50.0, 0.0, 1.0, "[]", "c", "[]"),
                            )
                        await conn.commit()
            except Exception as exc:
                errors.append(f"writer[{kind}]: {exc}")

        async def reader(n: int) -> None:
            try:
                async with aiosqlite.connect(db) as conn:
                    await conn.execute("PRAGMA busy_timeout=5000;")
                    for _ in range(n):
                        await (await conn.execute(
                            "SELECT COUNT(*) FROM signal_history"
                        )).fetchone()
            except Exception as exc:
                errors.append(f"reader: {exc}")

        await asyncio.gather(
            writer("signal", 100),
            writer("signal", 100),
            writer("signal", 100),
            reader(50),
            reader(50),
            reader(50),
        )
        assert not any("locked" in e.lower() for e in errors), f"lock errors: {errors}"
        # Some rowcount > 0 proves writes landed
        async with aiosqlite.connect(db) as conn:
            count = await (await conn.execute("SELECT COUNT(*) FROM signal_history")).fetchone()
            assert count[0] >= 300, f"expected >=300 rows, got {count[0]}"

    asyncio.run(_run())


def test_analytics_fast_after_pruning(tmp_path: pytest.TempPathFactory) -> None:
    """Analytics query still fast after prune_signal_history reduces the table."""
    async def _run() -> None:
        from daemon.jobs import prune_signal_history

        db = str(tmp_path / "prune.db")
        await init_db(db)
        await _seed_signal_history(db, n_rows=50_000, span_days=200)
        result = await prune_signal_history(db, retention_days=30)
        assert result["deleted_rows"] > 0
        # Query still fast after prune
        async with aiosqlite.connect(db) as conn:
            t0 = time.monotonic()
            await (await conn.execute(
                "SELECT * FROM signal_history WHERE ticker = ? "
                "ORDER BY created_at DESC LIMIT 100",
                ("AAPL",),
            )).fetchall()
            assert time.monotonic() - t0 < 1.0

    asyncio.run(_run())
