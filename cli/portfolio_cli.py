from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from db.database import DEFAULT_DB_PATH, init_db
from portfolio.manager import PortfolioManager


def _format_currency(value: float) -> str:
    return f"${value:,.2f}"


def _format_pct(value: float) -> str:
    return f"{value * 100:,.1f}%"


def _print_portfolio(portfolio) -> None:
    total_cost_basis = sum(position.cost_basis for position in portfolio.positions)
    lines = []
    lines.append("=" * 63)
    lines.append(" PORTFOLIO OVERVIEW")
    lines.append("=" * 63)
    lines.append(
        f"{'Ticker':<8} {'Type':<6} {'Qty':>8} {'Avg Cost':>12} "
        f"{'Cost Basis':>12} {'Sector':<15}"
    )
    lines.append("-" * 63)
    for position in portfolio.positions:
        sector = position.sector or "-"
        lines.append(
            f"{position.ticker:<8} {position.asset_type:<6} "
            f"{position.quantity:>8,.2f} {_format_currency(position.avg_cost):>12} "
            f"{_format_currency(position.cost_basis):>12} {sector:<15}"
        )
    lines.append("-" * 63)
    lines.append(f"Total Cost Basis: {_format_currency(total_cost_basis)}")
    lines.append(f"Cash: {_format_currency(portfolio.cash)}")
    lines.append(f"Est. Total Value: {_format_currency(portfolio.total_value)}")
    lines.append("")
    lines.append("EXPOSURE (by cost basis):")
    lines.append(f"  US Stocks: {_format_pct(portfolio.stock_exposure_pct)}")
    lines.append(f"  Crypto:    {_format_pct(portfolio.crypto_exposure_pct)}")
    lines.append(f"  Cash:      {_format_pct(portfolio.cash_pct)}")
    lines.append("")
    lines.append("SECTOR BREAKDOWN:")
    if portfolio.sector_breakdown:
        for sector, pct in sorted(
            portfolio.sector_breakdown.items(), key=lambda item: item[1], reverse=True
        ):
            lines.append(f"  {sector}: {_format_pct(pct)}")
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append("TOP CONCENTRATION:")
    if portfolio.top_concentration:
        segments = [
            f"{ticker}: {_format_pct(pct)}" for ticker, pct in portfolio.top_concentration
        ]
        lines.append("  " + "  |  ".join(segments))
    else:
        lines.append("  (none)")
    lines.append("=" * 63)
    print("\n".join(lines))


async def _handle_add(args: argparse.Namespace) -> None:
    await init_db(args.db_path)
    manager = PortfolioManager(args.db_path)
    await manager.add_position(
        ticker=args.ticker,
        asset_type=args.asset_type,
        quantity=args.qty,
        avg_cost=args.cost,
        entry_date=args.date,
        sector=args.sector,
        industry=args.industry,
    )


async def _handle_remove(args: argparse.Namespace) -> None:
    await init_db(args.db_path)
    manager = PortfolioManager(args.db_path)
    await manager.remove_position(args.ticker)


async def _handle_show(args: argparse.Namespace) -> None:
    await init_db(args.db_path)
    manager = PortfolioManager(args.db_path)
    portfolio = await manager.load_portfolio()
    _print_portfolio(portfolio)


async def _handle_set_cash(args: argparse.Namespace) -> None:
    await init_db(args.db_path)
    manager = PortfolioManager(args.db_path)
    await manager.set_cash(args.amount)


async def _handle_scale(args: argparse.Namespace) -> None:
    await init_db(args.db_path)
    manager = PortfolioManager(args.db_path)
    await manager.scale_portfolio(args.multiplier)


async def _handle_split(args: argparse.Namespace) -> None:
    await init_db(args.db_path)
    manager = PortfolioManager(args.db_path)
    await manager.apply_split(args.ticker, args.ratio)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portfolio context manager CLI.")
    parser.add_argument(
        "--db",
        dest="db_path",
        default=str(DEFAULT_DB_PATH),
        help="Path to SQLite database.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a new position.")
    add_parser.add_argument("--ticker", required=True)
    add_parser.add_argument("--qty", required=True, type=float)
    add_parser.add_argument("--cost", required=True, type=float)
    add_parser.add_argument("--date", required=True)
    add_parser.add_argument("--asset-type", required=True, dest="asset_type")
    add_parser.add_argument("--sector")
    add_parser.add_argument("--industry")
    add_parser.set_defaults(func=_handle_add)

    remove_parser = subparsers.add_parser("remove", help="Remove a position.")
    remove_parser.add_argument("--ticker", required=True)
    remove_parser.set_defaults(func=_handle_remove)

    show_parser = subparsers.add_parser("show", help="Show portfolio overview.")
    show_parser.set_defaults(func=_handle_show)

    cash_parser = subparsers.add_parser("set-cash", help="Set portfolio cash.")
    cash_parser.add_argument("--amount", required=True, type=float)
    cash_parser.set_defaults(func=_handle_set_cash)

    scale_parser = subparsers.add_parser("scale", help="Scale all positions.")
    scale_parser.add_argument("--multiplier", required=True, type=float)
    scale_parser.set_defaults(func=_handle_scale)

    split_parser = subparsers.add_parser("split", help="Apply a stock split.")
    split_parser.add_argument("--ticker", required=True)
    split_parser.add_argument("--ratio", required=True, type=int)
    split_parser.set_defaults(func=_handle_split)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
