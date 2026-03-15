"""Tests for Sprint 31 Task 2: Watchlist Alert Evaluation Daemon Job.

Covers:
- run_watchlist_scan() with mocked price data
- Price-below alert generation
- Confidence-met alert generation
- No alerts when conditions not met
- get_tickers_with_active_alerts() query
- Error handling / never-raises behaviour

All tests use a temporary DB and mock yfinance -- no network calls.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from db.database import init_db
from watchlist.manager import WatchlistManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _setup_db(db_file: Path) -> WatchlistManager:
    """Initialize DB and return a WatchlistManager."""
    await init_db(db_file)
    return WatchlistManager(db_file)


async def _add_ticker_with_config(
    mgr: WatchlistManager,
    ticker: str,
    *,
    last_signal: str | None = None,
    last_confidence: float | None = None,
    alert_on_signal_change: bool = True,
    min_confidence: float = 60.0,
    alert_on_price_below: float | None = None,
    enabled: bool = True,
) -> None:
    """Add a ticker to watchlist with analysis data and alert config."""
    await mgr.add_ticker(ticker)
    if last_signal is not None and last_confidence is not None:
        await mgr.update_analysis(ticker, last_signal, last_confidence)
    await mgr.set_alert_config(
        ticker,
        alert_on_signal_change=alert_on_signal_change,
        min_confidence=min_confidence,
        alert_on_price_below=alert_on_price_below,
        enabled=enabled,
    )


# ---------------------------------------------------------------------------
# 1. get_tickers_with_active_alerts returns joined data
# ---------------------------------------------------------------------------

def test_get_tickers_with_active_alerts(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _setup_db(tmp_path / "wl.db")

        # Ticker with enabled config
        await _add_ticker_with_config(
            mgr, "AAPL",
            last_signal="BUY", last_confidence=75.0,
            alert_on_price_below=150.0, enabled=True,
        )
        # Ticker with disabled config
        await _add_ticker_with_config(
            mgr, "MSFT",
            last_signal="HOLD", last_confidence=50.0,
            enabled=False,
        )
        # Ticker with no config at all
        await mgr.add_ticker("GOOG")

        items = await mgr.get_tickers_with_active_alerts()
        assert len(items) == 1
        assert items[0]["ticker"] == "AAPL"
        assert items[0]["last_signal"] == "BUY"
        assert items[0]["last_confidence"] == 75.0
        assert items[0]["alert_on_price_below"] == 150.0
        assert items[0]["enabled"] == 1  # raw DB integer

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 2. get_tickers_with_active_alerts returns empty when none enabled
# ---------------------------------------------------------------------------

def test_get_tickers_with_active_alerts_empty(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _setup_db(tmp_path / "wl.db")
        await mgr.add_ticker("TSLA")
        items = await mgr.get_tickers_with_active_alerts()
        assert items == []

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 3. Price-below alert generation
# ---------------------------------------------------------------------------

def test_price_below_alert(tmp_path: Path) -> None:
    """When current price < alert_on_price_below, a PRICE_BELOW alert is created."""
    db_file = tmp_path / "wl.db"

    async def _run() -> None:
        mgr = await _setup_db(db_file)
        await _add_ticker_with_config(
            mgr, "AAPL",
            last_signal="HOLD", last_confidence=50.0,
            alert_on_price_below=150.0,
        )

        mock_provider = AsyncMock()
        mock_provider.get_current_price = AsyncMock(return_value=140.0)

        with patch(
            "data_providers.yfinance_provider.YFinanceProvider",
            return_value=mock_provider,
        ):
            from daemon.watchlist_job import run_watchlist_scan
            result = await run_watchlist_scan(str(db_file))

        assert result["tickers_checked"] == 1
        assert result["alerts_created"] >= 1
        assert result["errors"] == []

        # Verify alert was persisted
        from monitoring.store import AlertStore
        store = AlertStore(str(db_file))
        alerts = await store.get_recent_alerts(ticker="AAPL")
        price_alerts = [a for a in alerts if a["alert_type"] == "PRICE_BELOW"]
        assert len(price_alerts) >= 1
        assert price_alerts[0]["current_price"] == 140.0
        assert price_alerts[0]["trigger_price"] == 150.0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 4. No alert when price above threshold
# ---------------------------------------------------------------------------

def test_no_alert_when_price_above(tmp_path: Path) -> None:
    """When current price >= alert_on_price_below, no PRICE_BELOW alert."""
    db_file = tmp_path / "wl.db"

    async def _run() -> None:
        mgr = await _setup_db(db_file)
        await _add_ticker_with_config(
            mgr, "AAPL",
            last_signal="HOLD", last_confidence=50.0,
            alert_on_price_below=150.0,
        )

        mock_provider = AsyncMock()
        mock_provider.get_current_price = AsyncMock(return_value=160.0)

        with patch(
            "data_providers.yfinance_provider.YFinanceProvider",
            return_value=mock_provider,
        ):
            from daemon.watchlist_job import run_watchlist_scan
            result = await run_watchlist_scan(str(db_file))

        assert result["tickers_checked"] == 1
        # HOLD signal at 50% confidence below min_confidence=60%, so no
        # CONFIDENCE_MET alert either. No PRICE_BELOW since 160 >= 150.
        assert result["alerts_created"] == 0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 5. Confidence-met alert for actionable signal
# ---------------------------------------------------------------------------

def test_confidence_met_alert(tmp_path: Path) -> None:
    """BUY signal at confidence >= min_confidence triggers CONFIDENCE_MET."""
    db_file = tmp_path / "wl.db"

    async def _run() -> None:
        mgr = await _setup_db(db_file)
        await _add_ticker_with_config(
            mgr, "TSLA",
            last_signal="BUY", last_confidence=80.0,
            min_confidence=70.0,
        )

        mock_provider = AsyncMock()
        mock_provider.get_current_price = AsyncMock(return_value=250.0)

        with patch(
            "data_providers.yfinance_provider.YFinanceProvider",
            return_value=mock_provider,
        ):
            from daemon.watchlist_job import run_watchlist_scan
            result = await run_watchlist_scan(str(db_file))

        assert result["alerts_created"] >= 1

        from monitoring.store import AlertStore
        store = AlertStore(str(db_file))
        alerts = await store.get_recent_alerts(ticker="TSLA")
        conf_alerts = [a for a in alerts if a["alert_type"] == "CONFIDENCE_MET"]
        assert len(conf_alerts) >= 1
        assert "BUY" in conf_alerts[0]["message"]

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 6. No confidence alert when below threshold
# ---------------------------------------------------------------------------

def test_no_confidence_alert_below_threshold(tmp_path: Path) -> None:
    """BUY signal at confidence < min_confidence should NOT trigger alert."""
    db_file = tmp_path / "wl.db"

    async def _run() -> None:
        mgr = await _setup_db(db_file)
        await _add_ticker_with_config(
            mgr, "MSFT",
            last_signal="BUY", last_confidence=55.0,
            min_confidence=70.0,
        )

        mock_provider = AsyncMock()
        mock_provider.get_current_price = AsyncMock(return_value=400.0)

        with patch(
            "data_providers.yfinance_provider.YFinanceProvider",
            return_value=mock_provider,
        ):
            from daemon.watchlist_job import run_watchlist_scan
            result = await run_watchlist_scan(str(db_file))

        assert result["alerts_created"] == 0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 7. No confidence alert for HOLD signal
# ---------------------------------------------------------------------------

def test_no_confidence_alert_for_hold(tmp_path: Path) -> None:
    """HOLD signal should not generate CONFIDENCE_MET alert."""
    db_file = tmp_path / "wl.db"

    async def _run() -> None:
        mgr = await _setup_db(db_file)
        await _add_ticker_with_config(
            mgr, "GOOG",
            last_signal="HOLD", last_confidence=90.0,
            min_confidence=60.0,
        )

        mock_provider = AsyncMock()
        mock_provider.get_current_price = AsyncMock(return_value=180.0)

        with patch(
            "data_providers.yfinance_provider.YFinanceProvider",
            return_value=mock_provider,
        ):
            from daemon.watchlist_job import run_watchlist_scan
            result = await run_watchlist_scan(str(db_file))

        assert result["alerts_created"] == 0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 8. Multiple alerts from single scan
# ---------------------------------------------------------------------------

def test_multiple_alerts_multiple_tickers(tmp_path: Path) -> None:
    """Multiple tickers can each trigger alerts in a single scan."""
    db_file = tmp_path / "wl.db"

    async def _run() -> None:
        mgr = await _setup_db(db_file)
        # AAPL: price below
        await _add_ticker_with_config(
            mgr, "AAPL",
            last_signal="HOLD", last_confidence=50.0,
            alert_on_price_below=150.0,
        )
        # TSLA: confidence met
        await _add_ticker_with_config(
            mgr, "TSLA",
            last_signal="SELL", last_confidence=85.0,
            min_confidence=70.0,
        )

        prices = {"AAPL": 140.0, "TSLA": 200.0}
        mock_provider = AsyncMock()
        mock_provider.get_current_price = AsyncMock(
            side_effect=lambda t: prices.get(t, 100.0)
        )

        with patch(
            "data_providers.yfinance_provider.YFinanceProvider",
            return_value=mock_provider,
        ):
            from daemon.watchlist_job import run_watchlist_scan
            result = await run_watchlist_scan(str(db_file))

        assert result["tickers_checked"] == 2
        # AAPL: PRICE_BELOW, TSLA: CONFIDENCE_MET
        assert result["alerts_created"] == 2

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 9. Scan with no active configs returns early
# ---------------------------------------------------------------------------

def test_scan_no_active_configs(tmp_path: Path) -> None:
    """Scan returns early when no tickers have enabled alert configs."""
    db_file = tmp_path / "wl.db"

    async def _run() -> None:
        await init_db(db_file)

        from daemon.watchlist_job import run_watchlist_scan
        result = await run_watchlist_scan(str(db_file))

        assert result["tickers_checked"] == 0
        assert result["alerts_created"] == 0
        assert result["errors"] == []

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 10. Scan records to daemon_runs
# ---------------------------------------------------------------------------

def test_scan_records_daemon_run(tmp_path: Path) -> None:
    """Verify that run_watchlist_scan writes a daemon_runs row."""
    db_file = tmp_path / "wl.db"

    async def _run() -> None:
        mgr = await _setup_db(db_file)
        await _add_ticker_with_config(
            mgr, "AAPL",
            last_signal="HOLD", last_confidence=50.0,
            alert_on_price_below=150.0,
        )

        mock_provider = AsyncMock()
        mock_provider.get_current_price = AsyncMock(return_value=140.0)

        with patch(
            "data_providers.yfinance_provider.YFinanceProvider",
            return_value=mock_provider,
        ):
            from daemon.watchlist_job import run_watchlist_scan
            await run_watchlist_scan(str(db_file))

        import aiosqlite
        async with aiosqlite.connect(str(db_file)) as conn:
            row = await (
                await conn.execute(
                    "SELECT job_name, status FROM daemon_runs "
                    "WHERE job_name = 'watchlist_scan' ORDER BY id DESC LIMIT 1"
                )
            ).fetchone()
            assert row is not None
            assert row[0] == "watchlist_scan"
            assert row[1] == "success"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 11. Scan never raises on price fetch error
# ---------------------------------------------------------------------------

def test_scan_handles_price_error_gracefully(tmp_path: Path) -> None:
    """Price fetch failure for a ticker should not crash the scan."""
    db_file = tmp_path / "wl.db"

    async def _run() -> None:
        mgr = await _setup_db(db_file)
        await _add_ticker_with_config(
            mgr, "BADTICKER",
            last_signal="BUY", last_confidence=80.0,
            alert_on_price_below=100.0,
            min_confidence=70.0,
        )

        mock_provider = AsyncMock()
        mock_provider.get_current_price = AsyncMock(
            side_effect=ValueError("No price data")
        )

        with patch(
            "data_providers.yfinance_provider.YFinanceProvider",
            return_value=mock_provider,
        ):
            from daemon.watchlist_job import run_watchlist_scan
            result = await run_watchlist_scan(str(db_file))

        # Should not crash; price_below not triggered (no price), but
        # confidence_met still triggers since it doesn't require price
        assert result["tickers_checked"] == 1
        assert result["errors"] == []

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 12. HIGH severity for deep price drop
# ---------------------------------------------------------------------------

def test_price_below_high_severity(tmp_path: Path) -> None:
    """Price > 5% below threshold should get HIGH severity."""
    db_file = tmp_path / "wl.db"

    async def _run() -> None:
        mgr = await _setup_db(db_file)
        await _add_ticker_with_config(
            mgr, "NVDA",
            last_signal="HOLD", last_confidence=40.0,
            alert_on_price_below=100.0,
        )

        # 90 < 100 * 0.95 = 95 => HIGH
        mock_provider = AsyncMock()
        mock_provider.get_current_price = AsyncMock(return_value=90.0)

        with patch(
            "data_providers.yfinance_provider.YFinanceProvider",
            return_value=mock_provider,
        ):
            from daemon.watchlist_job import run_watchlist_scan
            await run_watchlist_scan(str(db_file))

        from monitoring.store import AlertStore
        store = AlertStore(str(db_file))
        alerts = await store.get_recent_alerts(ticker="NVDA")
        price_alerts = [a for a in alerts if a["alert_type"] == "PRICE_BELOW"]
        assert len(price_alerts) == 1
        assert price_alerts[0]["severity"] == "HIGH"

    asyncio.run(_run())
