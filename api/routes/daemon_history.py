"""Daemon run history endpoint — query past job executions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.deps import get_db_path

import aiosqlite

router = APIRouter()

_COLUMNS = (
    "id, job_name, status, started_at, "
    "duration_ms, result_json, error_message, created_at"
)


@router.get("/history")
async def get_daemon_history(
    job_name: str | None = Query(default=None, description="Filter by job name"),
    limit: int = Query(default=20, ge=1, le=200, description="Max rows to return"),
    db_path: str = Depends(get_db_path),
):
    """Return recent daemon run history, optionally filtered by job_name."""
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row

        if job_name:
            rows = await (
                await conn.execute(
                    f"SELECT {_COLUMNS} FROM daemon_runs "
                    "WHERE job_name = ? ORDER BY created_at DESC LIMIT ?",
                    (job_name, limit),
                )
            ).fetchall()
        else:
            rows = await (
                await conn.execute(
                    f"SELECT {_COLUMNS} FROM daemon_runs "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            ).fetchall()

        return {"data": [dict(r) for r in rows], "warnings": []}
