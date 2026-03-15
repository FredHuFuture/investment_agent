"""API routes for portfolio risk stress testing."""
from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends

from api.deps import get_db_path
from portfolio.manager import PortfolioManager
from engine.stress_test import StressTestEngine

router = APIRouter()


@router.get("/stress-test")
async def stress_test(db_path: str = Depends(get_db_path)):
    """Run predefined stress-test scenarios against the current portfolio."""
    pm = PortfolioManager(db_path)
    portfolio = await pm.load_portfolio()

    positions = [
        {
            "ticker": p.ticker,
            "asset_type": p.asset_type,
            "market_value": p.market_value,
            "sector": p.sector,
        }
        for p in portfolio.positions
        if p.status == "open"
    ]

    engine = StressTestEngine()
    scenarios = engine.run_scenarios(positions, portfolio.cash)
    return {"data": scenarios, "warnings": []}


@router.get("/monte-carlo")
async def monte_carlo(
    days: int = 90,
    simulations: int = 1000,
    horizon: int = 30,
    db_path: str = Depends(get_db_path),
):
    """Run a Monte Carlo simulation using historical portfolio value snapshots."""
    # Fetch recent value snapshots
    async with aiosqlite.connect(db_path) as conn:
        rows = await (
            await conn.execute(
                "SELECT date, total_value FROM value_snapshots ORDER BY date DESC LIMIT ?",
                (days + 1,),
            )
        ).fetchall()

    if len(rows) < 10:
        return {
            "data": {"error": "Insufficient data (need at least 10 snapshots)"},
            "warnings": ["Need more history"],
        }

    # Compute daily returns from chronological values
    values = [r[1] for r in reversed(rows)]
    daily_returns = [
        (values[i] - values[i - 1]) / values[i - 1]
        for i in range(1, len(values))
        if values[i - 1] > 0
    ]

    if len(daily_returns) < 10:
        return {
            "data": {"error": "Insufficient non-zero data to compute returns"},
            "warnings": ["Need more history with non-zero values"],
        }

    current_value = values[-1]

    from engine.monte_carlo import MonteCarloSimulator

    sim = MonteCarloSimulator(daily_returns)
    result = sim.simulate(current_value, horizon, simulations)
    return {"data": result, "warnings": []}
