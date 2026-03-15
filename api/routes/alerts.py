"""Monitoring and alerts endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.deps import get_db_path
from monitoring.monitor import PortfolioMonitor
from monitoring.store import AlertStore
from notifications.email_dispatcher import EmailDispatcher
from notifications.telegram_dispatcher import TelegramDispatcher

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


@router.post("/alerts/test-telegram")
async def test_telegram_notification(db_path: str = Depends(get_db_path)):
    """Send a test alert to Telegram to verify configuration."""
    tg = TelegramDispatcher()
    if not tg.is_configured:
        raise HTTPException(
            status_code=400,
            detail="Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.",
        )

    test_alert = {
        "ticker": "TEST",
        "alert_type": "TEST_NOTIFICATION",
        "severity": "INFO",
        "message": "This is a test alert from Investment Agent.",
        "recommended_action": "No action required -- test only.",
        "current_price": 100.00,
    }
    sent = await tg.send_alert(test_alert)
    if not sent:
        raise HTTPException(
            status_code=502,
            detail="Failed to send test message to Telegram.",
        )
    return {
        "data": {"sent": True, "message": "Test alert sent to Telegram"},
        "warnings": [],
    }


@router.post("/alerts/test-email")
async def test_email_notification(db_path: str = Depends(get_db_path)):
    """Send a test alert email to verify configuration."""
    dispatcher = EmailDispatcher()
    if not dispatcher.is_configured:
        raise HTTPException(
            status_code=400,
            detail=(
                "Email not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, "
                "SMTP_PASSWORD, and ALERT_TO_EMAILS environment variables."
            ),
        )

    test_alert = {
        "ticker": "TEST",
        "alert_type": "TEST_NOTIFICATION",
        "severity": "INFO",
        "message": "This is a test alert email from Investment Agent.",
        "recommended_action": "No action required -- configuration verified.",
        "current_price": 100.00,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    sent = await dispatcher.send_alert(test_alert)
    if not sent:
        raise HTTPException(
            status_code=502,
            detail="Failed to send test email. Check SMTP configuration and server logs.",
        )
    return {
        "data": {"sent": True, "message": "Test alert email sent successfully"},
        "warnings": [],
    }


@router.patch("/alerts/batch-acknowledge")
async def batch_acknowledge_alerts(
    body: dict,
    db_path: str = Depends(get_db_path),
):
    """Acknowledge multiple alerts at once."""
    alert_ids = body.get("alert_ids", [])
    store = AlertStore(db_path)
    count = await store.batch_acknowledge(alert_ids)
    return {"data": {"acknowledged_count": count}, "warnings": []}


@router.get("/alerts/timeline")
async def alert_timeline(
    days: int = Query(30, ge=1, le=90),
    db_path: str = Depends(get_db_path),
):
    """Alert count per day with severity breakdown for charting."""
    store = AlertStore(db_path)
    data = await store.get_alert_timeline(days)
    return {"data": data, "warnings": []}


@router.post("/monitor/check")
async def run_monitor_check(db_path: str = Depends(get_db_path)):
    """Run a portfolio health check (saves alerts + snapshot)."""
    monitor = PortfolioMonitor(db_path=db_path)
    result = await monitor.run_check()
    return {"data": result, "warnings": result.get("warnings", [])}


# ---------------------------------------------------------------------------
# Alert Rules CRUD
# ---------------------------------------------------------------------------

_ALERT_RULES_DDL = """
CREATE TABLE IF NOT EXISTS alert_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  metric TEXT NOT NULL,
  condition TEXT NOT NULL CHECK(condition IN ('gt','lt','eq')),
  threshold REAL NOT NULL,
  severity TEXT NOT NULL DEFAULT 'medium',
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


class CreateAlertRuleBody(BaseModel):
    name: str
    metric: str
    condition: str = Field(..., pattern=r"^(gt|lt|eq)$")
    threshold: float
    severity: Optional[str] = "medium"


class ToggleAlertRuleBody(BaseModel):
    enabled: bool


async def _ensure_alert_rules_table(conn: aiosqlite.Connection) -> None:
    await conn.execute(_ALERT_RULES_DDL)
    await conn.commit()


@router.get("/alerts/rules")
async def list_alert_rules(db_path: str = Depends(get_db_path)):
    """List all alert rules."""
    async with aiosqlite.connect(db_path) as conn:
        await _ensure_alert_rules_table(conn)
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, name, metric, condition, threshold, severity, enabled, created_at FROM alert_rules ORDER BY id DESC"
        )
        rows = await cursor.fetchall()
        rules = [
            {
                "id": row["id"],
                "name": row["name"],
                "metric": row["metric"],
                "condition": row["condition"],
                "threshold": row["threshold"],
                "severity": row["severity"],
                "enabled": bool(row["enabled"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    return {"data": rules, "warnings": []}


@router.post("/alerts/rules")
async def create_alert_rule(
    body: CreateAlertRuleBody,
    db_path: str = Depends(get_db_path),
):
    """Create a new alert rule."""
    async with aiosqlite.connect(db_path) as conn:
        await _ensure_alert_rules_table(conn)
        cursor = await conn.execute(
            "INSERT INTO alert_rules (name, metric, condition, threshold, severity) VALUES (?, ?, ?, ?, ?)",
            (body.name, body.metric, body.condition, body.threshold, body.severity),
        )
        await conn.commit()
        rule_id = cursor.lastrowid
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, name, metric, condition, threshold, severity, enabled, created_at FROM alert_rules WHERE id = ?",
            (rule_id,),
        )
        row = await cursor.fetchone()
        rule = {
            "id": row["id"],
            "name": row["name"],
            "metric": row["metric"],
            "condition": row["condition"],
            "threshold": row["threshold"],
            "severity": row["severity"],
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
        }
    return {"data": rule, "warnings": []}


@router.delete("/alerts/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    db_path: str = Depends(get_db_path),
):
    """Delete an alert rule."""
    async with aiosqlite.connect(db_path) as conn:
        await _ensure_alert_rules_table(conn)
        cursor = await conn.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
        await conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Alert rule not found")
    return {"data": {"deleted": True}, "warnings": []}


@router.patch("/alerts/rules/{rule_id}")
async def toggle_alert_rule(
    rule_id: int,
    body: ToggleAlertRuleBody,
    db_path: str = Depends(get_db_path),
):
    """Toggle the enabled flag on an alert rule."""
    async with aiosqlite.connect(db_path) as conn:
        await _ensure_alert_rules_table(conn)
        cursor = await conn.execute(
            "UPDATE alert_rules SET enabled = ? WHERE id = ?",
            (int(body.enabled), rule_id),
        )
        await conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, name, metric, condition, threshold, severity, enabled, created_at FROM alert_rules WHERE id = ?",
            (rule_id,),
        )
        row = await cursor.fetchone()
        rule = {
            "id": row["id"],
            "name": row["name"],
            "metric": row["metric"],
            "condition": row["condition"],
            "threshold": row["threshold"],
            "severity": row["severity"],
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
        }
    return {"data": rule, "warnings": []}
