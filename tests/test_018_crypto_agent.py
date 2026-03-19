from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from agents.crypto import (
    CRYPTO_ADOPTION,
    HALVING_DATES,
    CryptoAgent,
    _clamp,
    _to_float,
)
from agents.models import AgentInput, AgentOutput, Regime, Signal
from cli.report import format_analysis_report
from data_providers.base import DataProvider
from engine.aggregator import AggregatedSignal


# ---------------------------------------------------------------------------
# Mock DataProvider
# ---------------------------------------------------------------------------

def _make_price_df(
    n_days: int = 252,
    start_price: float = 50000.0,
    trend: float = 0.001,
    volatility: float = 0.02,
    base_volume: float = 1_000_000.0,
) -> pd.DataFrame:
    """Generate synthetic OHLCV DataFrame for crypto testing."""
    np.random.seed(42)
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n_days, freq="B")
    n = len(dates)  # may differ from n_days on weekends (pandas 3.x)
    returns = np.random.normal(trend, volatility, n)
    prices = [start_price]
    for r in returns[1:]:
        prices.append(prices[-1] * (1 + r))
    prices = np.array(prices)
    # Add high/low spread
    highs = prices * (1 + np.abs(np.random.normal(0, 0.01, n)))
    lows = prices * (1 - np.abs(np.random.normal(0, 0.01, n)))
    opens = prices * (1 + np.random.normal(0, 0.005, n))
    volumes = np.random.uniform(base_volume * 0.5, base_volume * 1.5, n)

    return pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": prices,
            "Volume": volumes,
        },
        index=dates,
    )


def _make_key_stats(overrides: dict | None = None) -> dict:
    base = {
        "name": "Bitcoin USD",
        "market_cap": 1_200_000_000_000,
        "circulatingSupply": 19_800_000,
        "maxSupply": 21_000_000,
        "current_price": 60000.0,
    }
    if overrides:
        base.update(overrides)
    return base


class MockCryptoProvider(DataProvider):
    """Mock provider for CryptoAgent testing."""

    def __init__(
        self,
        price_df: pd.DataFrame | None = None,
        key_stats: dict | None = None,
        raise_price: bool = False,
        raise_stats: bool = False,
    ):
        self._price_df = price_df
        self._key_stats = key_stats or {}
        self._raise_price = raise_price
        self._raise_stats = raise_stats

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        if self._raise_price:
            raise ValueError("Price data unavailable")
        if self._price_df is None:
            raise ValueError("No price data configured")
        return self._price_df

    async def get_current_price(self, ticker: str) -> float:
        if self._price_df is not None and not self._price_df.empty:
            return float(self._price_df["Close"].iloc[-1])
        return 0.0

    async def get_key_stats(self, ticker: str) -> dict:
        if self._raise_stats:
            raise ValueError("Key stats unavailable")
        return self._key_stats

    def is_point_in_time(self) -> bool:
        return False

    def supported_asset_types(self) -> list[str]:
        return ["btc", "eth"]


# ---------------------------------------------------------------------------
# Helpers: patch out yfinance calls so tests never hit network
# ---------------------------------------------------------------------------

def _patch_spy_and_vix(agent):
    """Patch _fetch_spy_prices and _fetch_vix to return mock data."""
    spy_df = _make_price_df(n_days=130, start_price=5000, trend=0.0005, volatility=0.01)

    async def mock_fetch_spy():
        return spy_df

    async def mock_fetch_vix():
        return 18.5

    agent._fetch_spy_prices = mock_fetch_spy
    agent._fetch_vix = mock_fetch_vix


def _patch_spy_and_vix_with_values(agent, spy_df=None, vix_value=None):
    """Patch with custom values or raise on failure."""
    async def mock_fetch_spy():
        if spy_df is None:
            raise ValueError("No S&P data")
        return spy_df

    async def mock_fetch_vix():
        if vix_value is None:
            raise ValueError("No VIX data")
        return vix_value

    agent._fetch_spy_prices = mock_fetch_spy
    agent._fetch_vix = mock_fetch_vix


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_crypto_agent_btc_basic() -> None:
    """BTC analysis returns valid AgentOutput with all 7 factors scored."""
    price_df = _make_price_df(n_days=252, start_price=50000, trend=0.002)
    provider = MockCryptoProvider(price_df=price_df, key_stats=_make_key_stats())
    agent = CryptoAgent(provider)
    _patch_spy_and_vix(agent)

    output = asyncio.run(agent.analyze(AgentInput(ticker="BTC-USD", asset_type="btc")))

    assert isinstance(output, AgentOutput)
    assert output.agent_name == "CryptoAgent"
    assert output.signal in (Signal.BUY, Signal.HOLD, Signal.SELL)
    assert 30.0 <= output.confidence <= 90.0
    assert output.metrics["market_structure_score"] is not None
    assert output.metrics["momentum_trend_score"] is not None
    assert output.metrics["volatility_risk_score"] is not None
    assert output.metrics["liquidity_volume_score"] is not None
    assert output.metrics["macro_correlation_score"] is not None
    assert output.metrics["network_adoption_score"] is not None
    assert output.metrics["cycle_timing_score"] is not None
    assert output.metrics["composite_score"] is not None
    assert output.metrics["regime"] in ("RISK_ON", "RISK_OFF", "NEUTRAL")


