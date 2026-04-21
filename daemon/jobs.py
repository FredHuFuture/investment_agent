"""Async job functions for the monitoring daemon.

Each function is self-contained, never raises (catches all exceptions),
and records its execution in the daemon_runs table.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from daemon.signal_comparator import compare_signals
from db.database import DEFAULT_DB_PATH
from engine.aggregator import AggregatedSignal
from engine.pipeline import AnalysisPipeline
from monitoring.models import Alert
from monitoring.monitor import PortfolioMonitor
from monitoring.store import AlertStore
from portfolio.manager import PortfolioManager
from tracking.store import SignalStore


# ---------------------------------------------------------------------------
# Public job functions
# ---------------------------------------------------------------------------

async def run_daily_check(
    db_path: str = str(DEFAULT_DB_PATH),
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Run the daily portfolio health check.

    Wraps PortfolioMonitor.run_check() with logging and daemon_runs recording.
    Never raises -- all exceptions are caught, logged, and recorded.

    Returns dict with result fields or error details.
    """
    if logger is None:
        logger = logging.getLogger("investment_daemon")

    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    # FOUND-07: Write start-of-run log row on its own connection so it is
    # committed independently of the job transaction. A ROLLBACK on the job
    # body will NOT erase this row.
    row_id: int | None = None
    try:
        async with aiosqlite.connect(db_path) as log_conn:
            row_id = await _begin_job_run_log(log_conn, "daily_check", started_at)
    except Exception as log_exc:
        logger.warning("_begin_job_run_log failed (non-fatal): %s", log_exc)

    try:
        monitor = PortfolioMonitor(db_path)
        result = await monitor.run_check()
        duration_ms = int((time.monotonic() - t0) * 1000)

        n_checked = result.get("checked_positions", 0)
        n_alerts = len(result.get("alerts", []))
        n_warnings = len(result.get("warnings", []))
        logger.info(
            "Daily check complete -- %d positions, %d alerts, %d warnings",
            n_checked, n_alerts, n_warnings,
        )
        for w in result.get("warnings", []):
            logger.warning("  %s", w)

        # --- Telegram notification for critical/high alerts ---
        try:
            from notifications.telegram_dispatcher import TelegramDispatcher

            tg = TelegramDispatcher()
            if tg.is_configured:
                raw_alerts = result.get("alerts", [])
                critical_alerts = [
                    a.to_dict() if hasattr(a, "to_dict") else a
                    for a in raw_alerts
                    if (a.severity if hasattr(a, "severity") else a.get("severity"))
                    in ("CRITICAL", "HIGH")
                ]
                if critical_alerts:
                    await tg.send_alert_digest(critical_alerts)
        except Exception as tg_exc:
            logger.warning("Telegram dispatch failed: %s", tg_exc)

        # --- Email notification for critical/high alerts ---
        try:
            from notifications.email_dispatcher import EmailDispatcher

            raw_alerts = result.get("alerts", [])
            critical_alerts_email = [
                a.to_dict() if hasattr(a, "to_dict") else a
                for a in raw_alerts
                if (a.severity if hasattr(a, "severity") else a.get("severity", ""))
                .upper() in ("CRITICAL", "HIGH")
            ]
            if critical_alerts_email:
                email_dispatcher = EmailDispatcher()
                if email_dispatcher.is_configured:
                    sent = await email_dispatcher.send_alert_digest(critical_alerts_email)
                    if sent:
                        logger.info(
                            "Email digest sent for %d critical/high alerts",
                            len(critical_alerts_email),
                        )
                    else:
                        logger.warning("Email digest dispatch returned False")
        except Exception as email_exc:
            logger.warning("Email dispatch failed (non-fatal): %s", email_exc)

        await _record_daemon_run(
            db_path=db_path,
            job_name="daily_check",
            status="success",
            started_at=started_at,
            duration_ms=duration_ms,
            result_json=json.dumps({
                "checked_positions": n_checked,
                "alerts_generated": n_alerts,
                "warnings": n_warnings,
            }),
        )
        # FOUND-07: Update job_run_log to 'success' on own connection.
        if row_id is not None:
            try:
                async with aiosqlite.connect(db_path) as log_conn:
                    await _end_job_run_log(log_conn, row_id, "success", duration_ms=duration_ms)
            except Exception as log_exc:
                logger.warning("_end_job_run_log (success) failed (non-fatal): %s", log_exc)
        return result

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        err_msg = str(exc)
        logger.error("Daily check failed: %s", err_msg, exc_info=True)
        await _record_daemon_run(
            db_path=db_path,
            job_name="daily_check",
            status="error",
            started_at=started_at,
            duration_ms=duration_ms,
            error_message=err_msg,
        )
        # FOUND-07: Update job_run_log to 'error' on own connection.
        if row_id is not None:
            try:
                async with aiosqlite.connect(db_path) as log_conn:
                    await _end_job_run_log(
                        log_conn, row_id, "error",
                        error_message=err_msg, duration_ms=duration_ms,
                    )
            except Exception as log_exc:
                logger.warning("_end_job_run_log (error) failed (non-fatal): %s", log_exc)
        return {"error": err_msg, "checked_positions": 0, "alerts": [], "warnings": []}


