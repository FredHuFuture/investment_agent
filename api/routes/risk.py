"""API routes for portfolio risk stress testing."""
from __future__ import annotations

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
