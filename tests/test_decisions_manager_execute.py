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
        self.calls = 0

    async def submit(self, order: Order) -> ExecutionReport:
        self.calls += 1
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


async def test_execute_field_tamper_after_approve_is_refused(mgr: DecisionManager) -> None:
    # Tamper a BINDING FIELD (quantity) after approval WITHOUT updating
    # proposal_hash. The gate recomputes the hash from the row's current fields,
    # so the altered terms must not execute.
    pa = await mgr.create_proposal(_signal(), quantity=1.0)
    await mgr.approve(pa.id, actor="alice")
    async with aiosqlite.connect(mgr._db_path) as conn:  # type: ignore[attr-defined]
        await conn.execute(
            "UPDATE decisions SET quantity=999 WHERE id=?", (pa.id,)
        )
        await conn.commit()
    adapter = StubAdapter(price=199.0)
    with pytest.raises(DecisionError) as ei:
        await mgr.execute(pa.id, adapter)
    assert ei.value.http_status == 409 and ei.value.code == "PROPOSAL_HASH_MISMATCH"
    assert adapter.calls == 0  # no fill at the tampered size
    refreshed = await mgr.get(pa.id)
    assert refreshed is not None and refreshed.status == "approved"


async def test_execute_asset_type_tamper_after_approve_is_refused(
    mgr: DecisionManager,
) -> None:
    # asset_type is part of the hashed binding fields (it selects the venue /
    # price provider), so tampering it after approval must trip the gate.
    pa = await mgr.create_proposal(_signal())  # asset_type="stock"
    await mgr.approve(pa.id, actor="alice")
    async with aiosqlite.connect(mgr._db_path) as conn:  # type: ignore[attr-defined]
        await conn.execute(
            "UPDATE decisions SET asset_type='btc' WHERE id=?", (pa.id,)
        )
        await conn.commit()
    adapter = StubAdapter(price=199.0)
    with pytest.raises(DecisionError) as ei:
        await mgr.execute(pa.id, adapter)
    assert ei.value.http_status == 409 and ei.value.code == "PROPOSAL_HASH_MISMATCH"
    assert adapter.calls == 0  # no fill under the unapproved asset type
    refreshed = await mgr.get(pa.id)
    assert refreshed is not None and refreshed.status == "approved"


async def test_double_execute_is_refused(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal())
    await mgr.approve(pa.id, actor="alice")
    adapter = StubAdapter(price=199.0)
    await mgr.execute(pa.id, adapter)
    with pytest.raises(DecisionError) as ei:
        await mgr.execute(pa.id, adapter)
    assert ei.value.http_status == 409 and ei.value.code == "DECISION_ALREADY_EXECUTED"
    assert adapter.calls == 1  # the refused 2nd execute never reached submit


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


async def test_execute_records_failed_audit_if_persist_fails(
    mgr: DecisionManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    import decisions.manager as mgr_mod
    real_append = mgr_mod.append_audit

    async def selective_append(conn, *, decision_id, event_type, actor, payload, created_at):
        if event_type == "EXECUTED":
            raise RuntimeError("commit boom")
        return await real_append(
            conn, decision_id=decision_id, event_type=event_type,
            actor=actor, payload=payload, created_at=created_at,
        )

    monkeypatch.setattr(mgr_mod, "append_audit", selective_append)

    pa = await mgr.create_proposal(_signal())
    await mgr.approve(pa.id, actor="alice")
    with pytest.raises(DecisionError) as ei:
        await mgr.execute(pa.id, StubAdapter(price=199.0))
    assert ei.value.http_status == 500 and ei.value.code == "EXECUTION_RECORD_FAILED"
    refreshed = await mgr.get(pa.id)
    assert refreshed is not None and refreshed.status == "approved"  # NOT executed
    async with aiosqlite.connect(mgr._db_path) as conn:  # type: ignore[attr-defined]
        conn.row_factory = aiosqlite.Row
        rows = await (await conn.execute(
            "SELECT event_type FROM decision_audit WHERE decision_id=? ORDER BY id", (pa.id,)
        )).fetchall()
    assert [r["event_type"] for r in rows] == ["PROPOSED", "APPROVED", "FAILED"]
