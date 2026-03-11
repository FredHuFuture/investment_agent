"""Backtesting endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.deps import get_db_path, resolve_asset_type
from api.models import BacktestRequest, BatchBacktestRequest
from backtesting.batch_runner import BatchConfig, BatchRunner
from backtesting.engine import Backtester
from backtesting.models import BacktestConfig

router = APIRouter()


@router.post("")
async def run_backtest(body: BacktestRequest, db_path: str = Depends(get_db_path)):
    """Run a single walk-forward backtest."""
    asset_type = resolve_asset_type(body.ticker, body.asset_type)
    config = BacktestConfig(
        ticker=body.ticker.upper(),
        start_date=body.start_date,
        end_date=body.end_date,
        asset_type=asset_type,
        initial_capital=body.initial_capital,
        rebalance_frequency=body.rebalance_frequency,
        agents=body.agents,
        position_size_pct=body.position_size_pct,
        stop_loss_pct=body.stop_loss_pct,
        take_profit_pct=body.take_profit_pct,
    )
    try:
        backtester = Backtester(config)
        result = await backtester.run(db_path=db_path)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {"code": "UPSTREAM_ERROR", "message": str(exc), "detail": None}
            },
        )
    trades_list = [
        {
            "entry_date": t.entry_date,
            "exit_date": t.exit_date,
            "signal": t.signal,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "pnl_pct": t.pnl_pct,
            "exit_reason": t.exit_reason,
            "holding_days": t.holding_days,
        }
        for t in result.trades
    ]
    return {
        "data": {
            "metrics": result.metrics,
            "trades": trades_list,
            "trades_count": len(result.trades),
            "equity_curve": result.equity_curve,
        },
        "warnings": result.warnings,
    }


@router.post("/batch")
async def run_batch_backtest(body: BatchBacktestRequest, db_path: str = Depends(get_db_path)):
    """Run batch backtests across tickers x agent combos."""
    config = BatchConfig(
        tickers=[t.upper() for t in body.tickers],
        agent_combos=body.agent_combos,
        start_date=body.start_date,
        end_date=body.end_date,
        initial_capital=body.initial_capital,
        position_size_pct=body.position_size_pct,
        rebalance_frequency=body.rebalance_frequency,
        stop_loss_pct=body.stop_loss_pct,
        take_profit_pct=body.take_profit_pct,
    )
    try:
        runner = BatchRunner(config)
        result = await runner.run(db_path=db_path)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {"code": "UPSTREAM_ERROR", "message": str(exc), "detail": None}
            },
        )
    return {
        "data": result.to_summary_dict(),
        "warnings": [],
        "errors": result.errors,
    }
