"""Tests for UI-04 target_weight column and PATCH endpoint (04-02 plan).

Tests validate:
- target_weight column added idempotently via _ensure_column
- set_target_weight persists value; returns True for open position
- set_target_weight returns False for nonexistent ticker
- PATCH endpoint rejects out-of-range values (422)
- PATCH endpoint returns 404 for unknown ticker
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_column_exists_after_init_db(tmp_path) -> None:
    """target_weight column must exist on active_positions after init_db."""
    import aiosqlite
    from db.database import init_db

    db_file = tmp_path / "test.db"
    await init_db(db_file)

    async with aiosqlite.connect(str(db_file)) as conn:
        rows = await (
            await conn.execute("PRAGMA table_info(active_positions)")
        ).fetchall()
        col_names = {row[1] for row in rows}
        col_types = {row[1]: row[2] for row in rows}

    assert "target_weight" in col_names, "target_weight column missing from active_positions"
    assert col_types["target_weight"].upper() == "REAL"


@pytest.mark.asyncio
async def test_set_target_weight_open_position(tmp_path) -> None:
    """set_target_weight stores value; subsequent query returns it."""
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

    result = await mgr.set_target_weight("AAPL", 0.15)
    assert result is True

    # Verify the persisted value
    import aiosqlite
    async with aiosqlite.connect(str(db_file)) as conn:
        row = await (
            await conn.execute(
                "SELECT target_weight FROM active_positions WHERE ticker='AAPL'"
            )
        ).fetchone()
    assert row is not None
    assert abs(row[0] - 0.15) < 1e-9


@pytest.mark.asyncio
async def test_set_target_weight_clear_with_none(tmp_path) -> None:
    """set_target_weight(None) clears the field (NULL in DB)."""
    from db.database import init_db
    from portfolio.manager import PortfolioManager

    db_file = tmp_path / "test.db"
    await init_db(db_file)

    mgr = PortfolioManager(str(db_file))
    await mgr.add_position(
        ticker="TSLA",
        asset_type="stock",
        quantity=5.0,
        avg_cost=200.0,
        entry_date="2024-01-01",
    )

    await mgr.set_target_weight("TSLA", 0.20)
    result = await mgr.set_target_weight("TSLA", None)
    assert result is True

    import aiosqlite
    async with aiosqlite.connect(str(db_file)) as conn:
        row = await (
            await conn.execute(
                "SELECT target_weight FROM active_positions WHERE ticker='TSLA'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] is None


@pytest.mark.asyncio
async def test_set_target_weight_nonexistent_ticker_returns_false(tmp_path) -> None:
    """set_target_weight returns False when ticker has no open position."""
    from db.database import init_db
    from portfolio.manager import PortfolioManager

    db_file = tmp_path / "test.db"
    await init_db(db_file)

    mgr = PortfolioManager(str(db_file))
    result = await mgr.set_target_weight("NONEXISTENT", 0.10)
    assert result is False


@pytest.mark.asyncio
async def test_patch_endpoint_clamps_out_of_range(tmp_path) -> None:
    """PATCH /positions/{ticker}/target-weight with 1.5 returns 422 (Pydantic)."""
    from db.database import init_db
    from api.app import create_app

    db_file = tmp_path / "test.db"
    await init_db(db_file)

    app = create_app(str(db_file))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.patch(
            "/portfolio/positions/AAPL/target-weight",
            json={"target_weight": 1.5},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_endpoint_404_on_missing_ticker(tmp_path) -> None:
    """PATCH /positions/{ticker}/target-weight returns 404 for unknown ticker."""
    from db.database import init_db
    from api.app import create_app

    db_file = tmp_path / "test.db"
    await init_db(db_file)

    app = create_app(str(db_file))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.patch(
            "/portfolio/positions/UNKNOWN/target-weight",
            json={"target_weight": 0.10},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_endpoint_success(tmp_path) -> None:
    """PATCH /positions/{ticker}/target-weight persists and returns the value."""
    from db.database import init_db
    from api.app import create_app
    from portfolio.manager import PortfolioManager

    db_file = tmp_path / "test.db"
    await init_db(db_file)

    mgr = PortfolioManager(str(db_file))
    await mgr.add_position(
        ticker="MSFT",
        asset_type="stock",
        quantity=5.0,
        avg_cost=300.0,
        entry_date="2024-01-01",
    )

    app = create_app(str(db_file))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.patch(
            "/portfolio/positions/MSFT/target-weight",
            json={"target_weight": 0.25},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["ticker"] == "MSFT"
    assert abs(data["data"]["target_weight"] - 0.25) < 1e-9
