"""CLI for running backtests and displaying results."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from backtesting.batch_runner import BatchConfig, BatchRunner
from backtesting.engine import Backtester
from backtesting.models import BacktestConfig
from db.database import DEFAULT_DB_PATH

# Auto-detect crypto tickers (case-insensitive)
_CRYPTO_TICKERS = {"BTC", "ETH", "BTC-USD", "ETH-USD"}

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

    # ---- batch subcommand ----
    batch_parser = subparsers.add_parser("batch", help="Run batch backtests across tickers and agent combos.")
    batch_parser.add_argument(
        "--tickers", required=True,
        help="Comma-separated tickers (e.g. AAPL,MSFT,BTC).",
    )
    batch_parser.add_argument(
        "--agents", default="technical",
        help=(
            "Semicolon-separated agent combos. Each combo is a comma-separated list. "
            "Example: 'technical;technical,crypto' runs two combos per ticker."
        ),
    )
    batch_parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD.")
    batch_parser.add_argument("--end", required=True, help="End date YYYY-MM-DD.")
    batch_parser.add_argument("--capital", type=float, default=100_000.0, help="Initial capital.")
    batch_parser.add_argument(
        "--frequency", default="weekly", choices=["daily", "weekly", "monthly"],
        help="Rebalance frequency (default: weekly).",
    )
    batch_parser.add_argument(
        "--position-size", type=float, default=1.0,
        help="Position size as fraction (default: 1.0 = full).",
    )
    batch_parser.add_argument(
        "--stop-loss", type=float, default=0.0,
        help="Stop loss fraction (default: 0 = disabled).",
    )
    batch_parser.add_argument(
        "--take-profit", type=float, default=0.0,
        help="Take profit fraction (default: 0 = disabled).",
    )
    batch_parser.add_argument(
        "--output-json", default=None,
        help="Path to write JSON results file.",
    )
    batch_parser.add_argument(
        "--chart", default=None,
        help="Path to write HTML comparison chart.",
    )

    # ---- optimize subcommand ----
    opt_parser = subparsers.add_parser(
        "optimize",
        help="Optimize agent weights and thresholds from backtest data.",
    )
    opt_parser.add_argument(
        "--tickers", required=True,
        help="Comma-separated tickers for training (e.g. AAPL,MSFT,SPY,BTC).",
    )
    opt_parser.add_argument("--start", required=True, help="Training start date YYYY-MM-DD.")
    opt_parser.add_argument("--end", required=True, help="Training end date YYYY-MM-DD.")
    opt_parser.add_argument(
        "--save", action="store_true",
        help="Save optimized weights to database for use with --adaptive-weights.",
    )

    return parser


def _resolve_agents(agents_str: str, asset_type: str = "stock") -> list[str]:
    if agents_str.lower() == "all":
        if asset_type in ("btc", "eth"):
            return ["CryptoAgent"]
        return ["TechnicalAgent", "FundamentalAgent", "MacroAgent"]
    mapping = {
        "technical": "TechnicalAgent",
        "fundamental": "FundamentalAgent",
        "macro": "MacroAgent",
        "crypto": "CryptoAgent",
    }
    result = []
    for part in agents_str.split(","):
        part = part.strip().lower()
        if part in mapping:
            result.append(mapping[part])
        else:
            print(f"  Warning: unknown agent '{part}', skipping.")
    if not result:
        return ["CryptoAgent"] if asset_type in ("btc", "eth") else ["TechnicalAgent"]
    return result


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
            print(f"    [!] {w}")
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
    ticker_upper = args.ticker.upper()
    asset_type = args.asset_type
    if asset_type == "stock" and ticker_upper in _CRYPTO_TICKERS:
        asset_type = "btc" if ticker_upper in ("BTC", "BTC-USD") else "eth"

    # Map bare crypto tickers to yfinance symbols
    if asset_type in ("btc", "eth"):
        _CRYPTO_YF_MAP = {"BTC": "BTC-USD", "ETH": "ETH-USD"}
        ticker_upper = _CRYPTO_YF_MAP.get(ticker_upper, ticker_upper)

    agent_names = _resolve_agents(args.agents, asset_type)
    config = BacktestConfig(
        ticker=ticker_upper,
        asset_type=asset_type,
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


def _cmd_batch(args) -> None:
    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    agent_combos = []
    for combo_str in args.agents.split(";"):
        combo_str = combo_str.strip()
        if combo_str:
            # Detect asset type from first ticker for agent resolution
            agent_names = _resolve_agents(combo_str, "stock")
            agent_combos.append(agent_names)
    if not agent_combos:
        agent_combos = [["TechnicalAgent"]]

    config = BatchConfig(
        tickers=tickers,
        agent_combos=agent_combos,
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        position_size_pct=args.position_size,
        rebalance_frequency=args.frequency,
        stop_loss_pct=args.stop_loss if args.stop_loss > 0 else None,
        take_profit_pct=args.take_profit if args.take_profit > 0 else None,
    )

    async def _run():
        def _progress(ticker: str, combo_key: str) -> None:
            print(f"  Running: {ticker} [{combo_key}]...")

        print(f"Batch backtest: {len(tickers)} tickers x {len(agent_combos)} combos")
        print(f"Period: {args.start} to {args.end}")
        print(_THIN)
        runner = BatchRunner(config)
        result = await runner.run(
            db_path=str(DEFAULT_DB_PATH),
            progress_callback=_progress,
        )
        _print_batch_report(result)

        if args.output_json:
            Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output_json).write_text(result.to_json(), encoding="utf-8")
            print(f"\nJSON results saved to {args.output_json}")

        if args.chart:
            from charts.backtest_comparison import generate_batch_summary_chart
            generate_batch_summary_chart(result, args.chart)
            print(f"Chart saved to {args.chart}")

    asyncio.run(_run())


def _print_batch_report(result) -> None:
    """Print ASCII summary table for batch results."""
    summary = result.to_summary_dict()
    if not summary:
        print("  No results to display.")
        return

    print()
    print(_SEP)
    print("  BATCH BACKTEST RESULTS")
    print(_SEP)
    print()

    # Header
    print(f"  {'Ticker':<8} {'Agents':<28} {'Return':>8} {'Ann.':>8} {'MaxDD':>8} {'Sharpe':>7} {'WinR':>6} {'Trades':>6}")
    print(f"  {'-'*8} {'-'*28} {'-'*8} {'-'*8} {'-'*8} {'-'*7} {'-'*6} {'-'*6}")

    for ticker in sorted(summary.keys()):
        combos = summary[ticker]
        for combo_key in sorted(combos.keys()):
            m = combos[combo_key]
            ret = _pct(m.get("total_return_pct"))
            ann = _pct(m.get("annualized_return_pct"))
            dd = _pct(m.get("max_drawdown_pct"))
            sharpe = _fmt(m.get("sharpe_ratio"))
            wr = m.get("win_rate")
            wr_str = f"{wr*100:.0f}%" if wr is not None else "N/A"
            trades = m.get("total_trades", 0)
            # Truncate combo_key for display
            combo_display = combo_key[:28]
            print(f"  {ticker:<8} {combo_display:<28} {ret:>8} {ann:>8} {dd:>8} {sharpe:>7} {wr_str:>6} {trades:>6}")

    print()

    if result.errors:
        print(_THIN)
        print("  ERRORS:")
        for e in result.errors:
            print(f"    ! {e}")
        print()

    print(_SEP)


def _cmd_optimize(args) -> None:
    from engine.weight_adapter import WeightAdapter

    tickers = [t.strip().upper() for t in args.tickers.split(",")]

    # Run single-agent backtests for each PIT-safe agent
    agent_combos = [["TechnicalAgent"], ["CryptoAgent"]]

    config = BatchConfig(
        tickers=tickers,
        agent_combos=agent_combos,
        start_date=args.start,
        end_date=args.end,
    )

    async def _run():
        print(f"Optimizing weights from backtest data...")
        print(f"Tickers: {', '.join(tickers)}")
        print(f"Period: {args.start} to {args.end}")
        print(f"Agent combos: {['+'.join(c) for c in agent_combos]}")
        print(_THIN)

        runner = BatchRunner(config)
        batch_result = await runner.run(db_path=str(DEFAULT_DB_PATH))

        adapter = WeightAdapter(db_path=str(DEFAULT_DB_PATH))
        weights = adapter.compute_weights_from_backtest(batch_result.results)

        # Print results
        print()
        print(_SEP)
        print("  OPTIMIZED WEIGHTS")
        print(_SEP)
        print()
        print(f"  Source: {weights.source}")
        print(f"  Sample size: {weights.sample_size}")
        print(f"  Buy threshold: {weights.buy_threshold}")
        print(f"  Sell threshold: {weights.sell_threshold}")
        print()

        for at, agent_weights in sorted(weights.weights.items()):
            print(f"  [{at}]")
            for agent_name, w in sorted(agent_weights.items(), key=lambda x: -x[1]):
                print(f"    {agent_name:<25} {w:.4f}  ({w*100:.1f}%)")
            print()

        if batch_result.errors:
            print(_THIN)
            print("  WARNINGS:")
            for e in batch_result.errors:
                print(f"    ! {e}")
            print()

        if args.save:
            await adapter.save_weights(weights)
            print(f"  Weights saved to database.")
            print(f"  Use '--adaptive-weights' flag with analyze_cli to apply.")

        print(_SEP)

    asyncio.run(_run())


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "run":
        _cmd_run(args)
    elif args.command == "batch":
        _cmd_batch(args)
    elif args.command == "optimize":
        _cmd_optimize(args)


if __name__ == "__main__":
    main()
