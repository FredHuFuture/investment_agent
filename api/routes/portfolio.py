"""Portfolio management endpoints."""
from __future__ import annotations

import asyncio
import logging

import aiosqlite
from fastapi import APIRouter, Depends

from api.deps import get_db_path, map_ticker, resolve_asset_type
from pydantic import BaseModel
from api.models import AddPositionRequest, BulkImportRequest, ClosePositionRequest, ScaleRequest, SetCashRequest, SplitRequest, ThesisResponse, UpdateThesisRequest
from data_providers.factory import get_provider
from portfolio.manager import PortfolioManager

logger = logging.getLogger(__name__)

router = APIRouter()


async def _fetch_price(ticker: str, asset_type: str) -> tuple[str, float]:
    """Fetch current price for a single position."""
    try:
        provider = get_provider(asset_type)
        yf_ticker = map_ticker(ticker, asset_type)
        price = await provider.get_current_price(yf_ticker)
        return ticker, price
    except Exception as exc:
        logger.warning("Failed to fetch price for %s: %s", ticker, exc)
        return ticker, 0.0


@router.get("")
async def get_portfolio(db_path: str = Depends(get_db_path)):
    """Return the current portfolio with live prices."""
    mgr = PortfolioManager(db_path)
    portfolio = await mgr.load_portfolio()

    # Fetch live prices for all positions in parallel
    warnings: list[str] = []
    if portfolio.positions:
        results = await asyncio.gather(
            *[_fetch_price(p.ticker, p.asset_type) for p in portfolio.positions]
        )
        price_map = dict(results)
        for pos in portfolio.positions:
            price = price_map.get(pos.ticker, 0.0)
            if price > 0:
                pos.current_price = price
            else:
                warnings.append(f"Could not fetch price for {pos.ticker}")

        # Recompute totals using market values now that we have prices
        portfolio = mgr.recompute_with_prices(portfolio)

    return {"data": portfolio.to_dict(), "warnings": warnings}


@router.post("/positions")
async def add_position(body: AddPositionRequest, db_path: str = Depends(get_db_path)):
    """Add a new position to the portfolio."""
    ticker = body.ticker.upper()
    asset_type = resolve_asset_type(ticker, body.asset_type)
    # Normalize crypto tickers to yfinance format for DB consistency
    ticker = map_ticker(ticker, asset_type)

    mgr = PortfolioManager(db_path)
    pos_id = await mgr.add_position(
        ticker=ticker,
        asset_type=asset_type,
        quantity=body.quantity,
        avg_cost=body.avg_cost,
        entry_date=body.entry_date,
        sector=body.sector,
        industry=body.industry,
        thesis_text=body.thesis_text,
        expected_return_pct=body.expected_return_pct,
        expected_hold_days=body.expected_hold_days,
        target_price=body.target_price,
        stop_loss=body.stop_loss,
    )
    return {"data": {"id": pos_id}, "warnings": []}


@router.post("/bulk-import")
async def bulk_import_positions(body: BulkImportRequest, db_path: str = Depends(get_db_path)):
    """Bulk-import positions from a list. Skips tickers that already exist."""
    import re
    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    mgr = PortfolioManager(db_path)
    imported = 0
    skipped = 0
    errors: list[dict] = []

    for item in body.positions:
        ticker = item.ticker.strip().upper()

        # Validate date format
        if not date_re.match(item.entry_date):
            errors.append({"ticker": ticker, "reason": f"Invalid date format: {item.entry_date}"})
            continue

        # Validate non-negative values
        if item.quantity <= 0:
            errors.append({"ticker": ticker, "reason": "Quantity must be positive"})
            continue
        if item.avg_cost <= 0:
            errors.append({"ticker": ticker, "reason": "Average cost must be positive"})
            continue

        asset_type = resolve_asset_type(ticker, item.asset_type)
        mapped_ticker = map_ticker(ticker, asset_type)

        try:
            await mgr.add_position(
                ticker=mapped_ticker,
                asset_type=asset_type,
                quantity=item.quantity,
                avg_cost=item.avg_cost,
                entry_date=item.entry_date,
                sector=item.sector,
            )
            imported += 1
        except ValueError:
            # Already exists
            skipped += 1
        except Exception as exc:
            errors.append({"ticker": mapped_ticker, "reason": str(exc)})

    return {"data": {"imported": imported, "skipped": skipped, "errors": errors}, "warnings": []}


