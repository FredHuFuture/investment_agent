"""CLOSE-02: Live Finnhub API round-trip.

Preconditions (test is skipped if any are absent):
  1. FINNHUB_API_KEY set to a valid free-tier key
  2. Network access to finnhub.io

Operator reproduction:
    export FINNHUB_API_KEY=<your_free_tier_key>
    pytest tests/test_close_02_finnhub_live.py -v
"""
from __future__ import annotations

import asyncio
import os
import time

import pytest

finnhub_key = os.getenv("FINNHUB_API_KEY")
LIVE_SKIP_REASON = (
    "CLOSE-02 live Finnhub test requires FINNHUB_API_KEY. "
    "Get a free key at https://finnhub.io/dashboard and export it."
)


@pytest.mark.skipif(not finnhub_key, reason=LIVE_SKIP_REASON)
@pytest.mark.network
def test_finnhub_sector_pe_live_round_trip() -> None:
    """CLOSE-02 evidence: live Finnhub peer-basket median P/E for technology."""
    from data_providers.finnhub_provider import FinnhubProvider

    async def _run():
        provider = FinnhubProvider()
        try:
            pe = await provider.get_sector_pe("technology")
        finally:
            await provider.aclose()
        return pe

    pe = asyncio.run(_run())
    assert pe is not None, "Finnhub returned None -- peer basket produced <2 valid P/E values"
    assert isinstance(pe, float), f"Expected float, got {type(pe).__name__}"
    assert 0 < pe < 1000, f"P/E sanity filter violated: {pe}"
    print(f"CLOSE-02 EVIDENCE: Finnhub sector P/E (technology) = {pe:.2f}")


@pytest.mark.skipif(not finnhub_key, reason=LIVE_SKIP_REASON)
@pytest.mark.network
def test_fundamental_agent_reasoning_contains_finnhub_marker() -> None:
    """CLOSE-02 evidence: FundamentalAgent on AAPL reasoning contains 'Finnhub sector P/E'."""
    from agents.fundamental import FundamentalAgent
    from agents.models import AgentInput
    from data_providers.yfinance_provider import YFinanceProvider
    # Reset any stale cached Finnhub provider singleton
    import data_providers.sector_pe_cache as spc

    # Force fresh FinnhubProvider pickup -- if other tests have nulled the
    # key, re-instantiating ensures this test uses the current FINNHUB_API_KEY.
    spc._finnhub_provider = None

    async def _run():
        provider = YFinanceProvider()
        agent = FundamentalAgent(provider)
        input_ = AgentInput(ticker="AAPL", asset_type="stock")
        return await agent.analyze(input_)

    output = asyncio.run(_run())
    reasoning = output.reasoning or ""
    assert "Finnhub sector P/E" in reasoning, (
        f"Expected 'Finnhub sector P/E' marker in reasoning; got: {reasoning!r}"
    )
    print(f"CLOSE-02 EVIDENCE: FundamentalAgent AAPL reasoning mentions Finnhub.")


@pytest.mark.skipif(not finnhub_key, reason=LIVE_SKIP_REASON)
@pytest.mark.network
def test_finnhub_rate_limit_not_tripped_under_three_calls() -> None:
    """Light smoke: three consecutive get_sector_pe calls complete <30s."""
    from data_providers.finnhub_provider import FinnhubProvider

    async def _run():
        provider = FinnhubProvider()
        try:
            t0 = time.monotonic()
            for sector in ("technology", "healthcare", "financials"):
                pe = await provider.get_sector_pe(sector)
                assert pe is None or (0 < pe < 1000), f"{sector} P/E sanity failed: {pe}"
            elapsed = time.monotonic() - t0
        finally:
            await provider.aclose()
        return elapsed

    elapsed = asyncio.run(_run())
    assert elapsed < 30.0, f"3 sector calls took {elapsed:.1f}s -- rate limit may be mis-configured"


def test_finnhub_live_tests_skip_cleanly_when_key_unset() -> None:
    """Meta-test: verify skipif guard is on the live tests."""
    for fn in (
        test_finnhub_sector_pe_live_round_trip,
        test_fundamental_agent_reasoning_contains_finnhub_marker,
        test_finnhub_rate_limit_not_tripped_under_three_calls,
    ):
        markers = getattr(fn, "pytestmark", [])
        skip_markers = [m for m in markers if m.name == "skipif"]
        assert skip_markers, f"{fn.__name__} missing skipif guard"
