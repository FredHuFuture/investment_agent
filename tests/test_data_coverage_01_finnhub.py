"""Tests for DATA-01: FinnhubProvider + FundamentalAgent Finnhub integration.

TDD file: RED tests written before implementation.
10 unit tests for FinnhubProvider, 5 integration tests for FundamentalAgent.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pandas as pd
import pytest

from data_providers.finnhub_provider import FINNHUB_BASE_URL, FinnhubProvider


# ============================================================================
# Helpers
# ============================================================================


def _make_mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Build a fake httpx.Response-like object."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ============================================================================
# T1: No key → RuntimeError on data calls
# ============================================================================


def test_finnhub_provider_no_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """FinnhubProvider() with no key → get_sector_pe raises RuntimeError."""
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    with pytest.warns(RuntimeWarning, match="FINNHUB_API_KEY"):
        provider = FinnhubProvider(api_key=None)
    assert provider._client is None
    with pytest.raises(RuntimeError, match="Finnhub API key missing"):
        asyncio.run(provider.get_sector_pe("technology"))


# ============================================================================
# T2: With key + monkeypatched HTTP → get_company_pe returns float
# ============================================================================


def test_finnhub_provider_with_key_returns_pe(monkeypatch: pytest.MonkeyPatch) -> None:
    """FinnhubProvider(api_key='test') + mocked response → get_company_pe returns 27.5."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test")
    provider = FinnhubProvider(api_key="test")
    mock_resp = _make_mock_response({"metric": {"peBasicExclExtraTTM": 27.5}})

    async def _run() -> float | None:
        with patch.object(provider._client, "get", new=AsyncMock(return_value=mock_resp)):
            return await provider.get_company_pe("AAPL")

    result = asyncio.run(_run())
    assert result == 27.5


# ============================================================================
# T3: get_sector_pe → median of peer basket
# ============================================================================


def test_finnhub_sector_pe_median_of_peers(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_sector_pe('technology') iterates 5 peers and returns the median."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test")
    provider = FinnhubProvider(api_key="test")

    # We'll return 5 distinct PE values for the technology peers
    pe_values = [25.0, 28.0, 30.0, 32.0, 35.0]  # median = 30.0
    call_count = 0

    async def fake_get_company_pe(ticker: str) -> float | None:
        nonlocal call_count
        val = pe_values[call_count % len(pe_values)]
        call_count += 1
        return val

    with patch.object(provider, "get_company_pe", side_effect=fake_get_company_pe):
        result = asyncio.run(provider.get_sector_pe("technology"))

    assert result == 30.0


# ============================================================================
# T4: Fewer than 2 valid peers → None
# ============================================================================


def test_finnhub_sector_pe_returns_none_on_few_peers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only 1 peer returns a value → get_sector_pe returns None (falls back to static)."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test")
    provider = FinnhubProvider(api_key="test")

    call_count = 0

    async def fake_get_company_pe(ticker: str) -> float | None:
        nonlocal call_count
        call_count += 1
        # Only first call returns a value; rest return None
        return 25.0 if call_count == 1 else None

    with patch.object(provider, "get_company_pe", side_effect=fake_get_company_pe):
        result = asyncio.run(provider.get_sector_pe("technology"))

    assert result is None


# ============================================================================
# T5: Rate limiter queues 61st call (using tiny period for test speed)
# ============================================================================


def test_finnhub_rate_limiter_queues_61st_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Firing 61 concurrent calls with max_calls=60 queues the 61st (takes non-zero time)."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test")

    from data_providers.rate_limiter import AsyncRateLimiter

    # Use a very small period so the test is fast (0.1s instead of 60s)
    fast_limiter = AsyncRateLimiter(max_calls=60, period_seconds=0.1)
    provider = FinnhubProvider(api_key="test")
    provider._limiter = fast_limiter  # type: ignore[assignment]

    mock_resp = _make_mock_response({"metric": {"peBasicExclExtraTTM": 20.0}})

    async def fake_get(path: str, **kwargs: Any) -> MagicMock:
        return mock_resp

    async def _run() -> float:
        with patch.object(provider._client, "get", side_effect=fake_get):
            start = time.monotonic()
            tasks = [provider.get_company_pe("AAPL") for _ in range(61)]
            await asyncio.gather(*tasks)
            return time.monotonic() - start

    elapsed = asyncio.run(_run())
    # The 61st call must wait at least some time (>= 0.01s in practice)
    assert elapsed >= 0.01, f"Expected rate-limiter delay but elapsed={elapsed:.4f}s"


