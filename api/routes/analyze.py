"""Analysis endpoint."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.deps import get_db_path, map_ticker, resolve_asset_type
from data_providers.factory import get_provider
from engine.pipeline import AnalysisPipeline
from engine.aggregator import SignalAggregator

router = APIRouter()


@router.get("/{ticker}/price-history")
async def get_price_history(
    ticker: str,
    asset_type: Literal["stock", "btc", "eth"] = Query("stock"),
    period: str = Query("1y"),
):
    """Fetch price history for chart display."""
    asset_type = resolve_asset_type(ticker, asset_type)
    yf_ticker = map_ticker(ticker, asset_type)

    provider = get_provider(asset_type)
    try:
        df = await provider.get_price_history(yf_ticker, period=period)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {"code": "UPSTREAM_ERROR", "message": str(exc), "detail": None}
            },
        )

    # Convert to OHLCV JSON: [{date, open, high, low, close, volume}, ...]
    points = []
    for idx, row in df.iterrows():
        points.append({
            "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]) if "Volume" in row else 0,
        })
    return {"data": points, "warnings": []}


@router.get("/{ticker}")
async def analyze_ticker(
    ticker: str,
    asset_type: Literal["stock", "btc", "eth"] = Query("stock"),
    adaptive_weights: bool = Query(False),
    db_path: str = Depends(get_db_path),
):
    """Run multi-agent analysis for a single ticker."""
    asset_type = resolve_asset_type(ticker, asset_type)
    yf_ticker = map_ticker(ticker, asset_type)

    pipeline = AnalysisPipeline(db_path=db_path, use_adaptive_weights=adaptive_weights)
    try:
        result = await pipeline.analyze_ticker(yf_ticker, asset_type)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {"code": "UPSTREAM_ERROR", "message": str(exc), "detail": None}
            },
        )
    return {"data": result.to_dict(), "warnings": result.warnings}


class CustomWeightsRequest(BaseModel):
    ticker: str
    asset_type: str = "stock"
    weights: dict[str, float]


@router.post("/{ticker}")
async def analyze_ticker_custom(
    ticker: str,
    body: CustomWeightsRequest,
    db_path: str = Depends(get_db_path),
):
    """Run analysis with user-specified agent weights."""
    asset_type = resolve_asset_type(ticker, body.asset_type)
    yf_ticker = map_ticker(ticker, asset_type)

    pipeline = AnalysisPipeline(db_path=db_path, use_adaptive_weights=False)

    custom_weights = dict(SignalAggregator.DEFAULT_WEIGHTS)
    custom_weights[asset_type] = dict(body.weights)

    try:
        result = await pipeline.analyze_ticker_custom(yf_ticker, asset_type, custom_weights)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {"code": "UPSTREAM_ERROR", "message": str(exc), "detail": None}
            },
        )
    return {"data": result.to_dict(), "warnings": result.warnings}