@router.delete("/positions/{ticker}")
async def remove_position(ticker: str, db_path: str = Depends(get_db_path)):
    """Remove a position by ticker."""
    mgr = PortfolioManager(db_path)
    removed = await mgr.remove_position(ticker.upper())
    if not removed:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={
                "error": {"code": "NOT_FOUND", "message": f"No position for '{ticker.upper()}'", "detail": None}
            },
        )
    return {"data": {"removed": True}, "warnings": []}


@router.post("/positions/{ticker}/close")
async def close_position(ticker: str, body: ClosePositionRequest, db_path: str = Depends(get_db_path)):
    """Close an open position and record realized P&L."""
    mgr = PortfolioManager(db_path)
    try:
        result = await mgr.close_position(
            ticker=ticker.upper(),
            exit_price=body.exit_price,
            exit_reason=body.exit_reason,
            exit_date=body.exit_date,
        )
    except ValueError as exc:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": str(exc), "detail": None}},
        )
    return {"data": result, "warnings": []}


@router.get("/history")
async def get_position_history(db_path: str = Depends(get_db_path)):
    """Return all closed positions."""
    mgr = PortfolioManager(db_path)
    closed = await mgr.get_closed_positions()
    return {
        "data": [p.to_dict() for p in closed],
        "warnings": [],
    }


@router.put("/cash")
async def set_cash(body: SetCashRequest, db_path: str = Depends(get_db_path)):
    """Set the portfolio cash balance."""
    mgr = PortfolioManager(db_path)
    await mgr.set_cash(body.amount)
    return {"data": {"cash": body.amount}, "warnings": []}


@router.post("/scale")
async def scale_portfolio(body: ScaleRequest, db_path: str = Depends(get_db_path)):
    """Scale all positions by a multiplier."""
    mgr = PortfolioManager(db_path)
    await mgr.scale_portfolio(body.multiplier)
    return {"data": {"multiplier": body.multiplier}, "warnings": []}


@router.post("/split")
async def apply_split(body: SplitRequest, db_path: str = Depends(get_db_path)):
    """Apply a stock split to a position."""
    mgr = PortfolioManager(db_path)
    await mgr.apply_split(body.ticker.upper(), body.ratio)
    return {"data": {"applied": True, "ticker": body.ticker.upper(), "ratio": body.ratio}, "warnings": []}


@router.get("/positions/{ticker}/thesis")
async def get_thesis(ticker: str, db_path: str = Depends(get_db_path)):
    """Get thesis data and drift summary for a position."""
    mgr = PortfolioManager(db_path)
    thesis = await mgr.get_thesis(ticker.upper())
    if thesis is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"No thesis found for '{ticker.upper()}'",
                    "detail": None,
                }
            },
        )
    return {"data": thesis, "warnings": []}


@router.put("/positions/{ticker}/thesis")
async def update_thesis(ticker: str, body: UpdateThesisRequest, db_path: str = Depends(get_db_path)):
    """Update thesis fields for an existing position."""
    mgr = PortfolioManager(db_path)
    try:
        result = await mgr.update_thesis(
            ticker=ticker.upper(),
            thesis_text=body.thesis_text,
            target_price=body.target_price,
            stop_loss=body.stop_loss,
            expected_hold_days=body.expected_hold_days,
            expected_return_pct=body.expected_return_pct,
        )
    except ValueError as exc:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": str(exc), "detail": None}},
        )
    return {"data": result, "warnings": []}


@router.get("/sector/{sector}")
async def get_positions_by_sector(sector: str, db_path: str = Depends(get_db_path)):
    """Return open positions filtered by sector name."""
    mgr = PortfolioManager(db_path)
    portfolio = await mgr.load_portfolio()
    filtered = []
    for p in portfolio.positions:
        pos_sector = p.get("sector", "") if isinstance(p, dict) else getattr(p, "sector", "")
        if (pos_sector or "").lower() == sector.lower():
            row = p if isinstance(p, dict) else p.to_dict()
            filtered.append(row)
    return {"data": filtered, "warnings": []}


