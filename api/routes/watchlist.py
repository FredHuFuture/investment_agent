"""Watchlist CRUD and analysis endpoints."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_db_path, map_ticker, resolve_asset_type
from watchlist.manager import WatchlistManager

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AddTickerRequest(BaseModel):
    ticker: str
    asset_type: str = "stock"
    notes: str = ""
    target_buy_price: float | None = None
    alert_below_price: float | None = None


class UpdateTickerRequest(BaseModel):
    notes: str | None = None
    target_buy_price: float | None = None
    alert_below_price: float | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_watchlist(db_path: str = Depends(get_db_path)):
    """Return all watchlist items."""
    mgr = WatchlistManager(db_path)
    items = await mgr.get_watchlist()
    return {"data": items, "warnings": []}


@router.post("")
async def add_to_watchlist(
    body: AddTickerRequest,
    db_path: str = Depends(get_db_path),
):
    """Add a ticker to the watchlist."""
    mgr = WatchlistManager(db_path)
    try:
        row_id = await mgr.add_ticker(
            ticker=body.ticker,
            asset_type=body.asset_type,
            notes=body.notes,
            target_buy_price=body.target_buy_price,
            alert_below_price=body.alert_below_price,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    item = await mgr.get_ticker(body.ticker.upper())
    return {"data": item, "warnings": []}


@router.delete("/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    db_path: str = Depends(get_db_path),
):
    """Remove a ticker from the watchlist."""
    mgr = WatchlistManager(db_path)
    removed = await mgr.remove_ticker(ticker)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker.upper()} not on watchlist")
    return {"data": {"ticker": ticker.upper(), "removed": True}, "warnings": []}


@router.put("/{ticker}")
async def update_watchlist_ticker(
    ticker: str,
    body: UpdateTickerRequest,
    db_path: str = Depends(get_db_path),
):
    """Update notes / price targets for a watchlist ticker."""
    mgr = WatchlistManager(db_path)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await mgr.update_ticker(ticker, **updates)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker.upper()} not on watchlist")
    item = await mgr.get_ticker(ticker.upper())
    return {"data": item, "warnings": []}


@router.post("/{ticker}/analyze")
async def analyze_watchlist_ticker(
    ticker: str,
    db_path: str = Depends(get_db_path),
):
    """Run the analysis pipeline on a watchlist ticker and persist the result."""
    mgr = WatchlistManager(db_path)
    item = await mgr.get_ticker(ticker)
    if not item:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker.upper()} not on watchlist")

    asset_type = resolve_asset_type(ticker, item["asset_type"])
    yf_ticker = map_ticker(ticker, asset_type)

    from engine.pipeline import AnalysisPipeline

    pipeline = AnalysisPipeline(db_path=db_path)
    try:
        result = await pipeline.analyze_ticker(yf_ticker, asset_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Analysis failed: {exc}")

    signal = result.final_signal
    confidence = result.final_confidence
    await mgr.update_analysis(ticker, signal, confidence)
    updated_item = await mgr.get_ticker(ticker)

    return {
        "data": {
            "watchlist_item": updated_item,
            "analysis": result.to_dict(),
        },
        "warnings": result.warnings,
    }