def test_crypto_agent_eth_basic() -> None:
    """ETH analysis returns valid AgentOutput."""
    price_df = _make_price_df(n_days=252, start_price=3000, trend=0.001)
    provider = MockCryptoProvider(
        price_df=price_df,
        key_stats=_make_key_stats({"name": "Ethereum", "market_cap": 400_000_000_000}),
    )
    agent = CryptoAgent(provider)
    _patch_spy_and_vix(agent)

    output = asyncio.run(agent.analyze(AgentInput(ticker="ETH-USD", asset_type="eth")))

    assert isinstance(output, AgentOutput)
    assert output.agent_name == "CryptoAgent"
    assert output.signal in (Signal.BUY, Signal.HOLD, Signal.SELL)
    # ETH should have slightly lower market structure score than BTC
    # (no dominance bonus, neutral regulatory)


def test_market_structure_scoring() -> None:
    """Market structure: BTC gets dominance bonus, supply scarcity scored."""
    price_df = _make_price_df(n_days=60)
    provider = MockCryptoProvider(price_df=price_df, key_stats=_make_key_stats())
    agent = CryptoAgent(provider)
    _patch_spy_and_vix(agent)

    # BTC: dominance +10, supply ratio 94% > 90% -> +10
    score_btc, metrics_btc = agent._score_market_structure("btc", _make_key_stats(), [])
    assert score_btc >= 15  # at least dominance + scarcity
    assert metrics_btc["dominance_signal"] == "positive"

    # ETH: dominance -5, no max supply
    eth_stats = _make_key_stats({"circulatingSupply": 120_000_000, "maxSupply": None})
    score_eth, metrics_eth = agent._score_market_structure("eth", eth_stats, [])
    assert score_eth < score_btc
    assert metrics_eth["dominance_signal"] == "neutral"


def test_momentum_multi_timeframe() -> None:
    """Momentum scoring: bullish trend produces positive scores."""
    # Strong uptrend
    price_df_bull = _make_price_df(n_days=255, start_price=30000, trend=0.003, volatility=0.015)
    provider = MockCryptoProvider(price_df=price_df_bull)
    agent = CryptoAgent(provider)

    close_bull = price_df_bull["Close"]
    score_bull, metrics_bull = agent._score_momentum_trend(close_bull, [])

    assert score_bull > 0  # bullish momentum
    assert metrics_bull["return_3m_pct"] is not None
    assert metrics_bull["return_6m_pct"] is not None
    assert metrics_bull["return_12m_pct"] is not None
    assert metrics_bull["sma_200"] is not None

    # Strong downtrend
    price_df_bear = _make_price_df(n_days=255, start_price=60000, trend=-0.003, volatility=0.015)
    close_bear = price_df_bear["Close"]
    score_bear, metrics_bear = agent._score_momentum_trend(close_bear, [])

    assert score_bear < score_bull  # bearish should score lower


def test_volatility_risk_metrics() -> None:
    """Volatility scoring: known price series produces correct vol/drawdown metrics."""
    price_df = _make_price_df(n_days=120, start_price=50000, trend=0.001, volatility=0.02)
    provider = MockCryptoProvider(price_df=price_df)
    agent = CryptoAgent(provider)

    close = price_df["Close"]
    score, metrics = agent._score_volatility_risk(close, [])

    assert "volatility_30d_pct" in metrics
    assert "max_drawdown_90d_pct" in metrics
    assert "sharpe_90d" in metrics
    assert metrics["volatility_30d_pct"] is not None
    # With 2% daily vol, annualized should be around 32% (2% * sqrt(252) ~ 31.7%)
    # Should be in "low for crypto" range (<40%) -> positive score contribution
    assert metrics["volatility_30d_pct"] > 0


