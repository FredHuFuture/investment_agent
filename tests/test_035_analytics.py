"""Tests for Sprint 13.2: Performance Analytics.

Tests the PortfolioAnalytics engine and the /analytics API endpoints.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite
import pytest
from httpx import ASGITransport, AsyncClient

from api.app import create_app
from db.database import init_db
from engine.analytics import PortfolioAnalytics
from portfolio.manager import PortfolioManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _setup_db(db_file: Path) -> str:
    """Initialize database and return path as string."""
    path = str(db_file)
    await init_db(path)
    return path


async def _insert_snapshots(db_path: str, count: int = 5) -> None:
    """Insert mock portfolio snapshots."""
    async with aiosqlite.connect(db_path) as conn:
        now = datetime.now(timezone.utc)
        for i in range(count):
            ts = (now - timedelta(days=count - 1 - i)).isoformat()
            total = 100_000 + i * 1000
            cash = 20_000 - i * 500
            await conn.execute(
                """
                INSERT INTO portfolio_snapshots
                    (timestamp, total_value, cash, positions_json, trigger_event)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ts, total, cash, json.dumps([]), "test"),
            )
        await conn.commit()


async def _insert_closed_positions(db_path: str) -> None:
    """Insert closed positions via PortfolioManager for realistic data."""
    mgr = PortfolioManager(db_path)

    # Winning trade: AAPL bought at $150, sold at $180 (20% gain)
    await mgr.add_position("AAPL", "stock", 100.0, 150.0, "2025-12-01")
    await mgr.close_position(
        "AAPL", exit_price=180.0, exit_reason="target_hit", exit_date="2026-01-15",
    )

    # Winning trade: MSFT bought at $400, sold at $440 (10% gain)
    await mgr.add_position("MSFT", "stock", 50.0, 400.0, "2026-01-01")
    await mgr.close_position(
        "MSFT", exit_price=440.0, exit_reason="target_hit", exit_date="2026-02-10",
    )

    # Losing trade: GOOG bought at $180, sold at $160 (-11.1% loss)
    await mgr.add_position("GOOG", "stock", 25.0, 180.0, "2026-01-05")
    await mgr.close_position(
        "GOOG", exit_price=160.0, exit_reason="stop_loss", exit_date="2026-02-20",
    )


async def _insert_all_winners(db_path: str) -> None:
    """Insert only winning closed positions."""
    mgr = PortfolioManager(db_path)
    await mgr.add_position("WIN1", "stock", 10.0, 100.0, "2025-11-01")
    await mgr.close_position(
        "WIN1", exit_price=120.0, exit_reason="target_hit", exit_date="2025-12-01",
    )
    await mgr.add_position("WIN2", "stock", 10.0, 200.0, "2025-11-15")
    await mgr.close_position(
        "WIN2", exit_price=250.0, exit_reason="target_hit", exit_date="2025-12-15",
    )


async def _insert_all_losers(db_path: str) -> None:
    """Insert only losing closed positions."""
    mgr = PortfolioManager(db_path)
    await mgr.add_position("LOSE1", "stock", 10.0, 100.0, "2025-11-01")
    await mgr.close_position(
        "LOSE1", exit_price=80.0, exit_reason="stop_loss", exit_date="2025-12-01",
    )
    await mgr.add_position("LOSE2", "stock", 10.0, 200.0, "2025-11-15")
    await mgr.close_position(
        "LOSE2", exit_price=150.0, exit_reason="stop_loss", exit_date="2025-12-15",
    )


# ---------------------------------------------------------------------------
# Test 1: Empty portfolio — no snapshots, no closed positions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_portfolio(tmp_path: Path) -> None:
    db_path = await _setup_db(tmp_path / "empty.db")
    analytics = PortfolioAnalytics(db_path)

    history = await analytics.get_value_history()
    assert history == []

    summary = await analytics.get_performance_summary()
    assert summary["total_trades"] == 0
    assert summary["win_rate"] == 0.0
    assert summary["best_trade"] is None
    assert summary["worst_trade"] is None

    monthly = await analytics.get_monthly_returns()
    assert monthly == []

    top = await analytics.get_top_performers()
    assert top["best"] == []
    assert top["worst"] == []


# ---------------------------------------------------------------------------
# Test 2: Value history with mock snapshots
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_value_history(tmp_path: Path) -> None:
    db_path = await _setup_db(tmp_path / "history.db")
    await _insert_snapshots(db_path, count=5)
    analytics = PortfolioAnalytics(db_path)

    history = await analytics.get_value_history(days=90)
    assert len(history) == 5
    # Should be ordered chronologically
    assert history[0]["total_value"] == 100_000
    assert history[-1]["total_value"] == 104_000
    # Check invested = total - cash
    for point in history:
        assert point["invested"] == point["total_value"] - point["cash"]
        assert "date" in point


# ---------------------------------------------------------------------------
# Test 3: Performance summary with mock closed positions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_performance_summary(tmp_path: Path) -> None:
    db_path = await _setup_db(tmp_path / "perf.db")
    await _insert_closed_positions(db_path)
    analytics = PortfolioAnalytics(db_path)

    summary = await analytics.get_performance_summary()
    assert summary["total_trades"] == 3
    assert summary["win_count"] == 2
    assert summary["loss_count"] == 1
    # Win rate: 2/3 = 66.67%
    assert abs(summary["win_rate"] - 66.67) < 0.1
    # Total realized P&L: (180-150)*100 + (440-400)*50 + (160-180)*25
    # = 3000 + 2000 + (-500) = 4500
    assert abs(summary["total_realized_pnl"] - 4500.0) < 0.01
    # Best trade should be AAPL (20%)
    assert summary["best_trade"]["ticker"] == "AAPL"
    assert abs(summary["best_trade"]["return_pct"] - 20.0) < 0.1
    # Worst trade should be GOOG (-11.1%)
    assert summary["worst_trade"]["ticker"] == "GOOG"
    assert summary["worst_trade"]["return_pct"] < 0
    # Avg hold days should be > 0
    assert summary["avg_hold_days"] > 0


