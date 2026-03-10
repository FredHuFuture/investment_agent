"""Tests for Task 011: SignalTracker — accuracy stats, calibration, agent performance."""
from __future__ import annotations

import json
from pathlib import Path

import aiosqlite
import pytest

from db.database import init_db
from tracking.store import SignalStore
from tracking.tracker import SignalTracker


async def _insert_resolved_signal(
    conn: aiosqlite.Connection,
    ticker: str = "TEST",
    asset_type: str = "stock",
    final_signal: str = "BUY",
    final_confidence: float = 65.0,
    regime: str | None = "RISK_ON",
    raw_score: float = 0.5,
    consensus_score: float = 1.0,
    outcome: str = "WIN",
    agent_signals: list | None = None,
) -> None:
    """Insert a resolved signal row directly for testing."""
    agent_json = json.dumps(agent_signals or [])
    await conn.execute(
        """
        INSERT INTO signal_history (
            ticker, asset_type, final_signal, final_confidence,
            regime, raw_score, consensus_score,
            agent_signals_json, reasoning, warnings_json,
            outcome, outcome_return_pct, outcome_resolved_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            ticker, asset_type, final_signal, final_confidence,
            regime, raw_score, consensus_score,
            agent_json, "test reasoning", None,
            outcome, 0.05 if outcome == "WIN" else -0.03,
        ),
    )


class TestSignalTracker:
    # 6. Basic accuracy stats
    @pytest.mark.asyncio
    async def test_accuracy_stats_basic(self, tmp_path: Path) -> None:
        db_path = tmp_path / "tracker_basic.db"
        await init_db(db_path)

        async with aiosqlite.connect(db_path) as conn:
            # 6 WIN BUY, 4 LOSS BUY
            for _ in range(6):
                await _insert_resolved_signal(conn, final_signal="BUY", outcome="WIN")
            for _ in range(4):
                await _insert_resolved_signal(conn, final_signal="BUY", outcome="LOSS")
            await conn.commit()

        store = SignalStore(str(db_path))
        tracker = SignalTracker(store)
        stats = await tracker.compute_accuracy_stats()

        assert stats["win_rate"] == pytest.approx(0.6)
        assert stats["resolved_count"] == 10
        assert stats["win_count"] == 6
        assert stats["loss_count"] == 4
        assert stats["by_signal"]["BUY"]["count"] == 10
        assert stats["by_signal"]["BUY"]["win_rate"] == pytest.approx(0.6)

    # 7. Accuracy stats by asset type and regime
    @pytest.mark.asyncio
    async def test_accuracy_stats_by_asset_and_regime(self, tmp_path: Path) -> None:
        db_path = tmp_path / "tracker_by_type.db"
        await init_db(db_path)

        async with aiosqlite.connect(db_path) as conn:
            # 4 stock WIN, 2 stock LOSS, 3 btc WIN, 1 btc LOSS
            for _ in range(4):
                await _insert_resolved_signal(conn, asset_type="stock", regime="RISK_ON", outcome="WIN")
            for _ in range(2):
                await _insert_resolved_signal(conn, asset_type="stock", regime="NEUTRAL", outcome="LOSS")
            for _ in range(3):
                await _insert_resolved_signal(conn, asset_type="btc", regime="RISK_ON", outcome="WIN")
            for _ in range(1):
                await _insert_resolved_signal(conn, asset_type="btc", regime="NEUTRAL", outcome="LOSS")
            await conn.commit()

        store = SignalStore(str(db_path))
        tracker = SignalTracker(store)
        stats = await tracker.compute_accuracy_stats()

        assert stats["by_asset_type"]["stock"]["count"] == 6
        assert stats["by_asset_type"]["stock"]["win_rate"] == pytest.approx(4/6, rel=1e-3)
        assert stats["by_asset_type"]["btc"]["count"] == 4
        assert stats["by_asset_type"]["btc"]["win_rate"] == pytest.approx(3/4)

        assert stats["by_regime"]["RISK_ON"]["count"] == 7
        assert stats["by_regime"]["RISK_ON"]["win_rate"] == pytest.approx(7/7)
        assert stats["by_regime"]["NEUTRAL"]["count"] == 3
        assert stats["by_regime"]["NEUTRAL"]["win_rate"] == pytest.approx(0.0)

    # 8. Calibration data structure and actual_win_rate computation
    @pytest.mark.asyncio
    async def test_calibration_data(self, tmp_path: Path) -> None:
        db_path = tmp_path / "tracker_cal.db"
        await init_db(db_path)

        async with aiosqlite.connect(db_path) as conn:
            # 10 signals in 30-40 bucket: 4 WIN, 6 LOSS
            for i in range(10):
                await _insert_resolved_signal(
                    conn,
                    final_confidence=35.0,
                    outcome="WIN" if i < 4 else "LOSS",
                )
            # 8 signals in 50-60 bucket: 5 WIN, 3 LOSS
            for i in range(8):
                await _insert_resolved_signal(
                    conn,
                    final_confidence=55.0,
                    outcome="WIN" if i < 5 else "LOSS",
                )
            # 7 signals in 70-80 bucket: 6 WIN, 1 LOSS
            for i in range(7):
                await _insert_resolved_signal(
                    conn,
                    final_confidence=75.0,
                    outcome="WIN" if i < 6 else "LOSS",
                )
            await conn.commit()

        store = SignalStore(str(db_path))
        tracker = SignalTracker(store)
        buckets = await tracker.compute_calibration_data(min_bucket_size=5)

        assert len(buckets) == 3
        bucket_labels = {b["confidence_bucket"] for b in buckets}
        assert "30-40" in bucket_labels
        assert "50-60" in bucket_labels
        assert "70-80" in bucket_labels

        b30 = next(b for b in buckets if b["confidence_bucket"] == "30-40")
        assert b30["sample_size"] == 10
        assert b30["actual_win_rate"] == pytest.approx(40.0)  # 4/10 = 40%
        assert b30["bucket_midpoint"] == pytest.approx(35.0)
        assert b30["expected_win_rate"] == pytest.approx(35.0)

    # 9. Calibration min_bucket_size filter
    @pytest.mark.asyncio
    async def test_calibration_min_bucket_filter(self, tmp_path: Path) -> None:
        db_path = tmp_path / "tracker_cal_filter.db"
        await init_db(db_path)

        async with aiosqlite.connect(db_path) as conn:
            # 10 signals in 50-60 bucket
            for i in range(10):
                await _insert_resolved_signal(
                    conn, final_confidence=55.0,
                    outcome="WIN" if i < 6 else "LOSS",
                )
            # Only 2 signals in 80-90 bucket (below min_bucket_size=5)
            for i in range(2):
                await _insert_resolved_signal(
                    conn, final_confidence=85.0, outcome="WIN",
                )
            await conn.commit()

        store = SignalStore(str(db_path))
        tracker = SignalTracker(store)
        buckets = await tracker.compute_calibration_data(min_bucket_size=5)

        bucket_labels = {b["confidence_bucket"] for b in buckets}
        assert "50-60" in bucket_labels
        assert "80-90" not in bucket_labels  # excluded (only 2 samples)

    # 10. Agent performance computation
    @pytest.mark.asyncio
    async def test_agent_performance(self, tmp_path: Path) -> None:
        db_path = tmp_path / "tracker_agents.db"
        await init_db(db_path)

        # 5 resolved signals: 3 WIN (Technical BUY), 2 LOSS (Technical BUY)
        # Technical agrees with final signal in all 5 cases
        tech_buy = {"agent_name": "TechnicalAgent", "signal": "BUY", "confidence": 70.0}

        async with aiosqlite.connect(db_path) as conn:
            for i in range(5):
                outcome = "WIN" if i < 3 else "LOSS"
                await _insert_resolved_signal(
                    conn,
                    final_signal="BUY",
                    outcome=outcome,
                    agent_signals=[tech_buy],
                )
            await conn.commit()

        store = SignalStore(str(db_path))
        tracker = SignalTracker(store)
        perf = await tracker.compute_agent_performance()

        assert "TechnicalAgent" in perf
        tech = perf["TechnicalAgent"]
        assert tech["total_signals"] == 5
        # Technical always agreed with final BUY
        assert tech["agreement_rate"] == pytest.approx(1.0)
        # avg_confidence = 70.0
        assert tech["avg_confidence"] == pytest.approx(70.0)
        # BUY: 5 signals, 3 wins → 60%
        assert tech["by_signal"]["BUY"]["count"] == 5
        assert tech["by_signal"]["BUY"]["accuracy"] == pytest.approx(0.6)
        # Directional accuracy = 3/5 = 0.60
        assert tech["directional_accuracy"] == pytest.approx(0.6)
