"""Tests for Sprint 13.1: Watchlist system.

Covers WatchlistManager CRUD, analysis updates, and edge cases.
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
# 1. Add ticker to watchlist
# ---------------------------------------------------------------------------

def test_add_ticker(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        row_id = await mgr.add_ticker("AAPL", asset_type="stock", notes="Big tech")
        assert isinstance(row_id, int)
        assert row_id > 0

        item = await mgr.get_ticker("AAPL")
        assert item is not None
        assert item["ticker"] == "AAPL"
        assert item["asset_type"] == "stock"
        assert item["notes"] == "Big tech"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 2. Duplicate ticker rejected
# ---------------------------------------------------------------------------

def test_duplicate_ticker_rejected(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("AAPL")

        with pytest.raises(ValueError, match="already on the watchlist"):
            await mgr.add_ticker("AAPL")

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 3. Remove ticker
# ---------------------------------------------------------------------------

def test_remove_ticker(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("MSFT")

        removed = await mgr.remove_ticker("MSFT")
        assert removed is True

        item = await mgr.get_ticker("MSFT")
        assert item is None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 4. Remove non-existent ticker returns False
# ---------------------------------------------------------------------------

def test_remove_nonexistent_ticker(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        removed = await mgr.remove_ticker("FAKE")
        assert removed is False

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 5. Get watchlist empty
# ---------------------------------------------------------------------------

def test_get_watchlist_empty(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        items = await mgr.get_watchlist()
        assert items == []

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 6. Get watchlist populated
# ---------------------------------------------------------------------------

def test_get_watchlist_populated(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("AAPL", notes="Apple")
        await mgr.add_ticker("GOOG", notes="Google")
        await mgr.add_ticker("TSLA", notes="Tesla")

        items = await mgr.get_watchlist()
        assert len(items) == 3
        tickers = {i["ticker"] for i in items}
        assert tickers == {"AAPL", "GOOG", "TSLA"}

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 7. Update ticker notes and prices
# ---------------------------------------------------------------------------

def test_update_ticker(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("NVDA", notes="GPU maker")

        updated = await mgr.update_ticker(
            "NVDA",
            notes="AI chip leader",
            target_buy_price=120.0,
            alert_below_price=100.0,
        )
        assert updated is True

        item = await mgr.get_ticker("NVDA")
        assert item is not None
        assert item["notes"] == "AI chip leader"
        assert item["target_buy_price"] == 120.0
        assert item["alert_below_price"] == 100.0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 8. Update non-existent ticker returns False
# ---------------------------------------------------------------------------

def test_update_nonexistent_ticker(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        updated = await mgr.update_ticker("FAKE", notes="nope")
        assert updated is False

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 9. Update analysis results
# ---------------------------------------------------------------------------

def test_update_analysis(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("AMZN")

        updated = await mgr.update_analysis("AMZN", signal="BUY", confidence=0.85)
        assert updated is True

        item = await mgr.get_ticker("AMZN")
        assert item is not None
        assert item["last_signal"] == "BUY"
        assert item["last_confidence"] == 0.85
        assert item["last_analysis_at"] is not None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 10. Get single ticker (not found)
# ---------------------------------------------------------------------------

def test_get_ticker_not_found(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        item = await mgr.get_ticker("ZZZZ")
        assert item is None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 11. Ticker normalization (lowercase input)
# ---------------------------------------------------------------------------

def test_ticker_normalization(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker("aapl")

        item = await mgr.get_ticker("aapl")
        assert item is not None
        assert item["ticker"] == "AAPL"

        # Duplicate should fail regardless of case
        with pytest.raises(ValueError):
            await mgr.add_ticker("Aapl")

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 12. Full lifecycle: add -> update -> analyze -> remove
# ---------------------------------------------------------------------------

def test_full_lifecycle(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")

        # Add
        row_id = await mgr.add_ticker(
            "META",
            asset_type="stock",
            notes="Social media",
            target_buy_price=500.0,
            alert_below_price=450.0,
        )
        assert row_id > 0

        # Verify add
        item = await mgr.get_ticker("META")
        assert item is not None
        assert item["target_buy_price"] == 500.0

        # Update notes
        await mgr.update_ticker("META", notes="Social + AI play")
        item = await mgr.get_ticker("META")
        assert item["notes"] == "Social + AI play"
        assert item["target_buy_price"] == 500.0  # unchanged

        # Update analysis
        await mgr.update_analysis("META", signal="HOLD", confidence=0.62)
        item = await mgr.get_ticker("META")
        assert item["last_signal"] == "HOLD"
        assert item["last_confidence"] == 0.62

        # Remove
        removed = await mgr.remove_ticker("META")
        assert removed is True

        # Verify removal
        items = await mgr.get_watchlist()
        assert len(items) == 0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 13. Add ticker with target prices
# ---------------------------------------------------------------------------

def test_add_ticker_with_prices(tmp_path: Path) -> None:
    async def _run() -> None:
        mgr = await _create_manager(tmp_path / "wl.db")
        await mgr.add_ticker(
            "BTC-USD",
            asset_type="btc",
            target_buy_price=60000.0,
            alert_below_price=55000.0,
        )

        item = await mgr.get_ticker("BTC-USD")
        assert item is not None
        assert item["asset_type"] == "btc"
        assert item["target_buy_price"] == 60000.0
        assert item["alert_below_price"] == 55000.0

    asyncio.run(_run())
