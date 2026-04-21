"""Tests for FOUND-04: backtest_mode flag on AgentInput prevents FundamentalAgent
from injecting look-ahead contaminated financials into historical backtests.

TDD file: RED written before implementation lands in models.py / fundamental.py /
backtesting/engine.py.
"""
from __future__ import annotations

import asyncio

import pandas as pd
import pytest

from agents.fundamental import FundamentalAgent
from agents.models import AgentInput, Signal
from data_providers.base import DataProvider


# ---------------------------------------------------------------------------
# Minimal counting provider (no network calls)
# ---------------------------------------------------------------------------

class CountingProvider(DataProvider):
    """Provider that counts calls to get_key_stats and get_financials."""

    def __init__(self) -> None:
        self.key_stats_calls = 0
        self.financials_calls = 0
        self.price_calls = 0

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        self.price_calls += 1
        return pd.DataFrame()

    async def get_current_price(self, ticker: str) -> float:
        return 100.0

    async def get_key_stats(self, ticker: str) -> dict:
        self.key_stats_calls += 1
        return {
            "market_cap": 1_000_000_000_000,
            "pe_ratio": 25.0,
            "forward_pe": 22.0,
            "sector": "Technology",
            "52w_high": 200.0,
            "current_price": 180.0,
        }

    async def get_financials(self, ticker: str, period: str = "annual") -> dict:
        self.financials_calls += 1
        return {"income_statement": None, "balance_sheet": None, "cash_flow": None}

    def is_point_in_time(self) -> bool:
        return False

    def supported_asset_types(self) -> list[str]:
        return ["stock"]


# ---------------------------------------------------------------------------
# Test A: AgentInput default backtest_mode is False
# ---------------------------------------------------------------------------

def test_agent_input_default_backtest_mode_false() -> None:
    """AgentInput(ticker, asset_type) must have .backtest_mode == False by default."""
    i = AgentInput(ticker="AAPL", asset_type="stock")
    assert i.backtest_mode is False


# ---------------------------------------------------------------------------
# Test B: AgentInput accepts backtest_mode=True
# ---------------------------------------------------------------------------

def test_agent_input_backtest_mode_true() -> None:
    """AgentInput(ticker, asset_type, backtest_mode=True) must have .backtest_mode is True."""
    i = AgentInput(ticker="AAPL", asset_type="stock", backtest_mode=True)
    assert i.backtest_mode is True


# ---------------------------------------------------------------------------
# Test C: Truthiness for int-like values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("val,expected_truthy", [
    (True, True),
    (False, False),
    (1, True),
    (0, False),
])
def test_backtest_mode_truthy_behavior(val: object, expected_truthy: bool) -> None:
    """backtest_mode is checked with `if agent_input.backtest_mode:` — verify truthy."""
    i = AgentInput(ticker="AAPL", asset_type="stock", backtest_mode=val)  # type: ignore[arg-type]
    assert bool(i.backtest_mode) is expected_truthy


# ---------------------------------------------------------------------------
# Test D: FundamentalAgent returns HOLD with no provider calls when backtest_mode=True
# ---------------------------------------------------------------------------

def test_fundamental_backtest_mode_returns_hold_without_calls() -> None:
    """In backtest_mode=True, FundamentalAgent returns HOLD, conf<=40, zero provider calls."""
    async def _run() -> None:
        provider = CountingProvider()
        agent = FundamentalAgent(provider)
        out = await agent.analyze(
            AgentInput(ticker="AAPL", asset_type="stock", backtest_mode=True)
        )
        assert out.signal == Signal.HOLD, f"Expected HOLD, got {out.signal}"
        assert out.confidence <= 40.0, f"Expected confidence<=40, got {out.confidence}"
        assert any(
            "backtest_mode" in w.lower() for w in out.warnings
        ), f"No backtest_mode warning found in {out.warnings}"
        assert provider.key_stats_calls == 0, (
            f"get_key_stats should NOT be called in backtest_mode; got {provider.key_stats_calls}"
        )
        assert provider.financials_calls == 0, (
            f"get_financials should NOT be called in backtest_mode; got {provider.financials_calls}"
        )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test E: FundamentalAgent still calls provider when backtest_mode=False (default)
# ---------------------------------------------------------------------------

def test_fundamental_backtest_mode_false_still_calls_provider() -> None:
    """In backtest_mode=False (default), provider.get_key_stats and get_financials are called.

    Note: get_key_stats may be called >1 time because get_sector_pe_median also
    calls it internally via the sector PE cache path.  We assert >= 1 for both.
    """
    async def _run() -> None:
        provider = CountingProvider()
        agent = FundamentalAgent(provider)
        # Should NOT raise — CountingProvider returns minimal data
        await agent.analyze(AgentInput(ticker="AAPL", asset_type="stock"))
        assert provider.key_stats_calls >= 1, (
            f"Expected >=1 get_key_stats call, got {provider.key_stats_calls}"
        )
        assert provider.financials_calls == 1, (
            f"Expected 1 get_financials call, got {provider.financials_calls}"
        )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test F: Backtester source code threads backtest_mode=True
# ---------------------------------------------------------------------------

def test_backtester_threads_backtest_mode_true() -> None:
    """Grep-level check: backtesting/engine.py must literally contain backtest_mode=True."""
    src = open("backtesting/engine.py", encoding="utf-8").read()
    assert "backtest_mode=True" in src, (
        "backtesting/engine.py must construct AgentInput with backtest_mode=True"
    )


# ---------------------------------------------------------------------------
# Test G: Regression — existing FundamentalAgent tests still pass
# (checked separately in test_006_fundamental_agent.py; this is a smoke test)
# ---------------------------------------------------------------------------

def test_fundamental_agent_non_backtest_smoke() -> None:
    """Smoke: a real analyze call (backtest_mode default) proceeds to provider calls."""
    async def _run() -> None:
        provider = CountingProvider()
        agent = FundamentalAgent(provider)
        out = await agent.analyze(AgentInput(ticker="AAPL", asset_type="stock"))
        # Signal can be anything — the key thing is provider was called
        assert provider.key_stats_calls >= 1
        assert provider.financials_calls >= 1
        assert out.agent_name == "FundamentalAgent"

    asyncio.run(_run())
