"""Tests for Task 008: AnalysisPipeline.

All tests mock DataProviders and Agents — no real network calls.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.models import AgentOutput, Regime, Signal
from engine.aggregator import AggregatedSignal


def _make_output(
    agent_name: str,
    signal: Signal,
    confidence: float,
    ticker: str = "AAPL",
    metrics: dict | None = None,
) -> AgentOutput:
    return AgentOutput(
        agent_name=agent_name,
        ticker=ticker,
        signal=signal,
        confidence=confidence,
        reasoning=f"{agent_name} says {signal.value}",
        metrics=metrics or {},
    )


class TestAnalysisPipeline:
    # 1. Stock E2E: all 3 agents (Technical, Fundamental, Macro) run successfully
    @pytest.mark.asyncio
    async def test_pipeline_stock_e2e(self) -> None:
        from engine.pipeline import AnalysisPipeline

        tech_out = _make_output("TechnicalAgent", Signal.BUY, 70)
        fund_out = _make_output("FundamentalAgent", Signal.BUY, 65)
        macro_out = _make_output(
            "MacroAgent", Signal.BUY, 58, metrics={"regime": "RISK_ON", "net_score": 25}
        )

        with (
            patch("engine.pipeline.get_provider") as mock_get_provider,
            patch("engine.pipeline.TechnicalAgent") as MockTech,
            patch("engine.pipeline.FundamentalAgent") as MockFund,
            patch("engine.pipeline.FredProvider"),
            patch("engine.pipeline.YFinanceProvider"),
            patch("engine.pipeline.MacroAgent") as MockMacro,
        ):
            mock_get_provider.return_value = MagicMock()

            mock_tech = MagicMock()
            mock_tech.name = "TechnicalAgent"
            mock_tech.analyze = AsyncMock(return_value=tech_out)
            MockTech.return_value = mock_tech

            mock_fund = MagicMock()
            mock_fund.name = "FundamentalAgent"
            mock_fund.analyze = AsyncMock(return_value=fund_out)
            MockFund.return_value = mock_fund

            mock_macro = MagicMock()
            mock_macro.name = "MacroAgent"
            mock_macro.analyze = AsyncMock(return_value=macro_out)
            MockMacro.return_value = mock_macro

            pipeline = AnalysisPipeline()
            result = await pipeline.analyze_ticker("AAPL", "stock")

        assert isinstance(result, AggregatedSignal)
        assert result.ticker == "AAPL"
        assert result.asset_type == "stock"
        # All 3 agents contributed
        assert len(result.agent_signals) == 3
        agent_names = {o.agent_name for o in result.agent_signals}
        assert "TechnicalAgent" in agent_names
        assert "FundamentalAgent" in agent_names
        assert "MacroAgent" in agent_names
        # Regime extracted
        assert result.regime == Regime.RISK_ON
        # No pipeline errors
        assert not any("failed" in w.lower() for w in result.warnings)

    # 2. Crypto: uses CryptoAgent only (no Technical/Fundamental/Macro)
    @pytest.mark.asyncio
    async def test_pipeline_crypto_uses_crypto_agent(self) -> None:
        from engine.pipeline import AnalysisPipeline

        crypto_out = _make_output(
            "CryptoAgent", Signal.BUY, 70, ticker="BTC",
            metrics={"regime": "RISK_ON", "composite_score": 25.0},
        )

        with (
            patch("engine.pipeline.get_provider") as mock_get_provider,
            patch("engine.pipeline.CryptoAgent") as MockCrypto,
        ):
            mock_get_provider.return_value = MagicMock()

            mock_crypto = MagicMock()
            mock_crypto.name = "CryptoAgent"
            mock_crypto.analyze = AsyncMock(return_value=crypto_out)
            MockCrypto.return_value = mock_crypto

            pipeline = AnalysisPipeline()
            result = await pipeline.analyze_ticker("BTC", "btc")

        assert isinstance(result, AggregatedSignal)
        # Only 1 agent for crypto (CryptoAgent)
        assert len(result.agent_signals) == 1
        agent_names = {o.agent_name for o in result.agent_signals}
        assert "CryptoAgent" in agent_names
        assert "TechnicalAgent" not in agent_names
        assert "FundamentalAgent" not in agent_names
        assert "MacroAgent" not in agent_names
        # CryptoAgent weight = 1.0
        weights = result.metrics["weights_used"]
        assert weights.get("CryptoAgent") == pytest.approx(1.0)

    # 3. No FRED key → MacroAgent skipped, result still valid, warning present
    @pytest.mark.asyncio
    async def test_pipeline_no_fred_key(self) -> None:
        from engine.pipeline import AnalysisPipeline

        tech_out = _make_output("TechnicalAgent", Signal.HOLD, 55)
        fund_out = _make_output("FundamentalAgent", Signal.HOLD, 60)

        with (
            patch("engine.pipeline.get_provider") as mock_get_provider,
            patch("engine.pipeline.TechnicalAgent") as MockTech,
            patch("engine.pipeline.FundamentalAgent") as MockFund,
            patch("engine.pipeline.FredProvider", side_effect=RuntimeError("No FRED API key")),
        ):
            mock_get_provider.return_value = MagicMock()

            mock_tech = MagicMock()
            mock_tech.name = "TechnicalAgent"
            mock_tech.analyze = AsyncMock(return_value=tech_out)
            MockTech.return_value = mock_tech

            mock_fund = MagicMock()
            mock_fund.name = "FundamentalAgent"
            mock_fund.analyze = AsyncMock(return_value=fund_out)
            MockFund.return_value = mock_fund

            pipeline = AnalysisPipeline()
            result = await pipeline.analyze_ticker("AAPL", "stock")

        assert isinstance(result, AggregatedSignal)
        # Only 2 agents (Technical + Fundamental)
        assert len(result.agent_signals) == 2
        agent_names = {o.agent_name for o in result.agent_signals}
        assert "TechnicalAgent" in agent_names
        assert "FundamentalAgent" in agent_names
        # Warning mentions MacroAgent was skipped
        assert any("MacroAgent skipped" in w for w in result.warnings)
