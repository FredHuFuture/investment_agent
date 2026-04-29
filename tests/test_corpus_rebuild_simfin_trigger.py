"""Phase 8 DATA-v2-04 + DATA-v2-02 SC-3: Corpus rebuild trigger + pipeline injection.

Covers Task 4 of plan 08-02:
- Pipeline injects SimfinProvider into FundamentalAgent when use_pit_fundamentals=True
- Pipeline does NOT inject SimfinProvider when use_pit_fundamentals=False
- First-enable observation schedules a BackgroundTask corpus rebuild
- Subsequent enables (after a successful or partial 'simfin' rebuild) do NOT re-rebuild
- POST /analytics/calibration/rebuild-corpus accepts the new fundamentals_provider param
- Pydantic Literal allowlist rejects bogus provider strings (T-08-02-02 SQL-injection
  mitigation: invalid values fail validation before reaching SQL)
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from typing import Any

import aiosqlite
import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

from db.database import init_db


# ---------------------------------------------------------------------------
# Async helper: seed an open AAPL position so first-enable lookup finds tickers
# ---------------------------------------------------------------------------


async def _seed_open_position(db_path: str, ticker: str = "AAPL") -> None:
    """Insert one open active_positions row for the trigger to pick up."""
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO active_positions
              (ticker, asset_type, quantity, avg_cost, entry_date, status)
            VALUES (?, 'stock', 10, 150.0, '2024-01-01', 'open')
            """,
            (ticker,),
        )
        await conn.commit()


# ---------------------------------------------------------------------------
# Fixture: fresh DB with one open AAPL position
# ---------------------------------------------------------------------------


@pytest.fixture
def trigger_db(tmp_path: Path) -> str:
    """Initialize a fresh DB and seed an open AAPL position. Returns db_path."""
    db_path = str(tmp_path / "test_trigger.db")
    asyncio.run(init_db(db_path))
    asyncio.run(_seed_open_position(db_path))
    return db_path


# ---------------------------------------------------------------------------
# Test 1: pipeline injects SimFin when use_pit_fundamentals=True
# ---------------------------------------------------------------------------


def test_pipeline_injects_simfin_when_use_pit_true(
    monkeypatch: pytest.MonkeyPatch, trigger_db: str
) -> None:
    """When use_pit_fundamentals=True AND SIMFIN_API_KEY set, pipeline calls
    FundamentalAgent.set_pit_provider with a SimfinProvider instance.
    """
    monkeypatch.setenv("SIMFIN_API_KEY", "TEST_KEY")

    async def _run() -> None:
        from engine.pipeline import AnalysisPipeline

        with patch("agents.fundamental.FundamentalAgent.set_pit_provider") as mock_set:
            pipeline = AnalysisPipeline(db_path=trigger_db)
            bg = BackgroundTasks()
            try:
                await pipeline.analyze_ticker(
                    ticker="AAPL",
                    asset_type="stock",
                    use_pit_fundamentals=True,
                    background_tasks=bg,
                )
            except Exception:
                # Downstream agents may fail without real provider data — that's fine,
                # we only need to verify set_pit_provider was reached.
                pass
            assert mock_set.called, (
                "FundamentalAgent.set_pit_provider must be invoked when "
                "use_pit_fundamentals=True"
            )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 2: pipeline does NOT inject SimFin when use_pit_fundamentals=False
# ---------------------------------------------------------------------------


def test_pipeline_does_not_inject_simfin_when_use_pit_false(
    monkeypatch: pytest.MonkeyPatch, trigger_db: str
) -> None:
    """Default analyze_ticker must NOT construct SimfinProvider — even with key set."""
    monkeypatch.setenv("SIMFIN_API_KEY", "TEST_KEY")

    async def _run() -> None:
        from engine.pipeline import AnalysisPipeline

        with patch("data_providers.simfin_provider.SimfinProvider") as mock_simfin:
            pipeline = AnalysisPipeline(db_path=trigger_db)
            try:
                await pipeline.analyze_ticker(
                    ticker="AAPL",
                    asset_type="stock",
                    use_pit_fundamentals=False,
                )
            except Exception:
                pass
            assert not mock_simfin.called, (
                "SimfinProvider must not be constructed when use_pit_fundamentals=False"
            )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 3: first-enable triggers corpus rebuild via BackgroundTasks
# ---------------------------------------------------------------------------


def test_first_simfin_enable_triggers_corpus_rebuild(trigger_db: str) -> None:
    """DATA-v2-04 SC-4 — first observed use_pit_fundamentals=True schedules a rebuild
    when corpus_rebuild_jobs has no successful 'simfin' row.
    """

    async def _run() -> None:
        from engine.pipeline import _trigger_simfin_corpus_rebuild_if_first

        bg = BackgroundTasks()
        triggered = await _trigger_simfin_corpus_rebuild_if_first(
            db_path=trigger_db,
            background_tasks=bg,
        )
        assert triggered is True, "First-enable should have scheduled a rebuild"
        assert len(bg.tasks) == 1, f"Expected 1 BackgroundTask, got {len(bg.tasks)}"

        task = bg.tasks[0]
        # Task.func is the bound function reference; verify it's rebuild_signal_corpus.
        assert "rebuild_signal_corpus" in str(task.func), (
            f"Scheduled task is not rebuild_signal_corpus: {task.func}"
        )
        # Verify the kwargs include fundamentals_provider='simfin'
        assert task.kwargs.get("fundamentals_provider") == "simfin", (
            f"Expected fundamentals_provider='simfin', got {task.kwargs!r}"
        )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 4: subsequent enable (with existing 'simfin' success row) does NOT re-rebuild
