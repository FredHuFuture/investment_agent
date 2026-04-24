"""API route for per-agent calibration metrics (SIG-02, SIG-03) and corpus rebuild (LIVE-01).

GET /analytics/calibration returns Brier score, rolling IC, and IC-IR per agent,
read from backtest_signal_history (populated by Plan 02-02 populate_signal_corpus).

WARNING 11 fix: the IC value is always surfaced under the stable key "ic_5d",
regardless of which horizon was requested. The companion "ic_horizon" field tells
the consumer which horizon produced the value. This avoids a dynamic key schema
(e.g., "ic_5d" vs "ic_21d") that would require frontend code changes on each
new horizon.

LIVE-01 additions:
  POST /analytics/calibration/rebuild-corpus  — trigger async batch rebuild
  GET  /analytics/calibration/rebuild-corpus/{job_id} — poll progress
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import aiosqlite
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from api.deps import get_db_path
from api.models import (
    RebuildCorpusProgressResponse,
    RebuildCorpusRequest,
    RebuildCorpusResponse,
)
from tracking.store import SignalStore
from tracking.tracker import SignalTracker

_route_logger = logging.getLogger(__name__)

router = APIRouter()

# The six canonical agents active in the production pipeline.
KNOWN_AGENTS = [
    "TechnicalAgent",
    "FundamentalAgent",
    "MacroAgent",
    "SentimentAgent",
    "CryptoAgent",
    "SummaryAgent",
]

# Agents expected to have null calibration metrics and the reason why.
# FundamentalAgent returns HOLD in backtest_mode (Phase 1 FOUND-04 contract) so it
# never generates directional signals in the backtest corpus.
NULL_EXPECTED: dict[str, str] = {
    "FundamentalAgent": (
        "FundamentalAgent returns HOLD in backtest_mode (Phase 1 FOUND-04 "
        "contract); excluded from backtest-generated signal corpus. "
        "Calibrate from live signal_history when outcome data accumulates."
    ),
}


@router.get("/calibration")
async def get_calibration(
    horizon: str = Query("5d", pattern="^(5d|21d)$"),
    window: int = Query(60, ge=10, le=252),
    db_path: str = Depends(get_db_path),
) -> dict:
    """Per-agent calibration metrics: Brier score, rolling IC, IC-IR.

    Data source: ``backtest_signal_history`` (populated by
    ``backtesting/signal_corpus.py``). The live ``signal_history`` table has
    insufficient rows (10 as of 2026-04-21) for calibration.

    Response marks ``preliminary_calibration=true`` to indicate that the window
    sizes (30/60/5) are data-scarcity defensive and should be revisited to the
    qlib standard (252/63) once live history accumulates.

    WARNING 11 fix: "ic_5d" is a stable key name — it always holds the IC value
    at the requested horizon. "ic_horizon" indicates which horizon was used.
    """
    store = SignalStore(db_path)
    tracker = SignalTracker(store)

    agent_metrics: dict[str, dict] = {}

    for agent in KNOWN_AGENTS:
        if agent in NULL_EXPECTED:
            # FOUND-04 contract: FundamentalAgent explicitly null with explanatory note
            agent_metrics[agent] = {
                "brier_score": None,
                "ic_5d": None,          # WARNING 11 fix: stable key, value None
                "ic_horizon": horizon,  # WARNING 11 fix: horizon indicator always present
                "ic_ir": None,
                "sample_size": 0,
                "preliminary_calibration": True,
                "signal_source": "backtest_generated",
                "note": NULL_EXPECTED[agent],
                "rolling_ic": [],  # LIVE-02: empty list for NULL_EXPECTED agents
            }
            continue

        brier = await tracker.compute_brier_score(agent, horizon=horizon)
        overall_ic, rolling = await tracker.compute_rolling_ic(
            agent, horizon=horizon, window=window,
        )
        icir = tracker.compute_icir(rolling) if rolling else None
        sample_size = sum(1 for ic in rolling if ic is not None) if rolling else 0

        agent_metrics[agent] = {
            "brier_score": brier,
            # WARNING 11 fix: stable "ic_5d" field always present regardless of horizon.
            # The value is the overall_ic computed at the requested horizon.
            # ic_horizon tells the consumer which horizon produced it.
            "ic_5d": overall_ic,
            "ic_horizon": horizon,  # "5d" or "21d"
            "ic_ir": icir,
            "sample_size": sample_size,
            "preliminary_calibration": True,
            "signal_source": "backtest_generated",
            # LIVE-02: expose rolling IC time series for CalibrationPage sparkline.
            # rolling is already computed above by compute_rolling_ic; pad with [] when empty.
            "rolling_ic": rolling or [],
        }

    corpus = await store.get_backtest_corpus_metadata()

    return {
        "data": {
            "agents": agent_metrics,
            "corpus_metadata": corpus,
            "horizon": horizon,
            "window_days": window,
        },
        "warnings": (
            ["Calibration is preliminary — window sizes are data-scarcity defensive"]
            if corpus.get("total_observations", 0) < 200
            else []
        ),
    }


# ---------------------------------------------------------------------------
# LIVE-01: POST /calibration/rebuild-corpus + GET /calibration/rebuild-corpus/{job_id}
# ---------------------------------------------------------------------------


@router.post("/calibration/rebuild-corpus", response_model=RebuildCorpusResponse)
async def rebuild_corpus_endpoint(
    body: RebuildCorpusRequest,
    background_tasks: BackgroundTasks,
    db_path: str = Depends(get_db_path),
) -> RebuildCorpusResponse:
    """LIVE-01: Trigger backtest signal corpus rebuild.

    Body: ``{"tickers": ["AAPL","NVDA"] | null, "asset_types": {"AAPL":"stock"} | null}``

    Returns 200 immediately with ``{job_id, status:"started", ticker_count}``.
    Per-ticker work runs as a FastAPI BackgroundTask after the response is sent.
    Poll ``GET /calibration/rebuild-corpus/{job_id}`` for progress.

    When ``tickers`` is null the endpoint enumerates all OPEN positions from
    active_positions via PortfolioManager.  Each ticker delegates to
    ``daemon.jobs.rebuild_signal_corpus(tickers=[(ticker, asset_type)])``
    (single-element list) which preserves the FOUND-07 two-connection pattern
    and BLOCKER-3 DELETE rollback guard intact.

    Status taxonomy: running → success (all OK) | partial (some failed) | error (all failed).
    """
    from portfolio.manager import PortfolioManager

    # Resolve ticker list
    if body.tickers is None:
        pm = PortfolioManager(db_path)
        positions = await pm.get_all_positions()
        tickers_with_type: list[tuple[str, str]] = [
            (p.ticker, p.asset_type) for p in positions if p.status == "open"
        ]
    else:
        at_map = body.asset_types or {}
        tickers_with_type = [
            (t, at_map.get(t, "stock")) for t in body.tickers
        ]

    if not tickers_with_type:
        raise HTTPException(
            status_code=400,
            detail=(
                "No tickers to rebuild: portfolio is empty and no explicit tickers supplied"
            ),
        )

    job_id = uuid.uuid4().hex
    started_at = datetime.now(timezone.utc).isoformat()

    # Persist initial job row synchronously (short-lived connection)
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO corpus_rebuild_jobs
                (job_id, status, tickers_total, tickers_completed,
                 ticker_progress_json, started_at)
            VALUES (?, 'running', ?, 0, ?, ?)
            """,
            (
                job_id,
                len(tickers_with_type),
                json.dumps({t: {"status": "pending"} for t, _ in tickers_with_type}),
                started_at,
            ),
        )
        await conn.commit()

    # FastAPI BackgroundTasks runs AFTER the response is sent.
    # In test mode (TestClient) it runs synchronously before the context manager exits.
    background_tasks.add_task(
        _run_batch_rebuild,
        db_path=db_path,
        job_id=job_id,
        tickers_with_type=tickers_with_type,
    )

    return RebuildCorpusResponse(
        job_id=job_id,
        status="started",
        ticker_count=len(tickers_with_type),
    )


