"""Tests for UI-06 PositionStatus FSM (04-02 plan).

Tests validate:
- Valid transitions: open→closed (close), closed→open (re-entry)
- Invalid transitions: open→open, closed→closed raise ValueError
- Enum round-trip: PositionStatus("open") == PositionStatus.OPEN
- close_position uses FSM guard in manager
"""
from __future__ import annotations

import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_open_to_closed_allowed() -> None:
    """open → closed is a valid transition (normal close)."""
    from portfolio.models import validate_status_transition

    # Should not raise
    result = validate_status_transition("open", "closed")
    assert result is None


@pytest.mark.asyncio
async def test_closed_to_open_allowed() -> None:
    """closed → open is a valid transition (re-entry after close)."""
    from portfolio.models import validate_status_transition

    # Should not raise
    result = validate_status_transition("closed", "open")
    assert result is None


@pytest.mark.asyncio
async def test_closed_to_closed_raises() -> None:
    """closed → closed is an invalid no-op transition."""
    from portfolio.models import validate_status_transition

    with pytest.raises(ValueError, match="Invalid PositionStatus transition"):
        validate_status_transition("closed", "closed")


@pytest.mark.asyncio
async def test_open_to_open_raises() -> None:
    """open → open is an invalid no-op transition."""
    from portfolio.models import validate_status_transition

    with pytest.raises(ValueError, match="Invalid PositionStatus transition"):
        validate_status_transition("open", "open")


@pytest.mark.asyncio
async def test_enum_round_trip() -> None:
    """PositionStatus string values match existing DB strings for back-compat."""
    from portfolio.models import PositionStatus

    assert PositionStatus("open") == PositionStatus.OPEN
    assert PositionStatus.OPEN.value == "open"
    assert PositionStatus("closed") == PositionStatus.CLOSED
    assert PositionStatus.CLOSED.value == "closed"


@pytest.mark.asyncio
async def test_close_position_uses_guard(tmp_path) -> None:
    """close_position succeeds first time; raises on second close (no open position)."""
    from db.database import init_db
    from portfolio.manager import PortfolioManager

    db_file = tmp_path / "test.db"
    await init_db(db_file)

    mgr = PortfolioManager(str(db_file))
    await mgr.add_position(
        ticker="AAPL",
        asset_type="stock",
        quantity=10.0,
        avg_cost=150.0,
        entry_date="2024-01-01",
    )

    # First close: should work
    result = await mgr.close_position("AAPL", exit_price=170.0)
    assert result["ticker"] == "AAPL"

    # Second close: no open position exists
    with pytest.raises(ValueError, match="No open position found for ticker"):
        await mgr.close_position("AAPL", exit_price=180.0)


@pytest.mark.asyncio
async def test_valid_transitions_dict_completeness() -> None:
    """VALID_TRANSITIONS covers all PositionStatus members."""
    from portfolio.models import VALID_TRANSITIONS, PositionStatus

    for member in PositionStatus:
        assert member.value in VALID_TRANSITIONS, (
            f"PositionStatus.{member.name} ({member.value!r}) "
            f"has no entry in VALID_TRANSITIONS"
        )
