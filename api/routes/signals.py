"""Signal tracking endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.deps import get_db_path
from tracking.store import SignalStore
from tracking.tracker import SignalTracker

router = APIRouter()


@router.get("/history")
async def get_signal_history(
    ticker: str | None = Query(None),
    signal: str | None = Query(None),
    limit: int = Query(20, ge=1, le=500),
    db_path: str = Depends(get_db_path),
):
    """Query signal history with optional filters."""
    store = SignalStore(db_path)
    history = await store.get_signal_history(ticker=ticker, signal=signal, limit=limit)
    return {"data": history, "warnings": []}


@router.get("/accuracy")
async def get_accuracy_stats(
    lookback: int = Query(100, ge=1),
    db_path: str = Depends(get_db_path),
):
    """Compute signal accuracy statistics."""
    tracker = SignalTracker(SignalStore(db_path))
    stats = await tracker.compute_accuracy_stats(lookback=lookback)
    return {"data": stats, "warnings": []}


@router.get("/calibration")
async def get_calibration(
    lookback: int = Query(100, ge=1),
    min_bucket_size: int = Query(5, ge=1),
    db_path: str = Depends(get_db_path),
):
    """Compute confidence calibration data."""
    tracker = SignalTracker(SignalStore(db_path))
    data = await tracker.compute_calibration_data(
        lookback=lookback, min_bucket_size=min_bucket_size,
    )
    return {"data": data, "warnings": []}


@router.get("/agents")
async def get_agent_performance(
    lookback: int = Query(100, ge=1),
    db_path: str = Depends(get_db_path),
):
    """Compute per-agent directional accuracy and agreement rates."""
    tracker = SignalTracker(SignalStore(db_path))
    perf = await tracker.compute_agent_performance(lookback=lookback)
    return {"data": perf, "warnings": []}


@router.get("/accuracy-trend")
async def accuracy_trend(
    window: int = Query(30, ge=5, le=100),
    db_path: str = Depends(get_db_path),
):
    """Rolling accuracy trend over resolved signals."""
    tracker = SignalTracker(SignalStore(db_path))
    data = await tracker.compute_accuracy_trend(window)
    return {"data": data, "warnings": []}


@router.get("/agent-agreement")
async def agent_agreement(
    lookback: int = Query(100, ge=10, le=500),
    db_path: str = Depends(get_db_path),
):
    """Pairwise agreement rates between agents."""
    tracker = SignalTracker(SignalStore(db_path))
    data = await tracker.compute_agent_agreement(lookback)
    return {"data": data, "warnings": []}
