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


@router.get("/health-score")
async def health_score(db_path: str = Depends(get_db_path)):
    """Compute a portfolio health score (0-100) from four sub-scores."""
    pm = PortfolioManager(db_path)
    portfolio = await pm.load_portfolio()

    open_positions = [p for p in portfolio.positions if p.status == "open"]
    n_positions = len(open_positions)

    # -- 1. Diversification score (25%) --
    if n_positions == 0:
        diversification_score = 0.0
        div_detail = "No open positions"
    else:
        sectors = {p.sector or "Unknown" for p in open_positions}
        n_sectors = len(sectors)

        # Position count score: 1 pos = 20, 3 pos = 50, 5+ pos = 80, 10+ = 100
        pos_score = min(n_positions * 10, 100)

        # Sector diversity: 1 sector = 30, 3 = 60, 5+ = 100
        sector_score = min(n_sectors * 20, 100)

        # Concentration: lower max concentration = higher score
        total_value = portfolio.total_value
        if total_value > 0:
            max_pct = max(
                (
                    (p.market_value if p.current_price > 0 else p.cost_basis) / total_value
                    for p in open_positions
                ),
                default=0,
            )
        else:
            max_pct = 1.0
        # 100% concentration = 0 score, 20% = 80, 10% = 90
        conc_score = max(0, (1 - max_pct) * 100)

        diversification_score = (pos_score + sector_score + conc_score) / 3
        div_detail = f"{n_positions} positions across {n_sectors} sectors"

    # -- 2. Risk score (25%) -- inverse of risk metrics
    risk_score = 50.0  # default neutral
    risk_detail = "No analytics data available"
    async with aiosqlite.connect(db_path) as conn:
        rows = await (
            await conn.execute(
                "SELECT date, total_value FROM value_snapshots ORDER BY date DESC LIMIT 91"
            )
        ).fetchall()

    if len(rows) >= 10:
        values = [r[1] for r in reversed(rows)]
        daily_returns_list = [
            (values[i] - values[i - 1]) / values[i - 1]
            for i in range(1, len(values))
            if values[i - 1] > 0
        ]
        if daily_returns_list:
            import statistics

            vol = statistics.stdev(daily_returns_list)
            ann_vol = vol * (252 ** 0.5)
            # Lower volatility = higher score.  ann_vol 0 = 100, 0.5+ = 0
            vol_score = max(0, 100 - ann_vol * 200)

            # Max drawdown
            peak = values[0]
            max_dd = 0.0
            for v in values:
                if v > peak:
                    peak = v
                dd = (v - peak) / peak if peak > 0 else 0
                if dd < max_dd:
                    max_dd = dd
            # -0% dd = 100, -20% dd = 0
            dd_score = max(0, 100 + max_dd * 500)

            # VaR 95 (simple historical)
            sorted_returns = sorted(daily_returns_list)
            idx = max(0, int(len(sorted_returns) * 0.05) - 1)
            var_95 = abs(sorted_returns[idx])
            # 0% var = 100, 5% var = 0
            var_score = max(0, 100 - var_95 * 2000)

            risk_score = (vol_score + dd_score + var_score) / 3
            risk_detail = f"Volatility: {ann_vol:.1%}, Max DD: {max_dd:.1%}"

    # -- 3. Thesis adherence score (25%) --
    if n_positions == 0:
        thesis_score = 0.0
        thesis_detail = "No open positions"
    else:
        with_thesis = 0
        on_target = 0
        for p in open_positions:
            has_thesis = p.thesis_text is not None or p.original_analysis_id is not None
            if has_thesis:
                with_thesis += 1
                # Check if within expected hold days and return drift
                within_hold = True
                within_return = True
                if p.expected_hold_days is not None and p.holding_days > p.expected_hold_days * 1.5:
                    within_hold = False
                if p.expected_return_pct is not None and p.cost_basis > 0:
                    actual_return = p.unrealized_pnl_pct
                    drift = abs(actual_return - p.expected_return_pct)
                    # If drift is more than 50% of expected return, not on target
                    if drift > abs(p.expected_return_pct) * 0.5 + 0.1:
                        within_return = False
                if within_hold and within_return:
                    on_target += 1

        # Score: % with thesis (50%) + % on target (50%)
        thesis_pct = (with_thesis / n_positions) * 100
        target_pct = (on_target / n_positions) * 100 if n_positions > 0 else 0
        thesis_score = (thesis_pct + target_pct) / 2
        thesis_detail = f"{with_thesis} of {n_positions} positions have thesis"

    # -- 4. Momentum score (25%) --
    if n_positions == 0:
        momentum_score = 0.0
        momentum_detail = "No open positions"
    else:
        pnl_pcts = [p.unrealized_pnl_pct for p in open_positions]
        in_profit = sum(1 for x in pnl_pcts if x > 0)

        # Base: percentage in profit (0-100)
        profit_pct_score = (in_profit / n_positions) * 100

        # Average P&L normalized: -10% avg = 0, 0% = 50, +10% avg = 100
        avg_pnl = sum(pnl_pcts) / n_positions
        avg_score = max(0, min(100, 50 + avg_pnl * 500))

        momentum_score = (profit_pct_score + avg_score) / 2
        momentum_detail = (
            f"{'Most' if in_profit > n_positions / 2 else 'Few'} positions in profit"
        )

    # -- Overall score --
    overall = (
        diversification_score * 0.25
        + risk_score * 0.25
        + thesis_score * 0.25
        + momentum_score * 0.25
    )

    return {
        "data": {
            "overall_score": round(overall, 1),
            "diversification_score": round(diversification_score, 1),
            "risk_score": round(risk_score, 1),
            "thesis_adherence_score": round(thesis_score, 1),
            "momentum_score": round(momentum_score, 1),
            "details": {
                "diversification": div_detail,
                "risk": risk_detail,
                "thesis_adherence": thesis_detail,
                "momentum": momentum_detail,
            },
        },
        "warnings": [],
    }
