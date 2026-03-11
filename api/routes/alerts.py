"""Monitoring and alerts endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.deps import get_db_path
from monitoring.monitor import PortfolioMonitor
from monitoring.store import AlertStore

router = APIRouter()


@router.get("/alerts")
async def get_alerts(
    ticker: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(20, ge=1, le=500),
    db_path: str = Depends(get_db_path),
):
    """Query recent monitoring alerts."""
    store = AlertStore(db_path)
    alerts = await store.get_recent_alerts(ticker=ticker, severity=severity, limit=limit)
    return {"data": alerts, "warnings": []}


@router.post("/monitor/check")
async def run_monitor_check(db_path: str = Depends(get_db_path)):
    """Run a portfolio health check (saves alerts + snapshot)."""
    monitor = PortfolioMonitor(db_path=db_path)
    result = await monitor.run_check()
    return {"data": result, "warnings": result.get("warnings", [])}
