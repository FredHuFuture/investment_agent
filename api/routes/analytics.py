"""API routes for portfolio performance analytics."""
from __future__ import annotations

import aiosqlite
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


@router.get("/risk")
async def portfolio_risk(
    days: int = Query(90, ge=7, le=365),
    db_path: str = Depends(get_db_path),
):
    """Portfolio risk metrics (volatility, Sharpe, drawdown, VaR)."""
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_portfolio_risk(days=days)
    return {"data": data, "warnings": []}


@router.get("/benchmark")
async def benchmark_comparison(
    days: int = Query(90, ge=7, le=365),
    benchmark: str = Query("SPY"),
    db_path: str = Depends(get_db_path),
):
    """Compare portfolio performance against a benchmark (e.g., SPY)."""
    from data_providers.factory import get_provider

    analytics = PortfolioAnalytics(db_path)
    provider = get_provider()
    data = await analytics.get_benchmark_comparison(
        provider=provider,
        benchmark_ticker=benchmark.upper(),
        days=days,
    )
    return {"data": data, "warnings": []}


@router.get("/correlations")
async def portfolio_correlations(
    lookback_days: int = Query(90, ge=30, le=365),
    db_path: str = Depends(get_db_path),
):
    """Pairwise correlation matrix for portfolio holdings."""
    from engine.correlation import calculate_portfolio_correlations
    from data_providers.factory import get_provider

    # Get active tickers from DB
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        rows = await (
            await conn.execute(
                "SELECT DISTINCT ticker FROM active_positions WHERE status = 'active'"
            )
        ).fetchall()

    tickers = [row["ticker"] for row in rows]
    if len(tickers) < 2:
        return {
            "data": {
                "correlation_matrix": {},
                "avg_correlation": 0.0,
                "high_correlation_pairs": [],
                "concentration_risk": "LOW",
                "tickers": tickers,
                "warnings": ["Need at least 2 positions for correlation analysis."],
            },
            "warnings": [],
        }

    provider = get_provider()
    result = await calculate_portfolio_correlations(tickers, provider, lookback_days)

    # Convert tuple keys to string keys for JSON serialization
    matrix = {}
    for key, val in result.get("correlation_matrix", {}).items():
        if isinstance(key, tuple):
            matrix[f"{key[0]}:{key[1]}"] = val
        else:
            matrix[str(key)] = val
    result["correlation_matrix"] = matrix

    # Convert tuple high_correlation_pairs to lists for JSON
    result["high_correlation_pairs"] = [
        list(pair) for pair in result.get("high_correlation_pairs", [])
    ]

    result["tickers"] = tickers

    return {"data": result, "warnings": result.pop("warnings", [])}
