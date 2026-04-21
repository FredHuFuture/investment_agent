"""Database initialization for Investment Analysis Agent."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

from db.connection_pool import db_pool

DEFAULT_DB_PATH = Path("data/investment_agent.db")


async def _ensure_column(
    conn: aiosqlite.Connection, table_name: str, column_name: str, column_type: str
) -> None:
    """Add a missing column for lightweight schema evolution."""
    table_info = await (await conn.execute(f"PRAGMA table_info({table_name});")).fetchall()
    existing_columns = {row[1] for row in table_info}

    if column_name not in existing_columns:
        await conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};"
        )


async def _migrate_add_portfolios(conn: aiosqlite.Connection) -> None:
    """Add the ``portfolios`` table and link existing positions to a default portfolio.

    The migration is idempotent: safe to run on every startup.
    """
    # 1. Create the portfolios table
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            cash REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            is_default INTEGER NOT NULL DEFAULT 0
        );
        """
    )

    # 2. Add portfolio_id column to active_positions if missing
    await _ensure_column(conn, "active_positions", "portfolio_id", "INTEGER NOT NULL DEFAULT 1")

    # 3. Add portfolio_id column to closed_positions (which is active_positions with status='closed')
    # active_positions already holds both open and closed rows, so the column above covers it.
    # If a separate closed_positions table existed we'd migrate it here; it doesn't, so this is a no-op.

    # 4. Create the "Default" portfolio row (id=1, is_default=1) if it doesn't already exist
    existing = await (
        await conn.execute("SELECT id FROM portfolios WHERE id = 1")
    ).fetchone()
    if existing is None:
        # Copy cash from portfolio_meta if it exists
        cash_row = await (
            await conn.execute("SELECT value FROM portfolio_meta WHERE key = 'cash'")
        ).fetchone()
        initial_cash = float(cash_row[0]) if cash_row is not None else 0.0

        await conn.execute(
            """
            INSERT INTO portfolios (id, name, description, cash, is_default)
            VALUES (1, 'Default', 'Default portfolio', ?, 1)
            """,
            (initial_cash,),
        )


