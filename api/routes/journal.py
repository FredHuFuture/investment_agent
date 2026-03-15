"""Trade journal annotation endpoints."""
from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_db_path
from engine.journal_analytics import JournalAnalytics

router = APIRouter()

_CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS trade_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_ticker TEXT NOT NULL,
    annotation_text TEXT NOT NULL,
    lesson_tag TEXT,
    created_at TEXT DEFAULT (datetime('now'))
)
"""


class CreateAnnotationRequest(BaseModel):
    annotation_text: str
    lesson_tag: str | None = None


async def _ensure_table(db_path: str) -> None:
    """Create the trade_annotations table if it does not exist."""
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(_CREATE_TABLE_SQL)
        await conn.commit()


@router.get("/annotations/{ticker}")
async def get_annotations(
    ticker: str,
    db_path: str = Depends(get_db_path),
):
    """Fetch all annotations for a closed position ticker."""
    await _ensure_table(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, position_ticker, annotation_text, lesson_tag, created_at "
            "FROM trade_annotations WHERE position_ticker = ? ORDER BY created_at DESC",
            (ticker.upper(),),
        )
        rows = await cursor.fetchall()

    data = [
        {
            "id": row["id"],
            "position_ticker": row["position_ticker"],
            "annotation_text": row["annotation_text"],
            "lesson_tag": row["lesson_tag"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {"data": data, "warnings": []}


@router.post("/annotations/{ticker}")
async def create_annotation(
    ticker: str,
    body: CreateAnnotationRequest,
    db_path: str = Depends(get_db_path),
):
    """Create a new annotation for a closed position."""
    if not body.annotation_text.strip():
        raise HTTPException(status_code=400, detail="Annotation text cannot be empty")

    await _ensure_table(db_path)
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO trade_annotations (position_ticker, annotation_text, lesson_tag) "
            "VALUES (?, ?, ?)",
            (ticker.upper(), body.annotation_text.strip(), body.lesson_tag),
        )
        await conn.commit()
        row_id = cursor.lastrowid

        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, position_ticker, annotation_text, lesson_tag, created_at "
            "FROM trade_annotations WHERE id = ?",
            (row_id,),
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=500, detail="Failed to create annotation")

    data = {
        "id": row["id"],
        "position_ticker": row["position_ticker"],
        "annotation_text": row["annotation_text"],
        "lesson_tag": row["lesson_tag"],
        "created_at": row["created_at"],
    }
    return {"data": data, "warnings": []}


@router.get("/lesson-stats")
async def lesson_stats(db_path: str = Depends(get_db_path)):
    """Compute win-rate-by-tag analytics for lesson annotations."""
    analytics = JournalAnalytics(db_path)
    data = await analytics.get_lesson_tag_stats()
    return {"data": data, "warnings": []}


# ---------------------------------------------------------------------------
# Position Quick Notes
# ---------------------------------------------------------------------------

_CREATE_POSITION_NOTES_SQL = """\
CREATE TABLE IF NOT EXISTS position_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    note_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


class CreatePositionNoteRequest(BaseModel):
    note_text: str


async def _ensure_position_notes_table(db_path: str) -> None:
    """Create the position_notes table if it does not exist."""
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(_CREATE_POSITION_NOTES_SQL)
        await conn.commit()


