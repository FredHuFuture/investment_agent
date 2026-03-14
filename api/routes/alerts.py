"""Monitoring and alerts endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db_path
from monitoring.monitor import PortfolioMonitor
from monitoring.store import AlertStore

router = APIRouter()


@router.get("/alerts")
async def get_alerts(
    ticker: str | None = Query(None),
    severity: str | None = Query(None),
    acknowledged: int | None = Query(None, ge=0, le=1),
    limit: int = Query(20, ge=1, le=500),
    db_path: str = Depends(get_db_path),
):
    """Query recent monitoring alerts."""
    store = AlertStore(db_path)
    alerts = await store.get_recent_alerts(
        ticker=ticker, severity=severity, acknowledged=acknowledged, limit=limit,
    )
    return {"data": alerts, "warnings": []}


@router.patch("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    db_path: str = Depends(get_db_path),
):
    """Set acknowledged=1 on a monitoring_alerts row."""
    store = AlertStore(db_path)
    found = await store.acknowledge_alert(alert_id)
    if not found:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"data": {"id": alert_id, "acknowledged": 1}, "warnings": []}


@router.delete("/alerts/{alert_id}")
async def delete_alert(
    alert_id: int,
    db_path: str = Depends(get_db_path),
):
    """Delete a single alert."""
    store = AlertStore(db_path)
    found = await store.delete_alert(alert_id)
    if not found:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"data": {"id": alert_id, "deleted": True}, "warnings": []}


@router.post("/monitor/check")
async def run_monitor_check(db_path: str = Depends(get_db_path)):
    """Run a portfolio health check (saves alerts + snapshot)."""
    monitor = PortfolioMonitor(db_path=db_path)
    result = await monitor.run_check()
    return {"data": result, "warnings": result.get("warnings", [])}
