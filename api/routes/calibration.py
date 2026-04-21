"""API route for per-agent calibration metrics (SIG-02, SIG-03).

GET /analytics/calibration returns Brier score, rolling IC, and IC-IR per agent,
read from backtest_signal_history (populated by Plan 02-02 populate_signal_corpus).

WARNING 11 fix: the IC value is always surfaced under the stable key "ic_5d",
regardless of which horizon was requested. The companion "ic_horizon" field tells
the consumer which horizon produced the value. This avoids a dynamic key schema
(e.g., "ic_5d" vs "ic_21d") that would require frontend code changes on each
new horizon.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.deps import get_db_path
from tracking.store import SignalStore
from tracking.tracker import SignalTracker

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