# ---------------------------------------------------------------------------


def test_subsequent_simfin_enable_does_not_re_rebuild(trigger_db: str) -> None:
    """If a successful simfin rebuild already exists, _trigger returns False."""

    async def _run() -> None:
        # Seed a 'success' simfin rebuild row so first-enable detects prior rebuild
        async with aiosqlite.connect(trigger_db) as conn:
            await conn.execute(
                """
                INSERT INTO corpus_rebuild_jobs
                  (job_id, status, tickers_total, tickers_completed,
                   ticker_progress_json, started_at, completed_at,
                   fundamentals_provider)
                VALUES (?, 'success', 1, 1, '{}', ?, ?, 'simfin')
                """,
                (
                    uuid.uuid4().hex,
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            await conn.commit()

        from engine.pipeline import _trigger_simfin_corpus_rebuild_if_first

        bg = BackgroundTasks()
        triggered = await _trigger_simfin_corpus_rebuild_if_first(
            db_path=trigger_db,
            background_tasks=bg,
        )
        assert triggered is False, (
            "Subsequent enable should NOT schedule a new rebuild"
        )
        assert len(bg.tasks) == 0, "No BackgroundTask should have been added"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 5: 'partial' status also satisfies first-enable check (no re-rebuild)
# ---------------------------------------------------------------------------


def test_subsequent_simfin_enable_with_partial_status_also_skips_rebuild(
    trigger_db: str,
) -> None:
    """A 'partial' rebuild is also considered a successful first-enable observation."""

    async def _run() -> None:
        async with aiosqlite.connect(trigger_db) as conn:
            await conn.execute(
                """
                INSERT INTO corpus_rebuild_jobs
                  (job_id, status, tickers_total, tickers_completed,
                   ticker_progress_json, started_at, completed_at,
                   fundamentals_provider)
                VALUES (?, 'partial', 2, 1, '{}', ?, ?, 'simfin')
                """,
                (
                    uuid.uuid4().hex,
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            await conn.commit()

        from engine.pipeline import _trigger_simfin_corpus_rebuild_if_first

        bg = BackgroundTasks()
        triggered = await _trigger_simfin_corpus_rebuild_if_first(
            db_path=trigger_db,
            background_tasks=bg,
        )
        assert triggered is False
        assert len(bg.tasks) == 0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 6: rebuild-corpus endpoint accepts fundamentals_provider param
# ---------------------------------------------------------------------------


def test_rebuild_corpus_endpoint_accepts_fundamentals_provider_param(
    tmp_path: Path,
) -> None:
    """POST /analytics/calibration/rebuild-corpus accepts fundamentals_provider in body
    AND propagates it into the corpus_rebuild_jobs row.
    """
    import daemon.jobs as dj
    from api.app import create_app

    captured_provider: list[str] = []

    async def _stub_rebuild(
        db_path: str,
        tickers: list[tuple[str, str]] | None = None,
        **kwargs: Any,
    ) -> dict:
        captured_provider.append(kwargs.get("fundamentals_provider", "yfinance"))
        return {"rows_inserted": 100, "tickers_processed": 1, "run_id": "stub"}

    original = dj.rebuild_signal_corpus
    dj.rebuild_signal_corpus = _stub_rebuild  # type: ignore[attr-defined]

    db_path = str(tmp_path / "test.db")
    asyncio.run(init_db(db_path))
    app = create_app(db_path=db_path)

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/analytics/calibration/rebuild-corpus",
                json={
                    "tickers": ["AAPL"],
                    "asset_types": {"AAPL": "stock"},
                    "fundamentals_provider": "simfin",
                },
            )
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert "job_id" in body, f"job_id missing from: {body}"
        assert body["status"] == "started"

        # The stub captured fundamentals_provider — should be 'simfin'
        assert captured_provider == ["simfin"], (
            f"Expected ['simfin'], got {captured_provider!r}"
        )

        # Confirm the corpus_rebuild_jobs row has fundamentals_provider='simfin'
        async def _check_row() -> str | None:
            async with aiosqlite.connect(db_path) as conn:
                cursor = await conn.execute(
                    "SELECT fundamentals_provider FROM corpus_rebuild_jobs "
                    "WHERE job_id = ?",
                    (body["job_id"],),
                )
                r = await cursor.fetchone()
                return r[0] if r else None

        provider_in_db = asyncio.run(_check_row())
        assert provider_in_db == "simfin", (
            f"corpus_rebuild_jobs.fundamentals_provider not 'simfin': {provider_in_db!r}"
        )
    finally:
        dj.rebuild_signal_corpus = original  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Test 7: Pydantic Literal allowlist rejects invalid provider strings
# ---------------------------------------------------------------------------


def test_rebuild_corpus_endpoint_rejects_invalid_provider(tmp_path: Path) -> None:
    """T-08-02-02 mitigation: Pydantic Literal['yfinance','simfin'] rejects 'bogus'."""
    from api.app import create_app

    db_path = str(tmp_path / "test.db")
    asyncio.run(init_db(db_path))
    app = create_app(db_path=db_path)

    with TestClient(app) as client:
        resp = client.post(
            "/analytics/calibration/rebuild-corpus",
            json={
                "tickers": ["AAPL"],
                "asset_types": {"AAPL": "stock"},
                "fundamentals_provider": "bogus_provider; DROP TABLE",
            },
        )
    assert resp.status_code == 422, (
        f"Expected 422 for invalid provider, got {resp.status_code}: {resp.text}"
    )
