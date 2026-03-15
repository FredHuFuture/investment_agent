"""Monitoring and alerts endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

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


@router.post("/monitor/check")
async def run_monitor_check(db_path: str = Depends(get_db_path)):
    """Run a portfolio health check (saves alerts + snapshot)."""
    monitor = PortfolioMonitor(db_path=db_path)
    result = await monitor.run_check()
    return {"data": result, "warnings": result.get("warnings", [])}