async def _migrate_ticker_unique_to_partial(conn: aiosqlite.Connection) -> None:
    """Replace the blanket UNIQUE on active_positions.ticker with a partial
    unique index that only constrains *open* positions.

    This allows re-opening a position for the same ticker after closing one.
    The migration is idempotent: safe to run on every startup.

    SQLite auto-generates ``sqlite_autoindex_active_positions_1`` for an inline
    ``UNIQUE`` constraint.  These autoindexes **cannot** be dropped via
    ``DROP INDEX``.  The only way to remove the constraint is to rebuild the
    table without the ``UNIQUE`` keyword on the column definition.
    """
    # 1. Check whether the autoindex still exists
    row = await (
        await conn.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'index' AND tbl_name = 'active_positions' "
            "AND name = 'sqlite_autoindex_active_positions_1';"
        )
    ).fetchone()

    if row is not None:
        # --- full table rebuild required ---
        # Grab current column info so we build a faithful copy
        table_info = await (
            await conn.execute("PRAGMA table_info(active_positions);")
        ).fetchall()
        col_names = [c[1] for c in table_info]

        cols_csv = ", ".join(col_names)

        await conn.execute(
            "ALTER TABLE active_positions RENAME TO _active_positions_old;"
        )

        # Recreate the table WITHOUT the inline UNIQUE on ticker
        await conn.execute(
            """
            CREATE TABLE active_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                asset_type TEXT NOT NULL CHECK (asset_type IN ('stock', 'btc', 'eth')),
                quantity REAL NOT NULL,
                avg_cost REAL NOT NULL,
                sector TEXT,
                industry TEXT,
                entry_date TEXT NOT NULL,
                original_analysis_id INTEGER,
                expected_return_pct REAL,
                expected_hold_days INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'open',
                exit_price REAL,
                exit_date TEXT,
                exit_reason TEXT,
                realized_pnl REAL,
                FOREIGN KEY (original_analysis_id) REFERENCES positions_thesis(id)
            );
            """
        )

        # Copy data — only columns that exist in BOTH old and new tables
        new_info = await (
            await conn.execute("PRAGMA table_info(active_positions);")
        ).fetchall()
        new_col_names = {c[1] for c in new_info}
        common_cols = [c for c in col_names if c in new_col_names]
        common_csv = ", ".join(common_cols)

        await conn.execute(
            f"INSERT INTO active_positions ({common_csv}) "
            f"SELECT {common_csv} FROM _active_positions_old;"
        )
        await conn.execute("DROP TABLE _active_positions_old;")

    # 2. Also drop any user-created unique index on ticker (non-autoindex)
    rows = await (
        await conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'index' AND tbl_name = 'active_positions' "
            "AND name != 'idx_active_positions_ticker_open' "
            "AND name NOT LIKE 'sqlite_autoindex_%';"
        )
    ).fetchall()

    for (idx_name,) in rows:
        info = await (
            await conn.execute(f"PRAGMA index_info(\"{idx_name}\");")
        ).fetchall()
        col_names_idx = [r[2] for r in info]
        if col_names_idx == ["ticker"]:
            idx_list = await (
                await conn.execute("PRAGMA index_list(active_positions);")
            ).fetchall()
            for il_row in idx_list:
                if il_row[1] == idx_name and il_row[2] == 1:
                    await conn.execute(f"DROP INDEX IF EXISTS \"{idx_name}\";")
                    break

    # 3. Create the partial unique index (idempotent via IF NOT EXISTS)
    await conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_active_positions_ticker_open
        ON active_positions(ticker) WHERE status = 'open';
        """
    )


async def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> Path:
    """Initialize SQLite database and required schema.

    Also initialises the module-level ``db_pool`` singleton so the daemon can
    reuse connections without opening a new one per operation.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    await db_pool.init(path)

    async with db_pool.connection() as conn:
        # FOUND-06: Enforce WAL + safe defaults on the canonical database connection.
        # Individual connections in db_pool also set these, but this ensures
        # the database file is in WAL mode even for callers that bypass the pool.
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA synchronous=NORMAL;")
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute("PRAGMA foreign_keys=ON;")

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions_thesis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                expected_signal TEXT NOT NULL,
                expected_confidence REAL NOT NULL,
                expected_entry_price REAL NOT NULL,
                expected_target_price REAL,
                expected_return_pct REAL,
                expected_stop_loss REAL,
                expected_hold_days INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await _ensure_column(
            conn=conn,
            table_name="positions_thesis",
            column_name="expected_return_pct",
            column_type="REAL",
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thesis_id INTEGER NOT NULL,
                action TEXT NOT NULL CHECK (action IN ('BUY', 'SELL')),
                quantity REAL NOT NULL,
                executed_price REAL NOT NULL,
                executed_at TEXT NOT NULL,
                reason TEXT NOT NULL CHECK (
                    reason IN ('manual', 'target_hit', 'stop_loss')
                ),
                FOREIGN KEY (thesis_id)
                    REFERENCES positions_thesis(id)
                    ON DELETE CASCADE
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_value REAL NOT NULL,
                cash REAL NOT NULL,
                positions_json TEXT NOT NULL,
                trigger_event TEXT NOT NULL
            );
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS active_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                asset_type TEXT NOT NULL CHECK (asset_type IN ('stock', 'btc', 'eth')),
                quantity REAL NOT NULL,
                avg_cost REAL NOT NULL,
                sector TEXT,
                industry TEXT,
                entry_date TEXT NOT NULL,
                original_analysis_id INTEGER,
                expected_return_pct REAL,
                expected_hold_days INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'open',
                exit_price REAL,
                exit_date TEXT,
                exit_reason TEXT,
                realized_pnl REAL,
                FOREIGN KEY (original_analysis_id) REFERENCES positions_thesis(id)
            );
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_trade_executions_thesis_id
            ON trade_executions(thesis_id);
            """
        )
        # Sprint 8: close-position lifecycle columns
        for col, ctype in [
            ("status", "TEXT NOT NULL DEFAULT 'open'"),
            ("exit_price", "REAL"),
            ("exit_date", "TEXT"),
            ("exit_reason", "TEXT"),
            ("realized_pnl", "REAL"),
        ]:
            await _ensure_column(conn, "active_positions", col, ctype)

        # Migrate blanket UNIQUE(ticker) -> partial unique index on open positions only.
        # This allows re-opening a position for the same ticker after closing one.
        await _migrate_ticker_unique_to_partial(conn)

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_active_positions_ticker
            ON active_positions(ticker);
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_active_positions_asset_type
            ON active_positions(asset_type);
            """
        )

        # FOUND-06: Covering index on portfolio_snapshots(timestamp) for analytics scans.
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_timestamp
            ON portfolio_snapshots(timestamp);
            """
        )

        # Task 010: monitoring alerts
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS monitoring_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL CHECK (
                    severity IN ('CRITICAL', 'HIGH', 'WARNING', 'INFO')
                ),
                message TEXT NOT NULL,
                recommended_action TEXT,
                current_price REAL,
                trigger_price REAL,
                acknowledged INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_monitoring_alerts_ticker_time
            ON monitoring_alerts(ticker, created_at);
            """
        )

        # Task 011: signal history
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                final_signal TEXT NOT NULL CHECK (
                    final_signal IN ('BUY', 'HOLD', 'SELL')
                ),
                final_confidence REAL NOT NULL,
                regime TEXT,
                raw_score REAL NOT NULL,
                consensus_score REAL NOT NULL,
                agent_signals_json TEXT NOT NULL,
                reasoning TEXT NOT NULL,
                warnings_json TEXT,
                thesis_id INTEGER,
                outcome TEXT CHECK (
                    outcome IS NULL OR outcome IN ('WIN', 'LOSS', 'OPEN', 'SKIPPED')
                ),
                outcome_return_pct REAL,
                outcome_resolved_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (thesis_id) REFERENCES positions_thesis(id)
            );
            """
        )
        # FOUND-06: Rename legacy idx_signal_history_ticker → idx_signal_history_ticker_created
        # (DROP is a no-op if the old name never existed; covers both fresh installs
        # and existing DBs that were initialized before this rename).
        # Note: briefly holds a write lock during rebuild on large existing DBs, but
        # init_db runs at startup before API traffic — this is acceptable.
        await conn.execute("DROP INDEX IF EXISTS idx_signal_history_ticker;")
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_signal_history_ticker_created
            ON signal_history(ticker, created_at);
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_signal_history_outcome
            ON signal_history(outcome, final_signal);
            """
        )

        # Task 014: daemon execution history
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daemon_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('success', 'error', 'skipped')
                ),
                started_at TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                result_json TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_daemon_runs_job_time
            ON daemon_runs(job_name, created_at);
            """
        )

        # FOUND-07: job_run_log — durable start/finish tracking with 'running' + 'aborted' states.
        # daemon_runs records COMPLETED outcomes only. job_run_log records an explicit
        # start-of-run row with status='running'; the row is updated to
        # 'success'|'error' on completion, or 'aborted' by the startup reconciler
        # if the daemon crashed mid-job.
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_run_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL CHECK (
                    status IN ('running', 'success', 'error', 'aborted')
                ),
                error_message TEXT,
                duration_ms INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_job_run_log_job_started
            ON job_run_log(job_name, started_at);
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_job_run_log_status
            ON job_run_log(status);
            """
        )

        # SIG-05: backtest_signal_history — stores per-bar per-agent signals from
        # backtester runs, with computed forward returns for IC/Brier calibration
        # (Plan 02-03 consumes this table). Schema matches 02-RESEARCH.md Q4 DDL.
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_signal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                signal_date TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                raw_score REAL,
                signal TEXT NOT NULL,
                confidence REAL,
                forward_return_5d REAL,
                forward_return_21d REAL,
                source TEXT DEFAULT 'backtest',
                backtest_run_id TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_bsh_ticker_date
            ON backtest_signal_history(ticker, signal_date)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_bsh_agent_date
            ON backtest_signal_history(agent_name, signal_date)
            """
        )

        # Task 013: price history cache for backtesting
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                asset_type TEXT NOT NULL DEFAULT 'stock',
                fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, date)
            );
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_price_cache_ticker_date
            ON price_history_cache(ticker, date);
            """
        )

        # Task 026: portfolio summaries (Claude weekly review)
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_text TEXT NOT NULL,
                generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                model TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                positions_covered TEXT NOT NULL
            );
            """
        )

        # Sprint 13.1: watchlist
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                asset_type TEXT NOT NULL DEFAULT 'stock',
                notes TEXT DEFAULT '',
                target_buy_price REAL,
                alert_below_price REAL,
                added_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_analysis_at TEXT,
                last_signal TEXT,
                last_confidence REAL,
                UNIQUE(ticker)
            );
            """
        )

        # Sprint 30: regime history snapshots
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS regime_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                regime TEXT NOT NULL,
                confidence REAL NOT NULL,
                vix REAL,
                yield_spread REAL,
                detected_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_regime_history_detected_at
            ON regime_history(detected_at);
            """
        )

        # Sprint 30: watchlist alert configs
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist_alert_configs (
                ticker TEXT PRIMARY KEY,
                alert_on_signal_change INTEGER NOT NULL DEFAULT 1,
                min_confidence REAL NOT NULL DEFAULT 60.0,
                alert_on_price_below REAL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )

        # Sprint 13.4: multi-portfolio support
        await _migrate_add_portfolios(conn)

        await conn.commit()

    return path
