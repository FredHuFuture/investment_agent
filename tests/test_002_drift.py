from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite

from db.database import init_db
from engine.drift_analyzer import DriftAnalyzer


async def _prepare_thesis_with_scaled_buys(db_file: Path) -> int:
    await init_db(db_file)

    async with aiosqlite.connect(db_file) as conn:
        thesis_cursor = await conn.execute(
            """
            INSERT INTO positions_thesis (
                ticker,
                asset_type,
                expected_signal,
                expected_confidence,
                expected_entry_price,
                expected_target_price,
                expected_return_pct,
                expected_stop_loss,
                expected_hold_days
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("TEST", "stock", "BUY", 75.0, 100.0, 110.0, 0.10, 95.0, 30),
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
                (thesis_id, "BUY", 100.0, 102.0, "2026-03-10T10:00:00", "manual"),
                (thesis_id, "BUY", 100.0, 104.0, "2026-03-10T14:00:00", "manual"),
            ],
        )
        await conn.commit()

    return int(thesis_id)


def test_002_compute_position_drift_with_scaling_in(tmp_path: Path) -> None:
    db_file = tmp_path / "drift_002.db"
    thesis_id = asyncio.run(_prepare_thesis_with_scaled_buys(db_file))

    analyzer = DriftAnalyzer(db_file)
    result = asyncio.run(analyzer.compute_position_drift(thesis_id))

    assert result["position_status"] == "open"
    assert result["weighted_avg_entry_price"] == 103.0
    assert result["entry_drift_pct"] == 0.03
    assert result["actual_return_pct"] is None
    assert result["return_drift_pct"] is None


async def _prepare_thesis_without_execution(db_file: Path) -> int:
    await init_db(db_file)

    async with aiosqlite.connect(db_file) as conn:
        thesis_cursor = await conn.execute(
            """
            INSERT INTO positions_thesis (
                ticker,
                asset_type,
                expected_signal,
                expected_confidence,
                expected_entry_price,
                expected_target_price,
                expected_return_pct,
                expected_stop_loss,
                expected_hold_days
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("NOEXEC", "stock", "BUY", 60.0, 50.0, 55.0, 0.10, 46.0, 20),
        )
        await conn.commit()
        thesis_id = thesis_cursor.lastrowid
        assert thesis_id is not None
        return int(thesis_id)


def test_002_no_executions_returns_none_metrics(tmp_path: Path) -> None:
    db_file = tmp_path / "drift_002_no_exec.db"
    thesis_id = asyncio.run(_prepare_thesis_without_execution(db_file))

    analyzer = DriftAnalyzer(db_file)
    result = asyncio.run(analyzer.compute_position_drift(thesis_id))

    assert result["position_status"] == "no_executions"
    assert result["weighted_avg_entry_price"] is None
    assert result["entry_drift_pct"] is None
