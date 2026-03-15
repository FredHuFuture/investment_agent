"""Portfolio management endpoints."""
from __future__ import annotations

import asyncio
import logging

import aiosqlite
from fastapi import APIRouter, Depends

from api.deps import get_db_path, map_ticker, resolve_asset_type
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
