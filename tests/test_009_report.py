from __future__ import annotations

import json

from agents.models import AgentOutput, Regime, Signal
from cli.report import format_analysis_json, format_analysis_report
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


def test_format_report_buy_signal() -> None:
    signal = AggregatedSignal(
        ticker="AAPL",
        asset_type="stock",
        final_signal=Signal.BUY,
        final_confidence=72.4,
        regime=Regime.RISK_ON,
        agent_signals=[
            _make_output(
                "TechnicalAgent",
                Signal.BUY,
                72.0,
                metrics={
                    "rsi_14": 42.3,
                    "trend_score": 12.0,
                    "momentum_score": 8.0,
                    "volatility_score": -4.0,
                },
            ),
            _make_output(
                "FundamentalAgent",
                Signal.BUY,
                65.0,
                metrics={
                    "pe_trailing": 18.2,
                    "roe": 0.351,
                    "revenue_growth": 0.124,
                    "debt_equity": 0.42,
                },
            ),
            _make_output(
                "MacroAgent",
                Signal.BUY,
                58.0,
                metrics={
                    "regime": "RISK_ON",
                    "vix_current": 14.2,
                    "yield_curve_spread": 1.2,
                    "net_score": 12.0,
                },
            ),
        ],
        reasoning="Combined reasoning",
        warnings=[],
    )

    output = format_analysis_report(signal)

    assert "BUY" in output
    assert "AAPL" in output
    assert "stock" in output
    assert "RISK_ON" in output
    assert "Technical" in output
    assert "Fundamental" in output
    assert "Macro" in output
    assert "WARNINGS:" in output


def test_format_report_hold_with_warnings() -> None:
    signal = AggregatedSignal(
        ticker="AAPL",
        asset_type="stock",
        final_signal=Signal.HOLD,
        final_confidence=45.0,
        regime=Regime.NEUTRAL,
        agent_signals=[],
        reasoning="Consensus unclear",
        warnings=["Low agent consensus"],
    )

    output = format_analysis_report(signal)

    assert "HOLD" in output
    assert "Low agent consensus" in output
    assert "(none)" not in output


def test_format_report_missing_metrics() -> None:
    signal = AggregatedSignal(
        ticker="AAPL",
        asset_type="stock",
        final_signal=Signal.BUY,
        final_confidence=70.0,
        regime=Regime.RISK_ON,
        agent_signals=[
            _make_output("TechnicalAgent", Signal.BUY, 70.0, metrics={}),
        ],
        reasoning="Ok",
        warnings=[],
    )

    output = format_analysis_report(signal)

    assert "(no detail)" in output


def test_format_json_roundtrip() -> None:
    signal = AggregatedSignal(
        ticker="AAPL",
        asset_type="stock",
        final_signal=Signal.BUY,
        final_confidence=75.0,
        regime=Regime.RISK_ON,
        agent_signals=[
            _make_output("TechnicalAgent", Signal.BUY, 70.0),
        ],
        reasoning="json test",
        warnings=[],
    )

    output = format_analysis_json(signal)
    data = json.loads(output)

    assert data["final_signal"] == "BUY"


# ---------------------------------------------------------------------------
# Task 014.5 -- Detail mode tests
# ---------------------------------------------------------------------------

