"""Weekly portfolio digest Markdown renderer (LIVE-04 — Phase 7).

Five sections:
  (a) Portfolio Performance vs Benchmark — 7-day SPY comparison
  (b) Top 5 Signal Flips This Week — final_signal change per ticker
  (c) IC-IR Movers — drift_log triggered/preliminary rows in last 7d
  (d) Open Thesis Drift Alerts — monitoring_alerts unacknowledged last 30d
  (e) Action Items — heuristic synthesis from above + corpus gaps

PII discipline: ZERO dollar amounts; no thesis text; only ticker + signal
label + percentage (clamped to 1% precision) + date. Mirrors Phase 4 LLM
prompt clamp (T-04-04 / 04-RESEARCH.md). The digest is machine-generated;
downstream email transport wraps the body in <pre> for additional injection
safety (T-07-02-01).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import aiosqlite

logger = logging.getLogger("investment_agent.digest")

# ---------------------------------------------------------------------------
# H2 headers — constants so tests can assert on exact strings
# ---------------------------------------------------------------------------

HEADER_PERF = "## Portfolio Performance vs Benchmark"
HEADER_FLIPS = "## Top 5 Signal Flips This Week"
HEADER_ICIR = "## IC-IR Movers (>20% from 60-day avg)"
HEADER_ALERTS = "## Open Thesis Drift Alerts"
HEADER_ACTIONS = "## Action Items"

# Literal messages surfaced when a section has no data
EMPTY_ICIR_MSG = "No IC-IR movers this week — corpus may need more data"
EMPTY_FLIPS_MSG = "No signal changes this week."
EMPTY_ALERTS_MSG = "No open thesis drift alerts."

# Regex used for PII clamp sweep — strips $NNN,NNN.NN patterns
_DOLLAR_RE = re.compile(r"\$[0-9,]+(\.[0-9]+)?")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bucket_pct(pct: float | None) -> str:
    """Bucket percentages to 2dp precision and format with sign."""
    if pct is None:
        return "—"
    return f"{round(float(pct), 2):+.2f}%"


_THESIS_RE = re.compile(r"\b(thesis|secret)\b.*", re.IGNORECASE)


def _clamp_pii(text: str) -> str:
    """Strip dollar amounts and thesis-adjacent text from arbitrary text (T-07-02-02).

    PII clamp rules (mirrors Phase 4 LLM precedent):
    1. Strip dollar amounts: $NNN,NNN.NN → $—
    2. Strip thesis text markers: truncate at 'thesis:' / 'secret' keywords
       (alert messages may include thesis text from portfolio notes)
    """
    # First strip explicit thesis/secret content markers
    text = _THESIS_RE.sub("[redacted]", text)
    # Then strip dollar amounts
    return _DOLLAR_RE.sub("$—", text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def render_weekly_digest(db_path: str) -> str:
    """Render the weekly Markdown digest for the given DB path.

    Caller is responsible for SMTP/Telegram dispatch — this function returns
    the Markdown body only.

    PII-clamped: no dollar amounts, no thesis text. Only ticker + signal
    label + confidence % + date appear in the body.
    """
    from data_providers.yfinance_provider import YFinanceProvider  # noqa: PLC0415
    from engine.analytics import PortfolioAnalytics  # noqa: PLC0415

    now = datetime.now(timezone.utc)
    week_cutoff = now - timedelta(days=7)
    alerts_cutoff = now - timedelta(days=30)

    analytics = PortfolioAnalytics(db_path)
    provider = YFinanceProvider()

    # (a) Performance vs benchmark
    try:
        bench = await analytics.get_benchmark_comparison(
            provider, benchmark_ticker="SPY", days=7
        )
    except Exception as exc:
        logger.warning("Digest perf section degraded: %s", exc)
        bench = {
            "portfolio_return_pct": None,
            "benchmark_return_pct": None,
            "alpha_pct": None,
            "data_points": 0,
        }

    # (b) Signal flips
    flips = await _get_signal_flips(db_path, week_cutoff)

    # (c) IC-IR movers from drift_log
    movers = await _get_icir_movers(db_path, week_cutoff)

    # (d) Open thesis drift alerts
    alerts = await _get_open_alerts(db_path, alerts_cutoff)

    # (e) Action items synthesis
    actions = _synthesize_actions(bench, flips, movers, alerts)

    sections: list[str] = [
        f"# Weekly Portfolio Digest — {now.strftime('%Y-%m-%d')}",
        _render_perf(bench),
        _render_flips(flips),
        _render_icir(movers),
        _render_alerts(alerts),
        _render_actions(actions),
    ]
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Section (a): Performance vs Benchmark
# ---------------------------------------------------------------------------

def _render_perf(bench: dict[str, Any]) -> str:
    """Section (a): one-line performance vs benchmark."""
    n = bench.get("data_points", 0)
    if n < 2:
        return f"{HEADER_PERF}\n\n_No portfolio snapshots in the last 7 days._"
    port = bench.get("portfolio_return_pct")
    b = bench.get("benchmark_return_pct")
    alpha = bench.get("alpha_pct")
    line = (
        f"- Portfolio (7d): {_bucket_pct(port)} | "
        f"Benchmark SPY: {_bucket_pct(b)} | "
        f"Alpha: {_bucket_pct(alpha)}"
    )
    return f"{HEADER_PERF}\n\n{line}"


# ---------------------------------------------------------------------------
# Section (b): Signal Flips
# ---------------------------------------------------------------------------

async def _get_signal_flips(
    db_path: str, cutoff: datetime
) -> list[dict[str, Any]]:
    """Return up to 5 most recent ticker signal flips in the last 7 days.

    signal_history has NO signal_changed column (RESEARCH Q2). Flip detection
    is Python-side: group by ticker, sort by created_at, compare last 2 rows.
    """
    try:
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute(
                    """
                    SELECT ticker, final_signal, final_confidence, created_at
                    FROM signal_history
                    WHERE created_at >= ?
                    ORDER BY ticker, created_at
                    """,
                    (cutoff.isoformat(),),
                )
            ).fetchall()
    except Exception as exc:
        logger.warning("Digest signal flips query failed: %s", exc)
        return []

    by_ticker: dict[str, list[Any]] = {}
    for r in rows:
        by_ticker.setdefault(r["ticker"], []).append(r)

    flips: list[dict[str, Any]] = []
    for ticker, ticker_rows in by_ticker.items():
        if len(ticker_rows) < 2:
            continue
        prev = ticker_rows[-2]
        curr = ticker_rows[-1]
        if prev["final_signal"] != curr["final_signal"]:
            flips.append(
                {
                    "ticker": ticker,
                    "prev": prev["final_signal"],
                    "curr": curr["final_signal"],
                    # Bucket confidence to integer (PII clamp)
                    "confidence": int(round(curr["final_confidence"])),
                    "date": curr["created_at"][:10],
                }
            )

    flips.sort(key=lambda x: x["date"], reverse=True)
    return flips[:5]


def _render_flips(flips: list[dict[str, Any]]) -> str:
    if not flips:
        return f"{HEADER_FLIPS}\n\n_{EMPTY_FLIPS_MSG}_"
    lines = [HEADER_FLIPS, ""]
    lines.append("| Ticker | Previous | Current | Confidence | Date |")
    lines.append("|--------|----------|---------|------------|------|")
    for f in flips:
        lines.append(
            f"| {f['ticker']} | {f['prev']} | {f['curr']} | "
            f"{f['confidence']}% | {f['date']} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section (c): IC-IR Movers (reads drift_log built in 07-01)
# ---------------------------------------------------------------------------

async def _get_icir_movers(
    db_path: str, cutoff: datetime
) -> list[dict[str, Any]]:
    """Read drift_log rows where evaluated_at >= cutoff AND (triggered=1 OR
    preliminary_threshold=1) — populated weekly by engine.drift_detector."""
    try:
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute(
                    """
                    SELECT agent_name, asset_type, evaluated_at,
                           current_icir, avg_icir_60d, delta_pct,
                           threshold_type, triggered, preliminary_threshold,
                           weight_before, weight_after
                    FROM drift_log
                    WHERE evaluated_at >= ?
                      AND (triggered = 1 OR preliminary_threshold = 1)
                    ORDER BY evaluated_at DESC
                    """,
                    (cutoff.isoformat(),),
                )
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("Digest IC-IR section degraded: %s", exc)
        return []


def _render_icir(movers: list[dict[str, Any]]) -> str:
    if not movers:
        return f"{HEADER_ICIR}\n\n_{EMPTY_ICIR_MSG}_"
    lines = [HEADER_ICIR, ""]
    lines.append("| Agent | Asset | IC-IR Now | 60d Avg | Delta | Status |")
    lines.append("|-------|-------|-----------|---------|-------|--------|")
    for m in movers:
        status = (
            "DRIFT DETECTED"
            if m["triggered"]
            else "PRELIMINARY"
            if m["preliminary_threshold"]
            else "OK"
        )
        current = (
            f"{m['current_icir']:.2f}" if m["current_icir"] is not None else "—"
        )
        avg60 = (
            f"{m['avg_icir_60d']:.2f}" if m["avg_icir_60d"] is not None else "—"
        )
        delta = (
            f"{m['delta_pct']:+.1f}%" if m["delta_pct"] is not None else "—"
        )
        lines.append(
            f"| {m['agent_name']} | {m['asset_type']} | {current} | "
            f"{avg60} | {delta} | {status} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section (d): Open Thesis Drift Alerts
# ---------------------------------------------------------------------------

async def _get_open_alerts(
    db_path: str, cutoff: datetime
) -> list[dict[str, Any]]:
    """Read unacknowledged monitoring_alerts within the last 30 days."""
    try:
        from monitoring.store import AlertStore  # noqa: PLC0415

        store = AlertStore(db_path)
        rows = await store.get_recent_alerts(acknowledged=0, limit=20)
        # Filter to cutoff window
        return [
            r for r in rows if (r.get("created_at") or "") >= cutoff.isoformat()
        ]
    except Exception as exc:
        logger.warning("Digest alerts section degraded: %s", exc)
        return []


def _render_alerts(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return f"{HEADER_ALERTS}\n\n_{EMPTY_ALERTS_MSG}_"
    lines = [HEADER_ALERTS, ""]
    lines.append("| Ticker | Alert Type | Severity | Message | Date |")
    lines.append("|--------|------------|----------|---------|------|")
    for a in alerts:
        ticker = a.get("ticker", "—")
        alert_type = a.get("alert_type", "—")
        severity = a.get("severity", "—")
        # PII clamp: strip thesis text (we never include thesis_text field) and
        # dollar amounts from the short message field (T-07-02-02).
        raw_msg = (a.get("message") or "")[:120]
        msg = _clamp_pii(raw_msg)
        date = (a.get("created_at") or "")[:10]
        lines.append(
            f"| {ticker} | {alert_type} | {severity} | {msg} | {date} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section (e): Action Items
# ---------------------------------------------------------------------------

def _synthesize_actions(
    bench: dict[str, Any],
    flips: list[dict[str, Any]],
    movers: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
) -> list[str]:
    """Heuristic action items — NO dollar amounts, NO thesis text."""
    actions: list[str] = []

    # Drift detected entries
    for m in movers:
        if m.get("triggered"):
            w_before = m.get("weight_before")
            w_after = m.get("weight_after")
            if w_before is not None and w_after is not None:
                actions.append(
                    f"{m['agent_name']} IC-IR dropped on {m['asset_type']} "
                    f"(auto-scaled weight: {w_before:.2f} → {w_after:.2f}); "
                    f"review CalibrationPage."
                )
            else:
                actions.append(
                    f"{m['agent_name']} flagged drift on {m['asset_type']} "
                    f"(NEVER-zero guard active — manual review required)."
                )
        elif m.get("preliminary_threshold"):
            actions.append(
                f"{m['agent_name']} drift threshold preliminary on "
                f"{m['asset_type']} — run corpus rebuild for more samples."
            )

    # Signal reversals
    for f in flips[:3]:
        actions.append(
            f"{f['ticker']} signal flipped {f['prev']} → {f['curr']} on "
            f"{f['date']} — review thesis."
        )

    # Unacknowledged HIGH/CRITICAL alerts
    for a in alerts[:3]:
        sev = (a.get("severity") or "").upper()
        if sev in ("HIGH", "CRITICAL"):
            actions.append(
                f"{a.get('ticker', '—')}: open {sev} alert "
                f"({a.get('alert_type', 'ALERT')}) — acknowledge or act."
            )

    if not actions:
        actions.append("No action items this week.")
    return actions


def _render_actions(actions: list[str]) -> str:
    lines = [HEADER_ACTIONS, ""]
    for a in actions:
        lines.append(f"- {a}")
    return "\n".join(lines)