@router.get("/positions/{ticker}/timeline")
async def get_position_timeline(ticker: str, db_path: str = Depends(get_db_path)):
    """Aggregate events from multiple tables into a chronological timeline."""
    upper_ticker = ticker.upper()
    events: list[dict] = []

    db_path_resolved = db_path
    async with aiosqlite.connect(db_path_resolved) as conn:
        conn.row_factory = aiosqlite.Row

        # 1. Entry event from active_positions
        cursor = await conn.execute(
            "SELECT entry_date, ticker, avg_cost, quantity, status, "
            "exit_date, exit_price, exit_reason, realized_pnl "
            "FROM active_positions WHERE UPPER(ticker) = ?",
            (upper_ticker,),
        )
        pos_rows = await cursor.fetchall()

        for row in pos_rows:
            events.append({
                "type": "entry",
                "date": row["entry_date"],
                "title": f"Opened position in {row['ticker']}",
                "detail": f"Bought {row['quantity']} shares @ ${row['avg_cost']:.2f}",
                "severity": None,
                "metadata": {
                    "avg_cost": row["avg_cost"],
                    "quantity": row["quantity"],
                },
            })

            # 5. Exit event (if closed)
            if row["status"] == "closed" and row["exit_date"]:
                events.append({
                    "type": "exit",
                    "date": row["exit_date"],
                    "title": f"Closed position in {row['ticker']}",
                    "detail": (
                        f"Exit @ ${row['exit_price']:.2f}"
                        + (f" — {row['exit_reason']}" if row["exit_reason"] else "")
                        + (f" — P&L: ${row['realized_pnl']:.2f}" if row["realized_pnl"] is not None else "")
                    ),
                    "severity": "critical",
                    "metadata": {
                        "exit_price": row["exit_price"],
                        "exit_reason": row["exit_reason"],
                        "realized_pnl": row["realized_pnl"],
                    },
                })

        # 2. Signals from signal_history
        cursor = await conn.execute(
            "SELECT created_at, final_signal, final_confidence, reasoning "
            "FROM signal_history WHERE UPPER(ticker) = ? ORDER BY created_at DESC",
            (upper_ticker,),
        )
        for row in await cursor.fetchall():
            reasoning = row["reasoning"] or ""
            events.append({
                "type": "signal",
                "date": row["created_at"],
                "title": f"Signal: {row['final_signal']} ({row['final_confidence']:.0%})",
                "detail": reasoning[:200] if reasoning else None,
                "severity": None,
                "metadata": {
                    "final_signal": row["final_signal"],
                    "final_confidence": row["final_confidence"],
                },
            })

        # 3. Alerts from monitoring_alerts
        cursor = await conn.execute(
            "SELECT created_at, alert_type, severity, message "
            "FROM monitoring_alerts WHERE UPPER(ticker) = ? ORDER BY created_at DESC",
            (upper_ticker,),
        )
        for row in await cursor.fetchall():
            events.append({
                "type": "alert",
                "date": row["created_at"],
                "title": f"Alert: {row['alert_type']}",
                "detail": row["message"],
                "severity": row["severity"].lower() if row["severity"] else None,
                "metadata": {
                    "alert_type": row["alert_type"],
                    "severity": row["severity"],
                },
            })

        # 4. Annotations from trade_annotations
        try:
            cursor = await conn.execute(
                "SELECT created_at, annotation_text, lesson_tag "
                "FROM trade_annotations WHERE UPPER(position_ticker) = ? ORDER BY created_at DESC",
                (upper_ticker,),
            )
            for row in await cursor.fetchall():
                tag = row["lesson_tag"]
                events.append({
                    "type": "annotation",
                    "date": row["created_at"],
                    "title": f"Annotation" + (f" [{tag}]" if tag else ""),
                    "detail": row["annotation_text"],
                    "severity": None,
                    "metadata": {
                        "lesson_tag": tag,
                    },
                })
        except Exception:
            # Table may not exist yet
            pass

    # Sort all events by date descending (newest first)
    events.sort(key=lambda e: e["date"] or "", reverse=True)

    return {"data": events, "warnings": []}


# ---------------------------------------------------------------------------
# Dividend endpoints
# ---------------------------------------------------------------------------

class AddDividendRequest(BaseModel):
    amount_per_share: float
    ex_date: str
    pay_date: str | None = None


