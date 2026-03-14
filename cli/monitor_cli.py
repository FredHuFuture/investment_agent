"""Portfolio monitoring CLI — check positions and view alerts."""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

from db.database import DEFAULT_DB_PATH
from monitoring.monitor import PortfolioMonitor
from monitoring.store import AlertStore

# Windows: aiodns (used by aiohttp/ccxt) requires SelectorEventLoop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_SEVERITY_ICONS = {
    "CRITICAL": "[!!]",
    "HIGH": "[! ]",
    "WARNING": "[* ]",
    "INFO": "[i ]",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="monitor",
        description="Portfolio monitoring commands.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check: run position health check
    subparsers.add_parser("check", help="Run portfolio health check.")

    # alerts: show recent alerts
    alerts_parser = subparsers.add_parser("alerts", help="Show recent alerts.")
    alerts_parser.add_argument("--ticker", help="Filter by ticker.")
    alerts_parser.add_argument(
        "--severity", choices=["CRITICAL", "HIGH", "WARNING", "INFO"]
    )
    alerts_parser.add_argument("--limit", type=int, default=20)

    return parser


def _cmd_check(db_path: str) -> None:
    async def _run() -> None:
        monitor = PortfolioMonitor(db_path=db_path)
        result = await monitor.run_check()

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        alerts = result["alerts"]
        checked = result["checked_positions"]
        print("=" * 64)
        print("  PORTFOLIO HEALTH CHECK")
        print(f"  {now}")
        print("=" * 64)
        print()
        print(f"  Positions checked: {checked}")
        print(f"  Alerts generated:  {len(alerts)}")

        if alerts:
            print()
            for alert in alerts:
                icon = _SEVERITY_ICONS.get(alert["severity"], "  ")
                print(
                    f"  {icon} {alert['severity']:<10} {alert['ticker']} -- {alert['alert_type']}"
                )
                print(f"     {alert['message']}")
                print(f"     -> {alert['recommended_action']}")
                print()
        else:
            print()
            print("  [OK] All positions healthy")

        if result["snapshot_saved"]:
            print("  Portfolio snapshot saved.")

        if result["warnings"]:
            print()
            print("  Warnings:")
            for w in result["warnings"]:
                print(f"    [!] {w}")

        print("=" * 64)

    asyncio.run(_run())


def _cmd_alerts(db_path: str, ticker: str | None, severity: str | None, limit: int) -> None:
    async def _run() -> None:
        store = AlertStore(db_path)
        alerts = await store.get_recent_alerts(ticker=ticker, severity=severity, limit=limit)

        if not alerts:
            print("No alerts found.")
            return

        print(f"Recent Alerts (last {limit}):")
        for alert in alerts:
            ts = str(alert["created_at"])[:16].replace("T", " ")
            print(
                f"  {ts}  {alert['severity']:<10} {alert['ticker']:<6} "
                f"{alert['alert_type']:<20} {alert['message'][:60]}"
            )

    asyncio.run(_run())


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    db_path = str(DEFAULT_DB_PATH)

    if args.command == "check":
        _cmd_check(db_path)
    elif args.command == "alerts":
        _cmd_alerts(db_path, args.ticker, args.severity, args.limit)


if __name__ == "__main__":
    main()
