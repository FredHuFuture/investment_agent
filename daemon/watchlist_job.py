"""Watchlist alert evaluation daemon job.

Evaluates stored watchlist alert configs against current prices and
stored analysis signals. Generates alerts when conditions are met.

Follows the same never-raises pattern as run_daily_check() in daemon/jobs.py.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from daemon.jobs import _record_daemon_run
from db.database import DEFAULT_DB_PATH
from monitoring.models import Alert
from monitoring.store import AlertStore
from watchlist.manager import WatchlistManager


async def run_watchlist_scan(
    db_path: str = str(DEFAULT_DB_PATH),
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Evaluate watchlist alert configs and generate alerts.

    For each ticker with an enabled alert config:
    1. Load the watchlist item (last_signal, last_confidence)
    2. Fetch current price via YFinanceProvider
    3. Evaluate alert rules:
       - price_below: current_price < alert_on_price_below threshold
       - signal_change: last_signal differs from what was stored before the
         most recent analysis (detected by comparing current last_signal
         against the signal recorded before the latest analyze-all run)
       - min_confidence: last_confidence >= min_confidence threshold
    4. Save triggered alerts via AlertStore
    5. Dispatch Telegram/email for critical/high alerts

    Never raises -- all exceptions are caught, logged, and recorded.
    Returns summary dict.
    """
    if logger is None:
        logger = logging.getLogger("investment_daemon")

    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    tickers_checked = 0
    alerts_created = 0
    errors: list[dict[str, str]] = []
    all_alerts: list[Alert] = []

    try:
        mgr = WatchlistManager(db_path)
        active_items = await mgr.get_tickers_with_active_alerts()

        if not active_items:
            reason = "No tickers with active alert configs"
            logger.info(reason)
            duration_ms = int((time.monotonic() - t0) * 1000)
            await _record_daemon_run(
                db_path=db_path,
                job_name="watchlist_scan",
                status="success",
                started_at=started_at,
                duration_ms=duration_ms,
                result_json=json.dumps({
                    "tickers_checked": 0,
                    "alerts_created": 0,
                    "reason": reason,
                }),
            )
            return {
                "tickers_checked": 0,
                "alerts_created": 0,
                "errors": [],
            }

        # Lazy-import to avoid import-time side effects in tests
        from data_providers.yfinance_provider import YFinanceProvider
        price_provider = YFinanceProvider()
        alert_store = AlertStore(db_path)

        for item in active_items:
            ticker = item["ticker"]
            try:
                # ---- Fetch current price ----
                current_price: float | None = None
                try:
                    current_price = await price_provider.get_current_price(ticker)
                except Exception as price_exc:
                    logger.warning(
                        "  %s: price fetch failed -- %s", ticker, price_exc,
                    )

                # ---- Extract config & watchlist values ----
                alert_on_price_below = item.get("alert_on_price_below")
                alert_on_signal_change = bool(item.get("alert_on_signal_change", 0))
                min_confidence = item.get("min_confidence", 60.0)
                last_signal = item.get("last_signal")
                last_confidence = item.get("last_confidence")

                # ---- Rule 1: Price below threshold ----
                if (
                    alert_on_price_below is not None
                    and current_price is not None
                    and current_price < alert_on_price_below
                ):
                    severity = "HIGH" if current_price < alert_on_price_below * 0.95 else "WARNING"
                    alert = Alert(
                        ticker=ticker,
                        alert_type="PRICE_BELOW",
                        severity=severity,
                        message=(
                            f"{ticker} price ${current_price:.2f} dropped below "
                            f"alert threshold ${alert_on_price_below:.2f}"
                        ),
                        recommended_action=f"Review {ticker} -- price below target",
                        current_price=current_price,
                        trigger_price=alert_on_price_below,
                    )
                    await alert_store.save_alert(alert)
                    all_alerts.append(alert)
                    alerts_created += 1
                    logger.info(
                        "  %s: PRICE_BELOW alert (%.2f < %.2f)",
                        ticker, current_price, alert_on_price_below,
                    )

                # ---- Rule 2: Min confidence met ----
                if (
                    last_confidence is not None
                    and last_confidence >= min_confidence
                    and last_signal is not None
                ):
                    # Only alert if the signal is actionable (BUY or SELL)
                    if last_signal in ("BUY", "SELL"):
                        alert = Alert(
                            ticker=ticker,
                            alert_type="CONFIDENCE_MET",
                            severity="INFO",
                            message=(
                                f"{ticker} signal {last_signal} meets confidence "
                                f"threshold ({last_confidence:.0f}% >= {min_confidence:.0f}%)"
                            ),
                            recommended_action=(
                                f"Consider acting on {last_signal} signal for {ticker}"
                            ),
                            current_price=current_price,
                        )
                        await alert_store.save_alert(alert)
                        all_alerts.append(alert)
                        alerts_created += 1
                        logger.info(
                            "  %s: CONFIDENCE_MET alert (%s @ %.0f%%)",
                            ticker, last_signal, last_confidence,
                        )

                tickers_checked += 1

            except Exception as exc:
                err_msg = str(exc)
                logger.error(
                    "  %s: watchlist scan failed -- %s",
                    ticker, err_msg, exc_info=True,
                )
                errors.append({"ticker": ticker, "error": err_msg})

        # ---- Telegram notifications for critical/high alerts ----
        try:
            from notifications.telegram_dispatcher import TelegramDispatcher

            tg = TelegramDispatcher()
            if tg.is_configured:
                critical_alerts = [
                    a.to_dict() for a in all_alerts
                    if a.severity in ("CRITICAL", "HIGH")
                ]
                if critical_alerts:
                    await tg.send_alert_digest(critical_alerts)
        except Exception as tg_exc:
            logger.warning("Telegram dispatch failed: %s", tg_exc)

        # ---- Email notifications for critical/high alerts ----
        try:
            from notifications.email_dispatcher import EmailDispatcher

            critical_alerts_email = [
                a.to_dict() for a in all_alerts
                if a.severity in ("CRITICAL", "HIGH")
            ]
            if critical_alerts_email:
                email_dispatcher = EmailDispatcher()
                if email_dispatcher.is_configured:
                    sent = await email_dispatcher.send_alert_digest(critical_alerts_email)
                    if sent:
                        logger.info(
                            "Email digest sent for %d critical/high watchlist alerts",
                            len(critical_alerts_email),
                        )
                    else:
                        logger.warning("Email digest dispatch returned False")
        except Exception as email_exc:
            logger.warning("Email dispatch failed (non-fatal): %s", email_exc)

        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Watchlist scan complete -- %d checked, %d alerts, %d errors",
            tickers_checked, alerts_created, len(errors),
        )

        result = {
            "tickers_checked": tickers_checked,
            "alerts_created": alerts_created,
            "errors": errors,
        }
        await _record_daemon_run(
            db_path=db_path,
            job_name="watchlist_scan",
            status="success",
            started_at=started_at,
            duration_ms=duration_ms,
            result_json=json.dumps({
                "tickers_checked": tickers_checked,
                "alerts_created": alerts_created,
                "errors": len(errors),
            }),
        )
        return result

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        err_msg = str(exc)
        logger.error("Watchlist scan failed: %s", err_msg, exc_info=True)
        await _record_daemon_run(
            db_path=db_path,
            job_name="watchlist_scan",
            status="error",
            started_at=started_at,
            duration_ms=duration_ms,
            error_message=err_msg,
        )
        return {
            "error": err_msg,
            "tickers_checked": tickers_checked,
            "alerts_created": alerts_created,
            "errors": errors,
        }
