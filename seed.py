"""Seed the database with a demo portfolio for new users."""

from __future__ import annotations

import asyncio
import platform
import sys

from db.database import DEFAULT_DB_PATH, init_db
from portfolio.manager import PortfolioManager


DEMO_POSITIONS = [
    {
        "ticker": "AAPL",
        "asset_type": "stock",
        "quantity": 100,
        "avg_cost": 186.0,
        "entry_date": "2025-12-15",
        "thesis_text": "AI integration across Apple ecosystem — Siri improvements + Apple Intelligence driving upgrade cycle",
        "expected_return_pct": 0.25,
        "expected_hold_days": 180,
        "target_price": 232.0,
        "stop_loss": 160.0,
    },
    {
        "ticker": "NVDA",
        "asset_type": "stock",
        "quantity": 50,
        "avg_cost": 130.0,
        "entry_date": "2025-11-01",
        "thesis_text": "Data center GPU demand from AI training. Blackwell architecture ramp through 2026.",
        "expected_return_pct": 0.40,
        "expected_hold_days": 365,
        "target_price": 182.0,
        "stop_loss": 105.0,
    },
    {
        "ticker": "BTC",
        "asset_type": "btc",
        "quantity": 1.5,
        "avg_cost": 42000.0,
        "entry_date": "2025-10-01",
        "thesis_text": "Post-halving supply shock + ETF inflows. Targeting $80K-100K cycle top.",
        "expected_return_pct": 1.0,
        "expected_hold_days": 540,
        "target_price": 84000.0,
        "stop_loss": 35000.0,
    },
    {
        "ticker": "GS",
        "asset_type": "stock",
        "quantity": 200,
        "avg_cost": 480.0,
        "entry_date": "2026-01-20",
    },
    {
        "ticker": "MSFT",
        "asset_type": "stock",
        "quantity": 75,
        "avg_cost": 420.0,
        "entry_date": "2026-02-01",
    },
]

DEMO_CASH = 200_000.0


async def main() -> None:
    # Initialize database schema
    await init_db(DEFAULT_DB_PATH)

    mgr = PortfolioManager(DEFAULT_DB_PATH)

    # Check if positions already exist
    existing = await mgr.get_all_positions()
    existing_tickers = {p.ticker for p in existing}

    if existing_tickers:
        print(f"Portfolio already has {len(existing_tickers)} position(s): {', '.join(sorted(existing_tickers))}")
        print("Skipping existing positions. Only adding new ones.\n")

    added: list[dict] = []
    skipped: list[str] = []

    for pos in DEMO_POSITIONS:
        ticker = pos["ticker"]
        if ticker in existing_tickers:
            skipped.append(ticker)
            continue

        await mgr.add_position(
            ticker=pos["ticker"],
            asset_type=pos["asset_type"],
            quantity=pos["quantity"],
            avg_cost=pos["avg_cost"],
            entry_date=pos["entry_date"],
            thesis_text=pos.get("thesis_text"),
            expected_return_pct=pos.get("expected_return_pct"),
            expected_hold_days=pos.get("expected_hold_days"),
            target_price=pos.get("target_price"),
            stop_loss=pos.get("stop_loss"),
        )
        added.append(pos)

    # Set cash
    await mgr.set_cash(DEMO_CASH)

    # Print summary
    if skipped:
        print(f"Skipped (already exist): {', '.join(skipped)}")

    if not added:
        print("No new positions added — portfolio already seeded.")
        print(f"  Cash set to: ${DEMO_CASH:,.0f}")
        return

    print("Seeded demo portfolio:")
    for pos in DEMO_POSITIONS:
        ticker = pos["ticker"]
        qty = pos["quantity"]
        cost = pos["avg_cost"]
        unit = "units " if pos["asset_type"] != "stock" else "shares"
        thesis = pos.get("thesis_text")

        status = "  SKIP" if ticker in skipped else "  +"
        line = f"{status} {ticker:<6} {qty:>5g} {unit} @ ${cost:>,.0f}"
        if thesis:
            short = thesis[:30] + "..." if len(thesis) > 30 else thesis
            line += f"  (thesis: {short})"
        print(line)

    print(f"  Cash: ${DEMO_CASH:,.0f}")
    print(f"\nAdded {len(added)} position(s).")
    print("\nRun 'make run' to start the dashboard.")


if __name__ == "__main__":
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
