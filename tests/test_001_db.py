from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiosqlite

from db.database import init_db


async def _run_db_flow(db_file: Path) -> None:
    await init_db(db_file)

    async with aiosqlite.connect(db_file) as conn:
        journal_mode_row = await (await conn.execute("PRAGMA journal_mode;")).fetchone()
        assert journal_mode_row is not None
        assert journal_mode_row[0].lower() == "wal"

        thesis_cursor = await conn.execute(
            """
            INSERT INTO positions_thesis (
                ticker,
                asset_type,
                expected_signal,
                expected_confidence,
                expected_entry_price,
                expected_target_price,
                expected_stop_loss,
                expected_hold_days
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("MSFT", "stock", "BUY", 78.5, 420.0, 460.0, 398.0, 45),
        )
        thesis_id = thesis_cursor.lastrowid
        assert thesis_id is not None

        await conn.executemany(
            """
            INSERT INTO trade_executions (
                thesis_id,
                action,
                quantity,
                executed_price,
                executed_at,
                reason
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (thesis_id, "BUY", 10.0, 422.0, "2026-03-09T10:00:00", "manual"),
                (thesis_id, "SELL", 4.0, 455.0, "2026-03-09T15:30:00", "target_hit"),
            ],
        )

        await conn.execute(
            """
            INSERT INTO portfolio_snapshots (
                timestamp,
                total_value,
                cash,
                positions_json,
                trigger_event
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "2026-03-09T16:00:00",
                250000.0,
                120000.0,
                json.dumps([{"ticker": "MSFT", "quantity": 6.0}]),
                "trade",
            ),
        )
        await conn.commit()

        thesis_row = await (
            await conn.execute(
                """
                SELECT ticker, asset_type, expected_signal, expected_confidence
                FROM positions_thesis
                WHERE id = ?
                """,
                (thesis_id,),
            )
        ).fetchone()
        assert thesis_row == ("MSFT", "stock", "BUY", 78.5)

        executions = await (
            await conn.execute(
                """
                SELECT action, quantity, executed_price, reason
                FROM trade_executions
                WHERE thesis_id = ?
                ORDER BY id
                """,
                (thesis_id,),
            )
        ).fetchall()
        assert len(executions) == 2
        assert executions[0] == ("BUY", 10.0, 422.0, "manual")
        assert executions[1] == ("SELL", 4.0, 455.0, "target_hit")


def test_001_db_schema_and_insert_flow(tmp_path: Path) -> None:
    db_file = tmp_path / "investment_agent.db"
    asyncio.run(_run_db_flow(db_file))