@router.get("/position-notes/{ticker}")
async def get_position_notes(
    ticker: str,
    db_path: str = Depends(get_db_path),
):
    """Fetch all quick notes for a position ticker."""
    await _ensure_position_notes_table(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, ticker, note_text, created_at "
            "FROM position_notes WHERE ticker = ? ORDER BY created_at DESC",
            (ticker.upper(),),
        )
        rows = await cursor.fetchall()

    data = [
        {
            "id": row["id"],
            "ticker": row["ticker"],
            "note_text": row["note_text"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {"data": data, "warnings": []}


@router.post("/position-notes/{ticker}")
async def create_position_note(
    ticker: str,
    body: CreatePositionNoteRequest,
    db_path: str = Depends(get_db_path),
):
    """Create a new quick note for a position."""
    if not body.note_text.strip():
        raise HTTPException(status_code=400, detail="Note text cannot be empty")

    await _ensure_position_notes_table(db_path)
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO position_notes (ticker, note_text) VALUES (?, ?)",
            (ticker.upper(), body.note_text.strip()),
        )
        await conn.commit()
        row_id = cursor.lastrowid

        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, ticker, note_text, created_at "
            "FROM position_notes WHERE id = ?",
            (row_id,),
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=500, detail="Failed to create note")

    data = {
        "id": row["id"],
        "ticker": row["ticker"],
        "note_text": row["note_text"],
        "created_at": row["created_at"],
    }
    return {"data": data, "warnings": []}


# ---------------------------------------------------------------------------
# Trade Journal Insights
# ---------------------------------------------------------------------------


@router.get("/insights")
async def get_insights(db_path: str = Depends(get_db_path)):
    """Generate actionable trading insights from closed position data."""
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT ticker, sector, quantity, avg_cost, entry_date, "
            "exit_date, exit_reason, realized_pnl, expected_hold_days, "
            "expected_return_pct "
            "FROM active_positions WHERE status = 'closed'"
        )
        rows = await cursor.fetchall()

    if len(rows) < 3:
        return {
            "data": [
                {
                    "type": "insufficient_data",
                    "title": "More Trades Needed",
                    "detail": (
                        f"You have {len(rows)} closed trade(s). "
                        "Close at least 3 trades to unlock trading insights."
                    ),
                    "metric_value": len(rows),
                    "severity": "neutral",
                }
            ],
            "warnings": [],
        }

    insights: list[dict] = []

    # Helper: compute hold days between two date strings
    def _hold_days(entry: str | None, exit_d: str | None) -> int | None:
        if not entry or not exit_d:
            return None
        try:
            from datetime import datetime

            fmt = "%Y-%m-%d"
            d1 = datetime.strptime(entry[:10], fmt)
            d2 = datetime.strptime(exit_d[:10], fmt)
            return max((d2 - d1).days, 0)
        except (ValueError, TypeError):
            return None

    # Build enriched list
    trades: list[dict] = []
    for r in rows:
        cost_basis = r["avg_cost"] * r["quantity"] if r["avg_cost"] and r["quantity"] else 0
        pnl = r["realized_pnl"] or 0
        ret_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0
        hold = _hold_days(r["entry_date"], r["exit_date"])
        trades.append(
            {
                "ticker": r["ticker"],
                "sector": r["sector"],
                "cost_basis": cost_basis,
                "pnl": pnl,
                "return_pct": ret_pct,
                "hold_days": hold,
                "expected_hold_days": r["expected_hold_days"],
                "is_win": pnl > 0,
            }
        )

    total = len(trades)
    wins = sum(1 for t in trades if t["is_win"])
    win_rate = (wins / total * 100) if total else 0

    # --- 1. Best performing sector ---
    sector_returns: dict[str, list[float]] = {}
    for t in trades:
        sec = t["sector"] or "Unknown"
        sector_returns.setdefault(sec, []).append(t["return_pct"])
    if sector_returns:
        best_sector = max(sector_returns, key=lambda s: sum(sector_returns[s]) / len(sector_returns[s]))
        best_avg = sum(sector_returns[best_sector]) / len(sector_returns[best_sector])
        count_in_sector = len(sector_returns[best_sector])
        insights.append(
            {
                "type": "best_sector",
                "title": "Best Performing Sector",
                "detail": (
                    f"{best_sector} leads with an average return of "
                    f"{best_avg:+.1f}% across {count_in_sector} trade(s)."
                ),
                "metric_value": round(best_avg, 1),
                "severity": "positive" if best_avg > 0 else "negative",
            }
        )

    # --- 2. Average hold time vs expected ---
    actual_holds = [t["hold_days"] for t in trades if t["hold_days"] is not None]
    expected_holds = [t["expected_hold_days"] for t in trades if t["expected_hold_days"] is not None]
    if actual_holds:
        avg_hold = sum(actual_holds) / len(actual_holds)
        if expected_holds:
            avg_expected = sum(expected_holds) / len(expected_holds)
            diff = avg_hold - avg_expected
            if abs(diff) < 3:
                sev = "positive"
                msg = f"Average hold of {avg_hold:.0f} days is close to your {avg_expected:.0f}-day target."
            elif diff > 0:
                sev = "negative"
                msg = (
                    f"Average hold of {avg_hold:.0f} days exceeds your "
                    f"{avg_expected:.0f}-day target by {diff:.0f} days."
                )
            else:
                sev = "neutral"
                msg = (
                    f"Average hold of {avg_hold:.0f} days is {abs(diff):.0f} days "
                    f"shorter than your {avg_expected:.0f}-day target."
                )
        else:
            sev = "neutral"
            msg = f"Average hold time is {avg_hold:.0f} days across {len(actual_holds)} trades."
        insights.append(
            {
                "type": "hold_time",
                "title": "Hold Time Analysis",
                "detail": msg,
                "metric_value": round(avg_hold, 0),
                "severity": sev,
            }
        )

    # --- 3. Win rate trend (first half vs second half) ---
    if total >= 4:
        mid = total // 2
        early_wins = sum(1 for t in trades[:mid] if t["is_win"])
        late_wins = sum(1 for t in trades[mid:] if t["is_win"])
        early_rate = early_wins / mid * 100
        late_rate = late_wins / (total - mid) * 100
        diff = late_rate - early_rate
        if diff > 5:
            sev = "positive"
            trend_word = "improving"
        elif diff < -5:
            sev = "negative"
            trend_word = "declining"
        else:
            sev = "neutral"
            trend_word = "steady"
        insights.append(
            {
                "type": "win_rate_trend",
                "title": "Win Rate Trend",
                "detail": (
                    f"Your win rate is {trend_word}: early trades {early_rate:.0f}% "
                    f"vs recent trades {late_rate:.0f}%."
                ),
                "metric_value": round(late_rate, 1),
                "severity": sev,
            }
        )

    # --- 4. Biggest lesson (most common lesson_tag) ---
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT lesson_tag, COUNT(*) as cnt "
            "FROM trade_annotations "
            "WHERE lesson_tag IS NOT NULL AND lesson_tag != '' "
            "GROUP BY lesson_tag ORDER BY cnt DESC LIMIT 1"
        )
        top_tag = await cursor.fetchone()
    if top_tag:
        tag_name = top_tag["lesson_tag"].replace("_", " ").title()
        insights.append(
            {
                "type": "biggest_lesson",
                "title": "Biggest Lesson",
                "detail": (
                    f"Your most common lesson tag is '{tag_name}' "
                    f"with {top_tag['cnt']} annotation(s). "
                    "Review these trades for recurring patterns."
                ),
                "metric_value": top_tag["cnt"],
                "severity": "neutral",
            }
        )

    # --- 5. Position sizing: larger vs smaller positions ---
    if total >= 4:
        sorted_by_size = sorted(trades, key=lambda t: t["cost_basis"])
        mid = total // 2
        small_avg_ret = sum(t["return_pct"] for t in sorted_by_size[:mid]) / mid
        large_avg_ret = sum(t["return_pct"] for t in sorted_by_size[mid:]) / (total - mid)
        diff = large_avg_ret - small_avg_ret
        if diff > 2:
            sev = "positive"
            msg = (
                f"Larger positions averaged {large_avg_ret:+.1f}% vs "
                f"{small_avg_ret:+.1f}% for smaller ones. "
                "Your sizing conviction appears well-placed."
            )
        elif diff < -2:
            sev = "negative"
            msg = (
                f"Larger positions averaged {large_avg_ret:+.1f}% vs "
                f"{small_avg_ret:+.1f}% for smaller ones. "
                "Consider scaling down high-conviction bets."
            )
        else:
            sev = "neutral"
            msg = (
                f"Position size shows little impact: large positions {large_avg_ret:+.1f}% "
                f"vs small {small_avg_ret:+.1f}%."
            )
        insights.append(
            {
                "type": "position_sizing",
                "title": "Position Sizing Impact",
                "detail": msg,
                "metric_value": round(diff, 1),
                "severity": sev,
            }
        )

    # --- 6. Hold time vs returns correlation ---
    trades_with_hold = [t for t in trades if t["hold_days"] is not None and t["hold_days"] > 0]
    if len(trades_with_hold) >= 4:
        holds = [t["hold_days"] for t in trades_with_hold]
        rets = [t["return_pct"] for t in trades_with_hold]
        n = len(holds)
        mean_h = sum(holds) / n
        mean_r = sum(rets) / n
        cov = sum((holds[i] - mean_h) * (rets[i] - mean_r) for i in range(n)) / n
        std_h = (sum((h - mean_h) ** 2 for h in holds) / n) ** 0.5
        std_r = (sum((r - mean_r) ** 2 for r in rets) / n) ** 0.5
        corr = cov / (std_h * std_r) if std_h > 0 and std_r > 0 else 0
        if corr > 0.3:
            sev = "positive"
            msg = "Longer holds tend to produce better returns. Patience may be paying off."
        elif corr < -0.3:
            sev = "negative"
            msg = "Longer holds tend to produce worse returns. Consider tighter exit timing."
        else:
            sev = "neutral"
            msg = "Hold duration shows no strong relationship with returns."
        insights.append(
            {
                "type": "hold_return_correlation",
                "title": "Hold Time vs Returns",
                "detail": msg,
                "metric_value": round(corr, 2),
                "severity": sev,
            }
        )

    return {"data": insights, "warnings": []}
