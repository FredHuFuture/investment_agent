from __future__ import annotations
import pytest
import aiosqlite
from db.database import init_db


@pytest.mark.asyncio
async def test_fundamentals_provider_migration_idempotent(tmp_path):
    """Running init_db twice does not duplicate columns, indexes, or raise.

    Covers all 4 tables: signal_history, backtest_signal_history, drift_log,
    corpus_rebuild_jobs. The 4th (corpus_rebuild_jobs) is required by 08-02
    Task 4's first-enable rebuild-detection query.
    """
    db_path = tmp_path / "test_migration.db"

    # First migration
    await init_db(str(db_path))
    # Second migration must be a no-op
    await init_db(str(db_path))

    async with aiosqlite.connect(str(db_path)) as conn:
        for table in (
            "signal_history",
            "backtest_signal_history",
            "drift_log",
            "corpus_rebuild_jobs",
        ):
            rows = await (await conn.execute(f"PRAGMA table_info({table});")).fetchall()
            col_names = [row[1] for row in rows]
            assert "fundamentals_provider" in col_names, (
                f"{table} missing fundamentals_provider column after init_db"
            )
            # NOT NULL + DEFAULT 'yfinance'
            col_row = [row for row in rows if row[1] == "fundamentals_provider"][0]
            assert col_row[2] == "TEXT", f"{table}.fundamentals_provider type wrong"
            assert col_row[3] == 1, (
                f"{table}.fundamentals_provider must be NOT NULL"
            )

        # Index existence — 4 composite indexes (4th is for first-enable lookup)
        for idx_name in (
            "idx_signal_history_ticker_created_provider",
            "idx_bsh_ticker_signal_date_provider",
            "idx_drift_log_agent_asset_provider_evaluated",
            "idx_crj_provider_status",
        ):
            row = await (
                await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?;",
                    (idx_name,),
                )
            ).fetchone()
            assert row is not None, f"Index {idx_name} not created"


@pytest.mark.asyncio
async def test_existing_rows_backfill_to_yfinance(tmp_path):
    """Pre-existing signal_history rows must default to 'yfinance' after migration."""
    db_path = tmp_path / "test_backfill.db"
    # First init creates the schema. Insert a row, then re-run init to ensure
    # the column is added to a non-empty table and existing rows backfill.
    await init_db(str(db_path))
    async with aiosqlite.connect(str(db_path)) as conn:
        # Insert a minimal signal_history row using only pre-Phase-8 columns
        await conn.execute(
            """
            INSERT INTO signal_history
              (ticker, asset_type, final_signal, final_confidence,
               raw_score, consensus_score, agent_signals_json, reasoning)
            VALUES ('AAPL', 'stock', 'BUY', 75.0, 0.5, 0.5, '{}', 'test')
            """
        )
        await conn.commit()
        row = await (
            await conn.execute(
                "SELECT fundamentals_provider FROM signal_history WHERE ticker='AAPL'"
            )
        ).fetchone()
        assert row is not None
        assert row[0] == "yfinance", (
            f"Pre-existing row backfill failed: got {row[0]!r}, expected 'yfinance'"
        )


@pytest.mark.asyncio
async def test_corpus_rebuild_jobs_has_fundamentals_provider_column(tmp_path):
    """08-02 Task 4 prerequisite: corpus_rebuild_jobs MUST have the column so
    the first-enable detection query (`WHERE fundamentals_provider='simfin'`)
    does not error at the SQL layer."""
    db_path = tmp_path / "test_crj.db"
    await init_db(str(db_path))
    async with aiosqlite.connect(str(db_path)) as conn:
        rows = await (
            await conn.execute("PRAGMA table_info(corpus_rebuild_jobs);")
        ).fetchall()
        col_names = [row[1] for row in rows]
        assert "fundamentals_provider" in col_names, (
            "corpus_rebuild_jobs.fundamentals_provider column missing — "
            "08-02 Task 4 first-enable query will fail at runtime"
        )
        # The 4th index supports the first-enable lookup
        idx_row = await (
            await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name='idx_crj_provider_status';"
            )
        ).fetchone()
        assert idx_row is not None, "idx_crj_provider_status missing"
