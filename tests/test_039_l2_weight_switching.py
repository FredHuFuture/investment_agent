"""Tests for Sprint 14.2: L2 Adaptive Weight Switching (Regime-Based).

Tests cover:
1. aggregate_with_regime with no adjustments (baseline fallback)
2. Bull market (RISK_ON) adjustments boost FundamentalAgent
3. Bear market (RISK_OFF) adjustments boost MacroAgent
4. Re-normalization: weights must sum to 1.0 after adjustments
5. Missing regime data falls back to default weights
6. Integration: pipeline with regime detection wired in
7. Edge case: unknown regime type
8. Edge case: empty signals list
9. RegimeDetector with RISK_ON MacroAgent output
10. RegimeDetector with no MacroAgent present (falls back to NEUTRAL)
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from agents.models import AgentOutput, Regime, Signal
from engine.aggregator import SignalAggregator, AggregatedSignal
from engine.regime import (
    RegimeDetector,
    RegimeInfo,
    REGIME_WEIGHT_ADJUSTMENTS,
)


# ---------------------------------------------------------------------------
# Helpers
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


def _stock_outputs_all_buy() -> list[AgentOutput]:
    """Four agents all saying BUY with varying confidence."""
    return [
        _make_output("TechnicalAgent", Signal.BUY, 70),
        _make_output("FundamentalAgent", Signal.BUY, 80),
        _make_output("MacroAgent", Signal.BUY, 60, {"regime": "RISK_ON", "net_score": 3}),
        _make_output("SentimentAgent", Signal.BUY, 55),
    ]


def _stock_outputs_mixed() -> list[AgentOutput]:
    """Mixed signals: Fundamental BUY, Technical HOLD, Macro SELL, Sentiment HOLD."""
    return [
        _make_output("TechnicalAgent", Signal.HOLD, 50),
        _make_output("FundamentalAgent", Signal.BUY, 75),
        _make_output("MacroAgent", Signal.SELL, 65, {"regime": "RISK_OFF", "net_score": -2}),
        _make_output("SentimentAgent", Signal.HOLD, 45),
    ]


# ---------------------------------------------------------------------------
# Tests: aggregate_with_regime
# ---------------------------------------------------------------------------

class TestAggregateWithRegime:
    """Tests for SignalAggregator.aggregate_with_regime()."""

    def setup_method(self) -> None:
        self.agg = SignalAggregator()

    # 1. No regime adjustments -> identical to baseline aggregate()
    def test_no_adjustments_matches_baseline(self) -> None:
        outputs = _stock_outputs_all_buy()
        baseline = self.agg.aggregate(outputs, "TEST", "stock")
        result = self.agg.aggregate_with_regime(outputs, "TEST", "stock", regime_adjustments=None)

        assert result.final_signal == baseline.final_signal
        assert result.final_confidence == baseline.final_confidence
        assert result.metrics["raw_score"] == baseline.metrics["raw_score"]

    # 1b. Empty dict also falls back to baseline
    def test_empty_adjustments_matches_baseline(self) -> None:
        outputs = _stock_outputs_all_buy()
        baseline = self.agg.aggregate(outputs, "TEST", "stock")
        result = self.agg.aggregate_with_regime(outputs, "TEST", "stock", regime_adjustments={})

        assert result.final_signal == baseline.final_signal
        assert result.metrics["raw_score"] == baseline.metrics["raw_score"]

    # 2. RISK_ON adjustments: FundamentalAgent gets more weight
    def test_risk_on_boosts_fundamental(self) -> None:
        outputs = _stock_outputs_mixed()
        risk_on_adj = REGIME_WEIGHT_ADJUSTMENTS["RISK_ON"]

        result = self.agg.aggregate_with_regime(
            outputs, "TEST", "stock", regime_adjustments=risk_on_adj,
        )

        # The regime-adjusted weights should be stored in metrics
        assert "regime_adjusted_weights" in result.metrics
        adjusted_weights = result.metrics["regime_adjusted_weights"]

        # FundamentalAgent should have higher weight than default 0.40 (relative)
        # since its multiplier is 1.3 and others are lower
        assert adjusted_weights["FundamentalAgent"] > adjusted_weights["TechnicalAgent"]
        assert adjusted_weights["FundamentalAgent"] > adjusted_weights["MacroAgent"]

    # 3. RISK_OFF adjustments: MacroAgent gets more weight
    def test_risk_off_boosts_macro(self) -> None:
        outputs = _stock_outputs_mixed()
        risk_off_adj = REGIME_WEIGHT_ADJUSTMENTS["RISK_OFF"]

        result = self.agg.aggregate_with_regime(
            outputs, "TEST", "stock", regime_adjustments=risk_off_adj,
        )

        adjusted_weights = result.metrics["regime_adjusted_weights"]

        # MacroAgent multiplier is 1.4, FundamentalAgent is 0.8
        # Base: Macro=0.20 * 1.4 = 0.28, Fundamental=0.40 * 0.8 = 0.32
        # So Fundamental still higher in absolute, but Macro's relative share increased
        base_macro_ratio = 0.20 / (0.25 + 0.40 + 0.20 + 0.15)  # 0.20
        adjusted_macro_ratio = adjusted_weights["MacroAgent"]
        assert adjusted_macro_ratio > base_macro_ratio

    # 4. Re-normalization: weights must sum to 1.0
    def test_weights_sum_to_one_after_adjustments(self) -> None:
        outputs = _stock_outputs_all_buy()

        for regime_key in ("RISK_ON", "RISK_OFF", "NEUTRAL"):
            adjustments = REGIME_WEIGHT_ADJUSTMENTS[regime_key]
            result = self.agg.aggregate_with_regime(
                outputs, "TEST", "stock", regime_adjustments=adjustments,
            )

            if "regime_adjusted_weights" in result.metrics:
                total = sum(result.metrics["regime_adjusted_weights"].values())
                assert abs(total - 1.0) < 1e-9, (
                    f"Regime {regime_key}: weights sum to {total}, expected 1.0"
                )

    # 5. NEUTRAL adjustments (all 1.0) -> same weights as default
    def test_neutral_adjustments_preserve_defaults(self) -> None:
        outputs = _stock_outputs_all_buy()
        neutral_adj = REGIME_WEIGHT_ADJUSTMENTS["NEUTRAL"]

        # All multipliers are 1.0, so aggregate_with_regime should detect
        # this and fall back to standard aggregate().
        baseline = self.agg.aggregate(outputs, "TEST", "stock")
        result = self.agg.aggregate_with_regime(
            outputs, "TEST", "stock", regime_adjustments=neutral_adj,
        )

        # Since all multipliers are 1.0, aggregate_with_regime detects this
        # and delegates to aggregate() without adjustments.
        assert result.final_signal == baseline.final_signal
        assert result.metrics["raw_score"] == baseline.metrics["raw_score"]

    # 6. Edge case: empty signals list
    def test_empty_signals_returns_hold(self) -> None:
        result = self.agg.aggregate_with_regime(
            [], "TEST", "stock",
            regime_adjustments=REGIME_WEIGHT_ADJUSTMENTS["RISK_ON"],
        )
        # Empty outputs -> aggregate() returns HOLD with low confidence
        assert result.final_signal == Signal.HOLD
        assert result.final_confidence == 30.0

    # 7. Regime adjustments tag is stored in metrics
    def test_regime_adjustments_in_metrics(self) -> None:
        outputs = _stock_outputs_all_buy()
        adj = {"TechnicalAgent": 1.5, "FundamentalAgent": 0.5}

        result = self.agg.aggregate_with_regime(
            outputs, "TEST", "stock", regime_adjustments=adj,
        )

        assert result.metrics["regime_adjustments"] == adj

    # 8. Custom extreme multipliers
    def test_extreme_multiplier_still_normalizes(self) -> None:
        outputs = _stock_outputs_all_buy()
        # Give one agent 10x, others 0.1x
        adj = {
            "TechnicalAgent": 10.0,
            "FundamentalAgent": 0.1,
            "MacroAgent": 0.1,
            "SentimentAgent": 0.1,
        }

        result = self.agg.aggregate_with_regime(
            outputs, "TEST", "stock", regime_adjustments=adj,
        )

        adjusted_weights = result.metrics["regime_adjusted_weights"]
        total = sum(adjusted_weights.values())
        assert abs(total - 1.0) < 1e-9

        # TechnicalAgent should dominate
        assert adjusted_weights["TechnicalAgent"] > 0.9


# ---------------------------------------------------------------------------
# Tests: RegimeDetector
# ---------------------------------------------------------------------------

class TestRegimeDetector:
    """Tests for RegimeDetector."""

    def setup_method(self) -> None:
        self.detector = RegimeDetector()

    def test_detect_risk_on_from_macro_agent(self) -> None:
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 70),
            _make_output("MacroAgent", Signal.BUY, 60, {"regime": "RISK_ON", "net_score": 3}),
        ]
        info = self.detector.detect(outputs)

        assert info.regime == Regime.RISK_ON
        assert info.source == "macro_agent"
        assert info.adjustments["FundamentalAgent"] == 1.3  # RISK_ON multiplier

    def test_detect_risk_off_from_macro_agent(self) -> None:
        outputs = [
            _make_output("MacroAgent", Signal.SELL, 65, {"regime": "RISK_OFF", "net_score": -2}),
        ]
        info = self.detector.detect(outputs)

        assert info.regime == Regime.RISK_OFF
        assert info.adjustments["MacroAgent"] == 1.4  # RISK_OFF multiplier
        assert info.metadata["macro_net_score"] == -2

    def test_detect_neutral_when_no_macro_agent(self) -> None:
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 70),
            _make_output("FundamentalAgent", Signal.HOLD, 50),
        ]
        info = self.detector.detect(outputs)

        assert info.regime == Regime.NEUTRAL
        # All NEUTRAL multipliers are 1.0
        for v in info.adjustments.values():
            assert v == 1.0

    def test_detect_neutral_when_regime_missing(self) -> None:
        # MacroAgent present but no regime in metrics
        outputs = [
            _make_output("MacroAgent", Signal.HOLD, 50, {"net_score": 0}),
        ]
        info = self.detector.detect(outputs)

        assert info.regime == Regime.NEUTRAL

    def test_detect_unknown_regime_falls_back_to_neutral(self) -> None:
        # MacroAgent has an invalid regime string
        outputs = [
            _make_output("MacroAgent", Signal.HOLD, 50, {"regime": "UNKNOWN_REGIME"}),
        ]
        info = self.detector.detect(outputs)

        assert info.regime == Regime.NEUTRAL

    def test_detect_empty_outputs(self) -> None:
        info = self.detector.detect([])

        assert info.regime == Regime.NEUTRAL
        assert info.adjustments == REGIME_WEIGHT_ADJUSTMENTS["NEUTRAL"]

    def test_get_adjustments_legacy_returns_copy(self) -> None:
        adj1 = self.detector.get_adjustments_legacy(Regime.RISK_ON)
        adj2 = self.detector.get_adjustments_legacy(Regime.RISK_ON)
        # Should be equal but not the same object
        assert adj1 == adj2
        assert adj1 is not adj2
        # Mutating one should not affect the other
        adj1["TechnicalAgent"] = 999.0
        assert adj2["TechnicalAgent"] != 999.0

    def test_custom_adjustments(self) -> None:
        custom = {
            "RISK_ON": {"TechnicalAgent": 2.0, "FundamentalAgent": 0.5},
            "NEUTRAL": {"TechnicalAgent": 1.0, "FundamentalAgent": 1.0},
        }
        detector = RegimeDetector(custom_adjustments=custom)
        outputs = [
            _make_output("MacroAgent", Signal.BUY, 60, {"regime": "RISK_ON"}),
        ]
        info = detector.detect(outputs)
        assert info.adjustments["TechnicalAgent"] == 2.0
        assert info.adjustments["FundamentalAgent"] == 0.5


# ---------------------------------------------------------------------------
# Tests: RegimeInfo
# ---------------------------------------------------------------------------

class TestRegimeInfo:
    def test_to_dict(self) -> None:
        info = RegimeInfo(
            regime=Regime.RISK_ON,
            adjustments={"TechnicalAgent": 1.1},
            source="macro_agent",
            metadata={"macro_net_score": 3},
        )
        d = info.to_dict()
        assert d["regime"] == "RISK_ON"
        assert d["adjustments"] == {"TechnicalAgent": 1.1}
        assert d["source"] == "macro_agent"
        assert d["metadata"]["macro_net_score"] == 3


# ---------------------------------------------------------------------------
# Tests: Pipeline integration (mocked agents)
# ---------------------------------------------------------------------------

class TestPipelineRegimeIntegration:
    """Integration test: pipeline wires regime detection into aggregation."""

    def test_pipeline_stores_regime_info_in_metrics(self) -> None:
        """Verify that the pipeline stores regime_info in the signal metrics
        when regime detection is available."""
        # We test the aggregator + regime detector directly since
        # the full pipeline requires real data providers.
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 70),
            _make_output("FundamentalAgent", Signal.BUY, 80),
            _make_output("MacroAgent", Signal.BUY, 60, {"regime": "RISK_ON", "net_score": 3}),
        ]

        # Simulate what the pipeline does:
        detector = RegimeDetector()
        regime_info = detector.detect(outputs)

        aggregator = SignalAggregator()
        regime_adjustments = None
        if any(v != 1.0 for v in regime_info.adjustments.values()):
            regime_adjustments = regime_info.adjustments

        if regime_adjustments is not None:
            signal = aggregator.aggregate_with_regime(
                outputs, "AAPL", "stock",
                regime_adjustments=regime_adjustments,
            )
        else:
            signal = aggregator.aggregate(outputs, "AAPL", "stock")

        signal.metrics["regime_info"] = regime_info.to_dict()

        # Verify regime info is stored
        assert "regime_info" in signal.metrics
        assert signal.metrics["regime_info"]["regime"] == "RISK_ON"
        assert "regime_adjusted_weights" in signal.metrics

    def test_pipeline_risk_off_shifts_weights(self) -> None:
        """RISK_OFF regime should shift weight toward MacroAgent."""
        outputs = [
            _make_output("TechnicalAgent", Signal.HOLD, 50),
            _make_output("FundamentalAgent", Signal.HOLD, 50),
            _make_output("MacroAgent", Signal.SELL, 80, {"regime": "RISK_OFF", "net_score": -4}),
            _make_output("SentimentAgent", Signal.SELL, 60),
        ]

        detector = RegimeDetector()
        regime_info = detector.detect(outputs)
        assert regime_info.regime == Regime.RISK_OFF

        aggregator = SignalAggregator()

        # Baseline (no regime adjustments)
        baseline = aggregator.aggregate(outputs, "SPY", "stock")
        baseline_score = baseline.metrics["raw_score"]

        # With regime adjustments (MacroAgent boosted in RISK_OFF)
        adjusted = aggregator.aggregate_with_regime(
            outputs, "SPY", "stock",
            regime_adjustments=regime_info.adjustments,
        )
        adjusted_score = adjusted.metrics["raw_score"]

        # Since MacroAgent is SELL with boosted weight, the adjusted score
        # should be more negative than baseline.
        assert adjusted_score < baseline_score

    def test_pipeline_neutral_regime_no_adjustment(self) -> None:
        """NEUTRAL regime should produce identical results to baseline."""
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 70),
            _make_output("FundamentalAgent", Signal.BUY, 80),
            _make_output("MacroAgent", Signal.BUY, 60, {"regime": "NEUTRAL", "net_score": 0}),
        ]

        detector = RegimeDetector()
        regime_info = detector.detect(outputs)
        assert regime_info.regime == Regime.NEUTRAL

        # All adjustments should be 1.0
        assert all(v == 1.0 for v in regime_info.adjustments.values())

        # So aggregate_with_regime should fall back to aggregate()
        aggregator = SignalAggregator()
        baseline = aggregator.aggregate(outputs, "TEST", "stock")
        result = aggregator.aggregate_with_regime(
            outputs, "TEST", "stock",
            regime_adjustments=regime_info.adjustments,
        )

        assert result.final_signal == baseline.final_signal
        assert result.metrics["raw_score"] == baseline.metrics["raw_score"]
