from __future__ import annotations

import asyncio

import pandas as pd
import pytest

from agents.fundamental import FundamentalAgent, NON_PIT_WARNING
from agents.models import AgentInput, Signal
from data_providers.base import DataProvider


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


def _mock_financials(overrides: dict | None = None) -> dict:
    income_statement = pd.DataFrame(
        {
            "2025": [120_000_000_000, 25_000_000_000, 30_000_000_000],
            "2024": [105_000_000_000, 20_000_000_000, 25_000_000_000],
        },
        index=["Total Revenue", "Net Income", "EBITDA"],
    )
    balance_sheet = pd.DataFrame(
        {
            "2025": [
                100_000_000_000,
                50_000_000_000,
                70_000_000_000,
                30_000_000_000,
                20_000_000_000,
            ]
        },
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
    if overrides:
        for section, updates in overrides.items():
            if section == "income_statement":
                for row, values in updates.items():
                    if isinstance(values, list):
                        income_statement.loc[row] = values
                    else:
                        income_statement.loc[row, "2025"] = values
            elif section == "balance_sheet":
                for row, value in updates.items():
                    balance_sheet.loc[row, "2025"] = value
            elif section == "cash_flow":
                for row, value in updates.items():
                    cash_flow.loc[row, "2025"] = value
    return {
        "income_statement": income_statement,
        "balance_sheet": balance_sheet,
        "cash_flow": cash_flow,
    }


class MockProvider(DataProvider):
    def __init__(self, key_stats: dict, financials: dict, raise_financials: bool = False):
        self._key_stats = key_stats
        self._financials = financials
        self._raise_financials = raise_financials

    async def get_price_history(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        raise NotImplementedError

    async def get_current_price(self, ticker: str) -> float:
        return 0.0

    async def get_financials(self, ticker: str, period: str = "annual") -> dict:
        if self._raise_financials:
            raise ValueError("No financials")
        return self._financials

    async def get_key_stats(self, ticker: str) -> dict:
        return self._key_stats

    def is_point_in_time(self) -> bool:
        return False

    def supported_asset_types(self) -> list[str]:
        return ["stock"]


def test_high_quality_value_stock() -> None:
    key_stats = _mock_key_stats(
        {"pe_ratio": 12.0, "forward_pe": 10.0, "market_cap": 250_000_000_000, "current_price": 150.0}
    )
    financials = _mock_financials(
        {
            "income_statement": {
                "Total Revenue": [140_000_000_000, 120_000_000_000],
                "Net Income": [40_000_000_000, 30_000_000_000],
                "EBITDA": [45_000_000_000, 35_000_000_000],
            },
            "balance_sheet": {
                "Total Stockholders Equity": 200_000_000_000,
                "Total Debt": 20_000_000_000,
                "Current Assets": 90_000_000_000,
                "Current Liabilities": 30_000_000_000,
                "Cash And Cash Equivalents": 20_000_000_000,
            },
            "cash_flow": {"Free Cash Flow": 25_000_000_000},
        }
    )
    provider = MockProvider(key_stats, financials)
    agent = FundamentalAgent(provider)
    output = asyncio.run(agent.analyze(AgentInput(ticker="TEST", asset_type="stock")))
    assert output.signal == Signal.BUY
    assert output.confidence >= 65


def test_overvalued_stock() -> None:
    key_stats = _mock_key_stats(
        {"pe_ratio": 45.0, "forward_pe": 35.0, "current_price": 195.0}
    )
    financials = _mock_financials(
        {
            "income_statement": {
                "Total Revenue": [80_000_000_000, 90_000_000_000],
                "Net Income": [2_000_000_000, 4_000_000_000],
                "EBITDA": [12_000_000_000, 14_000_000_000],
            },
            "balance_sheet": {
                "Total Stockholders Equity": 60_000_000_000,
                "Total Debt": 200_000_000_000,
                "Current Assets": 40_000_000_000,
                "Current Liabilities": 60_000_000_000,
                "Cash And Cash Equivalents": 10_000_000_000,
            },
            "cash_flow": {"Free Cash Flow": 5_000_000_000},
        }
    )
    provider = MockProvider(key_stats, financials)
    agent = FundamentalAgent(provider)
    output = asyncio.run(agent.analyze(AgentInput(ticker="TEST", asset_type="stock")))
    assert output.signal == Signal.SELL


def test_mediocre_stock() -> None:
    key_stats = _mock_key_stats({"pe_ratio": 22.0, "forward_pe": 22.0})
    financials = _mock_financials(
        {
            "income_statement": {
                "Total Revenue": [100_000_000_000, 100_000_000_000],
                "Net Income": [15_000_000_000, 15_000_000_000],
                "EBITDA": [30_000_000_000, 30_000_000_000],
            },
            "balance_sheet": {
                "Total Stockholders Equity": 150_000_000_000,
                "Total Debt": 100_000_000_000,
                "Current Assets": 90_000_000_000,
                "Current Liabilities": 60_000_000_000,
                "Cash And Cash Equivalents": 15_000_000_000,
            },
            "cash_flow": {"Free Cash Flow": 15_000_000_000},
        }
    )
    provider = MockProvider(key_stats, financials)
    agent = FundamentalAgent(provider)
    output = asyncio.run(agent.analyze(AgentInput(ticker="TEST", asset_type="stock")))
    assert output.signal == Signal.HOLD


def test_crypto_raises_not_implemented() -> None:
    provider = MockProvider(_mock_key_stats(), _mock_financials())
    agent = FundamentalAgent(provider)
    with pytest.raises(NotImplementedError):
        asyncio.run(agent.analyze(AgentInput(ticker="BTC", asset_type="btc")))


def test_missing_financials_graceful() -> None:
    provider = MockProvider(_mock_key_stats(), _mock_financials(), raise_financials=True)
    agent = FundamentalAgent(provider)
    output = asyncio.run(agent.analyze(AgentInput(ticker="TEST", asset_type="stock")))
    assert output.signal == Signal.HOLD
    assert output.confidence == 30.0
    assert output.warnings


def test_non_pit_warning_present() -> None:
    provider = MockProvider(_mock_key_stats(), _mock_financials())
    agent = FundamentalAgent(provider)
    output = asyncio.run(agent.analyze(AgentInput(ticker="TEST", asset_type="stock")))
    assert NON_PIT_WARNING in output.warnings


def test_all_none_metrics() -> None:
    provider = MockProvider({}, {})
    agent = FundamentalAgent(provider)
    output = asyncio.run(agent.analyze(AgentInput(ticker="TEST", asset_type="stock")))
    assert output.signal == Signal.HOLD
    assert output.confidence == 30.0


def test_metrics_keys_present() -> None:
    provider = MockProvider(_mock_key_stats(), _mock_financials())
    agent = FundamentalAgent(provider)
    output = asyncio.run(agent.analyze(AgentInput(ticker="TEST", asset_type="stock")))
    expected_keys = {
        "value_score",
        "quality_score",
        "growth_score",
        "composite_score",
        "pe_trailing",
        "pe_forward",
        "pb_ratio",
        "ev_ebitda",
        "roe",
        "profit_margin",
        "revenue_growth",
        "debt_equity",
        "current_ratio",
        "fcf_yield",
        "pct_from_52w_high",
        "market_cap",
        "dividend_yield",
        "sector",
        "peg_ratio",
        "earnings_growth",
        "analyst_rating",
    }
    assert expected_keys.issubset(set(output.metrics.keys()))


def test_peg_ratio_scoring() -> None:
    """PEG < 1.0 (cheap) should push value score higher vs PEG 3.0 (expensive)."""
    base_financials = _mock_financials()

    # Cheap PEG = 0.8 -> value score boost
    cheap_stats = _mock_key_stats({"pegRatio": 0.8})
    provider_cheap = MockProvider(cheap_stats, base_financials)
    agent = FundamentalAgent(provider_cheap)
    out_cheap = asyncio.run(agent.analyze(AgentInput(ticker="TEST", asset_type="stock")))

    # Expensive PEG = 3.0 -> value score penalty
    expensive_stats = _mock_key_stats({"pegRatio": 3.0})
    provider_exp = MockProvider(expensive_stats, base_financials)
    agent2 = FundamentalAgent(provider_exp)
    out_exp = asyncio.run(agent2.analyze(AgentInput(ticker="TEST", asset_type="stock")))

    assert out_cheap.metrics["value_score"] > out_exp.metrics["value_score"]
    assert out_cheap.metrics["peg_ratio"] == 0.8
    assert out_exp.metrics["peg_ratio"] == 3.0


def test_earnings_growth_scoring() -> None:
    """Strong earnings growth (35%) should give higher growth score than contraction (-15%)."""
    base_financials = _mock_financials()

    # Strong earnings growth
    strong_stats = _mock_key_stats({"earningsGrowth": 0.35})
    provider_strong = MockProvider(strong_stats, base_financials)
    agent = FundamentalAgent(provider_strong)
    out_strong = asyncio.run(agent.analyze(AgentInput(ticker="TEST", asset_type="stock")))

    # Earnings contraction
    weak_stats = _mock_key_stats({"earningsGrowth": -0.15})
    provider_weak = MockProvider(weak_stats, base_financials)
    agent2 = FundamentalAgent(provider_weak)
    out_weak = asyncio.run(agent2.analyze(AgentInput(ticker="TEST", asset_type="stock")))

    assert out_strong.metrics["growth_score"] > out_weak.metrics["growth_score"]
    assert out_strong.metrics["earnings_growth"] == 0.35
    assert out_weak.metrics["earnings_growth"] == -0.15


def test_analyst_rating_scoring() -> None:
    """Strong Buy rating (1.5) should give higher quality score than Sell rating (4.5)."""
    base_financials = _mock_financials()

    # Strong Buy
    buy_stats = _mock_key_stats({"recommendationMean": 1.5})
    provider_buy = MockProvider(buy_stats, base_financials)
    agent = FundamentalAgent(provider_buy)
    out_buy = asyncio.run(agent.analyze(AgentInput(ticker="TEST", asset_type="stock")))

    # Sell
    sell_stats = _mock_key_stats({"recommendationMean": 4.5})
    provider_sell = MockProvider(sell_stats, base_financials)
    agent2 = FundamentalAgent(provider_sell)
    out_sell = asyncio.run(agent2.analyze(AgentInput(ticker="TEST", asset_type="stock")))

    assert out_buy.metrics["quality_score"] > out_sell.metrics["quality_score"]
    assert out_buy.metrics["analyst_rating"] == 1.5
    assert out_sell.metrics["analyst_rating"] == 4.5


def test_missing_new_metrics_graceful() -> None:
    """Agent should work without pegRatio/earningsGrowth/recommendationMean (None-safe)."""
    # Base _mock_key_stats does NOT include pegRatio, earningsGrowth, recommendationMean
    key_stats = _mock_key_stats()
    financials = _mock_financials()
    provider = MockProvider(key_stats, financials)
    agent = FundamentalAgent(provider)
    output = asyncio.run(agent.analyze(AgentInput(ticker="TEST", asset_type="stock")))

    # Should complete without error
    assert output.signal in (Signal.BUY, Signal.HOLD, Signal.SELL)
    assert output.confidence >= 30.0
    # New metrics should be None when not provided
    assert output.metrics["peg_ratio"] is None
    assert output.metrics["earnings_growth"] is None
    assert output.metrics["analyst_rating"] is None
