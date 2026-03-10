"""Tests for Task 011: SignalStore — save, resolve, and query signal history."""
from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite
import pytest

from agents.models import Regime, Signal
from db.database import init_db
from engine.aggregator import AggregatedSignal, SignalAggregator
from tracking.store import SignalStore


def _make_aggregated_signal(
    ticker: str = "AAPL",
    asset_type: str = "stock",
    final_signal: Signal = Signal.BUY,
    final_confidence: float = 72.0,
    regime: Regime | None = Regime.RISK_ON,
    raw_score: float = 0.65,
    consensus_score: float = 1.0,
) -> AggregatedSignal:
    """Build a minimal AggregatedSignal for testing."""
    return AggregatedSignal(
        ticker=ticker,
        asset_type=asset_type,
        final_signal=final_signal,
        final_confidence=final_confidence,
        regime=regime,
        agent_signals=[],
        reasoning="Test reasoning",
        metrics={
            "raw_score": raw_score,
            "consensus_score": consensus_score,
            "buy_count": 2,
            "sell_count": 0,
            "hold_count": 1,
            "regime": regime.value if regime else None,
            "weights_used": {},
            "agent_contributions": {},
        },
        warnings=[],
    )


class TestSignalStore:
    # 1. Save signal and query by ticker
    @pytest.mark.asyncio
    async def test_save_and_query_signal(self, tmp_path: Path) -> None:
        db_path = tmp_path / "signals.db"
        await init_db(db_path)
        store = SignalStore(str(db_path))

        signal = _make_aggregated_signal(ticker="AAPL", final_signal=Signal.BUY, final_confidence=72.0)
        signal_id = await store.save_signal(signal)
        assert signal_id > 0

        rows = await store.get_signal_history(ticker="AAPL")
        assert len(rows) == 1
        row = rows[0]
        assert row["ticker"] == "AAPL"
        assert row["asset_type"] == "stock"
        assert row["final_signal"] == "BUY"
        assert row["final_confidence"] == pytest.approx(72.0)
        assert row["regime"] == "RISK_ON"
        assert row["raw_score"] == pytest.approx(0.65)
        assert row["consensus_score"] == pytest.approx(1.0)
        assert isinstance(row["agent_signals"], list)

    # 2. Resolve outcome manually
    @pytest.mark.asyncio
    async def test_resolve_outcome(self, tmp_path: Path) -> None:
        db_path = tmp_path / "resolve.db"
        await init_db(db_path)
        store = SignalStore(str(db_path))

        signal = _make_aggregated_signal(final_signal=Signal.BUY)
        signal_id = await store.save_signal(signal, thesis_id=None)

        await store.resolve_outcome(signal_id, "WIN", return_pct=0.08)

        rows = await store.get_signal_history()
        row = rows[0]
        assert row["outcome"] == "WIN"
        assert row["outcome_return_pct"] == pytest.approx(0.08)
        assert row["outcome_resolved_at"] is not None

    # 3. resolve_from_thesis — closed position → WIN
    @pytest.mark.asyncio
    async def test_resolve_from_thesis(self, tmp_path: Path) -> None:
        db_path = tmp_path / "resolve_thesis.db"
        await init_db(db_path)

        async with aiosqlite.connect(db_path) as conn:
            # Insert thesis
            cur = await conn.execute(
                """
                INSERT INTO positions_thesis (
                    ticker, asset_type, expected_signal, expected_confidence,
                    expected_entry_price
                ) VALUES (?, ?, ?, ?, ?)
                """,
                ("AAPL", "stock", "BUY", 72.0, 100.0),
            )
            thesis_id = int(cur.lastrowid)

            # Insert BUY and SELL executions
            await conn.executemany(
                """
                INSERT INTO trade_executions (thesis_id, action, quantity, executed_price, executed_at, reason)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (thesis_id, "BUY", 10.0, 100.0, "2026-01-01T10:00:00", "manual"),
                    (thesis_id, "SELL", 10.0, 110.0, "2026-02-01T10:00:00", "target_hit"),
                ],
            )
            await conn.commit()

        store = SignalStore(str(db_path))
        signal = _make_aggregated_signal(final_signal=Signal.BUY)
        await store.save_signal(signal, thesis_id=thesis_id)

        await store.resolve_from_thesis(thesis_id)

        rows = await store.get_signal_history()
        row = rows[0]
        assert row["outcome"] == "WIN"
        assert row["outcome_return_pct"] == pytest.approx(0.10, rel=1e-3)

    # 4. resolve_from_thesis — open position (no SELL)
    @pytest.mark.asyncio
    async def test_resolve_from_thesis_open_position(self, tmp_path: Path) -> None:
        db_path = tmp_path / "resolve_open.db"
        await init_db(db_path)

        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute(
                """
                INSERT INTO positions_thesis (
                    ticker, asset_type, expected_signal, expected_confidence,
                    expected_entry_price
                ) VALUES (?, ?, ?, ?, ?)
                """,
                ("AAPL", "stock", "BUY", 72.0, 100.0),
            )
            thesis_id = int(cur.lastrowid)
            await conn.execute(
                """
                INSERT INTO trade_executions (thesis_id, action, quantity, executed_price, executed_at, reason)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (thesis_id, "BUY", 10.0, 100.0, "2026-01-01T10:00:00", "manual"),
            )
            await conn.commit()

        store = SignalStore(str(db_path))
        signal = _make_aggregated_signal(final_signal=Signal.BUY)
        await store.save_signal(signal, thesis_id=thesis_id)

        await store.resolve_from_thesis(thesis_id)

        rows = await store.get_signal_history()
        row = rows[0]
        assert row["outcome"] == "OPEN"
        assert row["outcome_return_pct"] is None

    # 5. resolve_from_thesis — no executions → SKIPPED
    @pytest.mark.asyncio
    async def test_resolve_from_thesis_no_executions(self, tmp_path: Path) -> None:
        db_path = tmp_path / "resolve_skip.db"
        await init_db(db_path)

        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute(
                """
                INSERT INTO positions_thesis (
                    ticker, asset_type, expected_signal, expected_confidence,
                    expected_entry_price
                ) VALUES (?, ?, ?, ?, ?)
                """,
                ("AAPL", "stock", "BUY", 72.0, 100.0),
            )
            thesis_id = int(cur.lastrowid)
            await conn.commit()

        store = SignalStore(str(db_path))
        signal = _make_aggregated_signal(final_signal=Signal.BUY)
        await store.save_signal(signal, thesis_id=thesis_id)

        await store.resolve_from_thesis(thesis_id)

        rows = await store.get_signal_history()
        row = rows[0]
        assert row["outcome"] == "SKIPPED"