@router.get("/positions/{ticker}/dividends")
async def get_dividends(ticker: str, db_path: str = Depends(get_db_path)):
    """Return dividend history and yield-on-cost for a position."""
    upper_ticker = ticker.upper()

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Ensure dividends table exists
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS dividends ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ticker TEXT NOT NULL, "
            "amount_per_share REAL NOT NULL, "
            "total_amount REAL NOT NULL, "
            "ex_date TEXT NOT NULL, "
            "pay_date TEXT, "
            "created_at TEXT DEFAULT (datetime('now'))"
            ")"
        )
        await conn.commit()

        # Fetch all dividends for this ticker
        cursor = await conn.execute(
            "SELECT id, ticker, amount_per_share, total_amount, ex_date, pay_date, created_at "
            "FROM dividends WHERE UPPER(ticker) = ? ORDER BY ex_date DESC",
            (upper_ticker,),
        )
        rows = await cursor.fetchall()
        entries = [
            {
                "id": r["id"],
                "ticker": r["ticker"],
                "amount_per_share": r["amount_per_share"],
                "total_amount": r["total_amount"],
                "ex_date": r["ex_date"],
                "pay_date": r["pay_date"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

        total_dividends = sum(e["total_amount"] for e in entries)

        # Get avg_cost and quantity from active_positions to compute yield_on_cost
        cursor = await conn.execute(
            "SELECT avg_cost, quantity FROM active_positions WHERE UPPER(ticker) = ?",
            (upper_ticker,),
        )
        pos_row = await cursor.fetchone()
        cost_basis = (pos_row["avg_cost"] * pos_row["quantity"]) if pos_row else 0.0
        yield_on_cost_pct = (total_dividends / cost_basis) * 100 if cost_basis > 0 else 0.0

    return {
        "data": {
            "entries": entries,
            "total_dividends": total_dividends,
            "yield_on_cost_pct": yield_on_cost_pct,
        },
        "warnings": [],
    }


@router.get("/earnings/upcoming")
async def get_upcoming_earnings(db_path: str = Depends(get_db_path)):
    """Return upcoming earnings dates for all open positions (next 60 days)."""
    from datetime import date, datetime

    events: list[dict] = []
    warnings: list[str] = []

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT ticker FROM active_positions WHERE status = 'open'"
        )
        rows = await cursor.fetchall()

    tickers = [row["ticker"] for row in rows]
    if not tickers:
        return {"data": [], "warnings": []}

    today = date.today()

    for ticker in tickers:
        try:
            import yfinance as yf

            yf_ticker = yf.Ticker(ticker)
            cal = yf_ticker.calendar
            if cal is None or (hasattr(cal, "empty") and cal.empty):
                continue

            # yfinance .calendar can return a dict or DataFrame depending on version
            earnings_date_val = None
            estimate_eps = None
            actual_eps = None

            if isinstance(cal, dict):
                # Dict format: {"Earnings Date": [...], "EPS Estimate": ..., ...}
                ed = cal.get("Earnings Date")
                if ed:
                    if isinstance(ed, list) and len(ed) > 0:
                        earnings_date_val = ed[0]
                    else:
                        earnings_date_val = ed
                estimate_eps = cal.get("EPS Estimate")
                actual_eps = cal.get("Reported EPS")
            else:
                # DataFrame format
                if "Earnings Date" in cal.index:
                    ed = cal.loc["Earnings Date"]
                    if hasattr(ed, "iloc"):
                        earnings_date_val = ed.iloc[0]
                    else:
                        earnings_date_val = ed
                if "EPS Estimate" in cal.index:
                    est = cal.loc["EPS Estimate"]
                    estimate_eps = est.iloc[0] if hasattr(est, "iloc") else est
                if "Reported EPS" in cal.index:
                    act = cal.loc["Reported EPS"]
                    actual_eps = act.iloc[0] if hasattr(act, "iloc") else act

            if earnings_date_val is None:
                continue

            # Normalize to date
            if isinstance(earnings_date_val, datetime):
                earnings_date_obj = earnings_date_val.date()
            elif isinstance(earnings_date_val, date):
                earnings_date_obj = earnings_date_val
            elif isinstance(earnings_date_val, str):
                earnings_date_obj = datetime.strptime(earnings_date_val[:10], "%Y-%m-%d").date()
            else:
                # Pandas Timestamp
                earnings_date_obj = earnings_date_val.date() if hasattr(earnings_date_val, "date") else None
                if earnings_date_obj is None:
                    continue

            days_until = (earnings_date_obj - today).days
            if days_until < 0 or days_until > 60:
                continue

            # Sanitize EPS values
            try:
                estimate_eps = float(estimate_eps) if estimate_eps is not None else None
            except (TypeError, ValueError):
                estimate_eps = None
            try:
                actual_eps = float(actual_eps) if actual_eps is not None else None
            except (TypeError, ValueError):
                actual_eps = None

            events.append({
                "ticker": ticker,
                "earnings_date": earnings_date_obj.isoformat(),
                "days_until": days_until,
                "estimate_eps": estimate_eps,
                "actual_eps": actual_eps,
                "source": "yfinance",
            })
        except Exception as exc:
            logger.warning("Failed to fetch earnings for %s: %s", ticker, exc)
            warnings.append(f"Could not fetch earnings for {ticker}")

    # Sort by earnings date (soonest first)
    events.sort(key=lambda e: e["earnings_date"])

    return {"data": events, "warnings": warnings}


@router.post("/positions/{ticker}/dividends")
async def add_dividend(ticker: str, body: AddDividendRequest, db_path: str = Depends(get_db_path)):
    """Record a new dividend for a position."""
    upper_ticker = ticker.upper()

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Ensure dividends table exists
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS dividends ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ticker TEXT NOT NULL, "
            "amount_per_share REAL NOT NULL, "
            "total_amount REAL NOT NULL, "
            "ex_date TEXT NOT NULL, "
            "pay_date TEXT, "
            "created_at TEXT DEFAULT (datetime('now'))"
            ")"
        )

        # Look up the position's quantity
        cursor = await conn.execute(
            "SELECT quantity FROM active_positions WHERE UPPER(ticker) = ?",
            (upper_ticker,),
        )
        pos_row = await cursor.fetchone()
        if pos_row is None:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"No active position for '{upper_ticker}'",
                        "detail": None,
                    }
                },
            )

        quantity = pos_row["quantity"]
        total_amount = body.amount_per_share * quantity

        cursor = await conn.execute(
            "INSERT INTO dividends (ticker, amount_per_share, total_amount, ex_date, pay_date) "
            "VALUES (?, ?, ?, ?, ?)",
            (upper_ticker, body.amount_per_share, total_amount, body.ex_date, body.pay_date),
        )
        await conn.commit()
        new_id = cursor.lastrowid

    return {"data": {"id": new_id}, "warnings": []}


