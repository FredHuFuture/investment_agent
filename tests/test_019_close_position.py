"""Sprint 8: Investment Lifecycle Loop tests.

Tests for close_position(), get_closed_positions(), signal auto-resolution,
and the Position lifecycle fields.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite
import pytest

from db.database import init_db
from portfolio.manager import PortfolioManager
from portfolio.models import Position


async def _create_manager(db_file: Path) -> PortfolioManager:
    await init_db(db_file)
    return PortfolioManager(db_file)


# ---------------------------------------------------------------------------
# close_position basics
# ---------------------------------------------------------------------------

def test_close_position_records_pnl(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "close.db")
        await mgr.add_position("AAPL", "stock", 100.0, 150.0, "2026-01-01")
        result = await mgr.close_position("AAPL", exit_price=180.0)

        assert result["ticker"] == "AAPL"
        assert result["realized_pnl"] == pytest.approx(3000.0)  # (180-150)*100
        assert result["return_pct"] == pytest.approx(0.2)  # 20%
        assert result["exit_reason"] == "manual"

    asyncio.run(_run())


def test_close_position_with_reason_and_date(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "close2.db")
        await mgr.add_position("MSFT", "stock", 50.0, 400.0, "2026-01-15")
        result = await mgr.close_position(
            "MSFT",
            exit_price=450.0,
            exit_reason="target_hit",
            exit_date="2026-03-14",
        )

        assert result["exit_reason"] == "target_hit"
        assert result["exit_date"] == "2026-03-14"
        assert result["realized_pnl"] == pytest.approx(2500.0)

    asyncio.run(_run())


def test_close_position_with_loss(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "loss.db")
        await mgr.add_position("TSLA", "stock", 20.0, 300.0, "2026-02-01")
        result = await mgr.close_position("TSLA", exit_price=250.0, exit_reason="stop_loss")

        assert result["realized_pnl"] == pytest.approx(-1000.0)
        assert result["return_pct"] < 0

    asyncio.run(_run())


def test_close_nonexistent_position_raises(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "nopos.db")
        with pytest.raises(ValueError, match="No open position"):
            await mgr.close_position("FAKE", exit_price=100.0)

    asyncio.run(_run())


def test_close_already_closed_raises(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "double.db")
        await mgr.add_position("AAPL", "stock", 10.0, 150.0, "2026-01-01")
        await mgr.close_position("AAPL", exit_price=160.0)
        with pytest.raises(ValueError, match="No open position"):
            await mgr.close_position("AAPL", exit_price=170.0)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Closed positions do not appear in open queries
# ---------------------------------------------------------------------------

def test_closed_position_excluded_from_open(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "filter.db")
        await mgr.add_position("AAPL", "stock", 100.0, 150.0, "2026-01-01")
        await mgr.add_position("MSFT", "stock", 50.0, 400.0, "2026-01-01")
        await mgr.close_position("AAPL", exit_price=180.0)

        open_positions = await mgr.get_all_positions()
        assert len(open_positions) == 1
        assert open_positions[0].ticker == "MSFT"

        portfolio = await mgr.load_portfolio()
        assert len(portfolio.positions) == 1
        assert portfolio.positions[0].ticker == "MSFT"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# get_closed_positions
# ---------------------------------------------------------------------------

def test_get_closed_positions(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "history.db")
        await mgr.add_position("AAPL", "stock", 100.0, 150.0, "2026-01-01")
        await mgr.add_position("MSFT", "stock", 50.0, 400.0, "2026-01-15")
        await mgr.close_position("AAPL", exit_price=180.0, exit_date="2026-02-01")
        await mgr.close_position("MSFT", exit_price=380.0, exit_date="2026-03-01")

        closed = await mgr.get_closed_positions()
        assert len(closed) == 2
        # Ordered by exit_date DESC
        assert closed[0].ticker == "MSFT"
        assert closed[1].ticker == "AAPL"
        assert closed[0].status == "closed"
        assert closed[0].realized_pnl == pytest.approx(-1000.0)
        assert closed[1].realized_pnl == pytest.approx(3000.0)

    asyncio.run(_run())


def test_get_closed_positions_empty(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "empty.db")
        closed = await mgr.get_closed_positions()
        assert closed == []

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Position model lifecycle fields
# ---------------------------------------------------------------------------

def test_position_lifecycle_fields_in_dict(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "fields.db")
        await mgr.add_position("AAPL", "stock", 100.0, 150.0, "2026-01-01")

        pos = await mgr.get_position("AAPL")
        assert pos is not None
        assert pos.status == "open"
        assert pos.exit_price is None

        d = pos.to_dict()
        assert d["status"] == "open"
        assert d["exit_price"] is None
        assert d["realized_pnl"] is None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Signal auto-resolution on close
# ---------------------------------------------------------------------------

def test_signal_resolution_on_close(tmp_path: Path) -> None:
    """When a position is closed, linked OPEN signals should be resolved."""
    async def _run() -> None:
        db_file = tmp_path / "signals.db"
        mgr = await _create_manager(db_file)

        # Add position with thesis (creates thesis_id)
        await mgr.add_position(
            "AAPL", "stock", 100.0, 150.0, "2026-01-01",
            thesis_text="Strong buy thesis",
            target_price=200.0,
            expected_hold_days=90,
        )

        # Insert a signal referencing the thesis
        async with aiosqlite.connect(db_file) as conn:
            thesis_row = await (await conn.execute(
                "SELECT id FROM positions_thesis WHERE ticker = 'AAPL'"
            )).fetchone()
            thesis_id = thesis_row[0]

            await conn.execute(
                """
                INSERT INTO signal_history
                    (ticker, asset_type, final_signal, final_confidence,
                     raw_score, consensus_score, agent_signals_json,
                     reasoning, thesis_id, outcome)
                VALUES ('AAPL', 'stock', 'BUY', 0.75, 0.5, 0.45,
                        '[]', 'test', ?, 'OPEN')
                """,
                (thesis_id,),
            )
            await conn.commit()

        # Close position at a profit
        await mgr.close_position("AAPL", exit_price=180.0)

        # Check signal was resolved
        async with aiosqlite.connect(db_file) as conn:
            row = await (await conn.execute(
                "SELECT outcome, outcome_return_pct FROM signal_history WHERE ticker = 'AAPL'"
            )).fetchone()
            assert row[0] == "WIN"
            assert row[1] == pytest.approx(0.2)  # 20% return

    asyncio.run(_run())


def test_signal_resolution_loss(tmp_path: Path) -> None:
    """Closing at a loss should resolve signals as LOSS."""
    async def _run() -> None:
        db_file = tmp_path / "loss_signal.db"
        mgr = await _create_manager(db_file)

        await mgr.add_position(
            "TSLA", "stock", 10.0, 300.0, "2026-01-01",
            thesis_text="Speculative",
            stop_loss=250.0,
        )

        async with aiosqlite.connect(db_file) as conn:
            thesis_row = await (await conn.execute(
                "SELECT id FROM positions_thesis WHERE ticker = 'TSLA'"
            )).fetchone()
            thesis_id = thesis_row[0]

            await conn.execute(
                """
                INSERT INTO signal_history
                    (ticker, asset_type, final_signal, final_confidence,
                     raw_score, consensus_score, agent_signals_json,
                     reasoning, thesis_id, outcome)
                VALUES ('TSLA', 'stock', 'BUY', 0.6, 0.3, 0.3,
                        '[]', 'test', ?, 'OPEN')
                """,
                (thesis_id,),
            )
            await conn.commit()

        await mgr.close_position("TSLA", exit_price=240.0, exit_reason="stop_loss")

        async with aiosqlite.connect(db_file) as conn:
            row = await (await conn.execute(
                "SELECT outcome, outcome_return_pct FROM signal_history WHERE ticker = 'TSLA'"
            )).fetchone()
            assert row[0] == "LOSS"
            assert row[1] == pytest.approx(-0.2)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Trade execution recording
# ---------------------------------------------------------------------------

def test_trade_execution_recorded(tmp_path: Path) -> None:
    """Closing a position with a thesis should record a SELL trade."""
    async def _run() -> None:
        db_file = tmp_path / "trade.db"
        mgr = await _create_manager(db_file)

        await mgr.add_position(
            "GOOG", "stock", 25.0, 180.0, "2026-01-01",
            thesis_text="AI growth",
            target_price=220.0,
        )

        await mgr.close_position("GOOG", exit_price=210.0, exit_reason="target_hit")

        async with aiosqlite.connect(db_file) as conn:
            row = await (await conn.execute(
                "SELECT action, quantity, executed_price, reason FROM trade_executions"
            )).fetchone()
            assert row[0] == "SELL"
            assert float(row[1]) == 25.0
            assert float(row[2]) == 210.0
            assert row[3] == "target_hit"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Re-open position after closing (ticker UNIQUE constraint fix)
# ---------------------------------------------------------------------------

def test_reopen_position_after_close(tmp_path: Path) -> None:
    """After closing a position for ticker X, adding a new position for
    the same ticker X should succeed (no UNIQUE constraint violation)."""
    async def _run() -> None:
        db_file = tmp_path / "reopen.db"
        mgr = await _create_manager(db_file)

        # Open and close a position for AAPL
        await mgr.add_position("AAPL", "stock", 100.0, 150.0, "2026-01-01")
        await mgr.close_position("AAPL", exit_price=180.0, exit_date="2026-02-01")

        # Re-open a new position for the same ticker
        new_id = await mgr.add_position("AAPL", "stock", 50.0, 170.0, "2026-02-15")
        assert new_id is not None

        # The new position should be open and visible
        open_positions = await mgr.get_all_positions()
        assert len(open_positions) == 1
        assert open_positions[0].ticker == "AAPL"
        assert open_positions[0].quantity == 50.0
        assert open_positions[0].avg_cost == 170.0
        assert open_positions[0].status == "open"

        # The closed position should still exist in closed list
        closed = await mgr.get_closed_positions()
        assert len(closed) == 1
        assert closed[0].ticker == "AAPL"
        assert closed[0].status == "closed"
        assert closed[0].realized_pnl == pytest.approx(3000.0)

        # Attempting to add a *second* open position for the same ticker should fail
        with pytest.raises((ValueError, Exception)):
            await mgr.add_position("AAPL", "stock", 10.0, 175.0, "2026-03-01")

    asyncio.run(_run())
