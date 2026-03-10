"""CLI for the investment monitoring daemon."""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from daemon.config import DaemonConfig
from daemon.scheduler import MonitoringDaemon

_SEP = "=" * 64
_THIN = "-" * 64


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daemon_cli",
        description="Investment monitoring daemon -- scheduled portfolio checks.",
    )
    sub = parser.add_subparsers(dest="command")

    # start
    start_p = sub.add_parser("start", help="Start long-running daemon.")
    start_p.add_argument("--daily-hour", type=int, default=17)
    start_p.add_argument("--daily-minute", type=int, default=0)
    start_p.add_argument("--weekly-day", type=str, default="sat")
    start_p.add_argument("--weekly-hour", type=int, default=10)
    start_p.add_argument("--weekly-minute", type=int, default=0)
    start_p.add_argument("--timezone", type=str, default="US/Eastern")
    start_p.add_argument("--log-file", type=str, default="data/daemon.log")
    start_p.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    start_p.add_argument(
        "--no-daily", action="store_true", default=False,
        help="Disable the daily portfolio check job.",
    )
    start_p.add_argument(
        "--no-weekly", action="store_true", default=False,
        help="Disable the weekly revaluation job.",
    )

    # run-once
    once_p = sub.add_parser("run-once", help="Run a single job immediately, then exit.")
    once_p.add_argument("job", choices=["daily", "weekly"])

    # status
    sub.add_parser("status", help="Show daemon run history.")

    return parser


def _cmd_start(args) -> None:
    config = DaemonConfig(
        daily_hour=args.daily_hour,
        daily_minute=args.daily_minute,
        daily_enabled=not args.no_daily,
        weekly_day=args.weekly_day,
        weekly_hour=args.weekly_hour,
        weekly_minute=args.weekly_minute,
        weekly_enabled=not args.no_weekly,
        timezone=args.timezone,
        log_file=args.log_file,
        log_level=args.log_level,
    )
    daemon = MonitoringDaemon(config)
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        pass


def _cmd_run_once(args) -> None:
    daemon = MonitoringDaemon()

    async def _run():
        result = await daemon.run_once(args.job)
        if args.job == "daily":
            _print_daily_result(result)
        else:
            _print_weekly_result(result)

    asyncio.run(_run())


def _cmd_status(args) -> None:
    daemon = MonitoringDaemon()

    async def _run():
        status = await daemon.get_status()
        _print_status(status)

    asyncio.run(_run())


def _print_daily_result(result: dict) -> None:
    print(_SEP)
    print("  DAILY PORTFOLIO CHECK")
    print(_SEP)
    if "error" in result:
        print(f"  ERROR: {result['error']}")
    else:
        print(f"  Positions checked: {result.get('checked_positions', 0)}")
        alerts = result.get("alerts", [])
        print(f"  Alerts generated:  {len(alerts)}")
        if alerts:
            print()
            for a in alerts:
                sev = a.get("severity", "?")
                msg = a.get("message", "")
                ticker = a.get("ticker", "")
                print(f"  [{sev}] {ticker}: {msg}")
        warnings = result.get("warnings", [])
        if warnings:
            print()
            print("  Warnings:")
            for w in warnings:
                print(f"    - {w}")
    print(_SEP)


def _print_weekly_result(result: dict) -> None:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n_analyzed = result.get("positions_analyzed", 0)

    print(_SEP)
    print(f"  WEEKLY REVALUATION")
    print(f"  {now_str} ({n_analyzed} positions analyzed)")
    print(_SEP)
    print()

    if "error" in result:
        print(f"  ERROR: {result['error']}")
    else:
        reversals = {r["ticker"] for r in result.get("signal_reversals", [])}
        for reversal in result.get("signal_reversals", []):
            ticker = reversal["ticker"]
            orig = reversal["original_signal"]
            cur = reversal["current_signal"]
            conf = reversal["confidence"]
            marker = "  ** REVERSAL **"
            print(f"  {ticker}: {orig} -> {cur}  (confidence: {conf:.0f})  {marker}")

        n_rev = len(result.get("signal_reversals", []))
        n_saved = result.get("signals_saved", 0)
        n_alerts = result.get("alerts_generated", 0)
        n_err = len(result.get("errors", []))
        errors = result.get("errors", [])

        print()
        print(_THIN)
        print(f"  ALERTS: {n_alerts} generated")
        for r in result.get("signal_reversals", []):
            ticker = r["ticker"]
            orig = r["original_signal"]
            cur = r["current_signal"]
            conf = r["confidence"]
            print(f"  - [HIGH] {ticker}: Signal reversed from {orig} to {cur} (confidence: {conf:.0f})")
        print(_THIN)
        print(f"  Signals saved: {n_saved}")
        print(f"  Errors: {n_err}")
        if errors:
            for e in errors:
                print(f"    - {e['ticker']}: {e['error']}")

    print(_SEP)


def _print_status(status: dict) -> None:
    print(_SEP)
    print("  DAEMON STATUS")
    print(_SEP)

    if "error" in status:
        print(f"  Could not read status: {status['error']}")
        print(_SEP)
        return

    labels = {
        "daily_check": "Daily Check",
        "weekly_revaluation": "Weekly Revaluation",
        "catalyst_scan": "Catalyst Scan",
    }
    for key, label in labels.items():
        info = status.get(key, {})
        print(f"\n  {label}")
        last = info.get("last_run")
        stat = info.get("status", "never_run")
        dur_ms = info.get("duration_ms")
        if last is None:
            if key == "catalyst_scan":
                print("    Status:     not configured (requires Task 017)")
            else:
                print("    Status:     never run")
        else:
            dur_str = f"{dur_ms / 1000:.1f}s" if dur_ms is not None else "N/A"
            print(f"    Last run:   {last}")
            print(f"    Status:     {stat}")
            print(f"    Duration:   {dur_str}")

    print()
    print(_SEP)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "start":
        _cmd_start(args)
    elif args.command == "run-once":
        _cmd_run_once(args)
    elif args.command == "status":
        _cmd_status(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
