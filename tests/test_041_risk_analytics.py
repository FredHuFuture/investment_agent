"""Tests for Sprint 17-19 analytics endpoints: risk, correlations, benchmark.

All tests use a temp SQLite DB and mock external dependencies (no network calls).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pandas as pd
import pytest

from api.app import create_app
from db.database import init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "test_analytics.db")
    await init_db(path)
    return path


@pytest.fixture
async def client(db_path: str):
    app = create_app(db_path=db_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _seed_snapshots(db_path: str, days: int = 30, base_value: float = 100000.0):
    """Insert portfolio_snapshots rows for the last N days with slight variations."""
    import aiosqlite

    now = datetime.now(timezone.utc)
    async with aiosqlite.connect(db_path) as conn:
        for i in range(days):
            ts = (now - timedelta(days=days - 1 - i)).isoformat()
            # Simulate slight daily fluctuation: +/- 0.5% around base
            import math
            value = base_value + base_value * 0.005 * math.sin(i * 0.5)
            cash = 20000.0
            positions_json = json.dumps([{"ticker": "AAPL", "value": value - cash}])
            await conn.execute(
                """
                INSERT INTO portfolio_snapshots (timestamp, total_value, cash, positions_json, trigger_event)
                VALUES (?, ?, ?, ?, 'test_seed')
                """,
                (ts, value, cash, positions_json),
            )
        await conn.commit()


async def _seed_positions(db_path: str, tickers: list[str] | None = None):
    """Insert active_positions rows for testing."""
    import aiosqlite

    if tickers is None:
        tickers = ["AAPL", "MSFT", "GOOGL"]

    async with aiosqlite.connect(db_path) as conn:
        for ticker in tickers:
            await conn.execute(
                """
                INSERT INTO active_positions
                    (ticker, asset_type, quantity, avg_cost, entry_date, status)
                VALUES (?, 'stock', 10, 150.0, '2025-01-01', 'active')
                """,
                (ticker,),
            )
        await conn.commit()


def _mock_price_df(ticker: str, days: int = 90) -> pd.DataFrame:
    """Create a mock price DataFrame with Close column."""
    import numpy as np

    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    base_price = {"SPY": 450.0, "AAPL": 180.0, "MSFT": 350.0, "GOOGL": 140.0, "QQQ": 380.0}
    price = base_price.get(ticker, 100.0)
    # Generate slightly random-looking prices
    np.random.seed(hash(ticker) % 2**31)
    changes = np.random.normal(0, 0.01, len(dates))
    prices = price * (1 + np.cumsum(changes))
    return pd.DataFrame(
        {"Close": prices, "Open": prices * 0.999, "High": prices * 1.01, "Low": prices * 0.99, "Volume": 1000000},
        index=dates,
    )


# ---------------------------------------------------------------------------
# 1. GET /analytics/risk -- with snapshot data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_risk_with_data(client: httpx.AsyncClient, db_path: str):
    await _seed_snapshots(db_path, days=30)

    resp = await client.get("/analytics/risk?days=30")
    assert resp.status_code == 200

    body = resp.json()
    assert "data" in body
    assert "warnings" in body

    data = body["data"]
    # All expected risk fields should be present
    for key in (
        "daily_volatility",
        "annualized_volatility",
        "max_drawdown_pct",
        "current_drawdown_pct",
        "var_95",
        "cvar_95",
        "positive_days",
        "negative_days",
        "data_points",
    ):
        assert key in data, f"Missing key: {key}"

    # With 30 days of data, data_points should be 30
    assert data["data_points"] == 30
    # Volatility should be non-negative
    assert data["daily_volatility"] >= 0
    assert data["annualized_volatility"] >= 0


# ---------------------------------------------------------------------------
# 2. GET /analytics/risk -- with days parameter (default 90)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_risk_default_days(client: httpx.AsyncClient, db_path: str):
    # Seed 10 days of data; default is 90 days window -- should still work
    await _seed_snapshots(db_path, days=10)

    resp = await client.get("/analytics/risk")
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["data_points"] == 10


# ---------------------------------------------------------------------------
# 3. GET /analytics/risk -- empty portfolio (no snapshots)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_risk_empty_portfolio(client: httpx.AsyncClient):
    resp = await client.get("/analytics/risk")
    assert resp.status_code == 200

    data = resp.json()["data"]
    # Should return zeroed risk metrics
    assert data["data_points"] == 0
    assert data["daily_volatility"] == 0.0
    assert data["max_drawdown_pct"] == 0.0


# ---------------------------------------------------------------------------
# 4. GET /analytics/correlations -- with < 2 tickers (empty matrix + warning)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_correlations_less_than_two_tickers(client: httpx.AsyncClient, db_path: str):
    # Seed only 1 position
    await _seed_positions(db_path, tickers=["AAPL"])

    resp = await client.get("/analytics/correlations")
    assert resp.status_code == 200

    body = resp.json()
    data = body["data"]
    assert data["correlation_matrix"] == {}
    assert data["avg_correlation"] == 0.0
    assert data["high_correlation_pairs"] == []
    assert data["concentration_risk"] == "LOW"
    assert data["tickers"] == ["AAPL"]
    # Should have a warning about needing >= 2 positions
    assert any("at least 2" in w.lower() for w in data.get("warnings", []))


# ---------------------------------------------------------------------------
# 5. GET /analytics/correlations -- no positions at all
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_correlations_no_positions(client: httpx.AsyncClient):
    resp = await client.get("/analytics/correlations")
    assert resp.status_code == 200

    body = resp.json()
    data = body["data"]
    assert data["correlation_matrix"] == {}
    assert data["tickers"] == []


# ---------------------------------------------------------------------------
# 6. GET /analytics/correlations -- with positions (mocked provider)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_correlations_with_positions(client: httpx.AsyncClient, db_path: str):
    await _seed_positions(db_path, tickers=["AAPL", "MSFT"])

    mock_provider = AsyncMock()
    mock_provider.get_price_history = AsyncMock(side_effect=lambda ticker, **kw: _mock_price_df(ticker))

    with patch("data_providers.factory.get_provider", return_value=mock_provider):
        resp = await client.get("/analytics/correlations?lookback_days=60")

    assert resp.status_code == 200

    body = resp.json()
    data = body["data"]
    assert "correlation_matrix" in data
    assert "avg_correlation" in data
    assert "high_correlation_pairs" in data
    assert "concentration_risk" in data
    assert set(data["tickers"]) == {"AAPL", "MSFT"}


# ---------------------------------------------------------------------------
# 7. GET /analytics/benchmark -- default params (mocked provider)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_benchmark_default(client: httpx.AsyncClient, db_path: str):
    # Need snapshots so the portfolio value history exists
    await _seed_snapshots(db_path, days=30)

    mock_provider = AsyncMock()
    mock_provider.get_price_history = AsyncMock(return_value=_mock_price_df("SPY", days=90))

    with patch("data_providers.factory.get_provider", return_value=mock_provider):
        resp = await client.get("/analytics/benchmark")

    assert resp.status_code == 200

    body = resp.json()
    data = body["data"]
    assert "series" in data
    assert "benchmark_ticker" in data
    assert data["benchmark_ticker"] == "SPY"
    assert "portfolio_return_pct" in data
    assert "benchmark_return_pct" in data
    assert "alpha_pct" in data
    assert "data_points" in data


# ---------------------------------------------------------------------------
# 8. GET /analytics/benchmark -- custom benchmark ticker and days
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_benchmark_custom(client: httpx.AsyncClient, db_path: str):
    await _seed_snapshots(db_path, days=60)

    mock_provider = AsyncMock()
    mock_provider.get_price_history = AsyncMock(return_value=_mock_price_df("QQQ", days=120))

    with patch("data_providers.factory.get_provider", return_value=mock_provider):
        resp = await client.get("/analytics/benchmark?benchmark=QQQ&days=60")

    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["benchmark_ticker"] == "QQQ"


# ---------------------------------------------------------------------------
# 9. GET /analytics/benchmark -- empty portfolio (no snapshots)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_benchmark_empty_portfolio(client: httpx.AsyncClient):
    mock_provider = AsyncMock()
    mock_provider.get_price_history = AsyncMock(return_value=_mock_price_df("SPY"))

    with patch("data_providers.factory.get_provider", return_value=mock_provider):
        resp = await client.get("/analytics/benchmark")

    assert resp.status_code == 200

    data = resp.json()["data"]
    # Should return empty result gracefully
    assert data["data_points"] == 0
    assert data["series"] == []
    assert data["portfolio_return_pct"] == 0.0


# ---------------------------------------------------------------------------
# 10. GET /analytics/risk -- sharpe_ratio and sortino_ratio present
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_risk_includes_ratios(client: httpx.AsyncClient, db_path: str):
    await _seed_snapshots(db_path, days=30)

    resp = await client.get("/analytics/risk?days=30")
    assert resp.status_code == 200

    data = resp.json()["data"]
    # These fields should always be present (may be None if insufficient data)
    assert "sharpe_ratio" in data
    assert "sortino_ratio" in data
    assert "best_day_pct" in data
    assert "worst_day_pct" in data
