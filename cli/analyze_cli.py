from __future__ import annotations

import argparse
import asyncio
import sys

from cli.report import format_analysis_json, format_analysis_report
from engine.pipeline import AnalysisPipeline

# Auto-detect crypto tickers (case-insensitive)
_CRYPTO_TICKERS = {"BTC", "ETH", "BTC-USD", "ETH-USD"}

# Windows: aiodns (used by aiohttp/ccxt) requires SelectorEventLoop,
# not the default ProactorEventLoop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def _run_analysis(
    ticker: str, asset_type: str, json_output: bool, detail: bool = False
) -> None:
    """Run the analysis pipeline and print results."""
    pipeline = AnalysisPipeline()
    result = await pipeline.analyze_ticker(ticker, asset_type)

    if json_output:
        print(format_analysis_json(result))
    else:
        print(format_analysis_report(result, detail=detail))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run investment analysis for a single ticker."
    )
    parser.add_argument(
        "ticker",
        type=str,
        help="Ticker symbol (e.g. AAPL, MSFT, BTC).",
    )
    parser.add_argument(
        "--asset-type",
        dest="asset_type",
        choices=["stock", "btc", "eth"],
        default="stock",
        help="Asset type (default: stock).",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output as JSON instead of formatted report.",
    )
    parser.add_argument(
        "--detail", "-d",
        dest="detail",
        action="store_true",
        help="Show full agent analysis breakdown (all metrics, reasoning, weights).",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    ticker_upper = args.ticker.upper()

    # Auto-detect asset_type if not explicitly set
    asset_type = args.asset_type
    if asset_type == "stock" and ticker_upper in _CRYPTO_TICKERS:
        asset_type = "btc" if ticker_upper in ("BTC", "BTC-USD") else "eth"

    asyncio.run(
        _run_analysis(
            ticker=ticker_upper,
            asset_type=asset_type,
            json_output=args.json_output,
            detail=args.detail,
        )
    )


if __name__ == "__main__":
    main()
