"""Tests for Task 008: SignalAggregator.

All tests mock agent outputs directly — no real agents or network calls.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.models import AgentOutput, Regime, Signal
from engine.aggregator import AggregatedSignal, SignalAggregator


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_output(
    agent_name: str,
    signal: Signal,
    confidence: float,
    metrics: dict | None = None,
) -> AgentOutput:
    """Quickly construct an AgentOutput for testing."""
    return AgentOutput(
        agent_name=agent_name,
        ticker="TEST",
        signal=signal,
        confidence=confidence,
        reasoning=f"{agent_name} says {signal.value}",
        metrics=metrics or {},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSignalAggregator:
    def setup_method(self) -> None:
        self.agg = SignalAggregator()

    # 1. All agents BUY → final BUY, high confidence
    def test_all_buy_produces_buy(self) -> None:
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 72),
            _make_output("FundamentalAgent", Signal.BUY, 65),
            _make_output("MacroAgent", Signal.BUY, 58),
        ]
        result = self.agg.aggregate(outputs, "AAPL", "stock")

        assert result.final_signal == Signal.BUY
        assert result.final_confidence >= 80
        assert result.metrics["raw_score"] > 0.3
        assert result.metrics["buy_count"] == 3
        assert result.metrics["consensus_score"] == pytest.approx(1.0)

    # 2. All agents SELL → final SELL
    def test_all_sell_produces_sell(self) -> None:
        outputs = [
            _make_output("TechnicalAgent", Signal.SELL, 70),
            _make_output("FundamentalAgent", Signal.SELL, 75),
            _make_output("MacroAgent", Signal.SELL, 60),
        ]
        result = self.agg.aggregate(outputs, "AAPL", "stock")

        assert result.final_signal == Signal.SELL
        assert result.metrics["raw_score"] < -0.3
        assert result.metrics["sell_count"] == 3

    # 3. Mixed signals (BUY + SELL + HOLD) → HOLD + low consensus warning
    def test_mixed_produces_hold(self) -> None:
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 70),
            _make_output("FundamentalAgent", Signal.SELL, 70),
            _make_output("MacroAgent", Signal.HOLD, 70),
        ]
        result = self.agg.aggregate(outputs, "AAPL", "stock")

        assert result.final_signal == Signal.HOLD
        # With weights 0.30/0.45/0.25, BUY(Tech) and SELL(Fund) don't cancel:
        # raw_score = (0.30*0.70 - 0.45*0.70) / (0.30+0.45+0.25)*0.70 = -0.15
        assert abs(result.metrics["raw_score"]) < 0.3  # still within HOLD range
        assert any("Low agent consensus" in w for w in result.warnings)

    # 4. Two BUY + one HOLD → final BUY (weighted sum exceeds +0.3)
    def test_two_buy_one_hold(self) -> None:
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 70),
            _make_output("FundamentalAgent", Signal.BUY, 65),
            _make_output("MacroAgent", Signal.HOLD, 70),
        ]
        result = self.agg.aggregate(outputs, "AAPL", "stock")

        # raw_score ≈ 0.4725 / 0.6825 ≈ 0.692 → BUY
        assert result.final_signal == Signal.BUY
        assert result.metrics["raw_score"] > 0.3
        assert result.metrics["buy_count"] == 2
        assert result.metrics["hold_count"] == 1

    # 5. Confidence weighting: high-confidence BUY should dominate low-confidence SELL
    def test_confidence_weighting(self) -> None:
        # Technical=BUY(80), Fundamental=SELL(30), Macro=HOLD(60)
        # Technical effective = 0.30 * 0.80 = 0.240 >> Fundamental effective = 0.45 * 0.30 = 0.135
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 80),
            _make_output("FundamentalAgent", Signal.SELL, 30),
            _make_output("MacroAgent", Signal.HOLD, 60),
        ]
        result = self.agg.aggregate(outputs, "AAPL", "stock")

        # BUY side wins because Technical has much higher confidence
        # raw_score positive but may not exceed BUY threshold (0.30) with asymmetric weights
        assert result.metrics["raw_score"] > 0.0
        # Technical's weighted_contribution should be larger in absolute value than Fundamental's
        tech_contrib = abs(result.metrics["agent_contributions"]["TechnicalAgent"]["weighted_contribution"])
        fund_contrib = abs(result.metrics["agent_contributions"]["FundamentalAgent"]["weighted_contribution"])
        assert tech_contrib > fund_contrib

    # 6. Crypto weights: FundamentalAgent ignored (not in btc weights)
    def test_crypto_weights(self) -> None:
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 70),
            _make_output("MacroAgent", Signal.HOLD, 60),
            _make_output("FundamentalAgent", Signal.BUY, 80),  # should be ignored for btc
        ]
        result = self.agg.aggregate(outputs, "BTC", "btc")

        # FundamentalAgent has no weight for btc → excluded from contributions
        assert "FundamentalAgent" not in result.metrics["agent_contributions"]
        # Only Technical + Macro used; crypto weights applied
        assert "TechnicalAgent" in result.metrics["agent_contributions"]
        assert "MacroAgent" in result.metrics["agent_contributions"]
        # Verify btc weights used
        weights_used = result.metrics["weights_used"]
        assert weights_used.get("TechnicalAgent") == pytest.approx(0.45)
        assert weights_used.get("MacroAgent") == pytest.approx(0.55)

    # 7. Consensus score calculation accuracy
    def test_consensus_score_calculation(self) -> None:
        # 3/3 agree → 1.0
        all_buy = [
            _make_output("TechnicalAgent", Signal.BUY, 70),
            _make_output("FundamentalAgent", Signal.BUY, 70),
            _make_output("MacroAgent", Signal.BUY, 70),
        ]
        r1 = self.agg.aggregate(all_buy, "X", "stock")
        assert r1.metrics["consensus_score"] == pytest.approx(1.0)

        # 2/3 agree → 0.667
        two_buy_one_sell = [
            _make_output("TechnicalAgent", Signal.BUY, 70),
            _make_output("FundamentalAgent", Signal.BUY, 70),
            _make_output("MacroAgent", Signal.SELL, 70),
        ]
        r2 = self.agg.aggregate(two_buy_one_sell, "X", "stock")
        assert r2.metrics["consensus_score"] == pytest.approx(2 / 3, rel=1e-3)

        # 1/3 agree → 0.333
        all_diff = [
            _make_output("TechnicalAgent", Signal.BUY, 70),
            _make_output("FundamentalAgent", Signal.SELL, 70),
            _make_output("MacroAgent", Signal.HOLD, 70),
        ]
        r3 = self.agg.aggregate(all_diff, "X", "stock")
        assert r3.metrics["consensus_score"] == pytest.approx(1 / 3, rel=1e-3)

    # 8. Low consensus reduces confidence by 20%
    def test_low_consensus_reduces_confidence(self) -> None:
        # All different signals → consensus_score = 1/3 < 0.5
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 70),
            _make_output("FundamentalAgent", Signal.SELL, 70),
            _make_output("MacroAgent", Signal.HOLD, 70),
        ]
        result = self.agg.aggregate(outputs, "AAPL", "stock")

        # Confidence should be reduced (penalty applied)
        assert result.final_confidence < 70.0  # without penalty: 70, with 0.8x < 70
        assert any("Low agent consensus" in w for w in result.warnings)

    # 9. Empty outputs → HOLD fallback with warning
    def test_empty_outputs_fallback(self) -> None:
        result = self.agg.aggregate([], "AAPL", "stock")

        assert result.final_signal == Signal.HOLD
        assert result.final_confidence == pytest.approx(30.0)
        assert result.regime is None
        assert any("No agent produced a signal" in w for w in result.warnings)
        assert result.metrics["buy_count"] == 0
        assert result.metrics["sell_count"] == 0
        assert result.metrics["hold_count"] == 0

    # 10. Regime extraction from MacroAgent metrics
    def test_regime_extraction(self) -> None:
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 70),
            _make_output("MacroAgent", Signal.BUY, 65, metrics={"regime": "RISK_ON", "net_score": 32}),
        ]
        result = self.agg.aggregate(outputs, "AAPL", "stock")

        assert result.regime == Regime.RISK_ON
        assert result.metrics["regime"] == "RISK_ON"
        # Net score should appear in reasoning
        assert "RISK_ON" in result.reasoning

    # 11. Partial agent failure via pipeline → only valid outputs used, warning present
    @pytest.mark.asyncio
    async def test_partial_agent_failure(self) -> None:
        from engine.pipeline import AnalysisPipeline

        valid_tech = _make_output("TechnicalAgent", Signal.BUY, 70)
        valid_fund = _make_output("FundamentalAgent", Signal.BUY, 65)

        with (
            patch("engine.pipeline.get_provider") as mock_get_provider,
            patch("engine.pipeline.TechnicalAgent") as MockTech,
            patch("engine.pipeline.FundamentalAgent") as MockFund,
            patch("engine.pipeline.FredProvider"),
            patch("engine.pipeline.YFinanceProvider"),
            patch("engine.pipeline.MacroAgent") as MockMacro,
        ):
            # Configure mock providers
            mock_get_provider.return_value = MagicMock()

            # TechnicalAgent and FundamentalAgent return valid outputs
            mock_tech_inst = MagicMock()
            mock_tech_inst.name = "TechnicalAgent"
            mock_tech_inst.analyze = AsyncMock(return_value=valid_tech)
            MockTech.return_value = mock_tech_inst

            mock_fund_inst = MagicMock()
            mock_fund_inst.name = "FundamentalAgent"
            mock_fund_inst.analyze = AsyncMock(return_value=valid_fund)
            MockFund.return_value = mock_fund_inst

            # MacroAgent raises an exception
            mock_macro_inst = MagicMock()
            mock_macro_inst.name = "MacroAgent"
            mock_macro_inst.analyze = AsyncMock(side_effect=RuntimeError("FRED unavailable"))
            MockMacro.return_value = mock_macro_inst

            pipeline = AnalysisPipeline()
            result = await pipeline.analyze_ticker("AAPL", "stock")

        # Should still produce a signal from 2 valid agents
        assert result.final_signal in {Signal.BUY, Signal.HOLD, Signal.SELL}
        assert len(result.agent_signals) == 2
        # Warning should mention the failed agent
        assert any("MacroAgent failed" in w for w in result.warnings)

    # 12. to_dict() produces complete, JSON-serializable output
    def test_aggregated_signal_to_dict(self) -> None:
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 72),
            _make_output("FundamentalAgent", Signal.BUY, 65),
            _make_output(
                "MacroAgent", Signal.BUY, 58, metrics={"regime": "RISK_ON", "net_score": 20}
            ),
        ]
        result = self.agg.aggregate(outputs, "AAPL", "stock")
        d = result.to_dict()

        # All required top-level keys
        required_keys = {
            "ticker", "asset_type", "final_signal", "final_confidence",
            "regime", "agent_signals", "reasoning", "metrics", "warnings",
        }
        assert required_keys <= set(d.keys())

        # Values are the right types
        assert d["final_signal"] == "BUY"
        assert d["regime"] == "RISK_ON"
        assert isinstance(d["agent_signals"], list)
        assert len(d["agent_signals"]) == 3
        assert isinstance(d["metrics"], dict)
        assert isinstance(d["warnings"], list)

        # Must be JSON-serializable
        serialized = json.dumps(d)
        roundtripped = json.loads(serialized)
        assert roundtripped["final_signal"] == "BUY"
        assert roundtripped["ticker"] == "AAPL"
