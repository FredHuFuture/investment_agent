"""
Investment Agent -- Feature Demo Script
========================================
Run: python demo.py

Demonstrates all major features using a temporary database.
Your existing data/investment_agent.db is NOT touched.

Requires network access (fetches live data from Yahoo Finance).
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

# Windows event loop fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from db.database import init_db
from portfolio.manager import PortfolioManager
from engine.pipeline import AnalysisPipeline
from cli.report import format_analysis_report
from monitoring.monitor import PortfolioMonitor
from tracking.store import SignalStore
from tracking.tracker import SignalTracker
from backtesting.engine import Backtester
from backtesting.models import BacktestConfig

SEP = "=" * 64
THIN = "-" * 64
PAUSE = 1.5  # seconds between sections


def banner(title: str) -> None:
    print(f"\n\n{SEP}")
    print(f"  DEMO: {title}")
    print(SEP)
    time.sleep(PAUSE)


async def main() -> None:
    # Use a temp db so we don't touch real data
    tmp = tempfile.mkdtemp(prefix="invest_demo_")
    db_path = os.path.join(tmp, "demo.db")
    print(f"Demo database: {db_path}")
    print("(Your real data/investment_agent.db is untouched)\n")

    await init_db(db_path)

    # ===== 1. PORTFOLIO SETUP =====
    banner("1/7 -- Portfolio Setup")

    manager = PortfolioManager(db_path)
    await manager.set_cash(200_000)
    await manager.add_position(
        ticker="AAPL", asset_type="stock", quantity=100,
        avg_cost=185.50, entry_date="2026-01-15",
        sector="Technology", industry="Consumer Electronics",
    )
    await manager.add_position(
        ticker="MSFT", asset_type="stock", quantity=50,
        avg_cost=410.00, entry_date="2026-02-01",
        sector="Technology", industry="Software",
    )
    await manager.add_position(
        ticker="GOOGL", asset_type="stock", quantity=30,
        avg_cost=175.00, entry_date="2026-02-10",
        sector="Technology", industry="Internet Services",
    )

    portfolio = await manager.load_portfolio()

    total_cost_basis = sum(p.cost_basis for p in portfolio.positions)
    print(f"  Positions: {len(portfolio.positions)}")
    for p in portfolio.positions:
        print(f"    {p.ticker:<8} {p.quantity:>6.0f} shares @ ${p.avg_cost:>8,.2f}  = ${p.cost_basis:>10,.2f}")
    print(f"  Cash:      ${portfolio.cash:>10,.2f}")
    print(f"  Total:     ${portfolio.total_value:>10,.2f}")
    print(f"  Stock:     {portfolio.stock_exposure_pct*100:.1f}%")
    print(f"  Cash:      {portfolio.cash_pct*100:.1f}%")

    # ===== 2. SINGLE TICKER ANALYSIS (Standard) =====
    banner("2/7 -- Analysis: AAPL (Standard Mode)")

    pipeline = AnalysisPipeline()
    result = await pipeline.analyze_ticker("AAPL", "stock")
    print(format_analysis_report(result))

    # ===== 3. SINGLE TICKER ANALYSIS (Detail) =====
    banner("3/7 -- Analysis: AAPL (Detail Mode)")

    print(format_analysis_report(result, detail=True))

    # ===== 4. SECOND ANALYSIS =====
    banner("4/7 -- Analysis: MSFT")

    result_msft = await pipeline.analyze_ticker("MSFT", "stock")
    print(format_analysis_report(result_msft))

    # ===== 5. MONITORING CHECK =====
    banner("5/7 -- Position Monitoring Check")

    monitor = PortfolioMonitor(db_path)
    check_result = await monitor.run_check()

    checked = check_result.get("checked_positions", 0)
    alerts = check_result.get("alerts", [])
    warnings = check_result.get("warnings", [])
    print(f"  Positions checked: {checked}")
    print(f"  Alerts generated:  {len(alerts)}")
    if alerts:
        for alert in alerts:
            sev = alert.get("severity", "INFO") if isinstance(alert, dict) else getattr(alert, "severity", "INFO")
            msg = alert.get("message", str(alert)) if isinstance(alert, dict) else getattr(alert, "message", str(alert))
            print(f"    [{sev}] {msg}")
    else:
        print("    (no alerts -- all positions within expected ranges)")
    if warnings:
        for w in warnings:
            print(f"    Warning: {w}")
    print(f"  Snapshot saved: {check_result.get('snapshot_saved', False)}")

    # ===== 6. SIGNAL TRACKING =====
    banner("6/7 -- Signal Tracking")

    store = SignalStore(db_path)
    # Save the two signals we generated
    await store.save_signal(result, thesis_id=None)
    await store.save_signal(result_msft, thesis_id=None)

    tracker = SignalTracker(store)
    stats = await tracker.compute_accuracy_stats(lookback=50)
    print(f"  Total signals saved: {stats.get('total_signals', 0)}")
    print(f"  Resolved:            {stats.get('resolved', 0)}")
    print(f"  Unresolved (OPEN):   {stats.get('total_signals', 0) - stats.get('resolved', 0)}")
    print("  (Signals start as OPEN. Resolve with actual outcomes to compute win rate.)")

    calib = await tracker.compute_calibration_data(lookback=50)
    print(f"  Calibration buckets: {len(calib)}")
    for bucket in calib:
        conf = bucket.get("confidence_bucket", "?")
        count = bucket.get("count", 0)
        print(f"    [{conf}] -- {count} signals")

    # ===== 7. BACKTESTING =====
    banner("7/7 -- Backtesting: AAPL (2024-2025)")

    config = BacktestConfig(
        ticker="AAPL",
        asset_type="stock",
        start_date="2024-01-01",
        end_date="2025-12-31",
        initial_capital=100_000,
        rebalance_frequency="weekly",
        agents=["TechnicalAgent"],
        position_size_pct=0.10,
        stop_loss_pct=0.10,
        take_profit_pct=0.20,
    )

    print(f"  Ticker:     {config.ticker}")
    print(f"  Period:     {config.start_date} to {config.end_date}")
    print(f"  Agent:      TechnicalAgent only (PIT-safe)")
    print(f"  Capital:    ${config.initial_capital:,.0f}")
    print(f"  Rebalance:  {config.rebalance_frequency}")
    print()
    print("  Running backtest (fetching price history)...")
    print()

    backtester = Backtester(config)
    bt_result = await backtester.run(db_path=db_path)
    metrics = bt_result.metrics

    print(f"  Total Return:      {_pct(metrics.get('total_return_pct'))}")
    print(f"  Sharpe Ratio:      {_fmt(metrics.get('sharpe_ratio'))}")
    print(f"  Sortino Ratio:     {_fmt(metrics.get('sortino_ratio'))}")
    print(f"  Max Drawdown:      {_pct(metrics.get('max_drawdown_pct'))}")
    print(f"  Win Rate:          {_pct_raw(metrics.get('win_rate'))}")
    print(f"  Profit Factor:     {_fmt(metrics.get('profit_factor'))}")
    print(f"  Total Trades:      {metrics.get('total_trades', 0)}")

    if bt_result.warnings:
        print()
        for w in bt_result.warnings:
            print(f"  Warning: {w}")

    # ===== DONE =====
    print(f"\n\n{SEP}")
    print("  DEMO COMPLETE")
    print(SEP)
    print()
    print("  Features demonstrated:")
    print("    1. Portfolio setup (add positions, set cash)")
    print("    2. Single-ticker analysis (standard mode)")
    print("    3. Single-ticker analysis (detail mode -- full metrics)")
    print("    4. Multi-ticker analysis")
    print("    5. Position monitoring (health check + alerts)")
    print("    6. Signal tracking (history, calibration)")
    print("    7. Backtesting (walk-forward, technical agent)")
    print()
    print("  Not shown in this script (require browser / long-running):")
    print("    - Charts: python -m cli.charts_cli analysis AAPL")
    print("    - Daemon: python -m cli.daemon_cli start")
    print()
    print(f"  Demo database (can be deleted): {db_path}")
    print()


def _pct(val) -> str:
    if val is None:
        return "N/A"
    return f"{'+' if val >= 0 else ''}{val:.1f}%"


def _pct_raw(val) -> str:
    if val is None:
        return "N/A"
    return f"{val*100:.1f}%"


def _fmt(val) -> str:
    if val is None:
        return "N/A"
    if val == float("inf"):
        return "inf (no losses)"
    return f"{val:.2f}"


if __name__ == "__main__":
    asyncio.run(main())