# ---------------------------------------------------------------------------
# Test 4: Monthly returns grouping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monthly_returns(tmp_path: Path) -> None:
    db_path = await _setup_db(tmp_path / "monthly.db")
    await _insert_closed_positions(db_path)
    analytics = PortfolioAnalytics(db_path)

    monthly = await analytics.get_monthly_returns()
    assert len(monthly) >= 1
    # Check structure
    for entry in monthly:
        assert "month" in entry
        assert "pnl" in entry
        assert "trade_count" in entry
        assert entry["trade_count"] > 0

    # Jan 2026: AAPL closed (+3000), Feb 2026: MSFT (+2000) and GOOG (-500)
    months = {m["month"]: m for m in monthly}
    if "2026-01" in months:
        assert months["2026-01"]["trade_count"] == 1
        assert abs(months["2026-01"]["pnl"] - 3000.0) < 0.01
    if "2026-02" in months:
        assert months["2026-02"]["trade_count"] == 2
        assert abs(months["2026-02"]["pnl"] - 1500.0) < 0.01


# ---------------------------------------------------------------------------
# Test 5: Top performers ranking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_top_performers(tmp_path: Path) -> None:
    db_path = await _setup_db(tmp_path / "top.db")
    await _insert_closed_positions(db_path)
    analytics = PortfolioAnalytics(db_path)

    top = await analytics.get_top_performers(limit=5)
    assert len(top["best"]) == 3  # only 3 closed positions
    assert len(top["worst"]) == 3

    # Best should be ordered by return_pct descending
    assert top["best"][0]["ticker"] == "AAPL"  # 20%
    assert top["best"][1]["ticker"] == "MSFT"  # 10%
    assert top["best"][2]["ticker"] == "GOOG"  # -11.1%

    # Worst should be ordered by return_pct ascending
    assert top["worst"][0]["ticker"] == "GOOG"  # -11.1%
    assert top["worst"][1]["ticker"] == "MSFT"  # 10%
    assert top["worst"][2]["ticker"] == "AAPL"  # 20%

    # Each entry has expected keys
    for t in top["best"]:
        assert "ticker" in t
        assert "return_pct" in t
        assert "pnl" in t
        assert "entry_date" in t
        assert "exit_date" in t


# ---------------------------------------------------------------------------
# Test 6: Win rate — all wins
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_win_rate_all_wins(tmp_path: Path) -> None:
    db_path = await _setup_db(tmp_path / "allwins.db")
    await _insert_all_winners(db_path)
    analytics = PortfolioAnalytics(db_path)

    summary = await analytics.get_performance_summary()
    assert summary["win_rate"] == 100.0
    assert summary["win_count"] == 2
    assert summary["loss_count"] == 0
    assert summary["avg_loss_pct"] == 0.0
    assert summary["avg_win_pct"] > 0


# ---------------------------------------------------------------------------
# Test 7: Win rate — all losses
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_win_rate_all_losses(tmp_path: Path) -> None:
    db_path = await _setup_db(tmp_path / "alllosses.db")
    await _insert_all_losers(db_path)
    analytics = PortfolioAnalytics(db_path)

    summary = await analytics.get_performance_summary()
    assert summary["win_rate"] == 0.0
    assert summary["win_count"] == 0
    assert summary["loss_count"] == 2
    assert summary["avg_win_pct"] == 0.0
    assert summary["avg_loss_pct"] < 0
    assert summary["total_realized_pnl"] < 0


# ---------------------------------------------------------------------------
# Test 8: API endpoint — value-history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_value_history(tmp_path: Path) -> None:
    db_path = await _setup_db(tmp_path / "api_vh.db")
    await _insert_snapshots(db_path, count=3)
    app = create_app(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/analytics/value-history?days=90")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "warnings" in body
    assert len(body["data"]) == 3


# ---------------------------------------------------------------------------
# Test 9: API endpoint — performance summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_performance_summary(tmp_path: Path) -> None:
    db_path = await _setup_db(tmp_path / "api_perf.db")
    await _insert_closed_positions(db_path)
    app = create_app(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/analytics/performance")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["total_trades"] == 3
    assert body["data"]["win_count"] == 2


# ---------------------------------------------------------------------------
# Test 10: API endpoint — monthly returns
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_monthly_returns(tmp_path: Path) -> None:
    db_path = await _setup_db(tmp_path / "api_mr.db")
    await _insert_closed_positions(db_path)
    app = create_app(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/analytics/monthly-returns")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 1


# ---------------------------------------------------------------------------
# Test 11: API endpoint — top performers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_top_performers(tmp_path: Path) -> None:
    db_path = await _setup_db(tmp_path / "api_tp.db")
    await _insert_closed_positions(db_path)
    app = create_app(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/analytics/top-performers?limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert "best" in body["data"]
    assert "worst" in body["data"]
    assert len(body["data"]["best"]) <= 2
    assert len(body["data"]["worst"]) <= 2
