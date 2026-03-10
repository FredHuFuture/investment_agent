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
