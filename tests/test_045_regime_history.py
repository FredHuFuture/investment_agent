"""Tests for Sprint 30 Task 2: Regime history storage and API endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite
import pytest

from db.database import init_db
from engine.regime_history import RegimeHistoryStore


class TestRegimeHistoryStore:
    """Unit tests for RegimeHistoryStore save/query operations."""

    @pytest.mark.asyncio
    async def test_save_regime_returns_id(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        await init_db(db_path)
        store = RegimeHistoryStore(str(db_path))

        row_id = await store.save_regime("bull_market", 75.0)
        assert row_id is not None
        assert row_id > 0

    @pytest.mark.asyncio
    async def test_save_regime_with_optional_fields(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        await init_db(db_path)
        store = RegimeHistoryStore(str(db_path))

        row_id = await store.save_regime(
            "high_volatility", 85.0, vix=32.5, yield_spread=-0.15
        )
        assert row_id > 0

        # Verify the data was stored correctly
        async with aiosqlite.connect(str(db_path)) as conn:
            conn.row_factory = aiosqlite.Row
            row = await (
                await conn.execute(
                    "SELECT * FROM regime_history WHERE id = ?", (row_id,)
                )
            ).fetchone()
            assert row is not None
            assert row["regime"] == "high_volatility"
            assert row["confidence"] == 85.0
            assert row["vix"] == 32.5
            assert row["yield_spread"] == -0.15

    @pytest.mark.asyncio
    async def test_save_regime_without_optional_fields(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        await init_db(db_path)
        store = RegimeHistoryStore(str(db_path))

        row_id = await store.save_regime("sideways", 60.0)
        assert row_id > 0

        async with aiosqlite.connect(str(db_path)) as conn:
            conn.row_factory = aiosqlite.Row
            row = await (
                await conn.execute(
                    "SELECT * FROM regime_history WHERE id = ?", (row_id,)
                )
            ).fetchone()
            assert row is not None
            assert row["vix"] is None
            assert row["yield_spread"] is None

    @pytest.mark.asyncio
    async def test_get_history_empty(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        await init_db(db_path)
        store = RegimeHistoryStore(str(db_path))

        result = await store.get_history(days=90)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_history_single_regime(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        await init_db(db_path)
        store = RegimeHistoryStore(str(db_path))

        await store.save_regime("bull_market", 80.0)

        result = await store.get_history(days=90)
        assert len(result) == 1
        assert result[0]["regime"] == "bull_market"
        assert result[0]["confidence"] == 80.0
        assert result[0]["duration_days"] >= 1

    @pytest.mark.asyncio
    async def test_get_history_consecutive_same_regime_merges(
        self, tmp_path: Path
    ) -> None:
        """Consecutive entries of the same regime should be merged into one segment."""
        db_path = tmp_path / "test.db"
        await init_db(db_path)
        store = RegimeHistoryStore(str(db_path))

        # Insert two rows with same regime
        await store.save_regime("bull_market", 70.0)
        await store.save_regime("bull_market", 80.0)

        result = await store.get_history(days=90)
        # Should be merged into a single segment
        assert len(result) == 1
        assert result[0]["regime"] == "bull_market"
        # Confidence should be updated to latest
        assert result[0]["confidence"] == 80.0

    @pytest.mark.asyncio
    async def test_get_history_regime_changes_create_segments(
        self, tmp_path: Path
    ) -> None:
        """Different regimes should create separate segments."""
        db_path = tmp_path / "test.db"
        await init_db(db_path)
        store = RegimeHistoryStore(str(db_path))

        await store.save_regime("bull_market", 75.0)
        await store.save_regime("bear_market", 65.0)
        await store.save_regime("sideways", 55.0)

        result = await store.get_history(days=90)
        assert len(result) == 3
        assert result[0]["regime"] == "bull_market"
        assert result[1]["regime"] == "bear_market"
        assert result[2]["regime"] == "sideways"

    @pytest.mark.asyncio
    async def test_get_history_respects_days_filter(self, tmp_path: Path) -> None:
        """Only entries within the requested time window should be returned."""
        db_path = tmp_path / "test.db"
        await init_db(db_path)

        # Insert an old entry directly
        old_date = (datetime.now(timezone.utc) - timedelta(days=100)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        async with aiosqlite.connect(str(db_path)) as conn:
            await conn.execute(
                "INSERT INTO regime_history (regime, confidence, detected_at) VALUES (?, ?, ?)",
                ("bear_market", 70.0, old_date),
            )
            await conn.commit()

        store = RegimeHistoryStore(str(db_path))

        # Insert a recent entry
        await store.save_regime("bull_market", 80.0)

        # Query last 30 days - should only get the recent one
        result = await store.get_history(days=30)
        assert len(result) == 1
        assert result[0]["regime"] == "bull_market"

        # Query last 365 days - should get both
        result = await store.get_history(days=365)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_history_duration_calculation(self, tmp_path: Path) -> None:
        """Duration should reflect consecutive days of the same regime."""
        db_path = tmp_path / "test.db"
        await init_db(db_path)

        now = datetime.now(timezone.utc)
        dates = [
            (now - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
        ]

        async with aiosqlite.connect(str(db_path)) as conn:
            await conn.execute(
                "INSERT INTO regime_history (regime, confidence, detected_at) VALUES (?, ?, ?)",
                ("bull_market", 75.0, dates[0]),
            )
            await conn.execute(
                "INSERT INTO regime_history (regime, confidence, detected_at) VALUES (?, ?, ?)",
                ("bear_market", 65.0, dates[1]),
            )
            await conn.execute(
                "INSERT INTO regime_history (regime, confidence, detected_at) VALUES (?, ?, ?)",
                ("sideways", 50.0, dates[2]),
            )
            await conn.commit()

        store = RegimeHistoryStore(str(db_path))
        result = await store.get_history(days=90)

        assert len(result) == 3
        # First segment: 20 days ago to 10 days ago = 10 days
        assert result[0]["duration_days"] == 10
        # Second segment: 10 days ago to 5 days ago = 5 days
        assert result[1]["duration_days"] == 5
        # Third segment: 5 days ago to now = ~5 days
        assert result[2]["duration_days"] >= 4

    @pytest.mark.asyncio
    async def test_get_history_returns_correct_format(self, tmp_path: Path) -> None:
        """Each history entry should have date, regime, confidence, duration_days."""
        db_path = tmp_path / "test.db"
        await init_db(db_path)
        store = RegimeHistoryStore(str(db_path))

        await store.save_regime("risk_off", 90.0, vix=35.0, yield_spread=-0.5)

        result = await store.get_history(days=90)
        assert len(result) == 1
        entry = result[0]
        assert "date" in entry
        assert "regime" in entry
        assert "confidence" in entry
        assert "duration_days" in entry
        assert entry["regime"] == "risk_off"
        assert entry["confidence"] == 90.0


class TestRegimeHistoryAPI:
    """Integration tests for the /regime/history API endpoint."""

    @pytest.mark.asyncio
    async def test_api_endpoint_returns_data(self, tmp_path: Path) -> None:
        """Test the endpoint through direct store + FastAPI test client."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from api.routes.regime import router

        db_path = tmp_path / "api_test.db"
        await init_db(db_path)

        # Pre-populate some data
        store = RegimeHistoryStore(str(db_path))
        await store.save_regime("bull_market", 80.0, vix=15.0)
        await store.save_regime("bear_market", 70.0, vix=30.0)

        app = FastAPI()
        app.state.db_path = str(db_path)
        app.include_router(router, prefix="/regime")

        client = TestClient(app)
        response = client.get("/regime/history?days=90")
        assert response.status_code == 200

        body = response.json()
        assert "data" in body
        assert "warnings" in body
        assert len(body["data"]) == 2
        assert body["data"][0]["regime"] == "bull_market"
        assert body["data"][1]["regime"] == "bear_market"

    @pytest.mark.asyncio
    async def test_api_endpoint_days_param(self, tmp_path: Path) -> None:
        """Test that days query parameter is respected."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from api.routes.regime import router

        db_path = tmp_path / "api_days.db"
        await init_db(db_path)

        app = FastAPI()
        app.state.db_path = str(db_path)
        app.include_router(router, prefix="/regime")

        client = TestClient(app)

        # Empty data
        response = client.get("/regime/history?days=30")
        assert response.status_code == 200
        assert response.json()["data"] == []

    @pytest.mark.asyncio
    async def test_api_endpoint_default_days(self, tmp_path: Path) -> None:
        """Test that default days is 90 when not provided."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from api.routes.regime import router

        db_path = tmp_path / "api_default.db"
        await init_db(db_path)

        app = FastAPI()
        app.state.db_path = str(db_path)
        app.include_router(router, prefix="/regime")

        client = TestClient(app)

        response = client.get("/regime/history")
        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["warnings"] == []
