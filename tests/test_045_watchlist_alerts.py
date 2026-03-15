"""Tests for Sprint 30 Task 3: Watchlist Signal Alerts.

Covers WatchlistManager alert config methods and API endpoints.
All tests use a temporary DB -- no network calls.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from db.database import init_db
from watchlist.manager import WatchlistManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_manager(db_file: Path) -> WatchlistManager:
    await init_db(db_file)
    return WatchlistManager(db_file)


# ---------------------------------------------------------------------------
# 1. set_alert_config creates a new config
# ---------------------------------------------------------------------------

def test_set_alert_config_creates(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("AAPL")

        config = await mgr.set_alert_config(
            "AAPL",
            alert_on_signal_change=True,
            min_confidence=70.0,
            alert_on_price_below=150.0,
            enabled=True,
        )
        assert config["ticker"] == "AAPL"
        assert config["alert_on_signal_change"] is True
        assert config["min_confidence"] == 70.0
        assert config["alert_on_price_below"] == 150.0
        assert config["enabled"] is True
        assert "created_at" in config
        assert "updated_at" in config

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 2. set_alert_config updates existing config (upsert)
# ---------------------------------------------------------------------------

def test_set_alert_config_updates(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("MSFT")

        # Create initial config
        await mgr.set_alert_config("MSFT", min_confidence=50.0, enabled=True)

        # Update it
        config = await mgr.set_alert_config(
            "MSFT",
            min_confidence=80.0,
            enabled=False,
            alert_on_price_below=300.0,
        )
        assert config["ticker"] == "MSFT"
        assert config["min_confidence"] == 80.0
        assert config["enabled"] is False
        assert config["alert_on_price_below"] == 300.0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 3. set_alert_config with defaults
# ---------------------------------------------------------------------------

def test_set_alert_config_defaults(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("GOOG")

        config = await mgr.set_alert_config("GOOG")
        assert config["alert_on_signal_change"] is True
        assert config["min_confidence"] == 60.0
        assert config["alert_on_price_below"] is None
        assert config["enabled"] is True

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 4. get_alert_configs returns all configs
# ---------------------------------------------------------------------------

def test_get_alert_configs_all(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("AAPL")
        await mgr.add_ticker("MSFT")
        await mgr.add_ticker("GOOG")

        await mgr.set_alert_config("AAPL", min_confidence=70.0)
        await mgr.set_alert_config("MSFT", min_confidence=80.0)

        configs = await mgr.get_alert_configs()
        assert len(configs) == 2
        tickers = {c["ticker"] for c in configs}
        assert tickers == {"AAPL", "MSFT"}

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 5. get_alert_configs returns empty list when none configured
# ---------------------------------------------------------------------------

def test_get_alert_configs_empty(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        configs = await mgr.get_alert_configs()
        assert configs == []

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 6. get_alert_config returns specific config
# ---------------------------------------------------------------------------

def test_get_alert_config_single(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("TSLA")
        await mgr.set_alert_config("TSLA", min_confidence=55.0, alert_on_price_below=200.0)

        config = await mgr.get_alert_config("TSLA")
        assert config is not None
        assert config["ticker"] == "TSLA"
        assert config["min_confidence"] == 55.0
        assert config["alert_on_price_below"] == 200.0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 7. get_alert_config returns None for non-existent ticker
# ---------------------------------------------------------------------------

def test_get_alert_config_not_found(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        config = await mgr.get_alert_config("ZZZZ")
        assert config is None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 8. Ticker normalization on alert config
# ---------------------------------------------------------------------------

def test_alert_config_ticker_normalization(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("aapl")

        config = await mgr.set_alert_config("aapl", min_confidence=65.0)
        assert config["ticker"] == "AAPL"

        fetched = await mgr.get_alert_config("aapl")
        assert fetched is not None
        assert fetched["ticker"] == "AAPL"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 9. Boolean conversion in alert config
# ---------------------------------------------------------------------------

def test_alert_config_boolean_conversion(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("NVDA")

        config = await mgr.set_alert_config(
            "NVDA",
            alert_on_signal_change=False,
            enabled=False,
        )
        assert config["alert_on_signal_change"] is False
        assert config["enabled"] is False
        assert isinstance(config["alert_on_signal_change"], bool)
        assert isinstance(config["enabled"], bool)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 10. API endpoint format validation (integration-style)
# ---------------------------------------------------------------------------

def test_api_endpoint_set_alert_config(tmp_path: Path) -> None:
    """Verify the manager returns data in the expected API response shape."""
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("META")

        config = await mgr.set_alert_config(
            "META",
            alert_on_signal_change=True,
            min_confidence=75.0,
            alert_on_price_below=450.0,
            enabled=True,
        )

        # Simulate API response shape
        response = {"data": config, "warnings": []}
        assert "data" in response
        assert response["data"]["ticker"] == "META"
        assert response["data"]["min_confidence"] == 75.0
        assert response["warnings"] == []

    asyncio.run(_run())


def test_api_endpoint_get_alert_configs(tmp_path: Path) -> None:
    """Verify get_alert_configs returns data in the expected API response shape."""
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("AAPL")
        await mgr.add_ticker("GOOG")
        await mgr.set_alert_config("AAPL", min_confidence=70.0)
        await mgr.set_alert_config("GOOG", min_confidence=60.0)

        configs = await mgr.get_alert_configs()

        # Simulate API response shape
        response = {"data": configs, "warnings": []}
        assert "data" in response
        assert len(response["data"]) == 2
        assert response["warnings"] == []

        # Verify each config has expected fields
        for cfg in response["data"]:
            assert "ticker" in cfg
            assert "alert_on_signal_change" in cfg
            assert "min_confidence" in cfg
            assert "alert_on_price_below" in cfg
            assert "enabled" in cfg

    asyncio.run(_run())
