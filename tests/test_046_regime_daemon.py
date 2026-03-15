"""Tests for Sprint 31 Task 1: Automated regime detection daemon job."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest

from db.database import init_db


MOCK_REGIME_RESULT = {
    "regime": "bull_market",
    "confidence": 75.0,
    "indicators": {
        "trend_score": 0.45,
        "volatility_score": 0.20,
        "momentum_score": 0.35,
        "macro_score": 0.40,
        "vix_current": 15.0,
        "yield_curve_spread": 0.5,
    },
    "description": "Regime: Bull Market (confidence 75%).",
}


class TestRunRegimeDetection:
    """Unit tests for run_regime_detection() job function."""

    @pytest.mark.asyncio
    async def test_saves_to_regime_history(self, tmp_path: Path) -> None:
        """run_regime_detection should save a row to the regime_history table."""
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)

        with patch(
            "engine.regime.RegimeDetector"
        ) as MockDetector:
            instance = MockDetector.return_value
            instance.detect_regime.return_value = MOCK_REGIME_RESULT

            from daemon.jobs import run_regime_detection

            result = await run_regime_detection(db_path=db_path)

        assert result["regime"] == "bull_market"
        assert result["confidence"] == 75.0
        assert "error" not in result

        # Verify row in regime_history
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute("SELECT * FROM regime_history")
            ).fetchall()
            assert len(rows) == 1
            assert rows[0]["regime"] == "bull_market"
            assert rows[0]["confidence"] == 75.0

    @pytest.mark.asyncio
    async def test_records_daemon_run(self, tmp_path: Path) -> None:
        """run_regime_detection should insert a daemon_runs row with job_name='regime_detection'."""
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)

        with patch(
            "engine.regime.RegimeDetector"
        ) as MockDetector:
            instance = MockDetector.return_value
            instance.detect_regime.return_value = MOCK_REGIME_RESULT

            from daemon.jobs import run_regime_detection

            await run_regime_detection(db_path=db_path)

        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute(
                    "SELECT * FROM daemon_runs WHERE job_name = 'regime_detection'"
                )
            ).fetchall()
            assert len(rows) == 1
            assert rows[0]["status"] == "success"
            assert rows[0]["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_handles_error_gracefully(self, tmp_path: Path) -> None:
        """run_regime_detection should never raise; errors are caught and recorded."""
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)

        with patch(
            "engine.regime.RegimeDetector"
        ) as MockDetector:
            instance = MockDetector.return_value
            instance.detect_regime.side_effect = RuntimeError("API unavailable")

            from daemon.jobs import run_regime_detection

            result = await run_regime_detection(db_path=db_path)

        # Should NOT raise -- returns error dict
        assert "error" in result
        assert "API unavailable" in result["error"]

        # Error should be recorded in daemon_runs
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute(
                    "SELECT * FROM daemon_runs WHERE job_name = 'regime_detection'"
                )
            ).fetchall()
            assert len(rows) == 1
            assert rows[0]["status"] == "error"
            assert "API unavailable" in rows[0]["error_message"]

    @pytest.mark.asyncio
    async def test_result_contains_expected_keys(self, tmp_path: Path) -> None:
        """Successful result should contain regime, confidence, description, regime_changed."""
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)

        with patch(
            "engine.regime.RegimeDetector"
        ) as MockDetector:
            instance = MockDetector.return_value
            instance.detect_regime.return_value = MOCK_REGIME_RESULT

            from daemon.jobs import run_regime_detection

            result = await run_regime_detection(db_path=db_path)

        assert "regime" in result
        assert "confidence" in result
        assert "description" in result
        assert "regime_changed" in result
        assert "row_id" in result
        assert result["row_id"] > 0


class TestRunOnceRegime:
    """Test run_once('regime') integration via MonitoringDaemon."""

    @pytest.mark.asyncio
    async def test_run_once_regime(self, tmp_path: Path) -> None:
        """MonitoringDaemon.run_once('regime') should call run_regime_detection."""
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)

        with patch(
            "engine.regime.RegimeDetector"
        ) as MockDetector:
            instance = MockDetector.return_value
            instance.detect_regime.return_value = MOCK_REGIME_RESULT

            from daemon.config import DaemonConfig
            from daemon.scheduler import MonitoringDaemon

            config = DaemonConfig(db_path=db_path)
            daemon = MonitoringDaemon(config)
            result = await daemon.run_once("regime")

        assert result["regime"] == "bull_market"
        assert result["confidence"] == 75.0

    @pytest.mark.asyncio
    async def test_get_status_includes_regime(self, tmp_path: Path) -> None:
        """get_status() should include regime_detection in results."""
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)

        from daemon.config import DaemonConfig
        from daemon.scheduler import MonitoringDaemon

        config = DaemonConfig(db_path=db_path)
        daemon = MonitoringDaemon(config)
        status = await daemon.get_status()

        assert "regime_detection" in status
        assert status["regime_detection"]["status"] == "never_run"


class TestRegimeDetectionRegimeChange:
    """Test regime change detection and notification logic."""

    @pytest.mark.asyncio
    async def test_regime_change_detected(self, tmp_path: Path) -> None:
        """When regime changes, result should indicate regime_changed=True."""
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)

        from engine.regime_history import RegimeHistoryStore

        # Pre-populate with a different regime
        store = RegimeHistoryStore(db_path)
        await store.save_regime("bear_market", 65.0)

        with patch(
            "engine.regime.RegimeDetector"
        ) as MockDetector:
            instance = MockDetector.return_value
            instance.detect_regime.return_value = MOCK_REGIME_RESULT  # bull_market

            from daemon.jobs import run_regime_detection

            result = await run_regime_detection(db_path=db_path)

        assert result["regime"] == "bull_market"
        assert result["regime_changed"] is True
        assert result["previous_regime"] == "bear_market"

    @pytest.mark.asyncio
    async def test_same_regime_no_change(self, tmp_path: Path) -> None:
        """When regime stays the same, result should indicate regime_changed=False."""
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)

        from engine.regime_history import RegimeHistoryStore

        # Pre-populate with the same regime
        store = RegimeHistoryStore(db_path)
        await store.save_regime("bull_market", 70.0)

        with patch(
            "engine.regime.RegimeDetector"
        ) as MockDetector:
            instance = MockDetector.return_value
            instance.detect_regime.return_value = MOCK_REGIME_RESULT  # bull_market

            from daemon.jobs import run_regime_detection

            result = await run_regime_detection(db_path=db_path)

        assert result["regime"] == "bull_market"
        # Same regime consecutive -> merged into 1 segment, so no "previous"
        assert result["regime_changed"] is False
