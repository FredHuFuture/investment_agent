"""Tests for Task 025: Thesis tracking closed-loop (backend).

All tests use a temp SQLite DB -- no network calls.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from api.app import create_app
from db.database import init_db
from portfolio.manager import PortfolioManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "test_thesis.db")
    await init_db(path)
    return path


@pytest.fixture
async def client(db_path: str):
    app = create_app(db_path=db_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# 1. test_add_position_with_thesis
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_position_with_thesis(db_path: str):
    """Adding a position with thesis fields populates both tables."""
    mgr = PortfolioManager(db_path)
    pos_id = await mgr.add_position(
        ticker="AAPL",
        asset_type="stock",
        quantity=100,
        avg_cost=186.0,
        entry_date="2026-01-15",
        sector="Technology",
        thesis_text="AI growth thesis, strong Q4 earnings",
        expected_return_pct=0.18,
        expected_hold_days=60,
        target_price=220.0,
        stop_loss=170.0,
    )
    assert pos_id > 0

    # Verify position has thesis link
    pos = await mgr.get_position("AAPL")
    assert pos is not None
    assert pos.original_analysis_id is not None
    assert pos.expected_return_pct == 0.18
    assert pos.expected_hold_days == 60
    assert pos.thesis_text == "AI growth thesis, strong Q4 earnings"
    assert pos.target_price == 220.0
    assert pos.stop_loss == 170.0

    # Verify thesis record exists
    thesis = await mgr.get_thesis("AAPL")
    assert thesis is not None
    assert thesis["expected_signal"] == "BUY"
    assert thesis["expected_confidence"] == 0.7
    assert thesis["expected_entry_price"] == 186.0
    assert thesis["expected_target_price"] == 220.0
    assert thesis["expected_return_pct"] == 0.18
    assert thesis["expected_stop_loss"] == 170.0
    assert thesis["expected_hold_days"] == 60
    assert thesis["thesis_text"] == "AI growth thesis, strong Q4 earnings"


# ---------------------------------------------------------------------------
# 2. test_add_position_without_thesis
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_position_without_thesis(db_path: str):
    """Adding a position without thesis fields works (backward compatible)."""
    mgr = PortfolioManager(db_path)
    pos_id = await mgr.add_position(
        ticker="MSFT",
        asset_type="stock",
        quantity=50,
        avg_cost=415.0,
        entry_date="2026-02-01",
        sector="Technology",
    )
    assert pos_id > 0

    pos = await mgr.get_position("MSFT")
    assert pos is not None
    assert pos.original_analysis_id is None
    assert pos.expected_return_pct is None
    assert pos.expected_hold_days is None
    assert pos.thesis_text is None
    assert pos.target_price is None
    assert pos.stop_loss is None

    thesis = await mgr.get_thesis("MSFT")
    assert thesis is None


# ---------------------------------------------------------------------------
# 3. test_get_thesis
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_thesis(db_path: str):
    """get_thesis returns thesis data with drift fields."""
    mgr = PortfolioManager(db_path)
    await mgr.add_position(
        ticker="NVDA",
        asset_type="stock",
        quantity=30,
        avg_cost=800.0,
        entry_date="2026-01-01",
        thesis_text="Data center growth",
        expected_return_pct=0.25,
        expected_hold_days=90,
        target_price=1000.0,
    )

    thesis = await mgr.get_thesis("NVDA")
    assert thesis is not None
    assert thesis["ticker"] == "NVDA"
    assert thesis["thesis_text"] == "Data center growth"
    assert thesis["expected_return_pct"] == 0.25
    assert thesis["expected_hold_days"] == 90
    assert thesis["expected_target_price"] == 1000.0
    assert thesis["hold_days_elapsed"] is not None
    assert thesis["hold_days_elapsed"] >= 0

    # No thesis for non-existent ticker
    assert await mgr.get_thesis("FAKE") is None


# ---------------------------------------------------------------------------
# 4. test_portfolio_includes_thesis_fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_portfolio_includes_thesis_fields(db_path: str):
    """load_portfolio returns thesis data on each position."""
    mgr = PortfolioManager(db_path)
    await mgr.add_position(
        ticker="AAPL",
        asset_type="stock",
        quantity=100,
        avg_cost=186.0,
        entry_date="2026-01-15",
        thesis_text="AI growth",
        expected_return_pct=0.18,
        expected_hold_days=60,
        target_price=220.0,
        stop_loss=170.0,
    )
    await mgr.add_position(
        ticker="MSFT",
        asset_type="stock",
        quantity=50,
        avg_cost=415.0,
        entry_date="2026-02-01",
    )

    portfolio = await mgr.load_portfolio()
    assert len(portfolio.positions) == 2

    aapl = next(p for p in portfolio.positions if p.ticker == "AAPL")
    assert aapl.thesis_text == "AI growth"
    assert aapl.target_price == 220.0
    assert aapl.stop_loss == 170.0

    msft = next(p for p in portfolio.positions if p.ticker == "MSFT")
    assert msft.thesis_text is None
    assert msft.target_price is None
    assert msft.stop_loss is None

    # Also verify to_dict includes thesis fields
    aapl_dict = aapl.to_dict()
    assert aapl_dict["thesis_text"] == "AI growth"
    assert aapl_dict["target_price"] == 220.0
    assert aapl_dict["stop_loss"] == 170.0


# ---------------------------------------------------------------------------
# 5. test_thesis_endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_thesis_endpoint(client: httpx.AsyncClient, db_path: str):
    """GET /positions/AAPL/thesis returns thesis data."""
    # Add position with thesis via API
    resp = await client.post(
        "/portfolio/positions",
        json={
            "ticker": "AAPL",
            "asset_type": "stock",
            "quantity": 100,
            "avg_cost": 186.0,
            "entry_date": "2026-01-15",
            "thesis_text": "AI growth thesis",
            "expected_return_pct": 0.18,
            "expected_hold_days": 60,
            "target_price": 220.0,
            "stop_loss": 170.0,
        },
    )
    assert resp.status_code == 200

    # Get thesis
    resp = await client.get("/portfolio/positions/AAPL/thesis")
    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert data["ticker"] == "AAPL"
    assert data["thesis_text"] == "AI growth thesis"
    assert data["expected_return_pct"] == 0.18
    assert data["expected_hold_days"] == 60
    assert data["expected_target_price"] == 220.0
    assert data["expected_stop_loss"] == 170.0
    assert data["hold_days_elapsed"] is not None

    # 404 for no thesis
    resp = await client.get("/portfolio/positions/FAKE/thesis")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. test_expected_return_computed_from_target
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expected_return_computed_from_target(db_path: str):
    """When only target_price is given, expected_return_pct is auto-computed."""
    mgr = PortfolioManager(db_path)
    await mgr.add_position(
        ticker="GOOG",
        asset_type="stock",
        quantity=20,
        avg_cost=150.0,
        entry_date="2026-03-01",
        target_price=180.0,
        # expected_return_pct NOT provided -- should be auto-computed
    )

    pos = await mgr.get_position("GOOG")
    assert pos is not None
    # (180 - 150) / 150 = 0.2
    assert pos.expected_return_pct is not None
    assert abs(pos.expected_return_pct - 0.2) < 1e-6

    thesis = await mgr.get_thesis("GOOG")
    assert thesis is not None
    assert abs(thesis["expected_return_pct"] - 0.2) < 1e-6


# ---------------------------------------------------------------------------
# 7. test_hold_days_drift
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hold_days_drift(db_path: str):
    """Thesis with expected_hold_days produces correct drift fields."""
    mgr = PortfolioManager(db_path)
    # Use a fixed past date so hold_days_elapsed is deterministic and positive
    await mgr.add_position(
        ticker="TSLA",
        asset_type="stock",
        quantity=10,
        avg_cost=250.0,
        entry_date="2025-01-01",
        expected_hold_days=60,
        thesis_text="EV growth",
    )

    thesis = await mgr.get_thesis("TSLA")
    assert thesis is not None
    assert thesis["expected_hold_days"] == 60
    assert thesis["hold_days_elapsed"] is not None
    # Entry date is 2025-01-01, current date is at least 2026-03-11,
    # so hold_days_elapsed should be > 60
    assert thesis["hold_days_elapsed"] > 60
    assert thesis["hold_drift_days"] is not None
    # hold_drift_days = hold_days_elapsed - expected_hold_days
    assert thesis["hold_drift_days"] == thesis["hold_days_elapsed"] - 60
    assert thesis["hold_drift_days"] > 0  # overdue


# ---------------------------------------------------------------------------
# 8. test_thesis_fields_optional
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_thesis_fields_optional(client: httpx.AsyncClient):
    """All thesis fields are optional in the API request."""
    # Add position with NO thesis fields
    resp = await client.post(
        "/portfolio/positions",
        json={
            "ticker": "AMZN",
            "asset_type": "stock",
            "quantity": 25,
            "avg_cost": 185.0,
            "entry_date": "2026-03-01",
        },
    )
    assert resp.status_code == 200

    # Add position with ONLY thesis_text (partial thesis)
    resp = await client.post(
        "/portfolio/positions",
        json={
            "ticker": "META",
            "asset_type": "stock",
            "quantity": 40,
            "avg_cost": 500.0,
            "entry_date": "2026-03-01",
            "thesis_text": "Metaverse bet",
        },
    )
    assert resp.status_code == 200

    # Verify AMZN has no thesis
    resp = await client.get("/portfolio/positions/AMZN/thesis")
    assert resp.status_code == 404

    # Verify META has thesis with only thesis_text filled
    resp = await client.get("/portfolio/positions/META/thesis")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["thesis_text"] == "Metaverse bet"
    assert data["expected_return_pct"] is None
    assert data["expected_hold_days"] is None
    assert data["expected_target_price"] is None
    assert data["expected_stop_loss"] is None


# ---------------------------------------------------------------------------
# 9. test_update_existing_thesis
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_existing_thesis(db_path: str):
    """update_thesis updates fields on an existing thesis row."""
    mgr = PortfolioManager(db_path)
    await mgr.add_position(
        ticker="AAPL",
        asset_type="stock",
        quantity=100,
        avg_cost=186.0,
        entry_date="2026-01-15",
        thesis_text="Original thesis",
        expected_return_pct=0.18,
        expected_hold_days=60,
        target_price=220.0,
        stop_loss=170.0,
    )

    result = await mgr.update_thesis(
        ticker="AAPL",
        thesis_text="Updated thesis text",
        target_price=240.0,
        stop_loss=175.0,
        expected_hold_days=90,
    )

    assert result["thesis_text"] == "Updated thesis text"
    assert result["expected_target_price"] == 240.0
    assert result["expected_stop_loss"] == 175.0
    assert result["expected_hold_days"] == 90
    # expected_return_pct auto-computed: (240 - 186) / 186
    assert result["expected_return_pct"] is not None
    assert abs(result["expected_return_pct"] - (240.0 - 186.0) / 186.0) < 1e-6

    # Verify the position itself was also synced
    pos = await mgr.get_position("AAPL")
    assert pos is not None
    assert pos.expected_hold_days == 90


# ---------------------------------------------------------------------------
# 10. test_create_thesis_on_position_without_one
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_thesis_on_position_without_one(db_path: str):
    """update_thesis creates a new thesis row when position had none."""
    mgr = PortfolioManager(db_path)
    await mgr.add_position(
        ticker="MSFT",
        asset_type="stock",
        quantity=50,
        avg_cost=415.0,
        entry_date="2026-02-01",
        sector="Technology",
    )

    # Confirm no thesis exists
    thesis_before = await mgr.get_thesis("MSFT")
    assert thesis_before is None

    result = await mgr.update_thesis(
        ticker="MSFT",
        thesis_text="Cloud dominance play",
        target_price=500.0,
        expected_hold_days=120,
    )

    assert result["ticker"] == "MSFT"
    assert result["thesis_text"] == "Cloud dominance play"
    assert result["expected_target_price"] == 500.0
    assert result["expected_hold_days"] == 120
    # expected_return_pct auto-computed: (500 - 415) / 415
    assert result["expected_return_pct"] is not None
    assert abs(result["expected_return_pct"] - (500.0 - 415.0) / 415.0) < 1e-6

    # Verify position is now linked
    pos = await mgr.get_position("MSFT")
    assert pos is not None
    assert pos.original_analysis_id is not None
    assert pos.thesis_text == "Cloud dominance play"


# ---------------------------------------------------------------------------
# 11. test_update_thesis_auto_computes_return_pct
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_thesis_auto_computes_return_pct(db_path: str):
    """When target_price is given without expected_return_pct, return_pct is auto-computed."""
    mgr = PortfolioManager(db_path)
    await mgr.add_position(
        ticker="GOOG",
        asset_type="stock",
        quantity=20,
        avg_cost=150.0,
        entry_date="2026-03-01",
        thesis_text="Search moat",
        expected_return_pct=0.10,
        target_price=165.0,
    )

    # Update with a new target_price but no explicit expected_return_pct
    result = await mgr.update_thesis(
        ticker="GOOG",
        target_price=195.0,
    )

    # Auto-computed: (195 - 150) / 150 = 0.3
    assert result["expected_return_pct"] is not None
    assert abs(result["expected_return_pct"] - 0.3) < 1e-6
    assert result["expected_target_price"] == 195.0
