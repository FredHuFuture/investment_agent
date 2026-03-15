"""API routes for portfolio performance analytics."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.deps import get_db_path
from engine.analytics import PortfolioAnalytics

router = APIRouter()


@router.get("/value-history")
async def value_history(
    days: int = Query(90, ge=1, le=365),
    db_path: str = Depends(get_db_path),
):
    """Portfolio value over time for charting."""
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_value_history(days=days)
    return {"data": data, "warnings": []}


@router.get("/performance")
async def performance_summary(db_path: str = Depends(get_db_path)):
    """Overall performance metrics (win rate, avg P&L, etc.)."""
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_performance_summary()
    return {"data": data, "warnings": []}


@router.get("/monthly-returns")
async def monthly_returns(db_path: str = Depends(get_db_path)):
    """Monthly P&L breakdown."""
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_monthly_returns()
    return {"data": data, "warnings": []}


@router.get("/top-performers")
async def top_performers(
    limit: int = Query(5, ge=1, le=50),
    db_path: str = Depends(get_db_path),
):
    """Best and worst trades by return percentage."""
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_top_performers(limit=limit)
    return {"data": data, "warnings": []}
