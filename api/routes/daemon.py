"""Daemon status and run-once endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_db_path
from api.models import RunOnceRequest
from daemon.config import DaemonConfig
from daemon.scheduler import MonitoringDaemon

router = APIRouter()


@router.get("/status")
async def get_daemon_status(db_path: str = Depends(get_db_path)):
    """Get daemon job execution history."""
    config = DaemonConfig(db_path=db_path)
    daemon = MonitoringDaemon(config)
    status = await daemon.get_status()
    return {"data": status, "warnings": []}


@router.post("/run-once")
async def daemon_run_once(body: RunOnceRequest, db_path: str = Depends(get_db_path)):
    """Execute a single daemon job (daily or weekly)."""
    config = DaemonConfig(db_path=db_path)
    daemon = MonitoringDaemon(config)
    result = await daemon.run_once(body.job)
    return {"data": result, "warnings": []}
