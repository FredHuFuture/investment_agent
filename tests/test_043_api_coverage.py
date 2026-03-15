"""Tests for Task 043: API coverage for export, watchlist, thesis, scale/split, summary routes.

All tests use a temp SQLite DB and mock external dependencies (no network calls).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from api.app import create_app
from db.database import init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "test_043.db")
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

async def _add_position(client: httpx.AsyncClient, ticker: str = "AAPL", **overrides):
    """Seed a position into the DB via the API."""
    payload = {
        "ticker": ticker,
        "asset_type": "stock",
        "quantity": 10,
        "avg_cost": 150.0,
        "entry_date": "2024-01-01",
    }
    payload.update(overrides)
    resp = await client.post("/portfolio/positions", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ===========================================================================
# 1. Export routes (prefix: /api/export)
# ===========================================================================

@pytest.mark.asyncio
async def test_export_portfolio_csv(client: httpx.AsyncClient):
    resp = await client.get("/api/export/portfolio/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_export_trades_csv(client: httpx.AsyncClient):
    resp = await client.get("/api/export/trades/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_export_signals_csv(client: httpx.AsyncClient):
    resp = await client.get("/api/export/signals/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_export_alerts_csv(client: httpx.AsyncClient):
    resp = await client.get("/api/export/alerts/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


# ===========================================================================
# 2. Watchlist CRUD (prefix: /watchlist)
# ===========================================================================

@pytest.mark.asyncio
async def test_watchlist_add_and_list(client: httpx.AsyncClient):
    # Add
    resp = await client.post("/watchlist", json={"ticker": "MSFT"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ticker"] == "MSFT"

    # List
    resp = await client.get("/watchlist")
    assert resp.status_code == 200
    items = resp.json()["data"]
    tickers = [i["ticker"] for i in items]
    assert "MSFT" in tickers


@pytest.mark.asyncio
async def test_watchlist_update(client: httpx.AsyncClient):
    # Add first
    resp = await client.post("/watchlist", json={"ticker": "MSFT"})
    assert resp.status_code == 200

    # Update
    resp = await client.put("/watchlist/MSFT", json={
        "notes": "test note",
        "target_buy_price": 300,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["notes"] == "test note"
    assert data["target_buy_price"] == 300


@pytest.mark.asyncio
async def test_watchlist_remove(client: httpx.AsyncClient):
    # Add
    await client.post("/watchlist", json={"ticker": "MSFT"})

    # Remove
    resp = await client.delete("/watchlist/MSFT")
    assert resp.status_code == 200
    assert resp.json()["data"]["removed"] is True

    # Confirm gone
    resp = await client.get("/watchlist")
    items = resp.json()["data"]
    tickers = [i["ticker"] for i in items]
    assert "MSFT" not in tickers


@pytest.mark.asyncio
async def test_watchlist_remove_not_found(client: httpx.AsyncClient):
    resp = await client.delete("/watchlist/UNKNOWN")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_watchlist_add_duplicate(client: httpx.AsyncClient):
    resp = await client.post("/watchlist", json={"ticker": "MSFT"})
    assert resp.status_code == 200

    resp = await client.post("/watchlist", json={"ticker": "MSFT"})
    assert resp.status_code == 409


# ===========================================================================
# 3. Portfolio thesis (prefix: /portfolio)
# ===========================================================================

@pytest.mark.asyncio
async def test_get_thesis(client: httpx.AsyncClient):
    # Add position with thesis fields
    await _add_position(
        client,
        ticker="AAPL",
        thesis_text="Strong momentum play",
        target_price=200.0,
        stop_loss=130.0,
        expected_hold_days=90,
        expected_return_pct=0.33,
    )

    resp = await client.get("/portfolio/positions/AAPL/thesis")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ticker"] == "AAPL"
    assert data["thesis_text"] == "Strong momentum play"
    assert data["expected_target_price"] == 200.0
    assert data["expected_stop_loss"] == 130.0
    assert data["expected_hold_days"] == 90


@pytest.mark.asyncio
async def test_update_thesis(client: httpx.AsyncClient):
    await _add_position(client, ticker="AAPL")

    resp = await client.put("/portfolio/positions/AAPL/thesis", json={
        "thesis_text": "updated thesis",
        "target_price": 200,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["thesis_text"] == "updated thesis"
    assert data["expected_target_price"] == 200


@pytest.mark.asyncio
async def test_thesis_not_found(client: httpx.AsyncClient):
    resp = await client.get("/portfolio/positions/UNKNOWN/thesis")
    assert resp.status_code == 404


# ===========================================================================
# 4. Portfolio scale and split
# ===========================================================================

@pytest.mark.asyncio
async def test_scale_portfolio(client: httpx.AsyncClient):
    await _add_position(client, ticker="AAPL")
    await client.put("/portfolio/cash", json={"amount": 50000.0})

    resp = await client.post("/portfolio/scale", json={"multiplier": 2.0})
    assert resp.status_code == 200
    assert resp.json()["data"]["multiplier"] == 2.0


@pytest.mark.asyncio
async def test_apply_split(client: httpx.AsyncClient):
    await _add_position(client, ticker="AAPL")

    resp = await client.post("/portfolio/split", json={"ticker": "AAPL", "ratio": 2})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["applied"] is True
    assert data["ticker"] == "AAPL"
    assert data["ratio"] == 2


# ===========================================================================
# 5. Summary routes (prefix: /summary)
# ===========================================================================

@pytest.mark.asyncio
async def test_summary_latest_empty(client: httpx.AsyncClient):
    resp = await client.get("/summary/latest")
    # 404 when no summary exists
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_summary_generate(client: httpx.AsyncClient):
    import os
    from agents.summary_agent import SummaryResult

    mock_result = SummaryResult(
        summary_text="Portfolio is doing great.",
        model="claude-sonnet-4-20250514",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.001,
        positions_covered=["AAPL", "MSFT"],
    )

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-key"}), \
         patch(
             "api.routes.summary.SummaryAgent.build_context",
             new_callable=AsyncMock,
             return_value=None,
         ), patch(
             "api.routes.summary.SummaryAgent.generate_summary",
             new_callable=AsyncMock,
             return_value=mock_result,
         ):
        resp = await client.post("/summary/generate")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["summary_text"] == "Portfolio is doing great."
    assert data["model"] == "claude-sonnet-4-20250514"
    assert data["input_tokens"] == 100
    assert data["output_tokens"] == 50
    assert data["positions_covered"] == ["AAPL", "MSFT"]