# ---------------------------------------------------------------------------
# Portfolio goals endpoints
# ---------------------------------------------------------------------------

class AddGoalRequest(BaseModel):
    label: str
    target_value: float
    target_date: str | None = None


@router.get("/goals")
async def get_portfolio_goals(db_path: str = Depends(get_db_path)):
    """List all portfolio goals."""
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS portfolio_goals ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "label TEXT NOT NULL, "
            "target_value REAL NOT NULL, "
            "target_date TEXT, "
            "created_at TEXT NOT NULL DEFAULT (datetime('now'))"
            ")"
        )
        await conn.commit()

        cursor = await conn.execute(
            "SELECT id, label, target_value, target_date, created_at "
            "FROM portfolio_goals ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        goals = [
            {
                "id": r["id"],
                "label": r["label"],
                "target_value": r["target_value"],
                "target_date": r["target_date"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    return {"data": goals, "warnings": []}


@router.post("/goals")
async def add_portfolio_goal(body: AddGoalRequest, db_path: str = Depends(get_db_path)):
    """Add a new portfolio goal."""
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS portfolio_goals ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "label TEXT NOT NULL, "
            "target_value REAL NOT NULL, "
            "target_date TEXT, "
            "created_at TEXT NOT NULL DEFAULT (datetime('now'))"
            ")"
        )

        cursor = await conn.execute(
            "INSERT INTO portfolio_goals (label, target_value, target_date) "
            "VALUES (?, ?, ?)",
            (body.label, body.target_value, body.target_date),
        )
        await conn.commit()
        new_id = cursor.lastrowid

        cursor = await conn.execute(
            "SELECT id, label, target_value, target_date, created_at "
            "FROM portfolio_goals WHERE id = ?",
            (new_id,),
        )
        row = await cursor.fetchone()

    return {
        "data": {
            "id": row["id"],
            "label": row["label"],
            "target_value": row["target_value"],
            "target_date": row["target_date"],
            "created_at": row["created_at"],
        },
        "warnings": [],
    }


@router.delete("/goals/{goal_id}")
async def delete_portfolio_goal(goal_id: int, db_path: str = Depends(get_db_path)):
    """Delete a portfolio goal by ID."""
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "DELETE FROM portfolio_goals WHERE id = ?",
            (goal_id,),
        )
        await conn.commit()
        deleted = cursor.rowcount > 0

    if not deleted:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"No goal with id {goal_id}",
                    "detail": None,
                }
            },
        )

    return {"data": {"deleted": True}, "warnings": []}
