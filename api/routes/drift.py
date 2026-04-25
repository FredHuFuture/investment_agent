"""API route for drift_log query (AN-02).

GET /api/v1/drift/log?days=7&limit=200

Returns the latest drift_log row per (agent_name, asset_type) within the
requested day window, sorted by evaluated_at DESC.

Response shape:
    {
        "drifts": [
            {
                "id": int,
                "agent_name": str,
                "asset_type": str,
                "evaluated_at": str,
                "current_icir": float | null,
                "avg_icir_60d": float | null,
                "delta_pct": float | null,
                "threshold_type": str | null,
                "triggered": bool,
                "preliminary_threshold": bool,
                "weight_before": float | null,
                "weight_after": float | null,
            },
            ...
        ]
    }
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import aiosqlite
from fastapi import APIRouter, Depends, Query

from api.deps import get_db_path

_route_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/log")
async def get_drift_log(
    days: int = Query(default=7, ge=1, le=365, description="Look-back window in days"),
    limit: int = Query(default=200, ge=1, le=1000, description="Max rows to return"),
    db_path: str = Depends(get_db_path),
) -> dict:
    """Return the latest drift_log rows within the specified look-back window.

    Rows are sorted by evaluated_at DESC (most recent first).
    ``triggered`` and ``preliminary_threshold`` are coerced from SQLite INTEGER
    to Python bool.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    try:
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute(
                    """
                    SELECT
                        id,
                        agent_name,
                        asset_type,
                        evaluated_at,
                        current_icir,
                        avg_icir_60d,
                        delta_pct,
                        threshold_type,
                        triggered,
                        preliminary_threshold,
                        weight_before,
                        weight_after
                    FROM drift_log
                    WHERE evaluated_at >= ?
                    ORDER BY evaluated_at DESC
                    LIMIT ?
                    """,
                    (cutoff, limit),
                )
            ).fetchall()
    except Exception as exc:
        _route_logger.warning("drift_log query failed: %s", exc)
        # Table may not exist yet (pre-init_db call) — return empty gracefully
        return {"drifts": []}

    drifts = []
    for row in rows:
        drifts.append(
            {
                "id": row["id"],
                "agent_name": row["agent_name"],
                "asset_type": row["asset_type"],
                "evaluated_at": row["evaluated_at"],
                "current_icir": row["current_icir"],
                "avg_icir_60d": row["avg_icir_60d"],
                "delta_pct": row["delta_pct"],
                "threshold_type": row["threshold_type"],
                "triggered": bool(row["triggered"]),
                "preliminary_threshold": bool(row["preliminary_threshold"]),
                "weight_before": row["weight_before"],
                "weight_after": row["weight_after"],
            }
        )

    return {"drifts": drifts}
