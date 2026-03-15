"""Tests for Task 044: API coverage for profiles, signals, and daemon routes.

All tests use a temp SQLite DB and mock external dependencies (no network calls).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from agents.models import AgentOutput, Regime, Signal
from api.app import create_app
from db.database import init_db
from engine.aggregator import AggregatedSignal
from tracking.store import SignalStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "test_044.db")
    await init_db(path)
    return path


@pytest.fixture
async def client(db_path: str):
    app = create_app(db_path=db_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(ticker: str, signal: Signal = Signal.BUY, confidence: float = 75.0) -> AggregatedSignal:
    """Build a minimal AggregatedSignal for insertion."""
    return AggregatedSignal(
        ticker=ticker,
        asset_type="stock",
        final_signal=signal,
        final_confidence=confidence,
        regime=Regime.NEUTRAL,
        agent_signals=[
            AgentOutput(
                agent_name="TestAgent",
                ticker=ticker,
                signal=signal,
                confidence=confidence,
                reasoning="test reasoning",
            )
        ],
        reasoning="test reasoning",
        metrics={"raw_score": 0.5, "consensus_score": 0.6},
    )


# ===========================================================================
# 1. Profile routes (prefix: /portfolios)
# ===========================================================================

@pytest.mark.asyncio
async def test_list_profiles_empty(client: httpx.AsyncClient):
    resp = await client.get("/portfolios")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_create_profile(client: httpx.AsyncClient):
    resp = await client.post("/portfolios", json={
        "name": "Test Portfolio",
        "description": "desc",
        "initial_cash": 10000,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "Test Portfolio"


@pytest.mark.asyncio
async def test_get_profile(client: httpx.AsyncClient):
    # Create a profile first
    create_resp = await client.post("/portfolios", json={
        "name": "Get Me",
        "description": "for get test",
        "initial_cash": 5000,
    })
    assert create_resp.status_code == 200
    profile_id = create_resp.json()["data"]["id"]

    # Retrieve it
    resp = await client.get(f"/portfolios/{profile_id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == profile_id
    assert data["name"] == "Get Me"


@pytest.mark.asyncio
async def test_update_profile(client: httpx.AsyncClient):
    # Create
    create_resp = await client.post("/portfolios", json={
        "name": "Original",
        "description": "original desc",
        "initial_cash": 1000,
    })
    assert create_resp.status_code == 200
    profile_id = create_resp.json()["data"]["id"]

    # Update
    resp = await client.put(f"/portfolios/{profile_id}", json={"name": "Updated"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_profile(client: httpx.AsyncClient):
    # Create
    create_resp = await client.post("/portfolios", json={
        "name": "Delete Me",
        "description": "",
        "initial_cash": 0,
    })
    assert create_resp.status_code == 200
    profile_id = create_resp.json()["data"]["id"]

    # Delete
    resp = await client.delete(f"/portfolios/{profile_id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["deleted"] is True


@pytest.mark.asyncio
async def test_set_default_profile(client: httpx.AsyncClient):
    # Create
    create_resp = await client.post("/portfolios", json={
        "name": "Default Me",
        "description": "",
        "initial_cash": 0,
    })
    assert create_resp.status_code == 200
    profile_id = create_resp.json()["data"]["id"]

    # Set default
    resp = await client.post(f"/portfolios/{profile_id}/set-default")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["default_profile_id"] == profile_id


@pytest.mark.asyncio
async def test_get_profile_not_found(client: httpx.AsyncClient):
    resp = await client.get("/portfolios/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_profile_not_found(client: httpx.AsyncClient):
    resp = await client.delete("/portfolios/99999")
    assert resp.status_code == 404


# ===========================================================================
# 2. Signal routes (prefix: /signals)
# ===========================================================================

@pytest.mark.asyncio
async def test_signal_history_empty(client: httpx.AsyncClient):
    resp = await client.get("/signals/history")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_signal_history_after_insert(client: httpx.AsyncClient, db_path: str):
    store = SignalStore(db_path)
    await store.save_signal(_make_signal("AAPL"))

    resp = await client.get("/signals/history")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert data[0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_signal_history_filter_by_ticker(client: httpx.AsyncClient, db_path: str):
    store = SignalStore(db_path)
    await store.save_signal(_make_signal("AAPL"))
    await store.save_signal(_make_signal("MSFT"))

    resp = await client.get("/signals/history", params={"ticker": "AAPL"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert all(entry["ticker"] == "AAPL" for entry in data)


@pytest.mark.asyncio
async def test_signal_history_filter_by_signal(client: httpx.AsyncClient, db_path: str):
    store = SignalStore(db_path)
    await store.save_signal(_make_signal("AAPL", signal=Signal.BUY))
    await store.save_signal(_make_signal("MSFT", signal=Signal.SELL))

    resp = await client.get("/signals/history", params={"signal": "BUY"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert all(entry["final_signal"] == "BUY" for entry in data)


@pytest.mark.asyncio
async def test_signal_calibration(client: httpx.AsyncClient):
    resp = await client.get("/signals/calibration")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_signal_agents(client: httpx.AsyncClient):
    resp = await client.get("/signals/agents")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, (list, dict))


@pytest.mark.asyncio
async def test_signal_accuracy(client: httpx.AsyncClient):
    resp = await client.get("/signals/accuracy")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, dict)


# ===========================================================================
# 3. Daemon routes (prefix: /daemon)
# ===========================================================================

@pytest.mark.asyncio
async def test_daemon_run_once_daily(client: httpx.AsyncClient):
    with patch(
        "daemon.scheduler.run_daily_check",
        new_callable=AsyncMock,
        return_value={"checked": 0, "alerts": 0},
    ):
        resp = await client.post("/daemon/run-once", json={"job": "daily"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["checked"] == 0
    assert data["alerts"] == 0


@pytest.mark.asyncio
async def test_daemon_run_once_weekly(client: httpx.AsyncClient):
    with patch(
        "daemon.scheduler.run_weekly_revaluation",
        new_callable=AsyncMock,
        return_value={"analyzed": 0, "reversals": 0},
    ):
        resp = await client.post("/daemon/run-once", json={"job": "weekly"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["analyzed"] == 0
    assert data["reversals"] == 0


@pytest.mark.asyncio
async def test_daemon_run_once_invalid_job(client: httpx.AsyncClient):
    resp = await client.post("/daemon/run-once", json={"job": "invalid"})
    assert resp.status_code == 422