@router.get(
    "/calibration/rebuild-corpus/{job_id}",
    response_model=RebuildCorpusProgressResponse,
)
async def rebuild_corpus_progress_endpoint(
    job_id: str,
    db_path: str = Depends(get_db_path),
) -> RebuildCorpusProgressResponse:
    """LIVE-01: Poll progress of a rebuild-corpus job.

    Returns 404 if job_id is unknown.
    """
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (
            await conn.execute(
                """
                SELECT job_id, status, tickers_total, tickers_completed,
                       ticker_progress_json, started_at, completed_at, error_message
                FROM corpus_rebuild_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            )
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return RebuildCorpusProgressResponse(
        job_id=row["job_id"],
        status=row["status"],
        tickers_total=row["tickers_total"],
        tickers_completed=row["tickers_completed"],
        ticker_progress=json.loads(row["ticker_progress_json"] or "{}"),
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        error_message=row["error_message"],
    )


async def _run_batch_rebuild(
    db_path: str,
    job_id: str,
    tickers_with_type: list[tuple[str, str]],
) -> None:
    """Background task: rebuild corpus per-ticker and persist progress.

    FOUND-07 contract: each ticker is passed as a *single-element* list
    ``[(ticker, asset_type)]`` to ``rebuild_signal_corpus``.  This preserves
    the existing two-connection pattern and BLOCKER-3 DELETE rollback guard
    inside that function — we add no second layer here.

    Per-ticker failures are isolated: exceptions are caught, recorded in
    ``ticker_progress_json``, and the loop continues to the next ticker.

    Security (T-05-01-04): exception text is truncated to 500 chars before
    persisting to DB, mirroring the daemon/jobs.py line ~1136 pattern.

    Outer exception guard (WR-01/WR-02): any systemic failure before or
    outside the per-ticker loop (e.g., ImportError on the deferred import)
    is caught and written to the job row as status='error' with error_message
    populated, preventing the row from being stuck at status='running'.
    """
    try:
        try:
            from daemon.jobs import rebuild_signal_corpus
        except Exception as import_exc:
            _route_logger.error(
                "rebuild_corpus_batch: failed to import rebuild_signal_corpus"
                " for job_id=%s: %s",
                job_id,
                import_exc,
            )
            raise  # re-raise so outer guard records it as error

        progress: dict[str, dict] = {
            t: {"status": "pending"} for t, _ in tickers_with_type
        }
        successes = 0
        failures = 0

        for ticker, asset_type in tickers_with_type:
            # Mark ticker as running and flush
            progress[ticker] = {"status": "running"}
            await _update_progress(db_path, job_id, progress, increment_completed=False)

            try:
                result = await rebuild_signal_corpus(
                    db_path=db_path,
                    tickers=[(ticker, asset_type)],
                )
                progress[ticker] = {
                    "status": "success",
                    "rows_inserted": int(result.get("rows_inserted", 0)),
                }
                successes += 1
            except Exception as exc:
                err_text = str(exc)[:500]  # T-05-01-04: truncate to 500 chars
                _route_logger.error(
                    "rebuild_corpus_batch: ticker=%s failed: %s",
                    ticker,
                    err_text,
                )
                progress[ticker] = {
                    "status": "error",
                    "error": err_text,
                }
                failures += 1

            # Increment tickers_completed and flush updated progress
            await _update_progress(db_path, job_id, progress, increment_completed=True)

        # Determine final job status
        if failures == 0:
            final_status = "success"
            error_summary: str | None = None
        elif successes == 0:
            final_status = "error"
            # WR-02: summarise per-ticker errors into error_message
            error_texts = [
                f"{t}: {progress[t].get('error', 'unknown error')}"
                for t in progress
                if progress[t].get("status") == "error"
            ]
            error_summary = "; ".join(error_texts)[:500]
        else:
            final_status = "partial"
            # WR-02: note that partial failures exist; details in ticker_progress
            failed_tickers = [
                t for t in progress if progress[t].get("status") == "error"
            ]
            error_summary = (
                f"{len(failed_tickers)} ticker(s) failed"
                f" (see ticker_progress for per-ticker errors): "
                + ", ".join(failed_tickers)
            )[:500]

        completed_at = datetime.now(timezone.utc).isoformat()
        try:
            async with aiosqlite.connect(db_path) as conn:
                await conn.execute(
                    """
                    UPDATE corpus_rebuild_jobs
                    SET status = ?, completed_at = ?, ticker_progress_json = ?,
                        error_message = ?
                    WHERE job_id = ?
                    """,
                    (
                        final_status,
                        completed_at,
                        json.dumps(progress),
                        error_summary,
                        job_id,
                    ),
                )
                await conn.commit()
        except Exception as upd_exc:
            _route_logger.warning(
                "rebuild_corpus_batch: final status update failed for job_id=%s: %s",
                job_id,
                upd_exc,
            )

    except Exception as outer_exc:
        # WR-01: systemic failure outside the per-ticker loop — mark job as error
        # so GET polling surfaces the failure instead of staying stuck at 'running'.
        _route_logger.error(
            "rebuild_corpus_batch: unhandled exception for job_id=%s: %s",
            job_id,
            outer_exc,
        )
        try:
            async with aiosqlite.connect(db_path) as conn:
                await conn.execute(
                    """
                    UPDATE corpus_rebuild_jobs
                    SET status = 'error', completed_at = ?, error_message = ?
                    WHERE job_id = ?
                    """,
                    (
                        datetime.now(timezone.utc).isoformat(),
                        str(outer_exc)[:500],
                        job_id,
                    ),
                )
                await conn.commit()
        except Exception:
            _route_logger.warning(
                "rebuild_corpus_batch: could not write outer error for job_id=%s",
                job_id,
            )


async def _update_progress(
    db_path: str,
    job_id: str,
    progress: dict[str, dict],
    increment_completed: bool,
) -> None:
    """Persist per-ticker progress to corpus_rebuild_jobs using a short-lived connection.

    Short-lived separate connection per call matches the WR-02 pattern used by
    daemon/jobs.py::prune_signal_history — avoids holding a write lock across
    the entire batch rebuild (which may take minutes for large portfolios).

    Failure here is non-fatal: logged as WARNING, batch continues.
    """
    try:
        async with aiosqlite.connect(db_path) as conn:
            if increment_completed:
                await conn.execute(
                    """
                    UPDATE corpus_rebuild_jobs
                    SET ticker_progress_json = ?,
                        tickers_completed = tickers_completed + 1
                    WHERE job_id = ?
                    """,
                    (json.dumps(progress), job_id),
                )
            else:
                await conn.execute(
                    """
                    UPDATE corpus_rebuild_jobs
                    SET ticker_progress_json = ?
                    WHERE job_id = ?
                    """,
                    (json.dumps(progress), job_id),
                )
            await conn.commit()
    except Exception as upd_exc:
        _route_logger.warning(
            "rebuild_corpus_batch: progress update failed for job_id=%s: %s",
            job_id,
            upd_exc,
        )
