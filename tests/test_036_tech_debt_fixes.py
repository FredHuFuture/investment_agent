"""Tests for Sprint 13.3: Tech debt fixes.

1. SHORT position drift sign inversion in monitoring/checker.py
2. Stock split thesis price adjustment in portfolio/manager.py

All tests use a temp SQLite DB -- no network calls.
"""
from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from db.database import init_db
from monitoring.checker import check_position
from portfolio.manager import PortfolioManager
from portfolio.models import Position


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "test_tech_debt.db")
    await init_db(path)
    return path


# ---------------------------------------------------------------------------
# SHORT position drift sign inversion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_long_position_drift_normal():
    """LONG position: price increase -> positive unrealized PnL (no inversion)."""
    pos = Position(
        ticker="AAPL",
        asset_type="stock",
        quantity=100,       # positive = LONG
        avg_cost=100.0,
        current_price=120.0,
    )
    # Price went up 20%, no stop/target -> should NOT generate SIGNIFICANT_LOSS
    alerts = check_position(pos, current_price=120.0)
    # No SIGNIFICANT_LOSS alert since the position is profitable
    loss_alerts = [a for a in alerts if a.alert_type == "SIGNIFICANT_LOSS"]
    assert len(loss_alerts) == 0, "LONG position with price increase should not trigger SIGNIFICANT_LOSS"


@pytest.mark.asyncio
async def test_long_position_drift_loss():
    """LONG position: price decrease -> negative unrealized PnL (triggers loss alert)."""
    pos = Position(
        ticker="AAPL",
        asset_type="stock",
        quantity=100,       # positive = LONG
        avg_cost=100.0,
        current_price=80.0,
    )
    # Price dropped 20% -> should trigger SIGNIFICANT_LOSS (threshold is -15%)
    alerts = check_position(pos, current_price=80.0)
    loss_alerts = [a for a in alerts if a.alert_type == "SIGNIFICANT_LOSS"]
    assert len(loss_alerts) == 1, "LONG position with 20% price drop should trigger SIGNIFICANT_LOSS"


@pytest.mark.asyncio
async def test_short_position_drift_inverted():
    """SHORT position: price increase = loss, drift should be negative (inverted)."""
    pos = Position(
        ticker="TSLA",
        asset_type="stock",
        quantity=-50,       # negative = SHORT
        avg_cost=200.0,
        current_price=240.0,
    )
    # Price went up 20% -> for SHORT this is a 20% loss -> should trigger SIGNIFICANT_LOSS
    alerts = check_position(pos, current_price=240.0)
    loss_alerts = [a for a in alerts if a.alert_type == "SIGNIFICANT_LOSS"]
    assert len(loss_alerts) == 1, "SHORT position with price increase should trigger SIGNIFICANT_LOSS"


@pytest.mark.asyncio
async def test_short_position_price_drop_is_gain():
    """SHORT position: price decrease = gain, should NOT trigger SIGNIFICANT_LOSS."""
    pos = Position(
        ticker="TSLA",
        asset_type="stock",
        quantity=-50,       # negative = SHORT
        avg_cost=200.0,
        current_price=140.0,
    )
    # Price dropped 30% -> for SHORT this is a 30% gain (exceeds 25% threshold)
    alerts = check_position(pos, current_price=140.0)
    loss_alerts = [a for a in alerts if a.alert_type == "SIGNIFICANT_LOSS"]
    gain_alerts = [a for a in alerts if a.alert_type == "SIGNIFICANT_GAIN"]
    assert len(loss_alerts) == 0, "SHORT position with price drop should NOT trigger SIGNIFICANT_LOSS"
    assert len(gain_alerts) == 1, "SHORT position with 30% price drop should trigger SIGNIFICANT_GAIN"


# ---------------------------------------------------------------------------
# Stock split thesis price adjustment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_split_adjusts_thesis_prices(db_path: str):
    """Stock split should adjust target_price and stop_loss in positions_thesis."""
    mgr = PortfolioManager(db_path)
    await mgr.add_position(
        ticker="NVDA",
        asset_type="stock",
        quantity=10,
        avg_cost=200.0,
        entry_date="2026-01-10",
        target_price=400.0,
        stop_loss=160.0,
    )

    # Apply a 4:1 split
    result = await mgr.apply_split("NVDA", 4)
    assert result is True

    # Verify position was adjusted
    pos = await mgr.get_position("NVDA")
    assert pos is not None
    assert pos.quantity == pytest.approx(40)       # 10 * 4
    assert pos.avg_cost == pytest.approx(50.0)     # 200 / 4

    # Verify thesis prices were adjusted
    assert pos.target_price == pytest.approx(100.0)  # 400 / 4
    assert pos.stop_loss == pytest.approx(40.0)      # 160 / 4


@pytest.mark.asyncio
async def test_split_with_no_thesis_prices(db_path: str):
    """Stock split should handle positions with no thesis (target_price/stop_loss are None)."""
    mgr = PortfolioManager(db_path)
    await mgr.add_position(
        ticker="GOOG",
        asset_type="stock",
        quantity=5,
        avg_cost=100.0,
        entry_date="2026-02-01",
        # No thesis fields -> no positions_thesis row
    )

    # Apply a 2:1 split -- should NOT error even without thesis
    result = await mgr.apply_split("GOOG", 2)
    assert result is True

    pos = await mgr.get_position("GOOG")
    assert pos is not None
    assert pos.quantity == pytest.approx(10)    # 5 * 2
    assert pos.avg_cost == pytest.approx(50.0)  # 100 / 2
    # No thesis prices to adjust -- should remain None
    assert pos.target_price is None
    assert pos.stop_loss is None


@pytest.mark.asyncio
async def test_split_with_partial_thesis(db_path: str):
    """Stock split with thesis that has target_price but no stop_loss."""
    mgr = PortfolioManager(db_path)
    await mgr.add_position(
        ticker="AMZN",
        asset_type="stock",
        quantity=20,
        avg_cost=180.0,
        entry_date="2026-01-20",
        target_price=360.0,
        # stop_loss intentionally omitted
    )

    result = await mgr.apply_split("AMZN", 3)
    assert result is True

    pos = await mgr.get_position("AMZN")
    assert pos is not None
    assert pos.quantity == pytest.approx(60)       # 20 * 3
    assert pos.avg_cost == pytest.approx(60.0)     # 180 / 3
    assert pos.target_price == pytest.approx(120.0)  # 360 / 3
    # stop_loss was NULL -> dividing NULL by 3 in SQL yields NULL
    assert pos.stop_loss is None


@pytest.mark.asyncio
async def test_split_ratio_validation(db_path: str):
    """Split ratio must be a positive integer."""
    mgr = PortfolioManager(db_path)

    with pytest.raises(ValueError, match="positive integer"):
        await mgr.apply_split("AAPL", 0)

    with pytest.raises(ValueError, match="positive integer"):
        await mgr.apply_split("AAPL", -2)


@pytest.mark.asyncio
async def test_split_nonexistent_ticker(db_path: str):
    """Splitting a non-existent ticker should return False."""
    mgr = PortfolioManager(db_path)
    result = await mgr.apply_split("ZZZZ", 4)
    assert result is False
