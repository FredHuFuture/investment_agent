from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import aiosqlite

from db.database import init_db
from engine.drift_analyzer import DriftAnalyzer


async def _create_thesis_with_executions(
    db_file: Path,
    ticker: str,
    expected_entry_price: float,
    expected_return_pct: float | None,
    expected_hold_days: int | None,
    executions: list[tuple[str, float, float, str]],
) -> int:
    await init_db(db_file)

    async with aiosqlite.connect(db_file) as conn:
        cursor = await conn.execute(
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
            (
                ticker,
                "stock",
                "BUY",
                70.0,
                expected_entry_price,
                None,
                expected_return_pct,
                None,
                expected_hold_days,
            ),
        )
        thesis_id = cursor.lastrowid
        assert thesis_id is not None

        if executions:
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
                    (
                        thesis_id,
                        action,
                        quantity,
                        price,
                        executed_at,
                        "manual",
                    )
                    for action, quantity, price, executed_at in executions
                ],
            )
        await conn.commit()

    return int(thesis_id)


def test_hold_drift_closed_position(tmp_path: Path) -> None:
    async def _run() -> None:
        db_file = tmp_path / "hold_closed.db"
        thesis_id = await _create_thesis_with_executions(
            db_file,
            "TEST",
            100.0,
            0.1,
            30,
            [
                ("BUY", 10.0, 100.0, "2026-01-01T10:00:00"),
                ("SELL", 10.0, 110.0, "2026-01-20T15:00:00"),
            ],
        )
        analyzer = DriftAnalyzer(db_file)
        result = await analyzer.compute_position_drift(thesis_id)
        assert result["actual_hold_days"] == 19
        assert result["hold_drift_days"] == -11

    asyncio.run(_run())


def test_hold_drift_open_position(tmp_path: Path) -> None:
    async def _run() -> None:
        db_file = tmp_path / "hold_open.db"
        thesis_id = await _create_thesis_with_executions(
            db_file,
            "TEST",
            100.0,
            0.1,
            60,
            [("BUY", 10.0, 100.0, "2026-02-01T10:00:00")],
        )
        analyzer = DriftAnalyzer(db_file)
        result = await analyzer.compute_position_drift(thesis_id)
        assert result["position_status"] == "open"
        expected_days = (date.today() - date(2026, 2, 1)).days
        assert result["actual_hold_days"] == expected_days
        assert result["hold_drift_days"] == expected_days - 60

    asyncio.run(_run())


def test_hold_drift_no_expected(tmp_path: Path) -> None:
    async def _run() -> None:
        db_file = tmp_path / "hold_none.db"
        thesis_id = await _create_thesis_with_executions(
            db_file,
            "TEST",
            100.0,
            0.1,
            None,
            [
                ("BUY", 10.0, 100.0, "2026-01-01T10:00:00"),
                ("SELL", 10.0, 110.0, "2026-01-10T10:00:00"),
            ],
        )
        analyzer = DriftAnalyzer(db_file)
        result = await analyzer.compute_position_drift(thesis_id)
        assert result["actual_hold_days"] == 9
        assert result["hold_drift_days"] is None

    asyncio.run(_run())


def test_drift_summary_closed_only(tmp_path: Path) -> None:
    async def _run() -> None:
        db_file = tmp_path / "summary_closed.db"
        await _create_thesis_with_executions(
            db_file,
            "WIN",
            100.0,
            0.1,
            10,
            [
                ("BUY", 10.0, 100.0, "2026-01-01T10:00:00"),
                ("SELL", 10.0, 120.0, "2026-01-10T10:00:00"),
            ],
        )
        await _create_thesis_with_executions(
            db_file,
            "LOSS",
            100.0,
            0.1,
            10,
            [
                ("BUY", 10.0, 100.0, "2026-01-05T10:00:00"),
                ("SELL", 10.0, 90.0, "2026-01-12T10:00:00"),
            ],
        )
        await _create_thesis_with_executions(
            db_file,
            "OPEN",
            100.0,
            0.1,
            10,
            [("BUY", 10.0, 100.0, "2026-02-01T10:00:00")],
        )
        analyzer = DriftAnalyzer(db_file)
        summary = await analyzer.compute_drift_summary(include_open=False)
        assert summary["closed_count"] == 2
        assert summary["open_count"] == 1
        assert summary["win_rate"] == 0.5
        assert summary["avg_return_drift_pct"] is not None
        entry_drifts = [d for d in summary["individual_drifts"] if d["position_status"] == "open"]
        assert entry_drifts

    asyncio.run(_run())


def test_drift_summary_include_open(tmp_path: Path) -> None:
    async def _run() -> None:
        db_file = tmp_path / "summary_open.db"
        await _create_thesis_with_executions(
            db_file,
            "WIN",
            100.0,
            0.1,
            10,
            [
                ("BUY", 10.0, 100.0, "2026-01-01T10:00:00"),
                ("SELL", 10.0, 120.0, "2026-01-10T10:00:00"),
            ],
        )
        await _create_thesis_with_executions(
            db_file,
            "OPEN",
            100.0,
            0.1,
            10,
            [("BUY", 10.0, 110.0, "2026-02-01T10:00:00")],
        )
        analyzer = DriftAnalyzer(db_file)
        summary = await analyzer.compute_drift_summary(include_open=True)
        assert summary["open_count"] == 1
        assert summary["avg_entry_drift_pct"] is not None
        assert summary["avg_return_drift_pct"] is not None

    asyncio.run(_run())


def test_drift_summary_empty_db(tmp_path: Path) -> None:
    async def _run() -> None:
        db_file = tmp_path / "summary_empty.db"
        await init_db(db_file)
        analyzer = DriftAnalyzer(db_file)
        summary = await analyzer.compute_drift_summary()
        assert summary["total_theses"] == 0
        assert summary["individual_drifts"] == []
        assert summary["avg_entry_drift_pct"] is None
        assert summary["avg_return_drift_pct"] is None

    asyncio.run(_run())


def test_win_rate_all_winners(tmp_path: Path) -> None:
    async def _run() -> None:
        db_file = tmp_path / "summary_wins.db"
        for idx in range(3):
            await _create_thesis_with_executions(
                db_file,
                f"WIN{idx}",
                100.0,
                0.1,
                10,
                [
                    ("BUY", 10.0, 100.0, "2026-01-01T10:00:00"),
                    ("SELL", 10.0, 120.0, "2026-01-10T10:00:00"),
                ],
            )
        analyzer = DriftAnalyzer(db_file)
        summary = await analyzer.compute_drift_summary()
        assert summary["win_rate"] == 1.0

    asyncio.run(_run())


def test_drift_summary_lookback_limit(tmp_path: Path) -> None:
    async def _run() -> None:
        db_file = tmp_path / "summary_limit.db"
        for idx in range(5):
            await _create_thesis_with_executions(
                db_file,
                f"TEST{idx}",
                100.0,
                0.1,
                10,
                [
                    ("BUY", 10.0, 100.0, f"2026-01-0{idx+1}T10:00:00"),
                    ("SELL", 10.0, 110.0, f"2026-01-1{idx+1}T10:00:00"),
                ],
            )
        analyzer = DriftAnalyzer(db_file)
        summary = await analyzer.compute_drift_summary(lookback=3)
        assert summary["total_theses"] == 3
        assert len(summary["individual_drifts"]) == 3

    asyncio.run(_run())