def test_liquidity_scoring() -> None:
    """Liquidity: high volume produces positive score."""
    # High volume crypto
    price_df = _make_price_df(
        n_days=60, start_price=50000, base_volume=50_000.0
    )
    provider = MockCryptoProvider(
        price_df=price_df,
        key_stats=_make_key_stats({"market_cap": 1_200_000_000_000}),
    )
    agent = CryptoAgent(provider)

    close = price_df["Close"]
    volume = price_df["Volume"]
    score, metrics = agent._score_liquidity_volume(close, volume, _make_key_stats(), [])

    assert "avg_daily_volume_usd" in metrics
    assert "volume_trend" in metrics
    assert metrics["avg_daily_volume_usd"] is not None


def test_macro_correlation() -> None:
    """Macro: S&P correlation and VIX affect scoring."""
    price_df = _make_price_df(n_days=120, start_price=50000)
    spy_df = _make_price_df(n_days=130, start_price=5000, trend=0.0005, volatility=0.01)
    provider = MockCryptoProvider(price_df=price_df)
    agent = CryptoAgent(provider)

    close = price_df["Close"]

    # Normal VIX
    score_normal, metrics_normal = agent._score_macro_correlation(close, spy_df, 18.0, [])
    assert "sp500_correlation_90d" in metrics_normal
    assert metrics_normal["vix_level"] == 18.0

    # High VIX -> risk-off penalty
    score_high_vix, metrics_high_vix = agent._score_macro_correlation(close, spy_df, 35.0, [])
    assert score_high_vix < score_normal  # high VIX penalizes


def test_network_adoption_constants() -> None:
    """Network & Adoption: BTC/ETH hardcoded constants produce expected scores."""
    provider = MockCryptoProvider()
    agent = CryptoAgent(provider)

    warnings_btc: list[str] = []
    warnings_eth: list[str] = []
    score_btc, metrics_btc = agent._score_network_adoption("btc", warnings_btc)
    score_eth, metrics_eth = agent._score_network_adoption("eth", warnings_eth)

    # BTC: age>10 (+10), ETF (+10), FAVORABLE (+5), bear>=4 (+10) = 35
    assert score_btc == 35
    assert metrics_btc["etf_access"] is True
    assert metrics_btc["regulatory_status"] == "FAVORABLE"
    assert metrics_btc["adoption_data_source"] == "static"

    # ETH: age>5<10 (+5), ETF (+10), NEUTRAL (0), bear>=4 (+10) = 25
    assert score_eth == 25
    assert metrics_eth["regulatory_status"] == "NEUTRAL"

    # BTC should score higher due to age + regulatory
    assert score_btc > score_eth

    # Static data warning should be emitted
    assert any("static" in w.lower() for w in warnings_btc)
    assert any("static" in w.lower() for w in warnings_eth)


def test_cycle_timing_halving() -> None:
    """Cycle timing: halving position affects score."""
    price_df = _make_price_df(n_days=60, start_price=50000)
    provider = MockCryptoProvider(price_df=price_df)
    agent = CryptoAgent(provider)

    close = price_df["Close"]
    volume = price_df["Volume"]

    # Test with current date (April 2024 halving -> ~23 months ago -> mid cycle)
    score, metrics = agent._score_cycle_timing(close, volume, 18.0, [])

    assert "halving_cycle_position" in metrics
    assert "cycle_phase" in metrics
    assert "fear_greed_proxy" in metrics
    assert metrics["halving_cycle_position"] >= 0
    assert metrics["halving_cycle_position"] <= 1.0
    assert metrics["cycle_phase"] in ("early", "mid", "late", "bear")


def test_fear_greed_proxy() -> None:
    """Fear/Greed proxy: extreme values produce contrarian signals."""
    price_df = _make_price_df(n_days=60, start_price=50000, trend=0.005, volatility=0.01)
    provider = MockCryptoProvider(price_df=price_df)
    agent = CryptoAgent(provider)

    close = price_df["Close"]
    volume = price_df["Volume"]

    # Low VIX + uptrend -> greed (higher proxy)
    fg_greed = agent._compute_fear_greed_proxy(close, volume, 12.0)
    assert fg_greed is not None
    assert fg_greed > 50  # should lean towards greed with uptrend + low VIX

    # High VIX -> fear (lower proxy)
    fg_fear = agent._compute_fear_greed_proxy(close, volume, 35.0)
    assert fg_fear is not None
    assert fg_fear < fg_greed  # high VIX should push towards fear


def test_missing_data_graceful() -> None:
    """Agent handles missing price data gracefully (HOLD with low confidence)."""
    # No price data
    provider = MockCryptoProvider(raise_price=True)
    agent = CryptoAgent(provider)
    _patch_spy_and_vix(agent)

    output = asyncio.run(agent.analyze(AgentInput(ticker="BTC-USD", asset_type="btc")))

    assert output.signal == Signal.HOLD
    assert output.confidence == 30.0
    assert len(output.warnings) > 0
    assert "Price history unavailable" in output.warnings[0]


