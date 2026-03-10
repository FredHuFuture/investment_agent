from __future__ import annotations

import asyncio
from datetime import datetime

import pandas as pd
import pytest

from agents.macro import MacroAgent
from agents.models import AgentInput, Regime, Signal
from data_providers.base import DataProvider


def _mock_vix_data(vix_value: float, num_days: int = 60) -> pd.DataFrame:
    dates = pd.date_range(end=datetime.utcnow(), periods=num_days, freq="B")
    data = pd.DataFrame(
        {
            "Open": [vix_value] * num_days,
            "High": [vix_value] * num_days,
            "Low": [vix_value] * num_days,
            "Close": [vix_value] * num_days,
            "Volume": [1_000_000] * num_days,
        },
        index=dates,
    )
    return data


def _mock_fred_series(values: list[float]) -> pd.Series:
    dates = pd.date_range(start="2020-01-01", periods=len(values), freq="MS")
    return pd.Series(values, index=dates)


class MockFredProvider(DataProvider):
    def __init__(
        self,
        fed_funds: pd.Series,
        treasury_10y: pd.Series,
        treasury_2y: pd.Series,
        m2: pd.Series,
        raise_runtime: bool = False,
    ):
        self._fed_funds = fed_funds
        self._treasury_10y = treasury_10y
        self._treasury_2y = treasury_2y
        self._m2 = m2
        self._raise_runtime = raise_runtime

    async def get_price_history(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        raise NotImplementedError

    async def get_current_price(self, ticker: str) -> float:
        return 0.0

    async def get_fed_funds_rate(self) -> pd.Series:
        if self._raise_runtime:
            raise RuntimeError("FRED API key not configured.")
        return self._fed_funds

    async def get_treasury_yield(self, maturity: str = "10y") -> pd.Series:
        if self._raise_runtime:
            raise RuntimeError("FRED API key not configured.")
        return self._treasury_10y if maturity == "10y" else self._treasury_2y

    async def get_m2_money_supply(self) -> pd.Series:
        if self._raise_runtime:
            raise RuntimeError("FRED API key not configured.")
        return self._m2

    def is_point_in_time(self) -> bool:
        return True

    def supported_asset_types(self) -> list[str]:
        return ["macro"]


class MockVixProvider(DataProvider):
    def __init__(self, vix_df: pd.DataFrame | None = None, raise_error: bool = False):
        self._vix_df = vix_df
        self._raise_error = raise_error

    async def get_price_history(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        if self._raise_error or self._vix_df is None:
            raise ValueError("VIX unavailable")
        return self._vix_df

    async def get_current_price(self, ticker: str) -> float:
        return 0.0

    def is_point_in_time(self) -> bool:
        return True

    def supported_asset_types(self) -> list[str]:
        return ["macro"]


def _build_agent(
    vix_value: float,
    fed_funds: list[float],
    treasury_10y: float,
    treasury_2y: float,
    m2_values: list[float],
) -> MacroAgent:
    fred = MockFredProvider(
        fed_funds=_mock_fred_series(fed_funds),
        treasury_10y=_mock_fred_series([treasury_10y]),
        treasury_2y=_mock_fred_series([treasury_2y]),
        m2=_mock_fred_series(m2_values),
    )
    vix = MockVixProvider(_mock_vix_data(vix_value))
    return MacroAgent(fred, vix)


def test_risk_on_regime() -> None:
    agent = _build_agent(
        vix_value=14.0,
        fed_funds=[5.0, 4.8, 4.6, 4.4],
        treasury_10y=4.0,
        treasury_2y=3.0,
        m2_values=[100] * 12 + [106],
    )
    output = asyncio.run(agent.analyze(AgentInput(ticker="SPY", asset_type="stock")))
    assert output.metrics["regime"] == Regime.RISK_ON.value
    assert output.signal == Signal.BUY


def test_risk_off_regime() -> None:
    agent = _build_agent(
        vix_value=32.0,
        fed_funds=[4.0, 4.2, 4.4, 4.6],
        treasury_10y=3.5,
        treasury_2y=4.0,
        m2_values=[100] * 12 + [98],
    )
    output = asyncio.run(agent.analyze(AgentInput(ticker="SPY", asset_type="stock")))
    assert output.metrics["regime"] == Regime.RISK_OFF.value
    assert output.signal == Signal.SELL


def test_neutral_regime() -> None:
    agent = _build_agent(
        vix_value=22.0,
        fed_funds=[4.0, 4.0, 4.0, 4.0],
        treasury_10y=3.2,
        treasury_2y=3.0,
        m2_values=[100] * 12 + [103],
    )
    output = asyncio.run(agent.analyze(AgentInput(ticker="SPY", asset_type="stock")))
    assert output.metrics["regime"] == Regime.NEUTRAL.value
    assert output.signal == Signal.HOLD


def test_crypto_buy_in_risk_on() -> None:
    agent = _build_agent(
        vix_value=14.0,
        fed_funds=[5.0, 4.8, 4.6, 4.4],
        treasury_10y=4.0,
        treasury_2y=3.0,
        m2_values=[100] * 12 + [106],
    )
    output = asyncio.run(agent.analyze(AgentInput(ticker="BTC", asset_type="btc")))
    assert output.signal == Signal.BUY


def test_crypto_sell_in_risk_off() -> None:
    agent = _build_agent(
        vix_value=32.0,
        fed_funds=[4.0, 4.2, 4.4, 4.6],
        treasury_10y=3.5,
        treasury_2y=4.0,
        m2_values=[100] * 12 + [98],
    )
    output = asyncio.run(agent.analyze(AgentInput(ticker="BTC", asset_type="btc")))
    assert output.signal == Signal.SELL


def test_missing_fred_key_graceful() -> None:
    fred = MockFredProvider(
        fed_funds=_mock_fred_series([4.0, 4.1, 4.2, 4.3]),
        treasury_10y=_mock_fred_series([3.5]),
        treasury_2y=_mock_fred_series([3.0]),
        m2=_mock_fred_series([100] * 13),
        raise_runtime=True,
    )
    vix = MockVixProvider(_mock_vix_data(20.0))
    agent = MacroAgent(fred, vix)
    output = asyncio.run(agent.analyze(AgentInput(ticker="SPY", asset_type="stock")))
    assert output.signal == Signal.HOLD
    assert output.confidence == 30.0
    assert any("FRED" in warning for warning in output.warnings)


def test_missing_vix_graceful() -> None:
    fred = MockFredProvider(
        fed_funds=_mock_fred_series([4.0, 3.9, 3.8, 3.7]),
        treasury_10y=_mock_fred_series([4.0]),
        treasury_2y=_mock_fred_series([3.0]),
        m2=_mock_fred_series([100] * 12 + [106]),
    )
    vix = MockVixProvider(raise_error=True)
    agent = MacroAgent(fred, vix)
    output = asyncio.run(agent.analyze(AgentInput(ticker="SPY", asset_type="stock")))
    assert output.signal in {Signal.BUY, Signal.HOLD, Signal.SELL}
    assert output.warnings


def test_regime_in_metrics() -> None:
    agent = _build_agent(
        vix_value=22.0,
        fed_funds=[4.0, 4.0, 4.0, 4.0],
        treasury_10y=3.2,
        treasury_2y=3.0,
        m2_values=[100] * 12 + [103],
    )
    output = asyncio.run(agent.analyze(AgentInput(ticker="SPY", asset_type="stock")))
    assert output.metrics["regime"] in {
        Regime.RISK_ON.value,
        Regime.RISK_OFF.value,
        Regime.NEUTRAL.value,
    }


def test_yield_curve_inversion() -> None:
    agent = _build_agent(
        vix_value=18.0,
        fed_funds=[4.0, 4.0, 4.0, 4.0],
        treasury_10y=3.5,
        treasury_2y=4.0,
        m2_values=[100] * 12 + [100],
    )
    output = asyncio.run(agent.analyze(AgentInput(ticker="SPY", asset_type="stock")))
    assert output.metrics["yield_curve_spread"] == pytest.approx(-0.5)
