"""Tests for PortfolioAnalytics.get_daily_pnl_heatmap() and GET /analytics/daily-pnl.

Covers:
- Correct shape: one entry per calendar-day transition in portfolio_snapshots
- Empty result when <2 snapshots
- Last-of-day semantics: multiple snapshots on the same day → use the latest one
- API endpoint structure: {data: [{date, pnl}], warnings: []}

All tests use asyncio_mode=auto; no asyncio.run() wrappers.
"""
from __future__ import annotations

import json
from datetime import timezone
from pathlib import Path

import aiosqlite
import httpx
import pytest

from api.app import create_app
from db.database import init_db
from engine.analytics import PortfolioAnalytics


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "test_daily_pnl.db")
    await init_db(path)
    return path


@pytest.fixture
async def client(db_path: str) -> httpx.AsyncClient:
    app = create_app(db_path=db_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _insert_snapshot(
    conn: aiosqlite.Connection, ts: str, total_value: float
) -> None:
    await conn.execute(
        "INSERT INTO portfolio_snapshots "
        "(timestamp, total_value, cash, positions_json, trigger_event) "
        "VALUES (?, ?, ?, ?, 'test')",
        (ts, total_value, 0.0, "[]"),
    )


# ---------------------------------------------------------------------------
# 1. Three snapshots on 3 different days: [100, 105, 110] → 2 P&L entries
# ---------------------------------------------------------------------------


async def test_daily_pnl_shape(tmp_path: Path) -> None:
    """Three consecutive daily snapshots yield 2 P&L entries with correct values."""
    db_path = str(tmp_path / "shape.db")
    await init_db(db_path)

    async with aiosqlite.connect(db_path) as conn:
        await _insert_snapshot(conn, "2026-04-18T12:00:00", 100.0)
        await _insert_snapshot(conn, "2026-04-19T12:00:00", 105.0)
        await _insert_snapshot(conn, "2026-04-20T12:00:00", 110.0)
        await conn.commit()

    analytics = PortfolioAnalytics(db_path)
    result = await analytics.get_daily_pnl_heatmap(days=30)

    assert len(result) == 2, f"Expected 2 entries, got {len(result)}: {result}"

    # First entry: day 2 - day 1 = 105 - 100 = 5
    assert result[0]["date"] == "2026-04-19"
    assert result[0]["pnl"] == pytest.approx(5.0, abs=1e-4)

    # Second entry: day 3 - day 2 = 110 - 105 = 5
    assert result[1]["date"] == "2026-04-20"
    assert result[1]["pnl"] == pytest.approx(5.0, abs=1e-4)

    # Both entries have correct keys
    for entry in result:
        assert "date" in entry
        assert "pnl" in entry
        assert isinstance(entry["date"], str)
        assert len(entry["date"]) == 10  # YYYY-MM-DD
        assert isinstance(entry["pnl"], float)


# ---------------------------------------------------------------------------
# 2. Single snapshot → empty list (needs ≥2 to compute diff)
# ---------------------------------------------------------------------------


async def test_daily_pnl_empty_when_single_snapshot(tmp_path: Path) -> None:
    """One snapshot yields empty list — can't compute day-over-day diff."""
    db_path = str(tmp_path / "single.db")
    await init_db(db_path)

    async with aiosqlite.connect(db_path) as conn:
        await _insert_snapshot(conn, "2026-04-20T12:00:00", 100.0)
        await conn.commit()

    analytics = PortfolioAnalytics(db_path)
    result = await analytics.get_daily_pnl_heatmap(days=30)

    assert result == []


# ---------------------------------------------------------------------------
# 3. No snapshots → empty list
# ---------------------------------------------------------------------------


async def test_daily_pnl_empty_when_no_snapshots(tmp_path: Path) -> None:
    db_path = str(tmp_path / "empty.db")
    await init_db(db_path)

    analytics = PortfolioAnalytics(db_path)
    result = await analytics.get_daily_pnl_heatmap(days=30)

    assert result == []


# ---------------------------------------------------------------------------
# 4. Multiple snapshots on the same day → last snapshot of day wins
# ---------------------------------------------------------------------------


async def test_daily_pnl_uses_last_of_day(tmp_path: Path) -> None:
    """Two snapshots on the same calendar day: last one (17:00) is used for that day.

    Setup:
      2026-04-20T09:00 → 100
      2026-04-20T17:00 → 103   ← LAST of 2026-04-20
      2026-04-21T12:00 → 108

    Expected P&L for 2026-04-21: 108 - 103 = 5 (not 108 - 100 = 8)
    """
    db_path = str(tmp_path / "last_of_day.db")
    await init_db(db_path)

    async with aiosqlite.connect(db_path) as conn:
        await _insert_snapshot(conn, "2026-04-20T09:00:00", 100.0)
        await _insert_snapshot(conn, "2026-04-20T17:00:00", 103.0)
        await _insert_snapshot(conn, "2026-04-21T12:00:00", 108.0)
        await conn.commit()

    analytics = PortfolioAnalytics(db_path)
    result = await analytics.get_daily_pnl_heatmap(days=30)

    # Only one calendar-day transition: 2026-04-20 → 2026-04-21
    assert len(result) == 1
    assert result[0]["date"] == "2026-04-21"
    assert result[0]["pnl"] == pytest.approx(5.0, abs=1e-4), (
        f"Expected 108 - 103 = 5 (last-of-day semantics), got {result[0]['pnl']}"
    )


# ---------------------------------------------------------------------------
# 5. Negative P&L day is returned correctly
# ---------------------------------------------------------------------------


async def test_daily_pnl_negative_day(tmp_path: Path) -> None:
    db_path = str(tmp_path / "negative.db")
    await init_db(db_path)

    async with aiosqlite.connect(db_path) as conn:
        await _insert_snapshot(conn, "2026-04-19T12:00:00", 110.0)
        await _insert_snapshot(conn, "2026-04-20T12:00:00", 100.0)
        await conn.commit()

    analytics = PortfolioAnalytics(db_path)
    result = await analytics.get_daily_pnl_heatmap(days=30)

    assert len(result) == 1
    assert result[0]["pnl"] == pytest.approx(-10.0, abs=1e-4)


# ---------------------------------------------------------------------------
# 6. API endpoint GET /analytics/daily-pnl returns correct JSON structure
# ---------------------------------------------------------------------------


async def test_api_daily_pnl_structure_empty(client: httpx.AsyncClient) -> None:
    """Empty DB returns correct envelope structure with empty data list."""
    resp = await client.get("/analytics/daily-pnl")
    assert resp.status_code == 200

    body = resp.json()
    assert "data" in body
    assert "warnings" in body
    assert isinstance(body["data"], list)
    assert body["data"] == []


async def test_api_daily_pnl_structure_with_data(
    client: httpx.AsyncClient, db_path: str
) -> None:
    """With seeded snapshots, API returns populated data list."""
    async with aiosqlite.connect(db_path) as conn:
        await _insert_snapshot(conn, "2026-04-18T12:00:00", 100.0)
        await _insert_snapshot(conn, "2026-04-19T12:00:00", 110.0)
        await conn.commit()

    resp = await client.get("/analytics/daily-pnl?days=30")
    assert resp.status_code == 200

    body = resp.json()
    assert "data" in body
    assert "warnings" in body
    data = body["data"]
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["date"] == "2026-04-19"
    assert data[0]["pnl"] == pytest.approx(10.0, abs=1e-4)


# ---------------------------------------------------------------------------
# 7. API endpoint GET /analytics/returns returns correct structure
# ---------------------------------------------------------------------------


async def test_api_returns_structure_empty(client: httpx.AsyncClient) -> None:
    """Empty DB: /analytics/returns returns envelope with aggregate and positions."""
    resp = await client.get("/analytics/returns")
    assert resp.status_code == 200

    body = resp.json()
    assert "data" in body
    assert "warnings" in body
    data = body["data"]
    assert "aggregate" in data
    assert "positions" in data
    agg = data["aggregate"]
    assert "ttwror" in agg
    assert "irr" in agg
    assert "snapshot_count" in agg
    assert agg["ttwror"] is None  # no snapshots
    assert agg["snapshot_count"] == 0