async def run_weekly_revaluation(
    db_path: str = str(DEFAULT_DB_PATH),
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Run weekly full re-analysis for all portfolio positions.

    For each position:
    1. Run AnalysisPipeline.analyze_ticker()
    2. Load original thesis signal/confidence from positions_thesis
    3. Compare signals -- if reversed, create SIGNAL_REVERSAL alert
    4. Save new signal to signal_history

    Never raises -- per-position errors are collected and the loop continues.
    Returns summary dict.
    """
    if logger is None:
        logger = logging.getLogger("investment_daemon")

    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    positions_analyzed = 0
    signal_reversals: list[dict] = []
    alerts_generated = 0
    signals_saved = 0
    errors: list[dict] = []

    # FOUND-07: Write start-of-run log row on its own connection.
    row_id: int | None = None
    try:
        async with aiosqlite.connect(db_path) as log_conn:
            row_id = await _begin_job_run_log(log_conn, "weekly_revaluation", started_at)
    except Exception as log_exc:
        if logger:
            logger.warning("_begin_job_run_log failed (non-fatal): %s", log_exc)

    try:
        pm = PortfolioManager(db_path)
        portfolio = await pm.load_portfolio()
        pipeline = AnalysisPipeline(db_path=db_path)

        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("PRAGMA foreign_keys=ON;")
            await conn.execute("BEGIN")
            try:
                alert_store = AlertStore(conn)
                signal_store = SignalStore(conn)

                for position in portfolio.positions:
                    try:
                        # Run full re-analysis
                        signal: AggregatedSignal = await pipeline.analyze_ticker(
                            position.ticker, position.asset_type, portfolio
                        )

                        # Load original thesis for comparison
                        original_signal: str | None = None
                        original_confidence: float | None = None
                        thesis_id = position.original_analysis_id

                        if thesis_id is not None:
                            thesis_row = await (
                                await conn.execute(
                                    """
                                    SELECT expected_signal, expected_confidence
                                    FROM positions_thesis
                                    WHERE id = ?
                                    """,
                                    (thesis_id,),
                                )
                            ).fetchone()
                            if thesis_row is not None:
                                original_signal = str(thesis_row[0]) if thesis_row[0] else None
                                original_confidence = float(thesis_row[1]) if thesis_row[1] else None

                        # Compare signals if original thesis exists
                        if original_signal and original_confidence is not None:
                            comparison = compare_signals(
                                original_signal=original_signal,
                                original_confidence=original_confidence,
                                current_signal=signal.final_signal.value,
                                current_confidence=signal.final_confidence,
                            )
                            logger.info(
                                "  %s: %s",
                                position.ticker,
                                comparison.summary,
                            )

                            if comparison.direction_reversed:
                                reversal_info = {
                                    "ticker": position.ticker,
                                    "original_signal": original_signal,
                                    "current_signal": signal.final_signal.value,
                                    "confidence": signal.final_confidence,
                                }
                                signal_reversals.append(reversal_info)

                                reversal_alert = Alert(
                                    ticker=position.ticker,
                                    alert_type="SIGNAL_REVERSAL",
                                    severity="HIGH",
                                    message=(
                                        f"Signal reversed from {original_signal} to "
                                        f"{signal.final_signal.value} "
                                        f"(confidence: {signal.final_confidence:.0f})"
                                    ),
                                    recommended_action=(
                                        f"Review position -- original thesis was {original_signal}, "
                                        f"re-analysis now signals {signal.final_signal.value}."
                                    ),
                                    current_price=signal.ticker_info.get("current_price"),
                                )
                                await alert_store.save_alert(reversal_alert)
                                alerts_generated += 1

                        # Save the new signal to signal_history
                        await signal_store.save_signal(signal, thesis_id=thesis_id)
                        signals_saved += 1
                        positions_analyzed += 1

                    except Exception as exc:
                        err_msg = str(exc)
                        logger.error("  %s: analysis failed -- %s", position.ticker, err_msg, exc_info=True)
                        errors.append({"ticker": position.ticker, "error": err_msg})

                # Save portfolio snapshot with weekly trigger
                now = datetime.now(timezone.utc).isoformat()
                import json as _json
                await conn.execute(
                    """
                    INSERT INTO portfolio_snapshots (
                        timestamp, total_value, cash, positions_json, trigger_event
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        now,
                        portfolio.total_value,
                        portfolio.cash,
                        _json.dumps([p.to_dict() for p in portfolio.positions]),
                        "weekly_revaluation",
                    ),
                )
                await conn.execute("COMMIT")
            except Exception:
                await conn.execute("ROLLBACK")
                raise

        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Weekly revaluation complete -- %d analyzed, %d reversals, %d errors",
            positions_analyzed, len(signal_reversals), len(errors),
        )

        result = {
            "positions_analyzed": positions_analyzed,
            "signal_reversals": signal_reversals,
            "alerts_generated": alerts_generated,
            "signals_saved": signals_saved,
            "errors": errors,
        }
        await _record_daemon_run(
            db_path=db_path,
            job_name="weekly_revaluation",
            status="success",
            started_at=started_at,
            duration_ms=duration_ms,
            result_json=json.dumps({
                "positions_analyzed": positions_analyzed,
                "signal_reversals": len(signal_reversals),
                "alerts_generated": alerts_generated,
                "signals_saved": signals_saved,
                "errors": len(errors),
            }),
        )
        # FOUND-07: Update job_run_log to 'success'.
        if row_id is not None:
            try:
                async with aiosqlite.connect(db_path) as log_conn:
                    await _end_job_run_log(log_conn, row_id, "success", duration_ms=duration_ms)
            except Exception as log_exc:
                logger.warning("_end_job_run_log (success) failed (non-fatal): %s", log_exc)
        return result

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        err_msg = str(exc)
        logger.error("Weekly revaluation failed: %s", err_msg, exc_info=True)
        await _record_daemon_run(
            db_path=db_path,
            job_name="weekly_revaluation",
            status="error",
            started_at=started_at,
            duration_ms=duration_ms,
            error_message=err_msg,
        )
        # FOUND-07: Update job_run_log to 'error'.
        if row_id is not None:
            try:
                async with aiosqlite.connect(db_path) as log_conn:
                    await _end_job_run_log(
                        log_conn, row_id, "error",
                        error_message=err_msg, duration_ms=duration_ms,
                    )
            except Exception as log_exc:
                logger.warning("_end_job_run_log (error) failed (non-fatal): %s", log_exc)
        return {
            "error": err_msg,
            "positions_analyzed": positions_analyzed,
            "signal_reversals": signal_reversals,
            "alerts_generated": alerts_generated,
            "signals_saved": signals_saved,
            "errors": errors,
        }