# ============================================================================
# T6: HTTP 429 → logs warning, returns empty dict (does not raise)
# ============================================================================


def test_finnhub_429_returns_empty_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock httpx returning 429 → _rate_limited_get returns {} without raising."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test")
    provider = FinnhubProvider(api_key="test")
    mock_resp = _make_mock_response({}, status_code=429)

    async def _run() -> dict:
        with patch.object(provider._client, "get", new=AsyncMock(return_value=mock_resp)):
            return await provider._rate_limited_get("/stock/metric", {"symbol": "AAPL"})

    result = asyncio.run(_run())
    assert result == {}


# ============================================================================
# T7: is_point_in_time → False
# ============================================================================


def test_finnhub_is_point_in_time_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """FinnhubProvider.is_point_in_time() must return False (TTM data, not PIT)."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test")
    provider = FinnhubProvider(api_key="test")
    assert provider.is_point_in_time() is False


# ============================================================================
# T8: supported_asset_types → ["stock"]
# ============================================================================


def test_finnhub_supported_asset_types_is_stock(monkeypatch: pytest.MonkeyPatch) -> None:
    """FinnhubProvider.supported_asset_types() must return ['stock']."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test")
    provider = FinnhubProvider(api_key="test")
    assert provider.supported_asset_types() == ["stock"]


# ============================================================================
# T9: Sanity filter — drops negative PE
# ============================================================================


def test_finnhub_sanity_filter_drops_negative_pe(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_company_pe returns None when API returns pe=-10 (sanity filter: pe <= 0)."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test")
    provider = FinnhubProvider(api_key="test")
    mock_resp = _make_mock_response({"metric": {"peBasicExclExtraTTM": -10.0}})

    async def _run() -> float | None:
        with patch.object(provider._client, "get", new=AsyncMock(return_value=mock_resp)):
            return await provider.get_company_pe("AAPL")

    result = asyncio.run(_run())
    assert result is None


# ============================================================================
# T10: Sanity filter — drops huge outlier
# ============================================================================


def test_finnhub_sanity_filter_drops_huge_outlier(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_company_pe returns None when API returns pe=5000 (sanity filter: pe > 1000)."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test")
    provider = FinnhubProvider(api_key="test")
    mock_resp = _make_mock_response({"metric": {"peBasicExclExtraTTM": 5000.0}})

    async def _run() -> float | None:
        with patch.object(provider._client, "get", new=AsyncMock(return_value=mock_resp)):
            return await provider.get_company_pe("AAPL")

    result = asyncio.run(_run())
    assert result is None


# ============================================================================
# INTEGRATION TESTS: FundamentalAgent + Finnhub sector P/E
# ============================================================================


def _mock_key_stats(overrides: dict | None = None) -> dict:
    base = {
        "market_cap": 500_000_000_000,
        "pe_ratio": 18.0,
        "forward_pe": 15.0,
        "beta": 1.1,
        "dividend_yield": 0.01,
        "sector": "Technology",
        "industry": "Software",
        "52w_high": 200.0,
        "52w_low": 140.0,
        "current_price": 180.0,
    }
    if overrides:
        base.update(overrides)
    return base


