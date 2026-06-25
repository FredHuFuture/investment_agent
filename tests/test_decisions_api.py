# tests/test_decisions_api.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from agents.models import Regime, Signal
from api.app import create_app
from db.database import init_db
from engine.aggregator import AggregatedSignal


def _signal(sig: Signal = Signal.BUY) -> AggregatedSignal:
    return AggregatedSignal(
        ticker="AAPL", asset_type="stock", final_signal=sig, final_confidence=72.0,
        regime=Regime.RISK_ON, agent_signals=[], reasoning="api test",
    )


@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "api.db")
    await init_db(path)
    return path


@pytest.fixture
async def client(db_path: str):
    app = create_app(db_path=db_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _patch_pipeline(sig: AggregatedSignal):
    # Patch the pipeline class used by the route so no network/analysis runs.
    mock_pipeline = AsyncMock()
    mock_pipeline.analyze_ticker = AsyncMock(return_value=sig)
    return patch("api.routes.decisions.AnalysisPipeline", return_value=mock_pipeline)


def _patch_paper_price(price: float = 188.0):
    # PaperExecutionAdapter built inside the route -> patch its price fetch.
    async def fake(ticker: str, asset_type: str) -> float:
        return price
    return patch("api.routes.decisions._build_adapter",
                 return_value=__import__("execution.paper", fromlist=["PaperExecutionAdapter"])
                 .PaperExecutionAdapter(price_fetch_fn=fake))


async def test_propose_creates_pending(client: httpx.AsyncClient) -> None:
    with _patch_pipeline(_signal()):
        r = await client.post("/decisions", json={"ticker": "AAPL"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "pending" and data["action"] == "BUY" and data["quantity"] == 1.0


async def test_gate_execute_before_approve_then_after(client: httpx.AsyncClient) -> None:
    with _patch_pipeline(_signal()):
        proposed = (await client.post("/decisions", json={"ticker": "AAPL"})).json()["data"]
    did = proposed["id"]

    # Before approve -> 409
    with _patch_paper_price():
        r1 = await client.post(f"/decisions/{did}/execute")
    assert r1.status_code == 409
    assert r1.json()["error"]["code"] == "DECISION_NOT_APPROVED"

    # Approve -> 200
    r2 = await client.post(f"/decisions/{did}/approve", json={"actor": "you"})
    assert r2.status_code == 200 and r2.json()["data"]["status"] == "approved"

    # After approve -> 200 filled
    with _patch_paper_price(188.0):
        r3 = await client.post(f"/decisions/{did}/execute")
    assert r3.status_code == 200
    assert r3.json()["data"]["status"] == "executed"
    assert r3.json()["data"]["execution_report"]["fill_price"] == 188.0


async def test_list_status_validation(client: httpx.AsyncClient) -> None:
    r = await client.get("/decisions", params={"status": "bogus"})
    assert r.status_code == 422  # FastAPI Literal validation


async def test_audit_and_verify(client: httpx.AsyncClient) -> None:
    with _patch_pipeline(_signal()):
        proposed = (await client.post("/decisions", json={"ticker": "AAPL"})).json()["data"]
    did = proposed["id"]
    await client.post(f"/decisions/{did}/approve", json={"actor": "you"})

    audit = await client.get(f"/decisions/{did}/audit")
    assert audit.status_code == 200
    events = [row["event_type"] for row in audit.json()["data"]]
    assert events == ["PROPOSED", "APPROVED"]

    verify = await client.get("/decisions/audit/verify")
    assert verify.status_code == 200 and verify.json()["data"]["valid"] is True


async def test_reject_then_404_on_missing(client: httpx.AsyncClient) -> None:
    with _patch_pipeline(_signal()):
        proposed = (await client.post("/decisions", json={"ticker": "AAPL"})).json()["data"]
    did = proposed["id"]
    r = await client.post(f"/decisions/{did}/reject", json={"actor": "you", "note": "no"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "rejected"

    missing = await client.get("/decisions/99999")
    assert missing.status_code == 404
