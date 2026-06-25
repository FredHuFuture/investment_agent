# tests/test_decisions_manager_create.py
from __future__ import annotations

from pathlib import Path

import pytest

from agents.models import Regime, Signal
from db.database import init_db
from decisions.manager import DecisionManager
from decisions.models import is_past, now_utc_iso
from engine.aggregator import AggregatedSignal


def _signal(sig: Signal = Signal.BUY, ticker: str = "AAPL") -> AggregatedSignal:
    return AggregatedSignal(
        ticker=ticker, asset_type="stock", final_signal=sig, final_confidence=70.0,
        regime=Regime.RISK_ON, agent_signals=[], reasoning="because",
    )


@pytest.fixture
async def mgr(tmp_path: Path) -> DecisionManager:
    db_file = str(tmp_path / "decisions.db")
    await init_db(db_file)
    return DecisionManager(db_file)


async def test_create_buy_defaults_quantity_to_one(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal())
    assert pa.id is not None
    assert pa.action == "BUY"
    assert pa.quantity == 1.0
    assert pa.status == "pending"
    assert not is_past(pa.valid_until)  # 24h in the future


async def test_create_explicit_quantity(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal(), quantity=7.0)
    assert pa.quantity == 7.0


async def test_create_hold_stores_null_quantity(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal(sig=Signal.HOLD))
    assert pa.action == "HOLD"
    assert pa.quantity is None


async def test_create_writes_proposed_audit_row(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal())
    import aiosqlite
    async with aiosqlite.connect(mgr._db_path) as conn:  # type: ignore[attr-defined]
        conn.row_factory = aiosqlite.Row
        rows = await (await conn.execute(
            "SELECT event_type FROM decision_audit WHERE decision_id=?", (pa.id,)
        )).fetchall()
    assert [r["event_type"] for r in rows] == ["PROPOSED"]


async def test_create_is_atomic_no_orphan_on_audit_failure(
    mgr: DecisionManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(*args, **kwargs):
        raise RuntimeError("audit insert failed")

    monkeypatch.setattr("decisions.manager.append_audit", boom)
    with pytest.raises(RuntimeError):
        await mgr.create_proposal(_signal())

    import aiosqlite
    async with aiosqlite.connect(mgr._db_path) as conn:  # type: ignore[attr-defined]
        count = await (await conn.execute("SELECT COUNT(*) FROM decisions")).fetchone()
    assert count[0] == 0  # decision row rolled back with the failed audit


async def test_list_filters_by_status(mgr: DecisionManager) -> None:
    await mgr.create_proposal(_signal(ticker="AAPL"))
    await mgr.create_proposal(_signal(ticker="MSFT"))
    pending = await mgr.list(status="pending")
    assert {p.ticker for p in pending} == {"AAPL", "MSFT"}
    approved = await mgr.list(status="approved")
    assert approved == []


async def test_expire_stale_transitions_and_audits(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal())
    # Force it stale by rewriting valid_until into the past.
    import aiosqlite
    async with aiosqlite.connect(mgr._db_path) as conn:  # type: ignore[attr-defined]
        await conn.execute(
            "UPDATE decisions SET valid_until=? WHERE id=?",
            ("2000-01-01T00:00:00+00:00", pa.id),
        )
        await conn.commit()
    n = await mgr.expire_stale()
    assert n == 1
    refreshed = await mgr.get(pa.id)
    assert refreshed is not None and refreshed.status == "expired"
