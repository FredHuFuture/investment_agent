"""Tests for P0 prediction accuracy improvements.

Covers:
- #1 Confidence-weighted consensus
- #2 Data completeness downweighting
- #3 Signal accuracy tracker
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.models import AgentOutput, Signal
from engine.aggregator import SignalAggregator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_output(
    name: str,
    signal: Signal,
    confidence: float,
    data_completeness: float = 1.0,
) -> AgentOutput:
    return AgentOutput(
        agent_name=name,
        ticker="AAPL",
        signal=signal,
        confidence=confidence,
        reasoning="test",
        data_completeness=data_completeness,
    )


# ---------------------------------------------------------------------------
# #1 Confidence-weighted consensus
# ---------------------------------------------------------------------------

class TestConfidenceWeightedConsensus:
    def test_all_agree_consensus_is_one(self) -> None:
        agg = SignalAggregator()
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 80),
            _make_output("FundamentalAgent", Signal.BUY, 60),
        ]
        result = agg.aggregate(outputs, "AAPL", "stock")
        assert result.metrics["consensus_score"] == pytest.approx(1.0)

    def test_high_confidence_minority_raises_consensus(self) -> None:
        """A 95%-confidence BUY + a 35%-confidence SELL should have higher
        consensus than two 50% signals disagreeing."""
        agg = SignalAggregator()
        outputs_strong = [
            _make_output("TechnicalAgent", Signal.BUY, 95),
            _make_output("FundamentalAgent", Signal.SELL, 35),
        ]
        outputs_even = [
            _make_output("TechnicalAgent", Signal.BUY, 50),
            _make_output("FundamentalAgent", Signal.SELL, 50),
        ]
        r1 = agg.aggregate(outputs_strong, "AAPL", "stock")
        r2 = agg.aggregate(outputs_even, "AAPL", "stock")
        # Strong BUY should give higher consensus (95/130 > 50/100)
        assert r1.metrics["consensus_score"] > r2.metrics["consensus_score"]

    def test_vote_counts_still_in_metrics(self) -> None:
        agg = SignalAggregator()
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 70),
            _make_output("FundamentalAgent", Signal.SELL, 50),
            _make_output("MacroAgent", Signal.HOLD, 60),
        ]
        result = agg.aggregate(outputs, "AAPL", "stock")
        assert result.metrics["buy_count"] == 1
        assert result.metrics["sell_count"] == 1
        assert result.metrics["hold_count"] == 1


# ---------------------------------------------------------------------------
# #2 Data completeness downweighting
# ---------------------------------------------------------------------------

class TestDataCompletenessDownweighting:
    def test_low_completeness_reduces_effective_weight(self) -> None:
        """Agent with 25% data completeness should have much less influence."""
        agg = SignalAggregator()
        # FundamentalAgent has only 2/8 metrics → completeness 0.25
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 70, data_completeness=1.0),
            _make_output("FundamentalAgent", Signal.SELL, 70, data_completeness=0.25),
        ]
        result = agg.aggregate(outputs, "AAPL", "stock")
        # With completeness downweighting, Technical's weight is boosted and
        # Fundamental's is reduced, so the signal should lean toward BUY
        assert result.final_signal == Signal.BUY

    def test_all_complete_unchanged(self) -> None:
        """When all agents have completeness=1.0, behavior identical to before."""
        agg = SignalAggregator()
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 70, data_completeness=1.0),
            _make_output("FundamentalAgent", Signal.BUY, 65, data_completeness=1.0),
        ]
        result = agg.aggregate(outputs, "AAPL", "stock")
        assert result.final_signal == Signal.BUY

    def test_completeness_in_agent_contributions(self) -> None:
        agg = SignalAggregator()
        outputs = [
            _make_output("TechnicalAgent", Signal.BUY, 70, data_completeness=0.8),
        ]
        result = agg.aggregate(outputs, "AAPL", "stock")
        contrib = result.metrics["agent_contributions"]["TechnicalAgent"]
        assert contrib["data_completeness"] == 0.8

    def test_agent_output_default_completeness(self) -> None:
        out = AgentOutput(
            agent_name="Test", ticker="X", signal=Signal.HOLD,
            confidence=50, reasoning="test",
        )
        assert out.data_completeness == 1.0


# ---------------------------------------------------------------------------
# #3 Signal accuracy tracker (unit tests with mock DB)
# ---------------------------------------------------------------------------

class TestAccuracyTracker:
    @pytest.mark.asyncio
    async def test_empty_db_returns_empty_report(self, tmp_path: Path) -> None:
        import aiosqlite
        from engine.accuracy_tracker import AccuracyTracker

        db = tmp_path / "test.db"
        async with aiosqlite.connect(db) as conn:
            await conn.execute(
                """CREATE TABLE signal_history (
                    id INTEGER PRIMARY KEY, final_signal TEXT, final_confidence REAL,
                    regime TEXT, outcome TEXT, agent_signals_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            await conn.commit()

        tracker = AccuracyTracker(db_path=db)
        report = await tracker.calibration_report()
        assert report["resolved_count"] == 0
        assert report["overall_accuracy"] == 0.0

    @pytest.mark.asyncio
    async def test_basic_accuracy(self, tmp_path: Path) -> None:
        import aiosqlite
        from engine.accuracy_tracker import AccuracyTracker

        db = tmp_path / "test.db"
        async with aiosqlite.connect(db) as conn:
            await conn.execute(
                """CREATE TABLE signal_history (
                    id INTEGER PRIMARY KEY, final_signal TEXT, final_confidence REAL,
                    regime TEXT, outcome TEXT, agent_signals_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            agents_json = json.dumps([
                {"agent_name": "TechnicalAgent", "signal": "BUY", "confidence": 70},
            ])
            for i in range(10):
                outcome = "WIN" if i < 7 else "LOSS"
                await conn.execute(
                    "INSERT INTO signal_history (final_signal, final_confidence, regime, outcome, agent_signals_json) VALUES (?,?,?,?,?)",
                    ("BUY", 70, "RISK_ON", outcome, agents_json),
                )
            await conn.commit()

        tracker = AccuracyTracker(db_path=db)
        report = await tracker.calibration_report()
        assert report["resolved_count"] == 10
        assert report["overall_accuracy"] == pytest.approx(0.7)
        assert "TechnicalAgent" in report["accuracy_by_agent"]
