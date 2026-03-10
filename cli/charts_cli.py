"""CLI for generating interactive HTML charts from analysis and portfolio data."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pandas_ta as ta

from charts.analysis_charts import create_agent_breakdown_chart, create_price_chart
from charts.portfolio_charts import create_allocation_chart, create_sector_chart
from charts.tracking_charts import create_calibration_chart, create_drift_scatter
from data_providers.factory import get_provider
from db.database import DEFAULT_DB_PATH
from engine.drift_analyzer import DriftAnalyzer
from engine.pipeline import AnalysisPipeline
from portfolio.manager import PortfolioManager
from tracking.store import SignalStore
from tracking.tracker import SignalTracker

DEFAULT_OUTPUT_DIR = "data/charts"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="charts",
        description="Generate interactive HTML charts.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Save chart HTML without opening browser.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for HTML files (default: {DEFAULT_OUTPUT_DIR}).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    analysis_parser = subparsers.add_parser(
        "analysis", help="Run fresh analysis and show price + agent charts."
    )
    analysis_parser.add_argument("ticker", help="Ticker symbol (e.g. AAPL, BTC-USD).")
    analysis_parser.add_argument(
        "--asset-type", default="stock", choices=["stock", "btc", "eth"],
        help="Asset type (default: stock).",
    )

    subparsers.add_parser("portfolio", help="Portfolio allocation and sector charts.")

    calibration_parser = subparsers.add_parser(
        "calibration", help="Signal confidence calibration chart."
    )
    calibration_parser.add_argument(
        "--lookback", type=int, default=100, help="Number of signals to look back (default: 100)."
    )

    subparsers.add_parser("drift", help="Expected vs actual return scatter.")

    return parser


def _save_and_open(fig, name: str, output_dir: str, no_open: bool) -> str:
    """Write figure to HTML file and optionally open in browser. Returns file path."""
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{ts}.html"
    filepath = os.path.join(output_dir, filename)
    fig.write_html(filepath, include_plotlyjs=True)
    print(f"  Saved: {filepath}")
    if not no_open:
        webbrowser.open(f"file://{os.path.abspath(filepath)}")
    return filepath


def _cmd_analysis(ticker: str, asset_type: str, output_dir: str, no_open: bool) -> None:
    async def _run() -> None:
        print(f"Running analysis for {ticker} ({asset_type})...")

        pipeline = AnalysisPipeline()
        signal = await pipeline.analyze_ticker(ticker, asset_type)

        provider = get_provider(asset_type)
        ohlcv = await provider.get_price_history(ticker, period="1y")

        # Compute indicators
        close = ohlcv["Close"]
        high = ohlcv["High"]
        low = ohlcv["Low"]

        sma_20 = ta.sma(close, length=20)
        sma_50 = ta.sma(close, length=50)
        sma_200 = ta.sma(close, length=200)
        rsi_14 = ta.rsi(close, length=14)
        bbands = ta.bbands(close, length=20, std=2.0)

        bb_upper = None
        bb_lower = None
        if bbands is not None and not bbands.empty:
            bb_cols = [c for c in bbands.columns if "BBU" in c or "BBL" in c]
            upper_cols = [c for c in bb_cols if "BBU" in c]
            lower_cols = [c for c in bb_cols if "BBL" in c]
            if upper_cols:
                bb_upper = bbands[upper_cols[0]]
            if lower_cols:
                bb_lower = bbands[lower_cols[0]]

        indicators = {
            "sma_20": sma_20,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "rsi_14": rsi_14,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
        }

        price_fig = create_price_chart(ohlcv, ticker, indicators)
        _save_and_open(price_fig, f"price_{ticker}", output_dir, no_open)

        agent_fig = create_agent_breakdown_chart(signal.agent_signals)
        _save_and_open(agent_fig, f"agents_{ticker}", output_dir, no_open)

        print(f"\nSignal: {signal.final_signal.value}  Confidence: {signal.final_confidence:.0f}%")
        if signal.warnings:
            for w in signal.warnings:
                print(f"  ⚠ {w}")

    asyncio.run(_run())


def _cmd_portfolio(output_dir: str, no_open: bool) -> None:
    async def _run() -> None:
        db_path = str(DEFAULT_DB_PATH)
        manager = PortfolioManager(db_path)
        portfolio = await manager.load_portfolio()

        alloc_fig = create_allocation_chart(portfolio)
        _save_and_open(alloc_fig, "portfolio_allocation", output_dir, no_open)

        sector_fig = create_sector_chart(portfolio)
        _save_and_open(sector_fig, "portfolio_sectors", output_dir, no_open)

    asyncio.run(_run())


def _cmd_calibration(lookback: int, output_dir: str, no_open: bool) -> None:
    async def _run() -> None:
        db_path = str(DEFAULT_DB_PATH)
        store = SignalStore(db_path)
        tracker = SignalTracker(store)
        data = await tracker.compute_calibration_data(lookback=lookback)
        fig = create_calibration_chart(data)
        _save_and_open(fig, "calibration", output_dir, no_open)

    asyncio.run(_run())


def _cmd_drift(output_dir: str, no_open: bool) -> None:
    async def _run() -> None:
        db_path = str(DEFAULT_DB_PATH)
        analyzer = DriftAnalyzer(db_path)

        # Collect drift summaries for all theses
        import aiosqlite
        drift_data: list[dict] = []
        try:
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                rows = await (
                    await conn.execute(
                        """
                        SELECT pt.id, pt.ticker, pt.expected_return_pct,
                               sh.outcome, sh.outcome_return_pct
                        FROM positions_thesis pt
                        LEFT JOIN signal_history sh ON sh.thesis_id = pt.id
                        WHERE sh.outcome IN ('WIN', 'LOSS')
                        """
                    )
                ).fetchall()
                for row in rows:
                    drift_data.append({
                        "ticker": row["ticker"],
                        "expected_return_pct": row["expected_return_pct"],
                        "actual_return_pct": row["outcome_return_pct"],
                        "outcome": row["outcome"],
                    })
        except Exception as exc:
            print(f"  Warning: could not load drift data: {exc}")

        fig = create_drift_scatter(drift_data)
        _save_and_open(fig, "drift_scatter", output_dir, no_open)

    asyncio.run(_run())


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "analysis":
        _cmd_analysis(args.ticker, args.asset_type, args.output_dir, args.no_open)
    elif args.command == "portfolio":
        _cmd_portfolio(args.output_dir, args.no_open)
    elif args.command == "calibration":
        _cmd_calibration(args.lookback, args.output_dir, args.no_open)
    elif args.command == "drift":
        _cmd_drift(args.output_dir, args.no_open)


if __name__ == "__main__":
    main()