def _make_full_signal() -> AggregatedSignal:
    """Build an AggregatedSignal with rich metrics for detail mode tests."""
    return AggregatedSignal(
        ticker="AAPL",
        asset_type="stock",
        final_signal=Signal.BUY,
        final_confidence=72.0,
        regime=Regime.RISK_ON,
        agent_signals=[
            _make_output(
                "TechnicalAgent",
                Signal.BUY,
                72.0,
                metrics={
                    "trend_score": 12.0,
                    "momentum_score": 8.0,
                    "volatility_score": -4.0,
                    "rsi_14": 42.3,
                    "sma_20": 182.30,
                    "sma_50": 178.50,
                    "sma_200": 165.20,
                    "macd_line": 1.23,
                    "macd_signal": 0.91,
                    "macd_histogram": 0.32,
                    "volume_ratio": 1.12,
                    "atr_14": 3.45,
                },
            ),
            _make_output(
                "FundamentalAgent",
                Signal.BUY,
                65.0,
                metrics={
                    "pe_trailing": 18.2,
                    "pe_forward": 16.5,
                    "roe": 0.351,
                    "revenue_growth": 0.124,
                    "debt_equity": 0.42,
                    "profit_margin": 0.245,
                },
            ),
            _make_output(
                "MacroAgent",
                Signal.BUY,
                58.0,
                metrics={
                    "regime": "RISK_ON",
                    "vix_current": 14.2,
                    "treasury_10y": 4.25,
                    "yield_curve_spread": 1.2,
                    "net_score": 12.0,
                },
            ),
        ],
        reasoning="Combined reasoning",
        metrics={
            "raw_score": 0.452,
            "consensus_score": 1.0,
            "buy_count": 3,
            "sell_count": 0,
            "hold_count": 0,
            "weights_used": {
                "TechnicalAgent": 0.35,
                "FundamentalAgent": 0.35,
                "MacroAgent": 0.30,
            },
            "agent_contributions": {
                "TechnicalAgent": {
                    "signal": "BUY",
                    "confidence": 72.0,
                    "weighted_contribution": 0.2520,
                },
                "FundamentalAgent": {
                    "signal": "BUY",
                    "confidence": 65.0,
                    "weighted_contribution": 0.2275,
                },
                "MacroAgent": {
                    "signal": "BUY",
                    "confidence": 58.0,
                    "weighted_contribution": 0.1740,
                },
            },
        },
        warnings=[],
    )


def test_detail_mode_shows_all_metrics() -> None:
    """Detail mode exposes indicator values absent from the standard report."""
    signal = _make_full_signal()

    detail_output = format_analysis_report(signal, detail=True)
    standard_output = format_analysis_report(signal)

    # Technical indicators visible in detail but NOT standard
    assert "42.3" in detail_output           # RSI
    assert "182.30" in detail_output         # SMA 20
    assert "1.23" in detail_output           # MACD line
    assert "3.45" in detail_output           # ATR

    # Fundamental indicators
    assert "18.2" in detail_output           # P/E trailing
    assert "16.5" in detail_output           # P/E forward

    # Macro indicators
    assert "14.2" in detail_output           # VIX
    assert "4.25" in detail_output           # Treasury 10Y

    # Dotted separators present in detail mode
    assert "." * 20 in detail_output

    # Weight contribution math present
    assert "0.35" in detail_output
    assert "contribution" in detail_output

    # Standard mode does NOT show these deep indicators
    assert "182.30" not in standard_output
    assert "contribution" not in standard_output


def test_detail_mode_shows_reasoning() -> None:
    """Agent reasoning string appears in detail mode but not standard mode."""
    signal = _make_full_signal()
    unique_reasoning = "Unique technical reasoning text xyz"
    signal.agent_signals[0].reasoning = unique_reasoning

    detail_output = format_analysis_report(signal, detail=True)
    standard_output = format_analysis_report(signal)

    # Reasoning visible in detail mode with "> " prefix
    assert unique_reasoning in detail_output
    assert "> " in detail_output

    # Reasoning NOT in standard one-liner
    assert unique_reasoning not in standard_output


def test_detail_mode_shows_aggregation_math() -> None:
    """AGGREGATION DETAIL section appears with weights, score, and consensus."""
    signal = _make_full_signal()
    output = format_analysis_report(signal, detail=True)

    assert "AGGREGATION DETAIL" in output
    assert "Weights:" in output
    assert "Raw Score:" in output
    assert "Consensus:" in output
    assert "Consensus Adj:" in output
    assert "Final:" in output
    # Threshold hint present
    assert "+/-0.30" in output


def test_standard_mode_unchanged() -> None:
    """format_analysis_report(signal) is identical with detail=False -- regression guard."""
    signal = AggregatedSignal(
        ticker="AAPL",
        asset_type="stock",
        final_signal=Signal.BUY,
        final_confidence=72.4,
        regime=Regime.RISK_ON,
        agent_signals=[
            _make_output(
                "TechnicalAgent",
                Signal.BUY,
                72.0,
                metrics={"rsi_14": 42.3, "trend_score": 12.0},
            ),
        ],
        reasoning="ok",
        warnings=[],
    )

    default_output = format_analysis_report(signal)
    explicit_false_output = format_analysis_report(signal, detail=False)

    # Both calls produce identical output
    assert default_output == explicit_false_output

    # Detail-specific markers absent from standard output
    assert "AGGREGATION DETAIL" not in default_output
    assert "> " not in default_output
    assert "contribution" not in default_output
