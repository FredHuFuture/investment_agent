"""Portfolio management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_db_path
from api.models import AddPositionRequest, ScaleRequest, SetCashRequest, SplitRequest
from portfolio.manager import PortfolioManager

router = APIRouter()


@router.get("")
async def get_portfolio(db_path: str = Depends(get_db_path)):
    """Return the current portfolio with positions and allocations."""
    mgr = PortfolioManager(db_path)
    portfolio = await mgr.load_portfolio()
    return {"data": portfolio.to_dict(), "warnings": []}


@router.post("/positions")
async def add_position(body: AddPositionRequest, db_path: str = Depends(get_db_path)):
    """Add a new position to the portfolio."""
    mgr = PortfolioManager(db_path)
    pos_id = await mgr.add_position(
        ticker=body.ticker.upper(),
        asset_type=body.asset_type,
        quantity=body.quantity,
        avg_cost=body.avg_cost,
        entry_date=body.entry_date,
        sector=body.sector,
        industry=body.industry,
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
