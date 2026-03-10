"""Tests for Task 010: PortfolioMonitor integration tests (mocked DataProviders)."""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest

from db.database import init_db
from monitoring.store import AlertStore
from monitoring.models import Alert


async def _setup_db(db_path: Path) -> None:
    """Initialize DB and insert 2 positions."""
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        entry_date = (date.today() - timedelta(days=5)).isoformat()
        # Position 1: AAPL, avg_cost=100
        await conn.execute(
            """
            INSERT INTO active_positions
                (ticker, asset_type, quantity, avg_cost, entry_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("AAPL", "stock", 10.0, 100.0, entry_date),
        )
        # Position 2: MSFT, avg_cost=100
        await conn.execute(
            """
            INSERT INTO active_positions
                (ticker, asset_type, quantity, avg_cost, entry_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("MSFT", "stock", 5.0, 100.0, entry_date),
        )
        await conn.commit()


class TestPortfolioMonitor:
    # 7. run_check generates alerts for bad position, not for healthy one
    @pytest.mark.asyncio
    async def test_monitor_run_check_with_alerts(self, tmp_path: Path) -> None:
        from monitoring.monitor import PortfolioMonitor
        db_path = str(tmp_path / "monitor_test.db")
        await _setup_db(Path(db_path))

        mock_provider = MagicMock()
        # AAPL at 75 (−25% → SIGNIFICANT_LOSS), MSFT at 105 (healthy)
        mock_provider.get_current_price = AsyncMock(side_effect=lambda ticker: (
            75.0 if ticker == "AAPL" else 105.0
        ))

        with patch("monitoring.monitor.get_provider", return_value=mock_provider):
            monitor = PortfolioMonitor(db_path=db_path)
            result = await monitor.run_check()

        assert result["checked_positions"] == 2
        assert result["snapshot_saved"] is True
        assert len(result["warnings"]) == 0

        # Should have 1 alert (AAPL significant loss)
        alert_types = [a["alert_type"] for a in result["alerts"]]
        assert "SIGNIFICANT_LOSS" in alert_types
        aapl_alerts = [a for a in result["alerts"] if a["ticker"] == "AAPL"]
        assert len(aapl_alerts) >= 1
        # MSFT should have no alerts
        msft_alerts = [a for a in result["alerts"] if a["ticker"] == "MSFT"]
        assert len(msft_alerts) == 0

        # Verify alerts were saved to DB
        async with aiosqlite.connect(db_path) as conn:
            rows = await (
                await conn.execute("SELECT COUNT(*) FROM monitoring_alerts")
            ).fetchone()
            assert rows[0] >= 1

    # 8. Price fetch failure for one position — warning generated, other positions still checked
    @pytest.mark.asyncio
    async def test_monitor_price_fetch_failure(self, tmp_path: Path) -> None:
        from monitoring.monitor import PortfolioMonitor
        db_path = str(tmp_path / "monitor_fail.db")
        await _setup_db(Path(db_path))

        mock_provider = MagicMock()

        def _price_side_effect(ticker: str) -> float:
            if ticker == "AAPL":
                raise RuntimeError("Network error")
            return 105.0

        mock_provider.get_current_price = AsyncMock(side_effect=_price_side_effect)

        with patch("monitoring.monitor.get_provider", return_value=mock_provider):
            monitor = PortfolioMonitor(db_path=db_path)
            result = await monitor.run_check()

        # AAPL skipped, MSFT still checked
        assert result["checked_positions"] == 1
        assert any("AAPL" in w for w in result["warnings"])
        assert result["snapshot_saved"] is True

    # 9. run_check saves a portfolio snapshot
    @pytest.mark.asyncio
    async def test_monitor_saves_snapshot(self, tmp_path: Path) -> None:
        from monitoring.monitor import PortfolioMonitor
        db_path = str(tmp_path / "monitor_snap.db")
        await _setup_db(Path(db_path))

        mock_provider = MagicMock()
        mock_provider.get_current_price = AsyncMock(return_value=100.0)

        with patch("monitoring.monitor.get_provider", return_value=mock_provider):
            monitor = PortfolioMonitor(db_path=db_path)
            await monitor.run_check()

        async with aiosqlite.connect(db_path) as conn:
            row = await (
                await conn.execute(
                    "SELECT trigger_event FROM portfolio_snapshots WHERE trigger_event='daily_check'"
                )
            ).fetchone()
        assert row is not None
        assert row[0] == "daily_check"

    # 10. AlertStore query filtering
    @pytest.mark.asyncio
    async def test_alert_store_query(self, tmp_path: Path) -> None:
        db_path = Path(tmp_path / "alert_store.db")
        await init_db(db_path)

        store = AlertStore(str(db_path))

        alerts_to_save = [
            Alert("AAPL", "STOP_LOSS_HIT", "CRITICAL", "Stop hit", "Close position", 88.0, 90.0),
            Alert("AAPL", "TIME_OVERRUN", "WARNING", "Time overrun", "Review", 88.0, None),
            Alert("MSFT", "TARGET_HIT", "INFO", "Target hit", "Consider profit", 185.0, 180.0),
            Alert("GOOGL", "SIGNIFICANT_LOSS", "HIGH", "Big loss", "Review", 120.0, None),
            Alert("MSFT", "SIGNIFICANT_GAIN", "INFO", "Big gain", "Consider profit", 200.0, None),
        ]
        await store.save_alerts(alerts_to_save)

        # Filter by ticker
        aapl_alerts = await store.get_recent_alerts(ticker="AAPL")
        assert len(aapl_alerts) == 2
        assert all(a["ticker"] == "AAPL" for a in aapl_alerts)

        # Filter by severity
        critical_alerts = await store.get_recent_alerts(severity="CRITICAL")
        assert len(critical_alerts) == 1
        assert critical_alerts[0]["alert_type"] == "STOP_LOSS_HIT"

        # All alerts
        all_alerts = await store.get_recent_alerts()
        assert len(all_alerts) == 5