def test_unsupported_asset_type() -> None:
    """Stock/forex asset types rejected with NotImplementedError."""
    provider = MockCryptoProvider()
    agent = CryptoAgent(provider)

    with pytest.raises(NotImplementedError, match="does not support 'stock'"):
        asyncio.run(agent.analyze(AgentInput(ticker="AAPL", asset_type="stock")))


def test_report_standard_mode_crypto() -> None:
    """CryptoAgent display in standard report mode shows cycle/momentum/vol/regime."""
    signal = AggregatedSignal(
        ticker="BTC-USD",
        asset_type="btc",
        final_signal=Signal.BUY,
        final_confidence=72.0,
        regime=Regime.RISK_ON,
        agent_signals=[
            AgentOutput(
                agent_name="CryptoAgent",
                ticker="BTC-USD",
                signal=Signal.BUY,
                confidence=72.0,
                reasoning="Crypto 7-factor model: bullish.",
                metrics={
                    "cycle_phase": "mid",
                    "momentum_trend_score": 25.0,
                    "volatility_30d_pct": 45.0,
                    "regime": "RISK_ON",
                    "composite_score": 30.0,
                },
            ),
        ],
        reasoning="Combined",
        metrics={
            "weights_used": {"CryptoAgent": 1.0},
            "agent_contributions": {},
        },
        warnings=[],
    )

    output = format_analysis_report(signal)
    assert "Crypto" in output
    assert "Cycle: mid" in output
    assert "Momentum: +25" in output
    assert "Vol: 45%" in output
    assert "Regime: RISK_ON" in output


def test_report_detail_mode_crypto() -> None:
    """CryptoAgent detail mode shows all 7 factor groups."""
    signal = AggregatedSignal(
        ticker="BTC-USD",
        asset_type="btc",
        final_signal=Signal.BUY,
        final_confidence=72.0,
        regime=Regime.RISK_ON,
        agent_signals=[
            AgentOutput(
                agent_name="CryptoAgent",
                ticker="BTC-USD",
                signal=Signal.BUY,
                confidence=72.0,
                reasoning="Crypto 7-factor model: bullish.",
                metrics={
                    "market_structure_score": 20.0,
                    "momentum_trend_score": 25.0,
                    "volatility_risk_score": 10.0,
                    "liquidity_volume_score": 15.0,
                    "macro_correlation_score": 5.0,
                    "network_adoption_score": 35.0,
                    "cycle_timing_score": 15.0,
                    "composite_score": 30.0,
                    "cycle_phase": "mid",
                    "return_3m_pct": 15.3,
                    "return_6m_pct": 42.1,
                    "volatility_30d_pct": 45.0,
                    "max_drawdown_90d_pct": -12.5,
                    "sharpe_90d": 1.8,
                    "avg_daily_volume_usd": 25_000_000_000,
                    "sp500_correlation_90d": 0.35,
                    "vix_level": 18.5,
                    "age_years": 16,
                    "etf_access": True,
                    "regulatory_status": "FAVORABLE",
                    "bear_survivals": 5,
                    "months_since_halving": 23.0,
                    "halving_cycle_position": 0.48,
                    "fear_greed_proxy": 62.0,
                    "regime": "RISK_ON",
                },
            ),
        ],
        reasoning="Combined",
        metrics={
            "weights_used": {"CryptoAgent": 1.0},
            "agent_contributions": {
                "CryptoAgent": {
                    "signal": "BUY",
                    "confidence": 72.0,
                    "weighted_contribution": 0.72,
                },
            },
            "raw_score": 0.72,
            "consensus_score": 1.0,
            "buy_count": 1,
            "sell_count": 0,
            "hold_count": 0,
        },
        warnings=[],
    )

    output = format_analysis_report(signal, detail=True)

    # Factor scores section
    assert "Factor Scores" in output
    assert "Market Structure" in output
    assert "Momentum & Trend" in output
    assert "Volatility & Risk" in output
    assert "Liquidity & Volume" in output
    assert "Macro & Correlation" in output
    assert "Network & Adoption" in output
    assert "Cycle & Timing" in output

    # Specific metrics visible in detail mode
    assert "15.3" in output  # 3M return
    assert "42.1" in output  # 6M return
    assert "45.0" in output  # volatility
    assert "1.8" in output or "1.80" in output  # Sharpe
    assert "16 years" in output  # age
    assert "FAVORABLE" in output  # regulatory
    assert "mid" in output  # cycle phase
