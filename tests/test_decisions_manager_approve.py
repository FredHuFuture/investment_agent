# tests/test_decisions_manager_approve.py
from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from agents.models import Regime, Signal
from db.database import init_db
from decisions.manager import DecisionManager
from decisions.models import DecisionError
from engine.aggregator import AggregatedSignal


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


async def test_approve_binds_hash_and_sets_status(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal())
    approved = await mgr.approve(pa.id, actor="alice")
    assert approved.status == "approved"
    assert approved.actor == "alice"
    assert approved.approved_proposal_hash == pa.proposal_hash
    assert approved.decided_at is not None


async def test_approve_missing_is_404(mgr: DecisionManager) -> None:
    with pytest.raises(DecisionError) as ei:
        await mgr.approve(999, actor="alice")
    assert ei.value.http_status == 404 and ei.value.code == "DECISION_NOT_FOUND"


async def test_approve_non_pending_is_409(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal())
    await mgr.approve(pa.id, actor="alice")
    with pytest.raises(DecisionError) as ei:
        await mgr.approve(pa.id, actor="bob")
    assert ei.value.http_status == 409 and ei.value.code == "DECISION_NOT_PENDING"


async def test_approve_stale_expires_and_refuses(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal())
    async with aiosqlite.connect(mgr._db_path) as conn:  # type: ignore[attr-defined]
        await conn.execute(
            "UPDATE decisions SET valid_until=? WHERE id=?",
            ("2000-01-01T00:00:00+00:00", pa.id),
        )
        await conn.commit()
    with pytest.raises(DecisionError) as ei:
        await mgr.approve(pa.id, actor="alice")
    assert ei.value.http_status == 409 and ei.value.code == "DECISION_EXPIRED"
    refreshed = await mgr.get(pa.id)
    assert refreshed is not None and refreshed.status == "expired"


async def test_reject_sets_status_and_note(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal())
    rejected = await mgr.reject(pa.id, actor="alice", note="thesis broke")
    assert rejected.status == "rejected"
    assert rejected.decision_note == "thesis broke"
    assert rejected.actor == "alice"


async def test_reject_non_pending_is_409(mgr: DecisionManager) -> None:
    pa = await mgr.create_proposal(_signal())
    await mgr.reject(pa.id, actor="alice", note="no")
    with pytest.raises(DecisionError) as ei:
        await mgr.reject(pa.id, actor="bob", note="again")
    assert ei.value.http_status == 409 and ei.value.code == "DECISION_NOT_PENDING"
