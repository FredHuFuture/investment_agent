"""Alert analytics / stats endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

import aiosqlite

from api.deps import get_db_path

router = APIRouter()


@router.get("/alerts/stats")
async def get_alert_stats(
    days: int = Query(30, ge=1, le=365),
    db_path: str = Depends(get_db_path),
):
    """Aggregate alert statistics over the requested period."""
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        period_filter = f"-{days} days"

        # --- total count ---
        row = await (
            await conn.execute(
                "SELECT COUNT(*) FROM monitoring_alerts WHERE created_at >= datetime('now', ?)",
                (period_filter,),
            )
        ).fetchone()
        total_count: int = row[0] if row else 0

        # --- unacknowledged count ---
        row = await (
            await conn.execute(
                "SELECT COUNT(*) FROM monitoring_alerts "
                "WHERE created_at >= datetime('now', ?) AND acknowledged = 0",
                (period_filter,),
            )
        ).fetchone()
        unacknowledged_count: int = row[0] if row else 0

        # --- ack rate ---
        if total_count > 0:
            ack_rate_pct = round(((total_count - unacknowledged_count) / total_count) * 100, 1)
        else:
            ack_rate_pct = 100.0

        # --- by_severity ---
        rows = await (
            await conn.execute(
                "SELECT severity, COUNT(*) AS cnt FROM monitoring_alerts "
                "WHERE created_at >= datetime('now', ?) GROUP BY severity",
                (period_filter,),
            )
        ).fetchall()
        by_severity: dict[str, int] = {r[0]: r[1] for r in rows}

        # --- by_type ---
        rows = await (
            await conn.execute(
                "SELECT alert_type, COUNT(*) AS cnt FROM monitoring_alerts "
                "WHERE created_at >= datetime('now', ?) GROUP BY alert_type",
                (period_filter,),
            )
        ).fetchall()
        by_type: dict[str, int] = {r[0]: r[1] for r in rows}

        # --- by_ticker (top 10) with severity breakdown ---
        rows = await (
            await conn.execute(
                "SELECT ticker, COUNT(*) AS cnt FROM monitoring_alerts "
                "WHERE created_at >= datetime('now', ?) AND ticker IS NOT NULL "
                "GROUP BY ticker ORDER BY cnt DESC LIMIT 10",
                (period_filter,),
            )
        ).fetchall()

        by_ticker: list[dict] = []
        for r in rows:
            ticker = r[0]
            count = r[1]
            sev_rows = await (
                await conn.execute(
                    "SELECT severity, COUNT(*) AS cnt FROM monitoring_alerts "
                    "WHERE created_at >= datetime('now', ?) AND ticker = ? "
                    "GROUP BY severity",
                    (period_filter, ticker),
                )
            ).fetchall()
            severity_breakdown = {sr[0]: sr[1] for sr in sev_rows}
            by_ticker.append(
                {"ticker": ticker, "count": count, "severity_breakdown": severity_breakdown}
            )

        # --- avg alerts per day ---
        avg_alerts_per_day = round(total_count / days, 1) if days > 0 else 0.0

    return {
        "data": {
            "total_count": total_count,
            "unacknowledged_count": unacknowledged_count,
            "ack_rate_pct": ack_rate_pct,
            "by_ticker": by_ticker,
            "by_type": by_type,
            "by_severity": by_severity,
            "avg_alerts_per_day": avg_alerts_per_day,
        },
        "warnings": [],
    }
