from __future__ import annotations

import asyncio
import json

from agents.models import AgentOutput, Regime, Signal
from cli.analyze_cli import _run_analysis
from engine.aggregator import AggregatedSignal
from engine.pipeline import AnalysisPipeline


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


def test_e2e_stock_analysis(capsys, monkeypatch) -> None:
    signal = AggregatedSignal(
        ticker="AAPL",
        asset_type="stock",
        final_signal=Signal.BUY,
        final_confidence=72.0,
        regime=Regime.RISK_ON,
        agent_signals=[
            _make_output("TechnicalAgent", Signal.BUY, 72.0),
            _make_output("FundamentalAgent", Signal.BUY, 65.0),
            _make_output("MacroAgent", Signal.BUY, 58.0),
        ],
        reasoning="Combined",
        warnings=[],
    )

    async def _fake_analyze(self, ticker: str, asset_type: str):
        return signal

    monkeypatch.setattr(AnalysisPipeline, "analyze_ticker", _fake_analyze)

    asyncio.run(_run_analysis("AAPL", "stock", json_output=False))
    output = capsys.readouterr().out

    assert "ANALYSIS REPORT" in output
    assert "AAPL" in output
    assert "BUY" in output
    assert "SIGNAL" in output


def test_e2e_crypto_analysis(capsys, monkeypatch) -> None:
    signal = AggregatedSignal(
        ticker="BTC",
        asset_type="btc",
        final_signal=Signal.BUY,
        final_confidence=65.0,
        regime=Regime.RISK_ON,
        agent_signals=[
            _make_output("TechnicalAgent", Signal.BUY, 68.0, ticker="BTC"),
            _make_output("MacroAgent", Signal.BUY, 62.0, ticker="BTC"),
        ],
        reasoning="Crypto",
        warnings=[],
    )

    async def _fake_analyze(self, ticker: str, asset_type: str):
        return signal

    monkeypatch.setattr(AnalysisPipeline, "analyze_ticker", _fake_analyze)

    asyncio.run(_run_analysis("BTC", "btc", json_output=False))
    output = capsys.readouterr().out

    assert "BTC" in output
    assert "btc" in output
    assert "Fundamental" not in output


def test_e2e_json_output(capsys, monkeypatch) -> None:
    signal = AggregatedSignal(
        ticker="MSFT",
        asset_type="stock",
        final_signal=Signal.BUY,
        final_confidence=70.0,
        regime=Regime.RISK_ON,
        agent_signals=[
            _make_output("TechnicalAgent", Signal.BUY, 70.0, ticker="MSFT"),
        ],
        reasoning="Json output",
        warnings=[],
    )

    async def _fake_analyze(self, ticker: str, asset_type: str):
        return signal

    monkeypatch.setattr(AnalysisPipeline, "analyze_ticker", _fake_analyze)

    asyncio.run(_run_analysis("MSFT", "stock", json_output=True))
    output = capsys.readouterr().out

    data = json.loads(output)
    assert data["ticker"] == "MSFT"


def test_e2e_pipeline_with_warnings(capsys, monkeypatch) -> None:
    signal = AggregatedSignal(
        ticker="AAPL",
        asset_type="stock",
        final_signal=Signal.HOLD,
        final_confidence=45.0,
        regime=Regime.NEUTRAL,
        agent_signals=[
            _make_output("TechnicalAgent", Signal.HOLD, 45.0),
        ],
        reasoning="Warnings",
        warnings=["MacroAgent skipped"],
    )

    async def _fake_analyze(self, ticker: str, asset_type: str):
        return signal

    monkeypatch.setattr(AnalysisPipeline, "analyze_ticker", _fake_analyze)

    asyncio.run(_run_analysis("AAPL", "stock", json_output=False))
    output = capsys.readouterr().out

    assert "MacroAgent skipped" in output
