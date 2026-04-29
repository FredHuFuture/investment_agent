"""Unit tests for SimfinProvider (Phase 8 DATA-v2-02).

Verifies:
- T-08-02-01 (no key in URL/logs)
- Pitfall 9 (no silent yfinance fallback — RuntimeError on missing key)
- 429 graceful return ({}) matches FinnhubProvider pattern
- asreported parameter routes to correct query string
- NotImplementedError for OHLCV / spot price (out of scope for SimFin)
"""
from __future__ import annotations

import logging
from unittest.mock import patch

import httpx
import pytest

from data_providers.simfin_provider import SIMFIN_BASE_URL, SimfinProvider


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def no_simfin_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip SIMFIN_API_KEY from the env for the duration of one test."""
    monkeypatch.delenv("SIMFIN_API_KEY", raising=False)


@pytest.fixture
def with_simfin_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a stable SIMFIN_API_KEY for tests that exercise the live-key path."""
    monkeypatch.setenv("SIMFIN_API_KEY", "TEST-KEY")


# ============================================================================
# T1: Lazy-key warn + no raise on init (mirrors FinnhubProvider lazy pattern)
# ============================================================================


def test_lazy_key_warning_no_raise_on_init(no_simfin_key: None) -> None:
    """Without SIMFIN_API_KEY, SimfinProvider() warns but does not raise."""
    with pytest.warns(RuntimeWarning, match="SIMFIN_API_KEY not set"):
        provider = SimfinProvider()
    assert provider._client is None


# ============================================================================
# T2: Pitfall 9 — get_financials raises RuntimeError when key missing
# (no silent yfinance fallback; arms tests/test_simfin_provider_no_silent_yfinance_fallback.py)
# ============================================================================


@pytest.mark.asyncio
async def test_get_financials_raises_runtime_error_when_key_missing(
    no_simfin_key: None,
) -> None:
    """Pitfall 9: caller must SEE the missing key, not silently fall back to yfinance."""
    with pytest.warns(RuntimeWarning):
        provider = SimfinProvider()
    with pytest.raises(RuntimeError, match="SIMFIN_API_KEY"):
        await provider.get_financials("AAPL", statement="pl", period="q1", fyear=2024)


# ============================================================================
# T3: Authorization header is set on the httpx client (T-08-02-01)
# ============================================================================


def test_auth_header_format(with_simfin_key: None) -> None:
    """API key MUST live in the Authorization header, not URL params."""
    provider = SimfinProvider()
    assert provider._client is not None
    assert provider._client.headers["Authorization"] == "api-key TEST-KEY"
    assert str(provider._client.base_url).rstrip("/") == SIMFIN_BASE_URL


# ============================================================================
# T4: asreported flag serializes to lowercase string in query params
# ============================================================================


@pytest.mark.asyncio
async def test_asreported_param_serializes_to_lowercase_string(
    with_simfin_key: None,
) -> None:
    """asreported=True → 'true' string; asreported=False → 'false' string."""
    captured: dict = {}

    async def fake_get(self, path, params=None):
        captured["path"] = path
        captured["params"] = params

        class R:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"data": []}

        return R()

    provider = SimfinProvider()
    with patch.object(httpx.AsyncClient, "get", fake_get):
        await provider.get_financials(
            "AAPL", statement="pl", period="q1", fyear=2024, asreported=True
        )
    assert captured["path"] == "/companies/statements"
    assert captured["params"]["asreported"] == "true"
    assert captured["params"]["ticker"] == "AAPL"
    assert captured["params"]["statements"] == "pl"
    assert captured["params"]["period"] == "q1"
    assert captured["params"]["fyear"] == 2024

    captured.clear()
    with patch.object(httpx.AsyncClient, "get", fake_get):
        await provider.get_financials(
            "AAPL", statement="bs", period="q2", asreported=False
        )
    assert captured["params"]["asreported"] == "false"
    assert captured["params"]["statements"] == "bs"
    assert "fyear" not in captured["params"]


# ============================================================================
# T5: HTTP 429 returns empty dict (matches FinnhubProvider pattern at lines 99-103)
# ============================================================================


@pytest.mark.asyncio
async def test_429_returns_empty_dict(with_simfin_key: None) -> None:
    """SimFin 429 → return {} so callers can fall back gracefully."""

    async def fake_get(self, path, params=None):
        req = httpx.Request(
            "GET", "https://prod.simfin.com/api/v3/companies/statements"
        )
        resp = httpx.Response(status_code=429, request=req)

        class R:
            status_code = 429

            def raise_for_status(self):
                raise httpx.HTTPStatusError(
                    "rate limit", request=req, response=resp
                )

            def json(self):
                return {}

        return R()

    provider = SimfinProvider()
    with patch.object(httpx.AsyncClient, "get", fake_get):
        result = await provider.get_financials(
            "AAPL", statement="pl", period="q1", fyear=2024
        )
    assert result == {}


# ============================================================================
# T6: Other HTTP errors (500, 401, etc.) propagate
# ============================================================================


@pytest.mark.asyncio
async def test_500_raises(with_simfin_key: None) -> None:
    """Server errors must not be swallowed — only 429 returns {}."""

    async def fake_get(self, path, params=None):
        req = httpx.Request(
            "GET", "https://prod.simfin.com/api/v3/companies/statements"
        )
        resp = httpx.Response(status_code=500, request=req)

        class R:
            status_code = 500

            def raise_for_status(self):
                raise httpx.HTTPStatusError(
                    "server error", request=req, response=resp
                )

            def json(self):
                return {}

        return R()

    provider = SimfinProvider()
    with patch.object(httpx.AsyncClient, "get", fake_get):
        with pytest.raises(httpx.HTTPStatusError):
            await provider.get_financials(
                "AAPL", statement="pl", period="q1", fyear=2024
            )


# ============================================================================
# T7: API key never appears in log lines (T-08-02-01)
# ============================================================================


@pytest.mark.asyncio
async def test_api_key_never_logged(
    with_simfin_key: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Caplog at INFO must never see the literal API key string."""
    caplog.set_level(logging.INFO)
    provider = SimfinProvider()
    assert provider._client is not None
    for record in caplog.records:
        assert "TEST-KEY" not in record.getMessage()


# ============================================================================
# T8: SimFin does not provide OHLCV — caller must use YFinanceProvider
# ============================================================================


@pytest.mark.asyncio
async def test_get_price_history_raises_not_implemented(with_simfin_key: None) -> None:
    """SimFin does not return OHLCV; caller routes to yfinance for prices."""
    provider = SimfinProvider()
    with pytest.raises(NotImplementedError):
        await provider.get_price_history("AAPL")


@pytest.mark.asyncio
async def test_get_current_price_raises_not_implemented(with_simfin_key: None) -> None:
    """SimFin does not return spot prices; caller routes to yfinance."""
    provider = SimfinProvider()
    with pytest.raises(NotImplementedError):
        await provider.get_current_price("AAPL")


# ============================================================================
# T9: is_point_in_time + supported_asset_types contract
# ============================================================================


def test_is_point_in_time_returns_true(with_simfin_key: None) -> None:
    """SimFin asreported=True path delivers PIT semantics."""
    provider = SimfinProvider()
    assert provider.is_point_in_time() is True


def test_supported_asset_types_returns_stock_only(with_simfin_key: None) -> None:
    """SimFin covers US/CA equities only — no crypto/macro support."""
    provider = SimfinProvider()
    assert provider.supported_asset_types() == ["stock"]
