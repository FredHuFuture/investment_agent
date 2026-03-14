from __future__ import annotations

from pathlib import Path
from typing import Any

import aiosqlite

from monitoring.models import Alert


class AlertStore:
    """Persist and query monitoring alerts."""

    def __init__(self, db: str | Path | aiosqlite.Connection) -> None:
        if isinstance(db, aiosqlite.Connection):
            self._connection: aiosqlite.Connection | None = db
            self._db_path: Path | None = None
        else:
            self._connection = None
            self._db_path = Path(db)

    async def _with_conn(self, func):
        if self._connection is not None:
            return await func(self._connection)
        if self._db_path is None:
            raise RuntimeError("AlertStore is missing both connection and database path.")
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute("PRAGMA foreign_keys=ON;")
            return await func(conn)

    async def save_alert(self, alert: Alert) -> int:
        """Insert alert into monitoring_alerts. Returns alert id."""
        async def _op(conn: aiosqlite.Connection) -> int:
            cursor = await conn.execute(
                """
                INSERT INTO monitoring_alerts (
                    ticker, alert_type, severity, message,
                    recommended_action, current_price, trigger_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.ticker, alert.alert_type, alert.severity,
                    alert.message, alert.recommended_action,
                    alert.current_price, alert.trigger_price,
                ),
            )
            await conn.commit()
            return int(cursor.lastrowid)

        return await self._with_conn(_op)

    async def save_alerts(self, alerts: list[Alert]) -> list[int]:
        """Insert multiple alerts in a single transaction."""
        if not alerts:
            return []

        async def _op(conn: aiosqlite.Connection) -> list[int]:
            ids: list[int] = []
            for alert in alerts:
                cursor = await conn.execute(
                    """
                    INSERT INTO monitoring_alerts (
                        ticker, alert_type, severity, message,
                        recommended_action, current_price, trigger_price
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        alert.ticker, alert.alert_type, alert.severity,
                        alert.message, alert.recommended_action,
                        alert.current_price, alert.trigger_price,
                    ),
                )
                ids.append(int(cursor.lastrowid))
            await conn.commit()
            return ids

        return await self._with_conn(_op)

    async def acknowledge_alert(self, alert_id: int) -> bool:
        """Set acknowledged=1 for a single alert. Returns True if found."""
        async def _op(conn: aiosqlite.Connection) -> bool:
            cursor = await conn.execute(
                "UPDATE monitoring_alerts SET acknowledged = 1 WHERE id = ?",
                (alert_id,),
            )
            await conn.commit()
            return cursor.rowcount > 0

        return await self._with_conn(_op)

    async def delete_alert(self, alert_id: int) -> bool:
        """Delete a single alert by id. Returns True if found."""
        async def _op(conn: aiosqlite.Connection) -> bool:
            cursor = await conn.execute(
                "DELETE FROM monitoring_alerts WHERE id = ?",
                (alert_id,),
            )
            await conn.commit()
            return cursor.rowcount > 0

        return await self._with_conn(_op)

    async def get_recent_alerts(
        self,
        ticker: str | None = None,
        limit: int = 20,
        severity: str | None = None,
        acknowledged: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query recent alerts, optionally filtered by ticker/severity.

        Returns list of dicts with all alert fields + id + created_at.
        Ordered by created_at DESC.
        """
        async def _op(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
            conditions: list[str] = []
            params: list[Any] = []
            if ticker is not None:
                conditions.append("ticker = ?")
                params.append(ticker)
            if severity is not None:
                conditions.append("severity = ?")
                params.append(severity)
            if acknowledged is not None:
                conditions.append("acknowledged = ?")
                params.append(acknowledged)
            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            params.append(limit)
            rows = await (
                await conn.execute(
                    f"""
                    SELECT id, ticker, alert_type, severity, message,
                           recommended_action, current_price, trigger_price,
                           acknowledged, created_at
                    FROM monitoring_alerts
                    {where}
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    params,
                )
            ).fetchall()
            return [
                {
                    "id": row[0],
                    "ticker": row[1],
                    "alert_type": row[2],
                    "severity": row[3],
                    "message": row[4],
                    "recommended_action": row[5],
                    "current_price": row[6],
                    "trigger_price": row[7],
                    "acknowledged": bool(row[8]),
                    "created_at": row[9],
                }
                for row in rows
            ]

        return await self._with_conn(_op)

    async def get_alert_count(self, ticker: str | None = None, days: int = 7) -> int:
        """Count alerts in the last N days."""
        async def _op(conn: aiosqlite.Connection) -> int:
            conditions: list[str] = [f"created_at >= datetime('now', '-{days} days')"]
            params: list[Any] = []
            if ticker is not None:
                conditions.append("ticker = ?")
                params.append(ticker)
            where = f"WHERE {' AND '.join(conditions)}"
            row = await (
                await conn.execute(
                    f"SELECT COUNT(*) FROM monitoring_alerts {where}",
                    params,
                )
            ).fetchone()
            return int(row[0]) if row else 0

        return await self._with_conn(_op)
