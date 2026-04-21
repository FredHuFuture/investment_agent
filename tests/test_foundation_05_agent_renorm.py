"""Tests for FOUND-05: SignalAggregator weight renormalization produces weights
summing to exactly 1.0 for every single-agent-disabled scenario across all
three supported asset types (stock / btc / eth).

Parametrized coverage:
  - stock: 4 agents × drop each → 4 parametrized cases
  - btc:   2 agents × drop each → 2 parametrized cases
  - eth:   2 agents × drop each → 2 parametrized cases
  Total parametrized: 8 cases (plus 4 regression tests = 12+ test items)

The existing SignalAggregator math (engine/aggregator.py lines 123-129) already
renormalizes correctly. This test suite exhaustively validates that invariant.
If any case fails, the aggregator math would need to be corrected in that task.
"""
from __future__ import annotations

import pytest

from agents.models import AgentOutput, Signal
from engine.aggregator import SignalAggregator


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _mk(
    name: str,
    signal: Signal = Signal.BUY,
    confidence: float = 60.0,
    data_completeness: float = 1.0,
) -> AgentOutput:
    """Build a minimal AgentOutput for aggregation testing."""
    return AgentOutput(
        agent_name=name,
        ticker="TEST",
        signal=signal,
        confidence=confidence,
        reasoning=f"{name} says {signal.value}",
        data_completeness=data_completeness,
    )


# Default agent names per asset class (mirrors aggregator.DEFAULT_WEIGHTS)
STOCK_AGENTS = ["TechnicalAgent", "FundamentalAgent", "MacroAgent", "SentimentAgent"]
BTC_AGENTS = ["CryptoAgent", "TechnicalAgent"]


# ---------------------------------------------------------------------------
# Test A: stock — parametrized, one agent missing per case (4 cases)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing", STOCK_AGENTS)
def test_stock_renormalizes_with_one_agent_missing(missing: str) -> None:
    """For stock, removing any single agent → remaining weights sum to 1.0."""
    agg = SignalAggregator()
    outputs = [_mk(a) for a in STOCK_AGENTS if a != missing]
    result = agg.aggregate(outputs, "AAPL", "stock")
    weights = result.metrics["weights_used"]
    total = sum(weights.values())
    assert total == pytest.approx(1.0, abs=1e-6), (
        f"stock missing={missing}: weights sum to {total} != 1.0 (weights={weights})"
    )
    # Confidence must not be crushed: 3 BUY agents @ 60% should yield >=50
    assert result.final_confidence >= 50.0, (
        f"stock missing={missing}: final_confidence={result.final_confidence} "
        f"(expected >=50 with 3 BUY@60 agents)"
    )


# ---------------------------------------------------------------------------
# Test B: btc — parametrized, one agent missing per case (2 cases)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing", BTC_AGENTS)
def test_btc_renormalizes_with_one_agent_missing(missing: str) -> None:
    """For btc, removing any single agent → remaining weights sum to 1.0."""
    agg = SignalAggregator()
    outputs = [_mk(a) for a in BTC_AGENTS if a != missing]
    result = agg.aggregate(outputs, "BTC-USD", "btc")
    weights = result.metrics["weights_used"]
    total = sum(weights.values())
    assert total == pytest.approx(1.0, abs=1e-6), (
        f"btc missing={missing}: weights sum to {total} (weights={weights})"
    )


# ---------------------------------------------------------------------------
# Test C: eth — parametrized, one agent missing per case (2 cases)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing", BTC_AGENTS)
def test_eth_renormalizes_with_one_agent_missing(missing: str) -> None:
    """For eth, removing any single agent → remaining weights sum to 1.0."""
    agg = SignalAggregator()
    outputs = [_mk(a) for a in BTC_AGENTS if a != missing]
    result = agg.aggregate(outputs, "ETH-USD", "eth")
    weights = result.metrics["weights_used"]
    total = sum(weights.values())
    assert total == pytest.approx(1.0, abs=1e-6), (
        f"eth missing={missing}: weights sum to {total} (weights={weights})"
    )


# ---------------------------------------------------------------------------
# Test D: empty agent outputs produce HOLD
# ---------------------------------------------------------------------------

def test_empty_agent_outputs_produce_hold() -> None:
    """aggregate([]) returns HOLD, weights_used={}, and the expected warning."""
    agg = SignalAggregator()
    result = agg.aggregate([], "AAPL", "stock")
    assert result.final_signal == Signal.HOLD
    assert "No agent produced a signal." in result.warnings
    assert result.metrics["weights_used"] == {}


# ---------------------------------------------------------------------------
# Test E: confidence not deflated by missing agent
# ---------------------------------------------------------------------------

def test_confidence_not_deflated_by_missing_agent() -> None:
    """3 BUY agents @ 100% confidence with SentimentAgent missing → final_confidence >= 60."""
    agg = SignalAggregator()
    outputs = [
        _mk(a, Signal.BUY, confidence=100.0)
        for a in ("TechnicalAgent", "FundamentalAgent", "MacroAgent")
    ]
    result = agg.aggregate(outputs, "AAPL", "stock")
    assert result.final_confidence >= 60.0, (
        f"confidence deflated to {result.final_confidence} when SentimentAgent missing"
    )


# ---------------------------------------------------------------------------
# Test F: data_completeness scales weight but sum stays 1.0
# ---------------------------------------------------------------------------

def test_data_completeness_scales_weight_but_sum_stays_one() -> None:
    """Halving TechnicalAgent completeness reduces its weight, but total stays 1.0."""
    agg = SignalAggregator()
    full_outputs = [_mk(a, data_completeness=1.0) for a in STOCK_AGENTS]
    half_outputs = [
        _mk("TechnicalAgent", data_completeness=0.5),
        _mk("FundamentalAgent", data_completeness=1.0),
        _mk("MacroAgent", data_completeness=1.0),
        _mk("SentimentAgent", data_completeness=1.0),
    ]

    r_full = agg.aggregate(full_outputs, "AAPL", "stock")
    r_half = agg.aggregate(half_outputs, "AAPL", "stock")

    # Both must sum to 1.0
    assert sum(r_full.metrics["weights_used"].values()) == pytest.approx(1.0, abs=1e-6)
    assert sum(r_half.metrics["weights_used"].values()) == pytest.approx(1.0, abs=1e-6)

    # TechnicalAgent's effective weight must be lower when completeness=0.5
    assert (
        r_half.metrics["weights_used"]["TechnicalAgent"]
        < r_full.metrics["weights_used"]["TechnicalAgent"]
    ), (
        "TechnicalAgent weight should decrease with data_completeness=0.5"
    )


# ---------------------------------------------------------------------------
# Test G: custom weights renormalize on missing agent
# ---------------------------------------------------------------------------

def test_custom_weights_renormalize_on_missing_agent() -> None:
    """With custom {Technical: 0.5, Fundamental: 0.5}, supplying only Technical → weight=1.0."""
    custom = {"stock": {"TechnicalAgent": 0.5, "FundamentalAgent": 0.5}}
    agg = SignalAggregator(weights=custom)
    outputs = [_mk("TechnicalAgent", Signal.BUY, confidence=80.0)]
    result = agg.aggregate(outputs, "AAPL", "stock")
    assert result.metrics["weights_used"]["TechnicalAgent"] == pytest.approx(1.0, abs=1e-6)
