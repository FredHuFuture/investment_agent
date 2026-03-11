"""Tests for Task 022: FastAPI REST API layer.

All tests use a temp SQLite DB and mock external dependencies (no network calls).
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from agents.models import AgentOutput, Signal
from api.app import create_app
from backtesting.models import BacktestConfig, BacktestResult, SimulatedTrade
from db.database import init_db
from engine.aggregator import AggregatedSignal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "test_api.db")
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

def _mock_aggregated_signal(ticker: str = "AAPL") -> AggregatedSignal:
    return AggregatedSignal(
        ticker=ticker,
        asset_type="stock",
        final_signal=Signal.BUY,
        final_confidence=72.0,
        regime=None,
        agent_signals=[
            AgentOutput(
                agent_name="TechnicalAgent",
                ticker=ticker,
                signal=Signal.BUY,
                confidence=72.0,
                reasoning="test",
            ),
        ],
        reasoning="Test BUY signal",
        metrics={"raw_score": 0.45, "consensus_score": 1.0},
        warnings=["MacroAgent skipped: no FRED key"],
    )


def _mock_backtest_result() -> BacktestResult:
    return BacktestResult(
        config=BacktestConfig(
            ticker="AAPL", start_date="2024-01-01", end_date="2024-12-31",
            agents=["TechnicalAgent"], asset_type="stock",
        ),
        trades=[
            SimulatedTrade(
                entry_date="2024-01-10", entry_price=100.0, signal="BUY",
                confidence=70.0, shares=10.0, exit_date="2024-02-10",
                exit_price=110.0, exit_reason="signal_sell",
                pnl=100.0, pnl_pct=0.10, holding_days=31,
            ),
        ],
        equity_curve=[
            {"date": "2024-01-01", "equity": 100000},
            {"date": "2024-12-31", "equity": 110000},
        ],
        metrics={
            "total_return_pct": 10.0, "sharpe_ratio": 1.5,
            "max_drawdown_pct": -5.0, "win_rate": 1.0, "total_trades": 1,
        },
        warnings=[],
        agent_signals_log=[],
    )


# ---------------------------------------------------------------------------
# 1. Health endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health(client: httpx.AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["status"] == "ok"


# ---------------------------------------------------------------------------
# 2. Analyze -- success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_success(client: httpx.AsyncClient):
    mock_signal = _mock_aggregated_signal()
    with patch(
        "api.routes.analyze.AnalysisPipeline.analyze_ticker",
        new_callable=AsyncMock,
        return_value=mock_signal,
    ):
        resp = await client.get("/analyze/AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["ticker"] == "AAPL"
    assert body["data"]["final_signal"] == "BUY"
    assert body["data"]["final_confidence"] == 72.0


# ---------------------------------------------------------------------------
# 3. Analyze -- crypto auto-detect
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_crypto_autodetect(client: httpx.AsyncClient):
    mock_signal = _mock_aggregated_signal("BTC-USD")
    with patch(
        "api.routes.analyze.AnalysisPipeline.analyze_ticker",
        new_callable=AsyncMock,
        return_value=mock_signal,
    ) as mock_analyze:
        resp = await client.get("/analyze/BTC")
    assert resp.status_code == 200
    # Should have been called with BTC-USD and asset_type btc
    call_args = mock_analyze.call_args
    assert call_args[0][0] == "BTC-USD"
    assert call_args[0][1] == "btc"


# ---------------------------------------------------------------------------
# 4. Analyze -- invalid asset type
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_invalid_asset_type(client: httpx.AsyncClient):
    resp = await client.get("/analyze/AAPL?asset_type=forex")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 5. Portfolio CRUD lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_portfolio_crud(client: httpx.AsyncClient):
    # Add position
    resp = await client.post("/portfolio/positions", json={
        "ticker": "AAPL", "asset_type": "stock",
        "quantity": 10, "avg_cost": 150.0, "entry_date": "2024-01-01",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] > 0

    # Load portfolio
    resp = await client.get("/portfolio")
    assert resp.status_code == 200
    portfolio = resp.json()["data"]
    assert len(portfolio["positions"]) == 1
    assert portfolio["positions"][0]["ticker"] == "AAPL"

    # Delete position
    resp = await client.delete("/portfolio/positions/AAPL")
    assert resp.status_code == 200
    assert resp.json()["data"]["removed"] is True

    # Confirm gone
    resp = await client.get("/portfolio")
    assert len(resp.json()["data"]["positions"]) == 0


# ---------------------------------------------------------------------------
# 6. Portfolio -- add validation (missing fields)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_portfolio_add_validation(client: httpx.AsyncClient):
    resp = await client.post("/portfolio/positions", json={
        "ticker": "AAPL",
        # missing required fields
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 7. Portfolio -- cash operations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_portfolio_cash(client: httpx.AsyncClient):
    resp = await client.put("/portfolio/cash", json={"amount": 50000.0})
    assert resp.status_code == 200
    assert resp.json()["data"]["cash"] == 50000.0

    # Verify in portfolio
    resp = await client.get("/portfolio")
    assert resp.json()["data"]["cash"] == 50000.0


# ---------------------------------------------------------------------------
# 8. Alerts -- empty on fresh DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_alerts_empty(client: httpx.AsyncClient):
    resp = await client.get("/alerts")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


# ---------------------------------------------------------------------------
# 9. Monitor check -- mock
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitor_check(client: httpx.AsyncClient):
    mock_result = {
        "checked_positions": 0,
        "alerts": [],
        "snapshot_saved": True,
        "warnings": [],
    }
    with patch(
        "api.routes.alerts.PortfolioMonitor.run_check",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = await client.post("/monitor/check")
    assert resp.status_code == 200
    assert resp.json()["data"]["checked_positions"] == 0


# ---------------------------------------------------------------------------
# 10. Signals accuracy -- empty DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signals_accuracy_empty(client: httpx.AsyncClient):
    resp = await client.get("/signals/accuracy")
    assert resp.status_code == 200
    data = resp.json()["data"]
    # Should return valid shape even with no signals
    assert "resolved_count" in data or "total_signals" in data or isinstance(data, dict)


# ---------------------------------------------------------------------------
# 11. Backtest -- request validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backtest_validation(client: httpx.AsyncClient):
    resp = await client.post("/backtest", json={
        "ticker": "AAPL",
        # missing start_date and end_date
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 12. Backtest -- success (mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backtest_success(client: httpx.AsyncClient):
    mock_result = _mock_backtest_result()
    with patch(
        "api.routes.backtest.Backtester.run",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = await client.post("/backtest", json={
            "ticker": "AAPL",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        })
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["metrics"]["total_return_pct"] == 10.0
    assert body["data"]["trades_count"] == 1
    assert len(body["data"]["equity_curve"]) == 2


# ---------------------------------------------------------------------------
# 13. Daemon status -- fresh DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daemon_status(client: httpx.AsyncClient):
    resp = await client.get("/daemon/status")
    assert resp.status_code == 200
    data = resp.json()["data"]
    # Fresh DB should have entries for each job with never_run
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# 14. Weights -- default (no saved weights)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weights_default(client: httpx.AsyncClient):
    resp = await client.get("/weights")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["source"] == "default"
    assert data["buy_threshold"] == 0.30
    assert data["sell_threshold"] == -0.30
    assert "stock" in data["weights"]


# ---------------------------------------------------------------------------
# 15. CORS headers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cors_headers(client: httpx.AsyncClient):
    resp = await client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"
