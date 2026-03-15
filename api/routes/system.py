"""System info endpoint."""
from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends

from api.deps import get_db_path

router = APIRouter()


@router.get("/info")
async def system_info(db_path: str = Depends(get_db_path)):
    """Return system status and aggregate DB counts."""
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM active_positions WHERE status='open'"
        )
        total_positions = (await cur.fetchone())[0]

        cur = await db.execute(
            "SELECT COUNT(*) FROM active_positions WHERE status='closed'"
        )
        total_closed = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COUNT(*) FROM signal_history")
        total_signals = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COUNT(*) FROM monitoring_alerts")
        total_alerts = (await cur.fetchone())[0]

    return {
        "data": {
            "status": "ok",
            "db_path": db_path,
            "version": "5.33",
            "total_positions": total_positions,
            "total_closed": total_closed,
            "total_signals": total_signals,
            "total_alerts": total_alerts,
        },
        "warnings": [],
    }
