"""Phase 8 DATA-v2-05 backend: GET /portfolio surfaces restated_deltas.

Covers Task 5 of plan 08-02:
- Without SIMFIN_API_KEY: response shape unchanged from v1.1 (restated_deltas
  is None for every position; no SimFin HTTP calls issued)
- With SIMFIN_API_KEY (mocked): per-metric delta_pct math is correct
- Zero as_filed: delta_pct is None (avoid division by zero)
- SimFin failure (raise/empty response): _compute_restated_deltas returns None
  gracefully (no crash propagates to the endpoint)
- Provider unconfigured (no key): _compute_restated_deltas returns None
  without attempting any HTTP call
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from db.database import init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def no_simfin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure SIMFIN_API_KEY is unset so SimfinProvider._client is None."""
    monkeypatch.delenv("SIMFIN_API_KEY", raising=False)


@pytest.fixture
def with_simfin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set a stub SIMFIN_API_KEY so SimfinProvider builds a httpx client."""
    monkeypatch.setenv("SIMFIN_API_KEY", "TEST_KEY_DO_NOT_USE")


# ---------------------------------------------------------------------------
# Test 1: GET /portfolio without SIMFIN_API_KEY returns v1.1 shape
# ---------------------------------------------------------------------------


def test_get_portfolio_returns_v1_shape_when_no_simfin_key(
    tmp_path: Path, no_simfin: None
) -> None:
    """Without SIMFIN_API_KEY, GET /portfolio shape stays v1.1-compatible:
    restated_deltas is None on every position; no SimFin HTTP calls attempted.
    """
    from fastapi.testclient import TestClient
    from api.app import create_app
    from portfolio.manager import PortfolioManager

    db_path = str(tmp_path / "test_no_simfin.db")
    asyncio.run(init_db(db_path))

    async def _seed() -> None:
        pm = PortfolioManager(db_path)
        await pm.add_position("AAPL", "stock", 10, 150.0, "2024-01-01")

    asyncio.run(_seed())

    app = create_app(db_path=db_path)

    with TestClient(app) as client:
        resp = client.get("/portfolio")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "data" in body and "positions" in body["data"]
    for pos in body["data"]["positions"]:
        # restated_deltas must be None (or absent) when SimFin is not configured
        rd = pos.get("restated_deltas")
        assert rd is None, (
            f"restated_deltas should be None without SIMFIN_API_KEY, got {rd!r}"
        )


# ---------------------------------------------------------------------------
# Test 2: _compute_restated_deltas math correctness (with mocked SimFin)
# ---------------------------------------------------------------------------


def test_compute_restated_deltas_math_correctness(with_simfin: None) -> None:
    """delta_pct = abs(restated - as_filed) / abs(as_filed) within 1e-6 tolerance.
    Net Income unchanged → delta_pct == 0.0.
    """

    async def _run() -> None:
        from api.routes.portfolio import _compute_restated_deltas
        from data_providers.simfin_provider import SimfinProvider

        provider = SimfinProvider()  # has client because SIMFIN_API_KEY=TEST_KEY

        async def fake_get_financials(
            ticker, statement="pl", period="q1", fyear=None, asreported=True,
        ):
            if asreported:
                # As-filed values (original 10-Q)
                return {
                    "data": [
                        {
                            "Revenue": 100_000_000,
                            "Net Income": 12_000_000,
                            "Publish Date": "2024-08-15",
                        }
                    ]
                }
            else:
                # Restated values (15% higher revenue; same net income)
                return {
                    "data": [
                        {
                            "Revenue": 115_000_000,
                            "Net Income": 12_000_000,
                            "Publish Date": "2024-08-15",
                        }
                    ]
                }

        provider.get_financials = fake_get_financials  # type: ignore[assignment]

        deltas = await _compute_restated_deltas(provider, "AAPL")
        assert deltas is not None and len(deltas) > 0

        revenue_delta = next((d for d in deltas if d.metric == "revenue"), None)
        assert revenue_delta is not None, "revenue delta entry missing"
        assert revenue_delta.as_filed == pytest.approx(100_000_000, abs=1)
        assert revenue_delta.restated == pytest.approx(115_000_000, abs=1)
        assert revenue_delta.delta_pct == pytest.approx(0.15, abs=1e-6), (
            f"Expected delta_pct=0.15, got {revenue_delta.delta_pct}"
        )
        assert revenue_delta.filing_date == "2024-08-15"

        ni_delta = next((d for d in deltas if d.metric == "net_income"), None)
        assert ni_delta is not None, "net_income delta entry missing"
        assert ni_delta.delta_pct == pytest.approx(0.0, abs=1e-9)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 3: zero as_filed → delta_pct is None (avoid div-by-zero)
# ---------------------------------------------------------------------------


def test_compute_restated_deltas_handles_zero_as_filed(with_simfin: None) -> None:
    """delta_pct must be None when as_filed=0 to avoid division by zero."""

    async def _run() -> None:
        from api.routes.portfolio import _compute_restated_deltas
        from data_providers.simfin_provider import SimfinProvider

        provider = SimfinProvider()

        async def fake_get_financials(
            ticker, statement="pl", period="q1", fyear=None, asreported=True,
        ):
            return {
                "data": [
                    {
                        "Revenue": 0,
                        "Net Income": 1_000_000,
                        "Publish Date": "2024-08-15",
                    }
                ]
            }

        provider.get_financials = fake_get_financials  # type: ignore[assignment]

        deltas = await _compute_restated_deltas(provider, "AAPL")
        assert deltas is not None
        revenue = next((d for d in deltas if d.metric == "revenue"), None)
        assert revenue is not None
        assert revenue.delta_pct is None, "delta_pct must be None when as_filed=0"
        assert revenue.as_filed == 0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 4: SimFin raises → helper returns None gracefully
# ---------------------------------------------------------------------------


def test_compute_restated_deltas_returns_none_on_simfin_failure(
    with_simfin: None,
) -> None:
    """When SimFin raises (network error, 5xx, etc.), helper returns None."""

    async def _run() -> None:
        from api.routes.portfolio import _compute_restated_deltas
        from data_providers.simfin_provider import SimfinProvider

        provider = SimfinProvider()

        async def fake_failing(
            ticker, statement="pl", period="q1", fyear=None, asreported=True,
        ):
            raise RuntimeError("SimFin unreachable")

        provider.get_financials = fake_failing  # type: ignore[assignment]

        result = await _compute_restated_deltas(provider, "AAPL")
        assert result is None, "Helper must return None when SimFin raises"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 5: Provider unconfigured (no key) → returns None without HTTP call
# ---------------------------------------------------------------------------


def test_compute_restated_deltas_returns_none_when_provider_unconfigured(
    no_simfin: None,
) -> None:
    """When SIMFIN_API_KEY is missing, _client is None and helper returns None."""

    async def _run() -> None:
        from api.routes.portfolio import _compute_restated_deltas
        from data_providers.simfin_provider import SimfinProvider

        provider = SimfinProvider()  # _client is None when key missing
        assert provider._client is None
        result = await _compute_restated_deltas(provider, "AAPL")
        assert result is None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 6 (defensive): empty SimFin response (rate limit / no data) → returns None
# ---------------------------------------------------------------------------


def test_compute_restated_deltas_returns_none_on_empty_response(
    with_simfin: None,
) -> None:
    """When SimFin returns {} (e.g., 429-rate-limit), helper returns None."""

    async def _run() -> None:
        from api.routes.portfolio import _compute_restated_deltas
        from data_providers.simfin_provider import SimfinProvider

        provider = SimfinProvider()

        async def fake_empty(
            ticker, statement="pl", period="q1", fyear=None, asreported=True,
        ):
            return {}

        provider.get_financials = fake_empty  # type: ignore[assignment]
        result = await _compute_restated_deltas(provider, "AAPL")
        assert result is None
