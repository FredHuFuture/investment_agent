# tests/test_decisions_manager_execute.py
from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from agents.models import Regime, Signal
from db.database import init_db
from decisions.manager import DecisionManager
from decisions.models import DecisionError, now_utc_iso
from engine.aggregator import AggregatedSignal
from execution.adapter import ExecutionAdapter, ExecutionReport, Order


# Inline test doubles — NOT placed under engine/ (test doubles stay in tests/).
class StubAdapter(ExecutionAdapter):
    def __init__(self, price: float) -> None:
        self._price = price

    async def submit(self, order: Order) -> ExecutionReport:
        return ExecutionReport(
            ticker=order.ticker, side=order.side.value, quantity=order.quantity,
            fill_price=self._price, status="FILLED", venue="PAPER",
            filled_at=now_utc_iso(),
        )


class FailingAdapter(ExecutionAdapter):
    async def submit(self, order: Order) -> ExecutionReport:
        raise RuntimeError("venue unreachable")


def _signal(sig: Signal = Signal.BUY) -> AggregatedSignal:
    return AggregatedSignal(
        ticker="AAPL", asset_type="stock", final_signal=sig, final_confidence=70.0,
        regime=Regime.RISK_ON, agent_signals=[], reasoning="because",
    )


@pytest.fixture
async def mgr(tmp_path: Path) -> DecisionManager:
    db_file = str(tmp_path / "decisions.db")
    await init_db(db_file)
    return DecisionManager(db_file)


async def test_execute_after_approve_fills(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal())
    await mgr.approve(pa.id, actor="alice")
    executed = await mgr.execute(pa.id, StubAdapter(price=199.0))
    assert executed.status == "executed"
    assert executed.execution_report_json is not None
    report = executed.to_dict()["execution_report"]
    assert report["status"] == "FILLED" and report["venue"] == "PAPER"
    assert report["fill_price"] == 199.0


async def test_execute_without_approve_is_refused(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal())
    with pytest.raises(DecisionError) as ei:
        await mgr.execute(pa.id, StubAdapter(price=199.0))
    assert ei.value.http_status == 409 and ei.value.code == "DECISION_NOT_APPROVED"
    refreshed = await mgr.get(pa.id)
    assert refreshed is not None and refreshed.status == "pending"


async def test_execute_hold_is_refused(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal(sig=Signal.HOLD))
    with pytest.raises(DecisionError) as ei:
        await mgr.execute(pa.id, StubAdapter(price=1.0))
    assert ei.value.http_status == 400 and ei.value.code == "HOLD_NOT_EXECUTABLE"


async def test_execute_expired_is_refused(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal())
    await mgr.approve(pa.id, actor="alice")
    async with aiosqlite.connect(mgr._db_path) as conn:  # type: ignore[attr-defined]
        await conn.execute(
            "UPDATE decisions SET valid_until=? WHERE id=?",
            ("2000-01-01T00:00:00+00:00", pa.id),
        )
        await conn.commit()
    with pytest.raises(DecisionError) as ei:
        await mgr.execute(pa.id, StubAdapter(price=199.0))
    assert ei.value.http_status == 409 and ei.value.code == "DECISION_EXPIRED"


async def test_execute_hash_mismatch_is_refused(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal())
    await mgr.approve(pa.id, actor="alice")
    # Simulate the proposal changing after approval -> binding is void.
    async with aiosqlite.connect(mgr._db_path) as conn:  # type: ignore[attr-defined]
        await conn.execute(
            "UPDATE decisions SET proposal_hash='DIFFERENT' WHERE id=?", (pa.id,)
        )
        await conn.commit()
    with pytest.raises(DecisionError) as ei:
        await mgr.execute(pa.id, StubAdapter(price=199.0))
    assert ei.value.http_status == 409 and ei.value.code == "PROPOSAL_HASH_MISMATCH"


async def test_double_execute_is_refused(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal())
    await mgr.approve(pa.id, actor="alice")
    await mgr.execute(pa.id, StubAdapter(price=199.0))
    with pytest.raises(DecisionError) as ei:
        await mgr.execute(pa.id, StubAdapter(price=199.0))
    assert ei.value.http_status == 409 and ei.value.code == "DECISION_ALREADY_EXECUTED"


async def test_adapter_failure_keeps_approved_and_writes_failed_audit(
    mgr: DecisionManager,
) -> None:
    pa = await mgr.create_proposal(_signal())
    await mgr.approve(pa.id, actor="alice")
    with pytest.raises(DecisionError) as ei:
        await mgr.execute(pa.id, FailingAdapter())
    assert ei.value.http_status == 500 and ei.value.code == "EXECUTION_FAILED"
    refreshed = await mgr.get(pa.id)
    assert refreshed is not None and refreshed.status == "approved"  # unchanged
    async with aiosqlite.connect(mgr._db_path) as conn:  # type: ignore[attr-defined]
        conn.row_factory = aiosqlite.Row
        rows = await (await conn.execute(
            "SELECT event_type FROM decision_audit WHERE decision_id=? ORDER BY id", (pa.id,)
        )).fetchall()
    assert [r["event_type"] for r in rows] == ["PROPOSED", "APPROVED", "FAILED"]
