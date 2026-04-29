"""Tests for FundamentalAgent dual-condition + SimFin routing (Phase 8 DATA-v2-02).

Verifies:
- Pitfall 1 — FOUND-04 default contract preserved (re-runs the 08-01 tripwire
  under the new dual-condition logic)
- SimFin path activates only when use_pit_fundamentals=True AND _pit_provider attached
- ValueError when use_pit_fundamentals=True but backtest_date missing
- Graceful fallback to yfinance when use_pit_fundamentals=True but no PIT provider
- set_pit_provider() correctly attaches the helper attribute
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from agents.fundamental import FundamentalAgent
from agents.models import AgentInput, Signal


# ============================================================================
# T1: FOUND-04 default contract — backtest_mode=True alone returns HOLD
# (re-runs 08-01 tripwire under dual-condition logic)
# ============================================================================


@pytest.mark.asyncio
async def test_backtest_mode_only_still_returns_hold() -> None:
    """FOUND-04 default contract: backtest_mode=True && use_pit_fundamentals=False
    MUST return HOLD/0.0. Re-runs 08-01 tripwire under dual-condition logic."""
    provider = AsyncMock()
    agent = FundamentalAgent(provider)
    out = await agent.analyze(
        AgentInput(
            ticker="AAPL",
            asset_type="stock",
            backtest_mode=True,
            use_pit_fundamentals=False,
        )
    )
    assert out.signal == Signal.HOLD
    assert out.data_completeness == 0.0
    provider.get_financials.assert_not_called()
    provider.get_key_stats.assert_not_called()


# ============================================================================
# T2: Dual-condition lifts FOUND-04 ONLY when use_pit_fundamentals=True
# ============================================================================


@pytest.mark.asyncio
async def test_use_pit_fundamentals_with_backtest_mode_calls_simfin() -> None:
    """backtest_mode=True + use_pit_fundamentals=True must route to SimFin."""
    yf = AsyncMock()
    yf.get_key_stats = AsyncMock(
        return_value={"pegRatio": 1.2, "trailingPE": 25.0, "sector": "Technology"}
    )
    yf.get_financials = AsyncMock(return_value={})
    pit = AsyncMock()
    pit.get_financials = AsyncMock(return_value={"data": [{"Revenue": 1000}]})
    agent = FundamentalAgent(yf)
    agent.set_pit_provider(pit)

    out = await agent.analyze(
        AgentInput(
            ticker="AAPL",
            asset_type="stock",
            backtest_mode=True,
            use_pit_fundamentals=True,
            backtest_date=date(2024, 6, 30),
        )
    )
    # SimFin path called with asreported=True
    pit.get_financials.assert_called_once()
    call_kwargs = pit.get_financials.call_args.kwargs
    assert call_kwargs.get("asreported") is True
    assert call_kwargs.get("fyear") == 2024
    assert any("SimFin" in w for w in out.warnings)
    # Output is a real AgentOutput (no FOUND-04 short-circuit)
    assert out.data_completeness != 0.0 or out.signal != Signal.HOLD or out.confidence != 30.0


# ============================================================================
# T3: ValueError raised when use_pit_fundamentals=True but backtest_date missing
# ============================================================================


@pytest.mark.asyncio
async def test_use_pit_fundamentals_without_backtest_date_raises() -> None:
    """use_pit_fundamentals=True with no backtest_date is a programming error."""
    agent = FundamentalAgent(AsyncMock())
    agent.set_pit_provider(AsyncMock())
    with pytest.raises(ValueError, match="backtest_date"):
        await agent.analyze(
            AgentInput(
                ticker="AAPL",
                asset_type="stock",
                backtest_mode=True,
                use_pit_fundamentals=True,
                backtest_date=None,
            )
        )


# ============================================================================
# T4: use_pit_fundamentals=True but no PIT provider attached → graceful fallback
# ============================================================================


@pytest.mark.asyncio
async def test_no_pit_provider_attached_falls_through_to_yfinance_with_warning() -> None:
    """When operator opts in but no PIT provider is configured, fall back to
    yfinance with an explicit warning so the discrepancy is visible."""
    yf = AsyncMock()
    yf.get_key_stats = AsyncMock(
        return_value={"pegRatio": 1.2, "trailingPE": 25.0, "sector": "Technology"}
    )
    yf.get_financials = AsyncMock(return_value={})
    agent = FundamentalAgent(yf)
    # Do NOT call set_pit_provider — _pit_provider is None
    out = await agent.analyze(
        AgentInput(
            ticker="AAPL",
            asset_type="stock",
            backtest_mode=False,
            use_pit_fundamentals=True,
        )
    )
    assert any(
        "no pit provider" in w.lower() or "not configured" in w.lower()
        for w in out.warnings
    )
    yf.get_financials.assert_called_once()


# ============================================================================
# T5: set_pit_provider() attaches the helper attribute
# ============================================================================


def test_set_pit_provider_attaches_attribute() -> None:
    agent = FundamentalAgent(AsyncMock())
    pit = AsyncMock()
    agent.set_pit_provider(pit)
    assert agent._pit_provider is pit


def test_pit_provider_default_is_none() -> None:
    """Without a call to set_pit_provider, _pit_provider stays None so the
    default v1.1 path runs unchanged."""
    agent = FundamentalAgent(AsyncMock())
    assert agent._pit_provider is None


# ============================================================================
# T6: SimFin path stays disabled by default — use_pit_fundamentals=False
# even when a PIT provider is attached must NOT call SimFin (operator
# explicit opt-in is the only switch)
# ============================================================================


@pytest.mark.asyncio
async def test_use_pit_fundamentals_false_skips_simfin_even_when_attached() -> None:
    yf = AsyncMock()
    yf.get_key_stats = AsyncMock(
        return_value={"pegRatio": 1.2, "trailingPE": 25.0, "sector": "Technology"}
    )
    yf.get_financials = AsyncMock(return_value={})
    pit = AsyncMock()
    pit.get_financials = AsyncMock(return_value={"data": []})
    agent = FundamentalAgent(yf)
    agent.set_pit_provider(pit)

    await agent.analyze(
        AgentInput(
            ticker="AAPL",
            asset_type="stock",
            backtest_mode=False,
            use_pit_fundamentals=False,  # operator did NOT opt in
        )
    )
    pit.get_financials.assert_not_called()  # SimFin must stay quiet
    yf.get_financials.assert_called_once()  # yfinance is the live path
