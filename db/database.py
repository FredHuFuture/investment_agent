"""Database initialization for Investment Analysis Agent."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

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


async def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> Path:
    """Initialize SQLite database and required schema.

    The connection enforces WAL mode to support concurrent reads/writes.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(path) as conn:
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA synchronous=NORMAL;")
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
            CREATE INDEX IF NOT EXISTS idx_trade_executions_thesis_id
            ON trade_executions(thesis_id);
            """
        )

        await conn.commit()

    return path