def _mock_financials() -> dict:
    income_statement = pd.DataFrame(
        {
            "2025": [120_000_000_000, 25_000_000_000, 30_000_000_000],
            "2024": [105_000_000_000, 20_000_000_000, 25_000_000_000],
        },
        index=["Total Revenue", "Net Income", "EBITDA"],
    )
    balance_sheet = pd.DataFrame(
        {"2025": [100_000_000_000, 50_000_000_000, 70_000_000_000, 30_000_000_000, 20_000_000_000]},
        index=[
            "Total Stockholders Equity",
            "Total Debt",
            "Current Assets",
            "Current Liabilities",
            "Cash And Cash Equivalents",
        ],
    )
    cash_flow = pd.DataFrame(
        {"2025": [18_000_000_000]},
        index=["Free Cash Flow"],
    )
    return {
        "income_statement": income_statement,
        "balance_sheet": balance_sheet,
        "cash_flow": cash_flow,
    }


class MockBaseProvider:
    """Minimal DataProvider mock for FundamentalAgent OHLCV/financials calls."""

    async def get_key_stats(self, ticker: str) -> dict:
        return _mock_key_stats()

    async def get_financials(self, ticker: str, period: str = "annual") -> dict:
        return _mock_financials()

    async def get_price_history(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        raise NotImplementedError

    async def get_current_price(self, ticker: str) -> float:
        return 0.0

    def is_point_in_time(self) -> bool:
        return False

    def supported_asset_types(self) -> list[str]:
        return ["stock"]


# ============================================================================
# I1: Finnhub key set → reasoning contains "Finnhub sector P/E"
# ============================================================================


def test_fundamental_agent_uses_finnhub_when_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """With FINNHUB_API_KEY set and FinnhubProvider mocked → reasoning has 'Finnhub sector P/E'."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test_key")

    from agents.fundamental import FundamentalAgent
    from agents.models import AgentInput
    from data_providers import sector_pe_cache

    # Reset module-level cache and provider so fresh Finnhub instance is created
    sector_pe_cache._cache.clear()
    sector_pe_cache._finnhub_provider = None

    provider = MockBaseProvider()
    agent = FundamentalAgent(provider)  # type: ignore[arg-type]

    async def _run() -> str:
        # Patch get_sector_pe to return 29.0 from "finnhub" source
        async def fake_get_median(sector: str | None, provider: Any = None) -> float | None:
            return 29.0

        async def fake_get_source(sector: str | None) -> str:
            return "finnhub"

        with (
            patch("data_providers.sector_pe_cache.get_sector_pe_median", side_effect=fake_get_median),
            patch("data_providers.sector_pe_cache.get_sector_pe_source", side_effect=fake_get_source),
        ):
            out = await agent.analyze(AgentInput(ticker="AAPL", asset_type="stock"))
        return out.reasoning

    reasoning = asyncio.run(_run())
    assert "Finnhub sector P/E" in reasoning, f"Expected 'Finnhub sector P/E' in: {reasoning!r}"


# ============================================================================
# I2: No key → reasoning contains "static sector median"
# ============================================================================


def test_fundamental_agent_falls_back_to_static_when_key_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """With FINNHUB_API_KEY unset → reasoning has 'static sector median'."""
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)

    from agents.fundamental import FundamentalAgent
    from agents.models import AgentInput
    from data_providers import sector_pe_cache

    sector_pe_cache._cache.clear()
    sector_pe_cache._finnhub_provider = None

    provider = MockBaseProvider()
    agent = FundamentalAgent(provider)  # type: ignore[arg-type]

    async def _run() -> str:
        # Patch source to return "static" (key is unset so this is the path)
        async def fake_get_source(sector: str | None) -> str:
            return "static"

        with patch("data_providers.sector_pe_cache.get_sector_pe_source", side_effect=fake_get_source):
            out = await agent.analyze(AgentInput(ticker="AAPL", asset_type="stock"))
        return out.reasoning

    reasoning = asyncio.run(_run())
    assert "static sector median" in reasoning, f"Expected 'static sector median' in: {reasoning!r}"


# ============================================================================
# I3: Finnhub failure → graceful fallback to static
# ============================================================================


def test_fundamental_agent_falls_back_on_finnhub_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """If FinnhubProvider.get_sector_pe raises → agent still completes with static fallback."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test_key")

    from agents.fundamental import FundamentalAgent
    from agents.models import AgentInput
    from data_providers import sector_pe_cache

    sector_pe_cache._cache.clear()
    sector_pe_cache._finnhub_provider = None

    provider = MockBaseProvider()
    agent = FundamentalAgent(provider)  # type: ignore[arg-type]

    async def _run() -> str:
        # Patch source to return "static" (fallback after Finnhub failure)
        async def fake_get_source(sector: str | None) -> str:
            return "static"

        # Patch median to raise (simulating Finnhub network failure)
        async def fake_get_median(sector: str | None, provider: Any = None) -> float | None:
            raise RuntimeError("Simulated Finnhub network failure")

        with (
            patch("data_providers.sector_pe_cache.get_sector_pe_median", side_effect=fake_get_median),
            patch("data_providers.sector_pe_cache.get_sector_pe_source", side_effect=fake_get_source),
        ):
            out = await agent.analyze(AgentInput(ticker="AAPL", asset_type="stock"))
        return out.reasoning

    reasoning = asyncio.run(_run())
    assert "static sector median" in reasoning, f"Expected fallback in: {reasoning!r}"


