"""Portfolio management endpoints."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends

from api.deps import get_db_path, map_ticker, resolve_asset_type
from api.models import AddPositionRequest, ClosePositionRequest, ScaleRequest, SetCashRequest, SplitRequest, ThesisResponse, UpdateThesisRequest
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
