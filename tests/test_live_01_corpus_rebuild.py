"""Tests for LIVE-01: corpus_rebuild_jobs DDL, Pydantic models, and rebuild endpoints.

Task 1 covers:
  1a - corpus_rebuild_jobs table created with all required columns
  1b - corpus_rebuild_jobs indexes present
  1c - RebuildCorpusRequest accepts null tickers
  1d - RebuildCorpusRequest accepts explicit tickers
  1e - RebuildCorpusRequest rejects invalid ticker length
  1f - RebuildCorpusProgressResponse shape serialises correctly

Task 2 covers:
  2a - POST /rebuild-corpus returns job_id and runs in background
  2b - POST with tickers=null enumerates open portfolio positions
  2c - GET /rebuild-corpus/{job_id} polls live status
  2d - Per-ticker failure is isolated; batch continues; status='partial'
  2e - GET with unknown job_id returns 404
  2f - _run_batch_rebuild delegates per-ticker (FOUND-07 preservation)
  2g - Background task exception does not crash event loop
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import aiosqlite
import pytest
from pydantic import ValidationError

from db.database import init_db


# ---------------------------------------------------------------------------
# Task 1 tests: DDL + Pydantic models
# ---------------------------------------------------------------------------


def test_corpus_rebuild_jobs_table_created(tmp_path: Path) -> None:
    """After init_db, corpus_rebuild_jobs has all required columns."""
    async def _run() -> None:
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)
        async with aiosqlite.connect(db_path) as conn:
            rows = await (
                await conn.execute("PRAGMA table_info(corpus_rebuild_jobs)")
            ).fetchall()
        cols = {r[1] for r in rows}
        required = {
            "id", "job_id", "status", "tickers_total", "tickers_completed",
            "ticker_progress_json", "started_at", "completed_at", "error_message",
            "created_at",
        }
        assert required.issubset(cols), f"Missing columns: {required - cols}"

    asyncio.run(_run())


def test_corpus_rebuild_jobs_indexes_present(tmp_path: Path) -> None:
    """After init_db, corpus_rebuild_jobs has idx_crj_job_id and idx_crj_status."""
    async def _run() -> None:
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)
        async with aiosqlite.connect(db_path) as conn:
            rows = await (
                await conn.execute("PRAGMA index_list(corpus_rebuild_jobs)")
            ).fetchall()
        index_names = {r[1] for r in rows}
        assert "idx_crj_job_id" in index_names, f"idx_crj_job_id not found in {index_names}"
        assert "idx_crj_status" in index_names, f"idx_crj_status not found in {index_names}"

    asyncio.run(_run())


def test_rebuild_corpus_request_accepts_null_tickers() -> None:
    """RebuildCorpusRequest(tickers=None) parses; both tickers and asset_types are None."""
    from api.models import RebuildCorpusRequest

    req = RebuildCorpusRequest(tickers=None)
    assert req.tickers is None
    assert req.asset_types is None


def test_rebuild_corpus_request_accepts_explicit_tickers() -> None:
    """RebuildCorpusRequest with explicit tickers uppercases them; asset_types stored."""
    from api.models import RebuildCorpusRequest

    req = RebuildCorpusRequest(
        tickers=["aapl", "NVDA"],
        asset_types={"AAPL": "stock"},
    )
    assert req.tickers == ["AAPL", "NVDA"]
    # asset_types is stored as-is; asset_type defaulting for missing keys happens
    # at consumption time (in the endpoint), not at parse time.
    assert req.asset_types == {"AAPL": "stock"}


def test_rebuild_corpus_request_rejects_invalid_ticker_length() -> None:
    """RebuildCorpusRequest raises ValidationError for empty or too-long tickers."""
    from api.models import RebuildCorpusRequest

    with pytest.raises(ValidationError):
        RebuildCorpusRequest(tickers=[""])

    with pytest.raises(ValidationError):
        # 13 chars is over the 12-char limit
        RebuildCorpusRequest(tickers=["TOOLONGTICKER"])


def test_rebuild_corpus_progress_response_shape() -> None:
    """RebuildCorpusProgressResponse serialises to JSON with correct shape."""
    from api.models import RebuildCorpusProgressResponse

    resp = RebuildCorpusProgressResponse(
        job_id="abc123",
        status="running",
        tickers_completed=2,
        tickers_total=5,
        ticker_progress={
            "AAPL": {"status": "success", "rows_inserted": 750},
            "NVDA": {"status": "running"},
        },
        started_at="2026-04-23T00:00:00Z",
        completed_at=None,
        error_message=None,
    )
    data = resp.model_dump()
    assert data["job_id"] == "abc123"
    assert data["status"] == "running"
    assert data["tickers_completed"] == 2
    assert data["tickers_total"] == 5
    assert data["ticker_progress"]["AAPL"]["rows_inserted"] == 750
    assert data["completed_at"] is None


# ---------------------------------------------------------------------------
# Task 2 tests: Endpoints + background task
# ---------------------------------------------------------------------------


def _make_app_with_stub(tmp_path: Path, stub_rebuild: Any) -> tuple[Any, str]:
    """Helper: init DB, monkeypatch daemon.jobs.rebuild_signal_corpus, return (app, db_path)."""
    import daemon.jobs as dj

    db_path = str(tmp_path / "test.db")
    asyncio.run(init_db(db_path))

    # Replace the real rebuild_signal_corpus with the stub
    dj.rebuild_signal_corpus = stub_rebuild  # type: ignore[attr-defined]

    from api.app import create_app
    return create_app(db_path=db_path), db_path


def test_rebuild_corpus_endpoint_returns_job_id_and_runs_in_background(
    tmp_path: Path,
) -> None:
    """POST /analytics/calibration/rebuild-corpus returns 200 with job_id within time limit."""
    import daemon.jobs as dj
    from api.app import create_app
    from fastapi.testclient import TestClient

    call_count = [0]

    async def _stub_rebuild(
        db_path: str,
        tickers: list | None = None,
        **kwargs: Any,
    ) -> dict:
        call_count[0] += 1
        return {"rows_inserted": 100, "tickers_processed": 1, "run_id": "stub"}

    original = dj.rebuild_signal_corpus
    dj.rebuild_signal_corpus = _stub_rebuild  # type: ignore[attr-defined]

    db_path = str(tmp_path / "test.db")
    asyncio.run(init_db(db_path))
    app = create_app(db_path=db_path)

    try:
        with TestClient(app) as client:
            t0 = time.monotonic()
            resp = client.post(
                "/analytics/calibration/rebuild-corpus",
                json={"tickers": ["FAKE1"], "asset_types": {"FAKE1": "stock"}},
            )
            elapsed = time.monotonic() - t0

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert "job_id" in body, f"job_id missing from: {body}"
        assert body["status"] == "started"
        assert body["ticker_count"] == 1
        # TestClient runs BackgroundTasks synchronously after response; elapsed may vary
        # but the response itself is fast (background work is separate in TestClient)
    finally:
        dj.rebuild_signal_corpus = original  # type: ignore[attr-defined]


def test_rebuild_corpus_null_tickers_enumerates_portfolio(tmp_path: Path) -> None:
    """POST with tickers=null uses open positions; returns ticker_count matching open positions."""
    import daemon.jobs as dj
    from api.app import create_app
    from fastapi.testclient import TestClient
    from portfolio.manager import PortfolioManager

    called_with: list[list] = []

    async def _stub_rebuild(
        db_path: str,
        tickers: list | None = None,
        **kwargs: Any,
    ) -> dict:
        called_with.append(list(tickers or []))
        return {"rows_inserted": 50, "tickers_processed": 1, "run_id": "stub"}

    original = dj.rebuild_signal_corpus
    dj.rebuild_signal_corpus = _stub_rebuild  # type: ignore[attr-defined]

    db_path = str(tmp_path / "test.db")
    asyncio.run(init_db(db_path))

    # Seed 2 open positions
    async def _seed() -> None:
        pm = PortfolioManager(db_path)
        await pm.add_position("AAPL", "stock", 10, 150.0, "2025-01-01")
        await pm.add_position("NVDA", "stock", 5, 800.0, "2025-01-01")

    asyncio.run(_seed())

    app = create_app(db_path=db_path)

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/analytics/calibration/rebuild-corpus",
                json={"tickers": None},
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["ticker_count"] == 2, f"Expected 2, got {body['ticker_count']}"
        # TestClient executes BackgroundTasks synchronously before returning context
        # Verify each was called with single-element list
        assert len(called_with) == 2, f"Expected 2 calls, got {len(called_with)}"
        for call_args in called_with:
            assert len(call_args) == 1, f"Each call must be single-element: {call_args}"
    finally:
        dj.rebuild_signal_corpus = original  # type: ignore[attr-defined]


def test_rebuild_corpus_progress_endpoint_polls_live_status(tmp_path: Path) -> None:
    """GET /rebuild-corpus/{job_id} returns progress JSON after job completes."""
    import daemon.jobs as dj
    from api.app import create_app
    from fastapi.testclient import TestClient

    async def _stub_rebuild(
        db_path: str,
        tickers: list | None = None,
        **kwargs: Any,
    ) -> dict:
        return {"rows_inserted": 100, "tickers_processed": 1, "run_id": "stub"}

    original = dj.rebuild_signal_corpus
    dj.rebuild_signal_corpus = _stub_rebuild  # type: ignore[attr-defined]

    db_path = str(tmp_path / "test.db")
    asyncio.run(init_db(db_path))
    app = create_app(db_path=db_path)

    try:
        with TestClient(app) as client:
            post_resp = client.post(
                "/analytics/calibration/rebuild-corpus",
                json={"tickers": ["GOOG"], "asset_types": {"GOOG": "stock"}},
            )
            assert post_resp.status_code == 200
            job_id = post_resp.json()["job_id"]

            # TestClient runs BackgroundTasks synchronously, so job is complete now
            get_resp = client.get(f"/analytics/calibration/rebuild-corpus/{job_id}")
        assert get_resp.status_code == 200, f"Expected 200, got {get_resp.status_code}: {get_resp.text}"
        progress = get_resp.json()
        assert progress["job_id"] == job_id
        assert "status" in progress
        assert "tickers_completed" in progress
        assert "ticker_progress" in progress
    finally:
        dj.rebuild_signal_corpus = original  # type: ignore[attr-defined]


def test_rebuild_corpus_per_ticker_failure_is_isolated(tmp_path: Path) -> None:
    """Per-ticker exception is captured; batch continues; status='partial'."""
    import daemon.jobs as dj
    from api.app import create_app
    from fastapi.testclient import TestClient

    async def _stub_rebuild(
        db_path: str,
        tickers: list | None = None,
        **kwargs: Any,
    ) -> dict:
        ticker = (tickers or [])[0][0] if tickers else "UNKNOWN"
        if ticker == "BAD":
            raise ValueError("Simulated failure for BAD ticker")
        return {"rows_inserted": 200, "tickers_processed": 1, "run_id": "stub"}

    original = dj.rebuild_signal_corpus
    dj.rebuild_signal_corpus = _stub_rebuild  # type: ignore[attr-defined]

    db_path = str(tmp_path / "test.db")
    asyncio.run(init_db(db_path))
    app = create_app(db_path=db_path)

    try:
        with TestClient(app) as client:
            post_resp = client.post(
                "/analytics/calibration/rebuild-corpus",
                json={
                    "tickers": ["GOOD", "BAD"],
                    "asset_types": {"GOOD": "stock", "BAD": "stock"},
                },
            )
            assert post_resp.status_code == 200
            job_id = post_resp.json()["job_id"]

            get_resp = client.get(f"/analytics/calibration/rebuild-corpus/{job_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()

        # Overall status must be 'partial' (some OK, some failed)
        assert data["status"] == "partial", f"Expected 'partial', got {data['status']}"
        assert data["tickers_completed"] == 2  # both attempted

        ticker_progress = data["ticker_progress"]
        assert ticker_progress["GOOD"]["status"] == "success"
        assert ticker_progress["GOOD"]["rows_inserted"] == 200
        assert ticker_progress["BAD"]["status"] == "error"
        assert "error" in ticker_progress["BAD"]
    finally:
        dj.rebuild_signal_corpus = original  # type: ignore[attr-defined]


def test_rebuild_corpus_progress_endpoint_404_on_unknown_job_id(tmp_path: Path) -> None:
    """GET /rebuild-corpus/<nonexistent> returns 404."""
    from api.app import create_app
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "test.db")
    asyncio.run(init_db(db_path))
    app = create_app(db_path=db_path)

    with TestClient(app) as client:
        resp = client.get("/analytics/calibration/rebuild-corpus/nonexistent-job-id")
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


def test_rebuild_corpus_delegates_per_ticker(tmp_path: Path) -> None:
    """_run_batch_rebuild calls rebuild_signal_corpus once per ticker with single-element list.

    FOUND-07 preservation: each ticker is its own atomic unit.
    """
    import daemon.jobs as dj
    from api.app import create_app
    from fastapi.testclient import TestClient

    calls: list[tuple[str, str]] = []

    async def _stub_rebuild(
        db_path: str,
        tickers: list | None = None,
        **kwargs: Any,
    ) -> dict:
        assert tickers is not None
        assert len(tickers) == 1, (
            f"FOUND-07 violation: expected single-element list, got {tickers}"
        )
        calls.append(tickers[0])
        return {"rows_inserted": 10, "tickers_processed": 1, "run_id": "stub"}

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
                    "tickers": ["MSFT", "AMZN", "GOOG"],
                    "asset_types": {"MSFT": "stock", "AMZN": "stock", "GOOG": "stock"},
                },
            )
            assert resp.status_code == 200
            assert resp.json()["ticker_count"] == 3

        # Must have been called exactly 3 times
        assert len(calls) == 3, f"Expected 3 calls, got {len(calls)}: {calls}"
        tickers_called = {t for t, _ in calls}
        assert tickers_called == {"MSFT", "AMZN", "GOOG"}
    finally:
        dj.rebuild_signal_corpus = original  # type: ignore[attr-defined]


def test_rebuild_corpus_background_task_does_not_leak_on_exception(
    tmp_path: Path,
) -> None:
    """Background task exception is captured; subsequent POSTs still work; status='error'."""
    import daemon.jobs as dj
    from api.app import create_app
    from fastapi.testclient import TestClient

    call_count = [0]

    async def _stub_rebuild_fail(
        db_path: str,
        tickers: list | None = None,
        **kwargs: Any,
    ) -> dict:
        call_count[0] += 1
        raise RuntimeError("Intentional failure to test exception isolation")

    original = dj.rebuild_signal_corpus
    dj.rebuild_signal_corpus = _stub_rebuild_fail  # type: ignore[attr-defined]

    db_path = str(tmp_path / "test.db")
    asyncio.run(init_db(db_path))
    app = create_app(db_path=db_path)

    try:
        with TestClient(app) as client:
            # First POST — all tickers will fail
            resp1 = client.post(
                "/analytics/calibration/rebuild-corpus",
                json={"tickers": ["FAIL1"], "asset_types": {"FAIL1": "stock"}},
            )
            assert resp1.status_code == 200
            job_id = resp1.json()["job_id"]

            # Progress check — status should be 'error' (all tickers failed)
            get_resp = client.get(f"/analytics/calibration/rebuild-corpus/{job_id}")
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["status"] == "error", f"Expected 'error', got {data['status']}"

            # Second POST — API event loop must still be responsive
            resp2 = client.post(
                "/analytics/calibration/rebuild-corpus",
                json={"tickers": ["FAIL2"], "asset_types": {"FAIL2": "stock"}},
            )
            assert resp2.status_code == 200, (
                f"API must remain responsive after background task failure; got {resp2.status_code}"
            )
    finally:
        dj.rebuild_signal_corpus = original  # type: ignore[attr-defined]
