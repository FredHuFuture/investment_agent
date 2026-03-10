"""CLI for running backtests and displaying results."""
from __future__ import annotations

import argparse
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from backtesting.engine import Backtester
from backtesting.models import BacktestConfig
from db.database import DEFAULT_DB_PATH

_SEP = "=" * 64
_THIN = "-" * 64


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backtest",
        description="Run backtests against historical price data.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Execute a backtest.")
    run_parser.add_argument("ticker", help="Ticker symbol (e.g. AAPL, BTC-USD).")
    run_parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD.")
    run_parser.add_argument("--end", required=True, help="End date YYYY-MM-DD.")
    run_parser.add_argument("--asset-type", default="stock", choices=["stock", "btc", "eth"])
    run_parser.add_argument("--capital", type=float, default=100_000.0, help="Initial capital.")
    run_parser.add_argument(
        "--agents",
        default="technical",
        help="Comma-separated agents: technical,macro,fundamental,all (default: technical).",
    )
    run_parser.add_argument(
        "--frequency",
        default="weekly",
        choices=["daily", "weekly", "monthly"],
        help="Rebalance frequency (default: weekly).",
    )
    run_parser.add_argument(
        "--position-size", type=float, default=0.10, help="Position size as fraction (default: 0.10)."
    )
    run_parser.add_argument(
        "--stop-loss", type=float, default=0.10, help="Stop loss fraction (default: 0.10, 0 to disable)."
    )
    run_parser.add_argument(
        "--take-profit", type=float, default=0.20, help="Take profit fraction (default: 0.20, 0 to disable)."
    )

    return parser


def _resolve_agents(agents_str: str) -> list[str]:
    if agents_str.lower() == "all":
        return ["TechnicalAgent", "FundamentalAgent", "MacroAgent"]
    mapping = {
        "technical": "TechnicalAgent",
        "fundamental": "FundamentalAgent",
        "macro": "MacroAgent",
    }
    result = []
    for part in agents_str.split(","):
        part = part.strip().lower()
        if part in mapping:
            result.append(mapping[part])
        else:
            print(f"  Warning: unknown agent '{part}', skipping.")
    return result or ["TechnicalAgent"]


def _print_report(result) -> None:
    cfg = result.config
    metrics = result.metrics
    trades = result.trades
    closed = [t for t in trades if t.pnl is not None]

    agent_str = ", ".join(cfg.agents or ["TechnicalAgent"])
    print(_SEP)
    print(f"  BACKTEST REPORT: {cfg.ticker}")
    print(f"  {cfg.start_date} to {cfg.end_date}  ({agent_str})")
    print(_SEP)
    print()
    print("  PERFORMANCE")
    print(f"  Total Return:       {_pct(metrics.get('total_return_pct'))}")
    print(f"  Annualized Return:  {_pct(metrics.get('annualized_return_pct'))}")
    print(f"  Sharpe Ratio:       {_fmt(metrics.get('sharpe_ratio'))}")
    print(f"  Sortino Ratio:      {_fmt(metrics.get('sortino_ratio'))}")
    print(f"  Max Drawdown:       {_pct(metrics.get('max_drawdown_pct'))}")
    print(f"  Calmar Ratio:       {_fmt(metrics.get('calmar_ratio'))}")
    print()
    print(_THIN)
    print("  TRADE STATISTICS")
    print(_THIN)
    n = metrics.get("total_trades", 0)
    wr = metrics.get("win_rate")
    wins = round(wr * n) if wr is not None and n else 0
    losses = n - wins
    print(f"  Total Trades:       {n}")
    if wr is not None:
        print(f"  Win Rate:           {wr*100:.1f}% ({wins}W / {losses}L)")
    else:
        print("  Win Rate:           N/A")
    pf = metrics.get("profit_factor")
    if pf == float("inf"):
        print("  Profit Factor:      ∞ (no losses)")
    elif pf is not None:
        print(f"  Profit Factor:      {pf:.2f}x")
    else:
        print("  Profit Factor:      N/A")
    print(f"  Avg Win:            {_pct(metrics.get('avg_win_pct'))}")
    print(f"  Avg Loss:           {_pct(metrics.get('avg_loss_pct'))}")
    hold = metrics.get("avg_holding_days")
    print(f"  Avg Holding:        {f'{hold:.0f} days' if hold is not None else 'N/A'}")
    print()

    if closed:
        print(_THIN)
        print("  TRADE LOG (last 5)")
        print(_THIN)
        for t in closed[-5:]:
            ep = f"${t.entry_price:.2f}" if t.entry_price else "-"
            xp = f"${t.exit_price:.2f}" if t.exit_price else "-"
            rp = f"{t.pnl_pct*100:+.1f}%" if t.pnl_pct is not None else "-"
            print(f"  {t.entry_date}  {t.signal:<4}  {ep} -> {t.exit_date}  {xp}  {rp:<8}  {t.exit_reason or '-'}")
        print()

    if result.warnings:
        print(_SEP)
        print("  WARNINGS:")
        for w in result.warnings:
            print(f"    ⚠ {w}")
        print()

    print(_SEP)


def _pct(val) -> str:
    if val is None:
        return "N/A"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.1f}%"


def _fmt(val) -> str:
    if val is None:
        return "N/A"
    return f"{val:.2f}"


def _cmd_run(args) -> None:
    agent_names = _resolve_agents(args.agents)
    config = BacktestConfig(
        ticker=args.ticker.upper(),
        asset_type=args.asset_type,
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        rebalance_frequency=args.frequency,
        agents=agent_names,
        position_size_pct=args.position_size,
        stop_loss_pct=args.stop_loss if args.stop_loss > 0 else None,
        take_profit_pct=args.take_profit if args.take_profit > 0 else None,
    )

    async def _run():
        print(f"Fetching data and running backtest for {config.ticker}...")
        backtester = Backtester(config)
        result = await backtester.run(db_path=str(DEFAULT_DB_PATH))
        _print_report(result)

    asyncio.run(_run())


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "run":
        _cmd_run(args)


if __name__ == "__main__":
    main()
