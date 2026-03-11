"""Analysis endpoint."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.deps import get_db_path, map_ticker, resolve_asset_type
from engine.pipeline import AnalysisPipeline

router = APIRouter()


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
