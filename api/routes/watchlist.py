"""Watchlist CRUD and analysis endpoints."""
from __future__ import annotations

from typing import Literal

import aiosqlite
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


class AlertConfigRequest(BaseModel):
    alert_on_signal_change: bool = True
    min_confidence: float = 60.0
    alert_on_price_below: float | None = None
    enabled: bool = True


class BulkAddItem(BaseModel):
    ticker: str
    asset_type: str = "stock"
    notes: str = ""
    target_buy_price: float | None = None


class BulkAddRequest(BaseModel):
    items: list[BulkAddItem]


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


@router.post("/bulk-add")
async def bulk_add_to_watchlist(
    body: BulkAddRequest,
    db_path: str = Depends(get_db_path),
):
    """Add multiple tickers to the watchlist at once."""
    mgr = WatchlistManager(db_path)
    added = 0
    skipped = 0
    errors: list[dict[str, str]] = []

    for item in body.items:
        ticker = item.ticker.strip().upper()
        if not ticker:
            continue
        try:
            await mgr.add_ticker(
                ticker=ticker,
                asset_type=item.asset_type,
                notes=item.notes,
                target_buy_price=item.target_buy_price,
            )
            added += 1
        except ValueError:
            # Already exists on the watchlist
            skipped += 1
        except Exception as exc:
            errors.append({"ticker": ticker, "reason": str(exc)})

    return {
        "data": {"added": added, "skipped": skipped, "errors": errors},
        "warnings": [],
    }


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


@router.get("/price-targets")
async def get_price_targets(db_path: str = Depends(get_db_path)):
    """Return watchlist items that are within 10% of their target buy price."""
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        # Get watchlist items with a target_buy_price set
        rows = await conn.execute_fetchall(
            "SELECT ticker, target_buy_price, last_signal, last_confidence "
            "FROM watchlist WHERE target_buy_price IS NOT NULL"
        )

        results = []
        for row in rows:
            ticker = row["ticker"]
            target = row["target_buy_price"]

            # Try price_history_cache (latest close)
            price_row = await conn.execute_fetchall(
                "SELECT close FROM price_history_cache "
                "WHERE ticker = ? ORDER BY date DESC LIMIT 1",
                (ticker,),
            )
            current_price = price_row[0]["close"] if price_row else None

            # Fallback: active_positions avg_cost as proxy (last known cost)
            if current_price is None:
                pos_row = await conn.execute_fetchall(
                    "SELECT avg_cost FROM active_positions "
                    "WHERE ticker = ? AND status = 'open' LIMIT 1",
                    (ticker,),
                )
                current_price = pos_row[0]["avg_cost"] if pos_row else None

            if current_price is None:
                continue

            distance_pct = (current_price - target) / target * 100
            if distance_pct > 10:
                continue

            results.append(
                {
                    "ticker": ticker,
                    "target_buy_price": target,
                    "current_price": round(current_price, 2),
                    "distance_pct": round(distance_pct, 2),
                    "last_signal": row["last_signal"],
                    "last_confidence": row["last_confidence"],
                }
            )

        results.sort(key=lambda x: x["distance_pct"])

    return {"data": results, "warnings": []}


@router.post("/scan")
async def scan_watchlist_alerts(db_path: str = Depends(get_db_path)):
    """Manually trigger watchlist alert scan."""
    from daemon.watchlist_job import run_watchlist_scan

    result = await run_watchlist_scan(db_path)
    return {"data": result, "warnings": []}


@router.post("/analyze-all")
async def analyze_all_watchlist(db_path: str = Depends(get_db_path)):
    """Run analysis on all watchlist tickers. Returns summary results."""
    mgr = WatchlistManager(db_path)
    items = await mgr.get_watchlist()

    if not items:
        return {"data": {"results": [], "total": 0, "success_count": 0}, "warnings": ["Watchlist is empty"]}

    from engine.pipeline import AnalysisPipeline

    pipeline = AnalysisPipeline(db_path=db_path)

    results = []
    warnings = []

    for item in items:
        asset_type = resolve_asset_type(item["ticker"], item["asset_type"])
        yf_ticker = map_ticker(item["ticker"], asset_type)
        try:
            result = await pipeline.analyze_ticker(yf_ticker, asset_type)
            await mgr.update_analysis(item["ticker"], result.final_signal, result.final_confidence)
            results.append({
                "ticker": item["ticker"],
                "signal": result.final_signal.value if hasattr(result.final_signal, "value") else result.final_signal,
                "confidence": result.final_confidence,
                "raw_score": result.metrics.get("raw_score", 0) if isinstance(result.metrics, dict) else 0,
                "status": "success",
            })
        except Exception as exc:
            warnings.append(f"Analysis failed for {item['ticker']}: {exc}")
            results.append({
                "ticker": item["ticker"],
                "signal": None,
                "confidence": None,
                "raw_score": None,
                "status": "error",
                "error": str(exc),
            })

    return {
        "data": {
            "results": results,
            "total": len(items),
            "success_count": sum(1 for r in results if r["status"] == "success"),
        },
        "warnings": warnings,
    }


@router.put("/{ticker}/alerts")
async def set_alert_config(
    ticker: str,
    body: AlertConfigRequest,
    db_path: str = Depends(get_db_path),
):
    """Upsert alert configuration for a watchlist ticker."""
    mgr = WatchlistManager(db_path)
    config = await mgr.set_alert_config(
        ticker.upper(),
        alert_on_signal_change=body.alert_on_signal_change,
        min_confidence=body.min_confidence,
        alert_on_price_below=body.alert_on_price_below,
        enabled=body.enabled,
    )
    return {"data": config, "warnings": []}


@router.get("/alert-configs")
async def get_alert_configs(db_path: str = Depends(get_db_path)):
    """Return all watchlist alert configurations."""
    mgr = WatchlistManager(db_path)
    configs = await mgr.get_alert_configs()
    return {"data": configs, "warnings": []}


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