async def run_weekly_summary(
    db_path: str = str(DEFAULT_DB_PATH),
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Generate a weekly portfolio summary using Claude API.

    Runs every Sunday at 6pm. Only runs if ANTHROPIC_API_KEY is set;
    logs a warning and records a 'skipped' run otherwise.
    Never raises -- all exceptions are caught, logged, and recorded.
    """
    import os

    if logger is None:
        logger = logging.getLogger("investment_daemon")

    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        reason = "ANTHROPIC_API_KEY not set -- skipping weekly summary"
        logger.warning(reason)
        await _record_daemon_run(
            db_path=db_path,
            job_name="weekly_summary",
            status="skipped",
            started_at=started_at,
            duration_ms=0,
            result_json=json.dumps({"reason": reason}),
        )
        return {"status": "skipped", "reason": reason}

    # FOUND-07: Write start-of-run log row on its own connection.
    row_id: int | None = None
    try:
        async with aiosqlite.connect(db_path) as log_conn:
            row_id = await _begin_job_run_log(log_conn, "weekly_summary", started_at)
    except Exception as log_exc:
        logger.warning("_begin_job_run_log failed (non-fatal): %s", log_exc)

    try:
        from agents.summary_agent import SummaryAgent, save_summary

        agent = SummaryAgent(api_key=api_key)
        context = await SummaryAgent.build_context(db_path)
        result = await agent.generate_summary(context)
        await save_summary(db_path, result)

        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Weekly summary generated -- %d positions, cost $%.4f",
            len(result.positions_covered),
            result.cost_usd,
        )

        await _record_daemon_run(
            db_path=db_path,
            job_name="weekly_summary",
            status="success",
            started_at=started_at,
            duration_ms=duration_ms,
            result_json=json.dumps({
                "positions_covered": len(result.positions_covered),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "cost_usd": result.cost_usd,
            }),
        )
        # FOUND-07: Update job_run_log to 'success'.
        if row_id is not None:
            try:
                async with aiosqlite.connect(db_path) as log_conn:
                    await _end_job_run_log(log_conn, row_id, "success", duration_ms=duration_ms)
            except Exception as log_exc:
                logger.warning("_end_job_run_log (success) failed (non-fatal): %s", log_exc)
        return {
            "status": "success",
            "positions_covered": result.positions_covered,
            "cost_usd": result.cost_usd,
        }

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        err_msg = str(exc)
        logger.error("Weekly summary failed: %s", err_msg, exc_info=True)
        await _record_daemon_run(
            db_path=db_path,
            job_name="weekly_summary",
            status="error",
            started_at=started_at,
            duration_ms=duration_ms,
            error_message=err_msg,
        )
        # FOUND-07: Update job_run_log to 'error'.
        if row_id is not None:
            try:
                async with aiosqlite.connect(db_path) as log_conn:
                    await _end_job_run_log(
                        log_conn, row_id, "error",
                        error_message=err_msg, duration_ms=duration_ms,
                    )
            except Exception as log_exc:
                logger.warning("_end_job_run_log (error) failed (non-fatal): %s", log_exc)
        return {"status": "error", "error": err_msg}


async def run_catalyst_scan(
    db_path: str = str(DEFAULT_DB_PATH),
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Scan portfolio positions for sentiment-based catalysts.

    For each open position:
    1. Fetch recent news headlines via WebNewsProvider
    2. Run SentimentAgent.analyze() for a sentiment signal
    3. If the signal DISAGREES with position direction at sufficient confidence,
       create a CATALYST alert

    Never raises -- per-position errors are caught and the loop continues.
    Returns summary dict.
    """
    from agents.models import AgentInput
    from agents.sentiment import SentimentAgent
    from data_providers.web_news_provider import WebNewsProvider
    from data_providers.yfinance_provider import YFinanceProvider

    if logger is None:
        logger = logging.getLogger("investment_daemon")

    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    # FOUND-07: Write start-of-run log row on its own connection.
    row_id: int | None = None
    try:
        async with aiosqlite.connect(db_path) as log_conn:
            row_id = await _begin_job_run_log(log_conn, "catalyst_scan", started_at)
    except Exception as log_exc:
        logger.warning("_begin_job_run_log failed (non-fatal): %s", log_exc)

    try:
        pm = PortfolioManager(db_path)
        positions = await pm.get_all_positions()

        if not positions:
            reason = "No open positions -- skipping catalyst scan"
            logger.info(reason)
            await _record_daemon_run(
                db_path=db_path,
                job_name="catalyst_scan",
                status="skipped",
                started_at=started_at,
                duration_ms=int((time.monotonic() - t0) * 1000),
                result_json=json.dumps({"reason": reason}),
            )
            # FOUND-07: Mark as success (skipped is a clean exit).
            if row_id is not None:
                try:
                    async with aiosqlite.connect(db_path) as log_conn:
                        await _end_job_run_log(
                            log_conn, row_id, "success",
                            duration_ms=int((time.monotonic() - t0) * 1000),
                        )
                except Exception:
                    pass
            return {"status": "skipped", "reason": reason}

        news_provider = WebNewsProvider()
        yf_provider = YFinanceProvider()
        agent = SentimentAgent(yf_provider, news_provider=news_provider)
        alert_store = AlertStore(db_path)

        positions_scanned = 0
        alerts_created = 0
        errors: list[dict[str, str]] = []

        for pos in positions:
            try:
                input_ = AgentInput(ticker=pos.ticker, asset_type=pos.asset_type)
                output = await agent.analyze(input_)

                signal = output.signal.value   # "BUY", "HOLD", or "SELL"
                confidence = output.confidence
                reasoning = output.reasoning

                should_alert = False
                severity = "WARNING"

                # Alert if signal DISAGREES with position direction
                # Long position (all open positions assumed long) with SELL signal
                if signal == "SELL" and confidence >= 60:
                    should_alert = True
                    severity = "WARNING" if confidence < 75 else "CRITICAL"
                # BUY signal at high confidence = potential opportunity to add
                elif signal == "BUY" and confidence >= 70:
                    should_alert = True
                    severity = "INFO" if confidence < 85 else "WARNING"

                if should_alert:
                    alert = Alert(
                        ticker=pos.ticker,
                        alert_type="CATALYST",
                        severity=severity,
                        message=f"SentimentAgent: {signal} ({confidence:.0f}%) — {reasoning[:200]}",
                        recommended_action=f"Review recent news for {pos.ticker}",
                        current_price=pos.current_price,
                        trigger_price=None,
                    )
                    await alert_store.save_alert(alert)
                    alerts_created += 1
                    logger.info(
                        "  %s: CATALYST alert (%s @ %.0f%%)",
                        pos.ticker, signal, confidence,
                    )
                else:
                    logger.info(
                        "  %s: %s @ %.0f%% -- no alert",
                        pos.ticker, signal, confidence,
                    )

                positions_scanned += 1

            except Exception as exc:
                err_msg = str(exc)
                logger.error(
                    "  %s: catalyst scan failed -- %s",
                    pos.ticker, err_msg, exc_info=True,
                )
                errors.append({"ticker": pos.ticker, "error": err_msg})

        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Catalyst scan complete -- %d scanned, %d alerts, %d errors",
            positions_scanned, alerts_created, len(errors),
        )

        result = {
            "status": "success",
            "positions_scanned": positions_scanned,
            "alerts_created": alerts_created,
            "errors": errors,
        }
        await _record_daemon_run(
            db_path=db_path,
            job_name="catalyst_scan",
            status="success",
            started_at=started_at,
            duration_ms=duration_ms,
            result_json=json.dumps({
                "positions_scanned": positions_scanned,
                "alerts_created": alerts_created,
                "errors": len(errors),
            }),
        )
        # FOUND-07: Update job_run_log to 'success'.
        if row_id is not None:
            try:
                async with aiosqlite.connect(db_path) as log_conn:
                    await _end_job_run_log(log_conn, row_id, "success", duration_ms=duration_ms)
            except Exception as log_exc:
                logger.warning("_end_job_run_log (success) failed (non-fatal): %s", log_exc)
        return result

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        err_msg = str(exc)
        logger.error("Catalyst scan failed: %s", err_msg, exc_info=True)
        await _record_daemon_run(
            db_path=db_path,
            job_name="catalyst_scan",
            status="error",
            started_at=started_at,
            duration_ms=duration_ms,
            error_message=err_msg,
        )
        # FOUND-07: Update job_run_log to 'error'.
        if row_id is not None:
            try:
                async with aiosqlite.connect(db_path) as log_conn:
                    await _end_job_run_log(
                        log_conn, row_id, "error",
                        error_message=err_msg, duration_ms=duration_ms,
                    )
            except Exception as log_exc:
                logger.warning("_end_job_run_log (error) failed (non-fatal): %s", log_exc)
        return {"status": "error", "error": err_msg}


