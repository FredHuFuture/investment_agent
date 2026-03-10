from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta
from typing import Iterable

import pandas as pd
import pytest

from agents.models import AgentInput, Signal
from agents.technical import TechnicalAgent
from data_providers.base import DataProvider


class MockProvider(DataProvider):
    def __init__(self, daily_df: pd.DataFrame, weekly_df: pd.DataFrame | None = None):
        self._daily_df = daily_df
        self._weekly_df = weekly_df if weekly_df is not None else daily_df.iloc[::5]

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        if interval == "1wk":
            if self._weekly_df is None:
                raise ValueError("Weekly data unavailable.")
            return self._weekly_df
        return self._daily_df

    async def get_current_price(self, ticker: str) -> float:
        return float(self._daily_df["Close"].iloc[-1])

    def is_point_in_time(self) -> bool:
        return True

    def supported_asset_types(self) -> list[str]:
        return ["stock", "btc", "eth"]


def _make_ohlcv(prices: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    if volumes is None:
        volumes = [1_000_000.0 for _ in prices]
    now = datetime.utcnow()
    dates = [now - timedelta(days=(len(prices) - i)) for i in range(len(prices))]
    close = pd.Series(prices, index=pd.to_datetime(dates))
    data = pd.DataFrame(
        {
            "Open": close * 0.995,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": volumes,
        },
        index=pd.to_datetime(dates),
    )
    return data


def _run_agent(prices: Iterable[float]) -> tuple[Signal, float, dict]:
    daily_df = _make_ohlcv(list(prices))
    provider = MockProvider(daily_df)
    agent = TechnicalAgent(provider)
    output = asyncio.run(
        agent.analyze(AgentInput(ticker="TEST", asset_type="stock"))
    )
    return output.signal, output.confidence, output.metrics


def test_bullish_trending_stock() -> None:
    prices = [100 + i * 0.2 + 8 * math.sin(i / 5) for i in range(250)]
    signal, confidence, metrics = _run_agent(prices)
    assert signal == Signal.BUY
    assert confidence >= 60
    assert metrics["trend_score"] > 0


def test_bearish_trending_stock() -> None:
    prices = [200 - i * 0.2 + 8 * math.sin(i / 5) for i in range(250)]
    signal, confidence, _ = _run_agent(prices)
    assert signal == Signal.SELL
    assert confidence >= 55


def test_sideways_produces_hold() -> None:
    prices = ([95.0, 105.0, 100.0, 100.0] * 62) + [95.0, 100.0]
    signal, _, _ = _run_agent(prices)
    assert signal == Signal.HOLD


def test_overbought_rsi_dampens() -> None:
    prices = [100 + i * 0.4 for i in range(240)] + [200, 205, 210, 215, 220, 225, 230, 235, 240, 245]
    signal, _, metrics = _run_agent(prices)
    assert metrics["momentum_score"] <= 20
    assert signal in {Signal.BUY, Signal.HOLD}


def test_crypto_asset_works() -> None:
    prices = [100 + i * 0.2 for i in range(250)]
    daily_df = _make_ohlcv(prices)
    provider = MockProvider(daily_df)
    agent = TechnicalAgent(provider)
    output = asyncio.run(
        agent.analyze(AgentInput(ticker="BTC", asset_type="btc"))
    )
    assert output.signal in {Signal.BUY, Signal.SELL, Signal.HOLD}


def test_insufficient_data_warns() -> None:
    prices = [100 + i * 0.2 for i in range(50)]
    daily_df = _make_ohlcv(prices)
    provider = MockProvider(daily_df)
    agent = TechnicalAgent(provider)
    output = asyncio.run(
        agent.analyze(AgentInput(ticker="TEST", asset_type="stock"))
    )
    assert output.warnings


def test_output_structure() -> None:
    prices = [100 + i * 0.2 for i in range(250)]
    daily_df = _make_ohlcv(prices)
    provider = MockProvider(daily_df)
    agent = TechnicalAgent(provider)
    output = asyncio.run(
        agent.analyze(AgentInput(ticker="TEST", asset_type="stock"))
    )

    payload = output.to_dict()
    assert payload["agent_name"] == "TechnicalAgent"
    assert payload["ticker"] == "TEST"
    assert payload["signal"] in {Signal.BUY.value, Signal.SELL.value, Signal.HOLD.value}
    assert 30.0 <= payload["confidence"] <= 95.0


def test_metrics_keys_present() -> None:
    prices = [100 + i * 0.2 for i in range(250)]
    daily_df = _make_ohlcv(prices)
    provider = MockProvider(daily_df)
    agent = TechnicalAgent(provider)
    output = asyncio.run(
        agent.analyze(AgentInput(ticker="TEST", asset_type="stock"))
    )

    expected_keys = {
        "trend_score",
        "momentum_score",
        "volatility_score",
        "composite_score",
        "sma_20",
        "sma_50",
        "sma_200",
        "rsi_14",
        "macd_line",
        "macd_signal",
        "macd_histogram",
        "bb_upper",
        "bb_lower",
        "bb_middle",
        "atr_14",
        "current_price",
        "volume_ratio",
        "weekly_trend_confirms",
    }
    assert expected_keys.issubset(set(output.metrics.keys()))
