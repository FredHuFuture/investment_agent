"""Tests for AN-02: GET /drift/log endpoint — shape, pagination, day filter."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from db.database import init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    asyncio.get_event_loop().run_until_complete(init_db(path))
    return path


@pytest.fixture
def client(db_path):
    app = create_app(db_path=db_path)
    return TestClient(app)


async def _insert_drift_row(
    db_path: str,
    agent_name: str = "TechnicalAgent",
    asset_type: str = "stock",
    days_ago: int = 1,
    triggered: bool = False,
    preliminary: bool = True,
    current_icir: float | None = None,
    delta_pct: float | None = None,
    weight_before: float | None = 0.4,
    weight_after: float | None = None,
    threshold_type: str = "none",
) -> None:
    """Insert a test drift_log row."""
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO drift_log (
                agent_name, asset_type, evaluated_at,
                current_icir, avg_icir_60d, delta_pct, threshold_type,
                triggered, preliminary_threshold, weight_before, weight_after
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_name, asset_type, ts,
                current_icir, None, delta_pct, threshold_type,
                1 if triggered else 0,
                1 if preliminary else 0,
                weight_before, weight_after,
            ),
        )
        await conn.commit()


# ---------------------------------------------------------------------------
# Smoke test — empty table
# ---------------------------------------------------------------------------

def test_drift_log_empty_returns_empty_list(client):
    """GET /drift/log on empty table returns {drifts: []}."""
    resp = client.get("/drift/log")
    assert resp.status_code == 200
    data = resp.json()
    assert "drifts" in data
    assert isinstance(data["drifts"], list)
    assert len(data["drifts"]) == 0


# ---------------------------------------------------------------------------
# Response shape test
# ---------------------------------------------------------------------------

def test_drift_log_shape(client, db_path):
    """Each drift entry has all 11 required fields with correct types."""
    asyncio.get_event_loop().run_until_complete(
        _insert_drift_row(
            db_path,
            agent_name="MacroAgent",
            asset_type="stock",
            days_ago=1,
            triggered=True,
            preliminary=False,
            current_icir=0.42,
            delta_pct=-25.0,
            weight_before=0.3,
            weight_after=0.21,
            threshold_type="drop_pct",
        )
    )

    resp = client.get("/drift/log?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["drifts"]) == 1

    entry = data["drifts"][0]
    # Required fields
    assert "id" in entry
    assert entry["agent_name"] == "MacroAgent"
    assert entry["asset_type"] == "stock"
    assert "evaluated_at" in entry
    assert entry["current_icir"] == pytest.approx(0.42, abs=1e-4)
    assert "avg_icir_60d" in entry
    assert entry["delta_pct"] == pytest.approx(-25.0, abs=1e-4)
    assert entry["threshold_type"] == "drop_pct"
    # triggered and preliminary_threshold must be Python booleans (not 0/1)
    assert entry["triggered"] is True
    assert entry["preliminary_threshold"] is False
    assert entry["weight_before"] == pytest.approx(0.3, abs=1e-4)
    assert entry["weight_after"] == pytest.approx(0.21, abs=1e-4)


# ---------------------------------------------------------------------------
# Day filter
# ---------------------------------------------------------------------------

def test_drift_log_day_filter(client, db_path):
    """days= parameter must exclude rows older than the window."""
    loop = asyncio.get_event_loop()
    # Recent row (1 day ago) — within 7d window
    loop.run_until_complete(
        _insert_drift_row(db_path, agent_name="TechnicalAgent", days_ago=1)
    )
    # Old row (30 days ago) — outside 7d window
    loop.run_until_complete(
        _insert_drift_row(db_path, agent_name="MacroAgent", days_ago=30)
    )

    resp = client.get("/drift/log?days=7")
    assert resp.status_code == 200
    data = resp.json()
    agents = [e["agent_name"] for e in data["drifts"]]
    assert "TechnicalAgent" in agents
    assert "MacroAgent" not in agents, "30-day-old row must be excluded by days=7 filter"


def test_drift_log_day_filter_wide_window(client, db_path):
    """Wide window (days=365) returns all rows."""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_insert_drift_row(db_path, agent_name="TechnicalAgent", days_ago=1))
    loop.run_until_complete(_insert_drift_row(db_path, agent_name="MacroAgent", days_ago=30))

    resp = client.get("/drift/log?days=365")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["drifts"]) >= 2


# ---------------------------------------------------------------------------
# Limit parameter
# ---------------------------------------------------------------------------

def test_drift_log_limit(client, db_path):
    """limit= parameter must cap the number of returned rows."""
    loop = asyncio.get_event_loop()
    for i in range(5):
        loop.run_until_complete(
            _insert_drift_row(db_path, agent_name=f"Agent{i}", days_ago=1)
        )

    resp = client.get("/drift/log?days=7&limit=3")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["drifts"]) <= 3


# ---------------------------------------------------------------------------
# Default parameters
# ---------------------------------------------------------------------------

def test_drift_log_default_params(client, db_path):
    """Default days=7, limit=200 applied when not specified."""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_insert_drift_row(db_path, days_ago=1))

    resp = client.get("/drift/log")
    assert resp.status_code == 200
    data = resp.json()
    assert "drifts" in data


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

def test_drift_log_invalid_days(client):
    """days=0 should be rejected (ge=1 constraint)."""
    resp = client.get("/drift/log?days=0")
    assert resp.status_code == 422


def test_drift_log_invalid_limit(client):
    """limit=0 should be rejected (ge=1 constraint)."""
    resp = client.get("/drift/log?limit=0")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Bool coercion
# ---------------------------------------------------------------------------

def test_drift_log_triggered_coerced_to_bool(client, db_path):
    """triggered and preliminary_threshold must be JSON booleans (not 0/1 integers)."""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        _insert_drift_row(
            db_path, triggered=True, preliminary=False, days_ago=1
        )
    )

    resp = client.get("/drift/log")
    data = resp.json()
    entry = data["drifts"][0]
    # FastAPI/JSON serializes Python bool as JSON true/false, not 0/1
    assert isinstance(entry["triggered"], bool), "triggered must be bool"
    assert isinstance(entry["preliminary_threshold"], bool), "preliminary_threshold must be bool"
    assert entry["triggered"] is True
    assert entry["preliminary_threshold"] is False