async def run_regime_detection(
    db_path: str = str(DEFAULT_DB_PATH),
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Run regime detection and save the result to regime_history.

    1. Detect current market regime via RegimeDetector
    2. Save snapshot to regime_history table
    3. If regime changed from last saved regime, send Telegram/email notification

    Never raises -- all exceptions are caught, logged, and recorded.
    Returns dict with regime detection results or error details.
    """
    from engine.regime import RegimeDetector
    from engine.regime_history import RegimeHistoryStore

    if logger is None:
        logger = logging.getLogger("investment_daemon")

    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    # FOUND-07: Write start-of-run log row on its own connection.
    jrl_row_id: int | None = None
    try:
        async with aiosqlite.connect(db_path) as log_conn:
            jrl_row_id = await _begin_job_run_log(log_conn, "regime_detection", started_at)
    except Exception as log_exc:
        logger.warning("_begin_job_run_log failed (non-fatal): %s", log_exc)

    try:
        detector = RegimeDetector()
        regime_result = detector.detect_regime()

        regime = regime_result["regime"]
        confidence = regime_result["confidence"]
        details = regime_result.get("indicators", {})
        description = regime_result.get("description", "")

        # Extract VIX and yield spread from details if available
        vix = details.get("vix_current")
        yield_spread = details.get("yield_curve_spread")

        # Save to regime_history
        store = RegimeHistoryStore(db_path)
        regime_history_row_id = await store.save_regime(regime, confidence, vix, yield_spread)

        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Regime detection complete -- %s (%.0f%% confidence)",
            regime, confidence,
        )

        # Check if regime changed from the last saved regime for notifications
        regime_changed = False
        previous_regime: str | None = None
        try:
            # Query the two most recent raw rows (including the one we just saved)
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                rows = await (
                    await conn.execute(
                        """
                        SELECT regime FROM regime_history
                        ORDER BY detected_at DESC
                        LIMIT 2
                        """,
                    )
                ).fetchall()
                if len(rows) >= 2:
                    # rows[0] is the one we just saved, rows[1] is the previous
                    previous_regime = rows[1]["regime"]
                    regime_changed = previous_regime != regime
                elif len(rows) == 1:
                    # First ever detection -- treat as a change
                    regime_changed = True
        except Exception as hist_exc:
            logger.warning("Could not check regime history: %s", hist_exc)

        # --- Telegram notification if regime changed ---
        if regime_changed:
            try:
                from notifications.telegram_dispatcher import TelegramDispatcher

                tg = TelegramDispatcher()
                if tg.is_configured:
                    change_msg = (
                        f"Regime changed: {previous_regime or 'N/A'} -> {regime} "
                        f"(confidence {confidence:.0f}%)"
                    )
                    await tg.send_alert_digest([{
                        "alert_type": "REGIME_CHANGE",
                        "severity": "WARNING",
                        "message": change_msg,
                        "ticker": "MARKET",
                    }])
            except Exception as tg_exc:
                logger.warning("Telegram dispatch failed: %s", tg_exc)

            # --- Email notification if regime changed ---
            try:
                from notifications.email_dispatcher import EmailDispatcher

                email_dispatcher = EmailDispatcher()
                if email_dispatcher.is_configured:
                    change_msg = (
                        f"Regime changed: {previous_regime or 'N/A'} -> {regime} "
                        f"(confidence {confidence:.0f}%)"
                    )
                    sent = await email_dispatcher.send_alert_digest([{
                        "alert_type": "REGIME_CHANGE",
                        "severity": "WARNING",
                        "message": change_msg,
                        "ticker": "MARKET",
                    }])
                    if sent:
                        logger.info("Regime change email notification sent")
                    else:
                        logger.warning("Regime change email dispatch returned False")
            except Exception as email_exc:
                logger.warning("Email dispatch failed (non-fatal): %s", email_exc)

        await _record_daemon_run(
            db_path=db_path,
            job_name="regime_detection",
            status="success",
            started_at=started_at,
            duration_ms=duration_ms,
            result_json=json.dumps({
                "regime": regime,
                "confidence": confidence,
                "regime_changed": regime_changed,
                "previous_regime": previous_regime,
                "row_id": regime_history_row_id,
            }),
        )
        # FOUND-07: Update job_run_log to 'success'.
        if jrl_row_id is not None:
            try:
                async with aiosqlite.connect(db_path) as log_conn:
                    await _end_job_run_log(log_conn, jrl_row_id, "success", duration_ms=duration_ms)
            except Exception as log_exc:
                logger.warning("_end_job_run_log (success) failed (non-fatal): %s", log_exc)
        return {
            "regime": regime,
            "confidence": confidence,
            "description": description,
            "regime_changed": regime_changed,
            "previous_regime": previous_regime,
            "row_id": regime_history_row_id,
        }

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        err_msg = str(exc)
        logger.error("Regime detection failed: %s", err_msg, exc_info=True)
        await _record_daemon_run(
            db_path=db_path,
            job_name="regime_detection",
            status="error",
            started_at=started_at,
            duration_ms=duration_ms,
            error_message=err_msg,
        )
        # FOUND-07: Update job_run_log to 'error'.
        if jrl_row_id is not None:
            try:
                async with aiosqlite.connect(db_path) as log_conn:
                    await _end_job_run_log(
                        log_conn, jrl_row_id, "error",
                        error_message=err_msg, duration_ms=duration_ms,
                    )
            except Exception as log_exc:
                logger.warning("_end_job_run_log (error) failed (non-fatal): %s", log_exc)
        return {"error": err_msg, "regime": None, "confidence": 0}


# ---------------------------------------------------------------------------
# FOUND-07: job_run_log helpers + reconciliation + pruning job
# ---------------------------------------------------------------------------

async def _begin_job_run_log(
    conn: aiosqlite.Connection,
    job_name: str,
    started_at: str | None = None,
) -> int:
    """Insert a row with status='running' and return its id.

    Caller MUST call _end_job_run_log on the same connection before returning.
    This commits immediately so the row is visible even if the main
    job transaction later rolls back.
    """
    if started_at is None:
        started_at = datetime.now(timezone.utc).isoformat()
    cursor = await conn.execute(
        """
        INSERT INTO job_run_log (job_name, started_at, status)
        VALUES (?, ?, 'running')
        """,
        (job_name, started_at),
    )
    await conn.commit()
    return int(cursor.lastrowid)


async def _end_job_run_log(
    conn: aiosqlite.Connection,
    row_id: int,
    status: str,
    error_message: str | None = None,
    duration_ms: int | None = None,
) -> None:
    """Finalize a job_run_log row. status must be 'success' or 'error'."""
    if status not in ("success", "error"):
        raise ValueError(f"invalid final status: {status!r}")
    completed_at = datetime.now(timezone.utc).isoformat()
    await conn.execute(
        """
        UPDATE job_run_log
        SET status = ?, completed_at = ?,
            error_message = ?, duration_ms = ?
        WHERE id = ?
        """,
        (status, completed_at, error_message, duration_ms, row_id),
    )
    await conn.commit()


async def reconcile_aborted_jobs(
    db_path: str = str(DEFAULT_DB_PATH),
    min_age_seconds: int = 5,
) -> int:
    """Mark stale 'running' rows as 'aborted'.

    Called at daemon startup. A row is considered stale if status='running'
    AND started_at is older than `min_age_seconds`. Returns count updated.
    """
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            """
            UPDATE job_run_log
            SET status = 'aborted',
                completed_at = ?,
                error_message = 'Daemon restarted with job in flight'
            WHERE status = 'running'
              AND (julianday('now') - julianday(started_at)) * 86400 > ?
            """,
            (datetime.now(timezone.utc).isoformat(), min_age_seconds),
        )
        await conn.commit()
        return cursor.rowcount or 0


async def prune_signal_history(
    db_path: str = str(DEFAULT_DB_PATH),
    retention_days: int = 90,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Delete signal_history rows older than retention_days.

    Returns {"deleted_rows": int, "retained_rows": int}.
    """
    if logger is None:
        logger = logging.getLogger("investment_daemon")

    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    row_id: int | None = None

    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("PRAGMA foreign_keys=ON;")
            row_id = await _begin_job_run_log(conn, "prune_signal_history", started_at)

            cursor = await conn.execute(
                """
                DELETE FROM signal_history
                WHERE created_at < date('now', ? || ' days')
                """,
                (f"-{int(retention_days)}",),
            )
            deleted = cursor.rowcount or 0

            retained_row = await (
                await conn.execute("SELECT COUNT(*) FROM signal_history")
            ).fetchone()
            retained_count = int(retained_row[0]) if retained_row else 0

            await conn.commit()

            duration_ms = int((time.monotonic() - t0) * 1000)
            await _end_job_run_log(
                conn, row_id, "success", duration_ms=duration_ms
            )

        logger.info(
            "prune_signal_history: deleted %d rows, %d retained",
            deleted,
            retained_count,
        )
        return {"deleted_rows": deleted, "retained_rows": retained_count}

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.error("prune_signal_history failed: %s", exc, exc_info=True)
        if row_id is not None:
            try:
                async with aiosqlite.connect(db_path) as conn:
                    await _end_job_run_log(
                        conn,
                        row_id,
                        "error",
                        error_message=str(exc),
                        duration_ms=duration_ms,
                    )
            except Exception:
                pass
        return {"deleted_rows": 0, "retained_rows": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

async def _record_daemon_run(
    db_path: str,
    job_name: str,
    status: str,
    started_at: str,
    duration_ms: int,
    result_json: str | None = None,
    error_message: str | None = None,
) -> None:
    """Insert a row into daemon_runs for auditing."""
    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute(
                """
                INSERT INTO daemon_runs
                    (job_name, status, started_at, duration_ms, result_json, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_name, status, started_at, duration_ms, result_json, error_message),
            )
            await conn.commit()
    except Exception as exc:
        # Never let audit recording crash the caller
        logging.getLogger("investment_daemon").error(
            "_record_daemon_run failed: %s", exc
        )
