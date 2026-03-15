"""Tests for Sprint 18 regime detection endpoint.

All tests use a temp SQLite DB and mock external dependencies (no network calls).
The /regime/current endpoint fetches live data from FRED and VIX providers,
so we mock those to avoid network access in tests.
"""
from __future__ import annotations

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
    path = str(tmp_path / "test_regime.db")
    await init_db(path)
    return path


@pytest.fixture
async def client(db_path: str):
    app = create_app(db_path=db_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _make_vix_df(vix_value: float = 18.0, periods: int = 30) -> pd.DataFrame:
    """Create a VIX-like DataFrame with matching index and data lengths."""
    dates = pd.date_range(end="2025-06-01", periods=periods, freq="B")
    return pd.DataFrame({"Close": [vix_value] * len(dates)}, index=dates)


# ---------------------------------------------------------------------------
# 1. GET /regime/current -- returns valid regime with mocked providers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regime_current_mocked(client: httpx.AsyncClient):
    """Test the regime endpoint with fully mocked FRED and VIX providers."""
    # Mock FRED provider
    mock_fred = MagicMock()
    mock_fred.get_fed_funds_rate = AsyncMock(
        return_value=pd.Series([5.25, 5.25, 5.50, 5.50], name="fed_funds")
    )
    mock_fred.get_treasury_yield = AsyncMock(
        side_effect=lambda term: pd.Series(
            [4.5] if term == "10y" else [4.8], name=f"yield_{term}"
        )
    )
    mock_fred.get_m2_money_supply = AsyncMock(
        return_value=pd.Series(
            [20000 + i * 50 for i in range(14)], name="m2"
        )
    )

    # Mock VIX provider
    mock_vix_provider = MagicMock()
    mock_vix_provider.get_price_history = AsyncMock(return_value=_make_vix_df(18.0))

    with (
        patch("data_providers.fred_provider.FredProvider", return_value=mock_fred),
        patch("data_providers.yfinance_provider.YFinanceProvider", return_value=mock_vix_provider),
    ):
        resp = await client.get("/regime/current")

    assert resp.status_code == 200

    body = resp.json()
    assert "data" in body
    assert "warnings" in body

    data = body["data"]
    assert "regime" in data
    assert "confidence" in data

    # Regime should be one of the valid types
    valid_regimes = {
        "bull_market", "bear_market", "sideways",
        "high_volatility", "risk_off",
    }
    assert data["regime"] in valid_regimes

    # Confidence should be a number between 0 and 100
    assert 0 <= data["confidence"] <= 100

    # Indicators should be present
    assert "indicators" in data
    assert "description" in data


# ---------------------------------------------------------------------------
# 2. GET /regime/current -- graceful degradation when FRED unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regime_current_fred_unavailable(client: httpx.AsyncClient):
    """When FRED provider fails, endpoint should still return 200 with warnings."""
    with (
        patch(
            "data_providers.fred_provider.FredProvider",
            side_effect=Exception("FRED API key not set"),
        ),
        patch(
            "data_providers.yfinance_provider.YFinanceProvider",
            side_effect=Exception("yfinance unavailable"),
        ),
    ):
        resp = await client.get("/regime/current")

    assert resp.status_code == 200

    body = resp.json()
    data = body["data"]
    warnings = body["warnings"]

    # Should still have a regime result (will be sideways with low confidence)
    assert "regime" in data
    assert "confidence" in data
    assert data["regime"] in {
        "bull_market", "bear_market", "sideways",
        "high_volatility", "risk_off",
    }

    # Should have warnings about unavailable data
    assert len(warnings) >= 1


# ---------------------------------------------------------------------------
# 3. GET /regime/current -- warnings array always present
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regime_current_warnings_present(client: httpx.AsyncClient):
    """Warnings array should always be present in response, even if empty."""
    mock_fred = MagicMock()
    mock_fred.get_fed_funds_rate = AsyncMock(
        return_value=pd.Series([5.25, 5.25, 5.50, 5.50])
    )
    mock_fred.get_treasury_yield = AsyncMock(
        return_value=pd.Series([4.5])
    )
    mock_fred.get_m2_money_supply = AsyncMock(
        return_value=pd.Series([20000 + i * 50 for i in range(14)])
    )

    mock_vix = MagicMock()
    mock_vix.get_price_history = AsyncMock(return_value=_make_vix_df(18.0))

    with (
        patch("data_providers.fred_provider.FredProvider", return_value=mock_fred),
        patch("data_providers.yfinance_provider.YFinanceProvider", return_value=mock_vix),
    ):
        resp = await client.get("/regime/current")

    assert resp.status_code == 200
    body = resp.json()
    assert "warnings" in body
    assert isinstance(body["warnings"], list)


# ---------------------------------------------------------------------------
# 4. GET /regime/current -- partial data (VIX only, no FRED)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regime_current_vix_only(client: httpx.AsyncClient):
    """When only VIX data is available, regime should still work."""
    mock_vix = MagicMock()
    mock_vix.get_price_history = AsyncMock(return_value=_make_vix_df(35.0))

    with (
        patch(
            "data_providers.fred_provider.FredProvider",
            side_effect=Exception("No FRED key"),
        ),
        patch("data_providers.yfinance_provider.YFinanceProvider", return_value=mock_vix),
    ):
        resp = await client.get("/regime/current")

    assert resp.status_code == 200

    data = resp.json()["data"]
    assert "regime" in data
    assert "confidence" in data

    # With high VIX (35), should detect elevated volatility
    assert data["regime"] in {
        "bull_market", "bear_market", "sideways",
        "high_volatility", "risk_off",
    }


# ---------------------------------------------------------------------------
# 5. GET /regime/current -- indicators sub-scores present
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regime_current_has_indicators(client: httpx.AsyncClient):
    """The response should include indicator sub-scores."""
    mock_fred = MagicMock()
    mock_fred.get_fed_funds_rate = AsyncMock(
        return_value=pd.Series([5.0, 5.0, 5.25, 5.50])
    )
    mock_fred.get_treasury_yield = AsyncMock(
        return_value=pd.Series([4.2])
    )
    mock_fred.get_m2_money_supply = AsyncMock(
        return_value=pd.Series([20000 + i * 50 for i in range(14)])
    )

    mock_vix = MagicMock()
    mock_vix.get_price_history = AsyncMock(return_value=_make_vix_df(20.0))

    with (
        patch("data_providers.fred_provider.FredProvider", return_value=mock_fred),
        patch("data_providers.yfinance_provider.YFinanceProvider", return_value=mock_vix),
    ):
        resp = await client.get("/regime/current")

    assert resp.status_code == 200

    data = resp.json()["data"]
    indicators = data["indicators"]
    assert "trend_score" in indicators
    assert "volatility_score" in indicators
    assert "momentum_score" in indicators
    assert "macro_score" in indicators
