"""SIG-06 portfolio VaR historical-simulation tests.

Tests:
  A  test_risk_endpoint_returns_cvar_95_and_99
  B  test_risk_endpoint_returns_portfolio_var
  C  test_portfolio_var_equals_var_95_for_portfolio_returns
  D  test_risk_endpoint_http_via_fastapi_testclient
  E  test_risk_endpoint_insufficient_data_returns_nulls
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

from db.database import init_db
from engine.analytics import PortfolioAnalytics


# ---------------------------------------------------------------------------
# Helper: seed portfolio_snapshots from a return series (async)
# (duplicated inline from test_signal_quality_01_cvar.py per plan spec)
# ---------------------------------------------------------------------------

async def _seed_snapshots_from_returns(
    db_file: Path,
    returns: list[float],
    start_value: float = 100.0,
) -> list[float]:
    """Insert portfolio_snapshots rows computed from a return series.

    Computes portfolio values: v[0]=start_value, v[i]=v[i-1]*(1+returns[i-1]).
    Rows inserted oldest-first so analytics ORDER BY timestamp ASC is correct.

    Returns the list of values inserted.
    """
    values: list[float] = [start_value]
    for r in returns:
        values.append(values[-1] * (1.0 + r))

    now = datetime.now(timezone.utc)
    async with aiosqlite.connect(db_file) as conn:
        for i, value in enumerate(values):
            ts = (now - timedelta(days=len(values) - 1 - i)).isoformat()
            await conn.execute(
                """
                INSERT INTO portfolio_snapshots
                    (timestamp, total_value, cash, positions_json, trigger_event)
                VALUES (?, ?, ?, ?, 'test_seed')
                """,
                (ts, value, 0.0, "[]"),
            )
        await conn.commit()
    return values


# ---------------------------------------------------------------------------
# Test A: risk endpoint returns cvar_95 and cvar_99 as non-null floats
# ---------------------------------------------------------------------------

async def test_risk_endpoint_returns_cvar_95_and_99(tmp_path: Path) -> None:
    """get_portfolio_risk returns non-null cvar_95 and cvar_99 when >= 10 snapshots."""
    db_file = tmp_path / "cvar_both.db"
    await init_db(db_file)
    returns = [-0.01, 0.015, -0.02, 0.005, -0.005, 0.01, -0.015, 0.008, -0.005, 0.012] * 15
    await _seed_snapshots_from_returns(db_file, returns, start_value=100_000.0)
    analytics = PortfolioAnalytics(str(db_file))
    result = await analytics.get_portfolio_risk(days=365)

    assert "cvar_95" in result, "cvar_95 field missing from result"
    assert "cvar_99" in result, "cvar_99 field missing from result"
    assert result["cvar_95"] is not None, "cvar_95 should not be None with sufficient data"
    assert result["cvar_99"] is not None, "cvar_99 should not be None with sufficient data"
    assert isinstance(result["cvar_95"], float), f"cvar_95 should be float, got {type(result['cvar_95'])}"
    assert isinstance(result["cvar_99"], float), f"cvar_99 should be float, got {type(result['cvar_99'])}"
    # Both should be positive (loss expressed as positive percentage)
    assert result["cvar_95"] >= 0.0, f"cvar_95 should be non-negative, got {result['cvar_95']}"
    assert result["cvar_99"] >= 0.0, f"cvar_99 should be non-negative, got {result['cvar_99']}"


# ---------------------------------------------------------------------------
# Test B: risk endpoint returns portfolio_var as positive float
# ---------------------------------------------------------------------------

async def test_risk_endpoint_returns_portfolio_var(tmp_path: Path) -> None:
    """get_portfolio_risk returns portfolio_var as positive float and portfolio_var_method as 'historical_simulation'."""
    db_file = tmp_path / "pvar.db"
    await init_db(db_file)
    returns = [-0.01, 0.015, -0.02, 0.005, -0.005, 0.01, -0.015, 0.008, -0.005, 0.012] * 15
    await _seed_snapshots_from_returns(db_file, returns, start_value=100_000.0)
    analytics = PortfolioAnalytics(str(db_file))
    result = await analytics.get_portfolio_risk(days=365)

    assert "portfolio_var" in result, "portfolio_var field missing from result"
    assert "portfolio_var_method" in result, "portfolio_var_method field missing from result"
    assert result["portfolio_var"] is not None, "portfolio_var should not be None with sufficient data"
    assert isinstance(result["portfolio_var"], float), (
        f"portfolio_var should be float, got {type(result['portfolio_var'])}"
    )
    assert result["portfolio_var"] >= 0.0, f"portfolio_var should be non-negative, got {result['portfolio_var']}"
    assert result["portfolio_var_method"] == "historical_simulation", (
        f"Expected 'historical_simulation', got {result['portfolio_var_method']!r}"
    )


# ---------------------------------------------------------------------------
# Test C: Tier 1 identity — portfolio_var == var_95 (same historical-sim VaR)
# ---------------------------------------------------------------------------

async def test_portfolio_var_equals_var_95_for_portfolio_returns(tmp_path: Path) -> None:
    """Tier 1 SIG-06: portfolio_var equals var_95 (both are historical-sim VaR on portfolio returns).

    Per 02-RESEARCH.md Q6: Tier 1 portfolio_var is historical-simulation VaR on the
    portfolio return series -- the same computation as var_95. They must be identical
    at floating-point precision.
    """
    db_file = tmp_path / "pv_identity.db"
    await init_db(db_file)
    returns = [-0.01, 0.01, -0.005, 0.005, -0.02, 0.015] * 30
    await _seed_snapshots_from_returns(db_file, returns, start_value=100_000.0)
    analytics = PortfolioAnalytics(str(db_file))
    result = await analytics.get_portfolio_risk(days=365)

    assert result["portfolio_var"] is not None
    assert result["var_95"] is not None
    # Tier 1 identity: portfolio_var is var_95 (both historical-sim VaR at 95% on portfolio returns)
    assert abs(result["portfolio_var"] - result["var_95"]) < 1e-6, (
        f"portfolio_var {result['portfolio_var']} should equal var_95 {result['var_95']} "
        f"(Tier 1 SIG-06 identity)"
    )


# ---------------------------------------------------------------------------
# Test D: FastAPI TestClient end-to-end HTTP test
# ---------------------------------------------------------------------------

def test_risk_endpoint_http_via_fastapi_testclient(tmp_path: Path) -> None:
    """GET /analytics/risk via FastAPI TestClient returns cvar_95/99/var_95/portfolio_var in JSON."""
    import asyncio

    async def _prepare() -> Path:
        db_file = tmp_path / "risk_http.db"
        await init_db(db_file)
        returns = [-0.01, 0.015, -0.02, 0.005, -0.005, 0.01, -0.015] * 20  # 140 obs
        await _seed_snapshots_from_returns(db_file, returns, start_value=100_000.0)
        return db_file

    db_file = asyncio.run(_prepare())

    from api.app import create_app
    from api.deps import get_db_path
    from fastapi.testclient import TestClient

    app = create_app(db_path=str(db_file))
    app.dependency_overrides[get_db_path] = lambda: str(db_file)

    with TestClient(app) as client:
        resp = client.get("/analytics/risk?days=365")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "data" in body, "Response must have 'data' envelope"
    data = body["data"]

    for field in ("cvar_95", "cvar_99", "var_95", "portfolio_var", "portfolio_var_method"):
        assert field in data, f"Field '{field}' missing from /analytics/risk response"

    assert data["cvar_95"] is not None, "cvar_95 should not be null in HTTP response"
    assert data["cvar_99"] is not None, "cvar_99 should not be null in HTTP response"
    assert data["var_95"] is not None, "var_95 should not be null in HTTP response"
    assert data["portfolio_var"] is not None, "portfolio_var should not be null in HTTP response"
    assert data["portfolio_var_method"] == "historical_simulation"
    # Monotonicity: 99% loss >= 95% loss
    assert data["cvar_99"] >= data["cvar_95"], (
        f"cvar_99 {data['cvar_99']} should be >= cvar_95 {data['cvar_95']}"
    )


# ---------------------------------------------------------------------------
# Test E: insufficient data returns null fields but 200 response
# ---------------------------------------------------------------------------

def test_risk_endpoint_insufficient_data_returns_nulls(tmp_path: Path) -> None:
    """GET /analytics/risk with <10 snapshots returns 200 with null cvar/var fields."""
    import asyncio

    async def _prepare() -> Path:
        db_file = tmp_path / "risk_small.db"
        await init_db(db_file)
        # Only 5 data points -> 4 returns < 10 threshold
        returns = [-0.01, 0.02, -0.005, 0.015]
        await _seed_snapshots_from_returns(db_file, returns, start_value=100_000.0)
        return db_file

    db_file = asyncio.run(_prepare())

    from api.app import create_app
    from api.deps import get_db_path
    from fastapi.testclient import TestClient

    app = create_app(db_path=str(db_file))
    app.dependency_overrides[get_db_path] = lambda: str(db_file)

    with TestClient(app) as client:
        resp = client.get("/analytics/risk?days=365")

    assert resp.status_code == 200, f"Expected 200 even with sparse data, got {resp.status_code}"
    data = resp.json()["data"]

    assert data["cvar_95"] is None, f"Expected null cvar_95, got {data['cvar_95']}"
    assert data["cvar_99"] is None, f"Expected null cvar_99, got {data['cvar_99']}"
    assert data["portfolio_var"] is None, f"Expected null portfolio_var, got {data['portfolio_var']}"
    assert data["portfolio_var_method"] == "insufficient_data"