# ============================================================================
# I4: backtest_mode=True → HOLD regardless of Finnhub presence (FOUND-04)
# ============================================================================


def test_fundamental_agent_backtest_mode_unchanged_by_finnhub(monkeypatch: pytest.MonkeyPatch) -> None:
    """FOUND-04 preserved: backtest_mode=True → HOLD, no provider calls, no Finnhub calls."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test_key")

    from agents.fundamental import FundamentalAgent
    from agents.models import AgentInput, Signal
    from data_providers import sector_pe_cache

    sector_pe_cache._cache.clear()
    sector_pe_cache._finnhub_provider = None

    finnhub_calls = 0

    async def fake_get_sector_pe(sector: str | None) -> float | None:
        nonlocal finnhub_calls
        finnhub_calls += 1
        return 29.0

    provider = MockBaseProvider()
    agent = FundamentalAgent(provider)  # type: ignore[arg-type]

    async def _run() -> None:
        with patch("data_providers.sector_pe_cache.get_sector_pe_median") as mock_median:
            out = await agent.analyze(AgentInput(ticker="AAPL", asset_type="stock", backtest_mode=True))
            assert out.signal == Signal.HOLD, f"Expected HOLD, got {out.signal}"
            assert out.confidence <= 40.0
            mock_median.assert_not_called()

    asyncio.run(_run())


# ============================================================================
# I5: sector_pe_cache reuses within TTL (mock call count == 1 for 2 invocations)
# ============================================================================


def test_sector_pe_cache_reuses_within_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two consecutive get_sector_pe_median calls within TTL → only 1 Finnhub HTTP call."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test_key")

    from data_providers import sector_pe_cache
    from data_providers.sector_pe_cache import get_sector_pe_median

    # Clear cache before test
    sector_pe_cache._cache.clear()
    sector_pe_cache._finnhub_provider = None

    call_count = 0

    async def fake_finnhub_sector_pe(sector: str | None) -> float | None:
        nonlocal call_count
        call_count += 1
        return 30.0

    async def _run() -> None:
        # Use api_key="test_key" directly so no RuntimeWarning fires while
        # FINNHUB_API_KEY is set in the environment.
        fh = FinnhubProvider(api_key="test_key")

        with patch.object(fh, "get_sector_pe", side_effect=fake_finnhub_sector_pe):
            sector_pe_cache._finnhub_provider = fh  # type: ignore[assignment]
            # First call — should hit Finnhub
            r1 = await get_sector_pe_median("technology", provider=None)
            # Second call — should hit cache
            r2 = await get_sector_pe_median("technology", provider=None)

        assert r1 == r2
        assert call_count == 1, f"Expected 1 Finnhub call, got {call_count}"

    asyncio.run(_run())
