"""CLOSE-02 operator CLI: live Finnhub round-trip and FundamentalAgent marker check.

Usage:
    export FINNHUB_API_KEY=<your_free_tier_key>
    python scripts/verify_close_02_finnhub.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone


def main() -> int:
    if not os.getenv("FINNHUB_API_KEY"):
        print("SKIP: FINNHUB_API_KEY not set. Get a free key at https://finnhub.io/")
        return 2

    from agents.fundamental import FundamentalAgent
    from agents.models import AgentInput
    from data_providers.finnhub_provider import FinnhubProvider
    from data_providers.yfinance_provider import YFinanceProvider
    import data_providers.sector_pe_cache as spc
    spc._finnhub_provider = None

    async def _run():
        provider = FinnhubProvider()
        try:
            pe = await provider.get_sector_pe("technology")
        finally:
            await provider.aclose()

        yf = YFinanceProvider()
        fa = FundamentalAgent(yf)
        out = await fa.analyze(AgentInput(ticker="AAPL", asset_type="stock"))
        return pe, out

    pe, out = asyncio.run(_run())
    ts = datetime.now(timezone.utc).isoformat()

    print("=" * 70)
    print(f"CLOSE-02 EVIDENCE  ({ts})")
    print(f"  sector=technology P/E: {pe}")
    print(f"  AAPL reasoning contains 'Finnhub sector P/E': "
          f"{'Finnhub sector P/E' in (out.reasoning or '')}")
    print(f"  AAPL reasoning: {out.reasoning!r}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
