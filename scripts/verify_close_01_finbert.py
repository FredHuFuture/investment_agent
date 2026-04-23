"""CLOSE-01 operator CLI: run live FinBERT round-trip and print evidence.

Usage:
    # 1. install the optional extra
    pip install -e .[llm-local]

    # 2. pre-download the model (optional but recommended)
    python scripts/fetch_finbert.py

    # 3. unset Anthropic key so FinBERT path is taken
    #    (PowerShell:  Remove-Item Env:ANTHROPIC_API_KEY)
    unset ANTHROPIC_API_KEY

    # 4. run this helper -- prints the evidence block for 03-HUMAN-UAT.md
    python scripts/verify_close_01_finbert.py NVDA
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from datetime import datetime, timezone


def main() -> int:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NVDA"

    if importlib.util.find_spec("transformers") is None:
        print("SKIP: transformers not installed. Run: pip install -e .[llm-local]")
        return 2
    if os.getenv("ANTHROPIC_API_KEY"):
        print(
            "SKIP: ANTHROPIC_API_KEY is set. "
            "Unset it to exercise the FinBERT branch."
        )
        return 2

    from agents.models import AgentInput
    from agents.sentiment import SentimentAgent
    from data_providers.web_news_provider import WebNewsProvider
    from data_providers.yfinance_provider import YFinanceProvider

    async def _run():
        yf_provider = YFinanceProvider()
        news_provider = WebNewsProvider()
        agent = SentimentAgent(yf_provider, news_provider=news_provider)
        return await agent.analyze(AgentInput(ticker=ticker, asset_type="stock"))

    output = asyncio.run(_run())
    ts = datetime.now(timezone.utc).isoformat()

    print("=" * 70)
    print(f"CLOSE-01 EVIDENCE  ({ts})")
    print(f"  ticker:     {ticker}")
    print(f"  signal:     {output.signal.value}")
    print(f"  confidence: {output.confidence:.0f}")
    print(f"  reasoning:  {output.reasoning!r}")
    print("=" * 70)
    print("Copy the block above into 03-HUMAN-UAT.md evidence section.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
