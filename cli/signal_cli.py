"""Signal tracking CLI — history, accuracy stats, calibration, agent performance."""
from __future__ import annotations

import argparse
import asyncio

from db.database import DEFAULT_DB_PATH
from tracking.store import SignalStore
from tracking.tracker import SignalTracker


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="signal",
        description="Signal tracking commands.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    history_parser = subparsers.add_parser("history", help="Show signal history.")
    history_parser.add_argument("--ticker", help="Filter by ticker.")
    history_parser.add_argument("--signal", choices=["BUY", "HOLD", "SELL"])
    history_parser.add_argument("--limit", type=int, default=20)

    stats_parser = subparsers.add_parser("stats", help="Show accuracy stats.")
    stats_parser.add_argument("--lookback", type=int, default=100)

    cal_parser = subparsers.add_parser("calibration", help="Show confidence calibration.")
    cal_parser.add_argument("--lookback", type=int, default=100)
    cal_parser.add_argument("--min-bucket", type=int, default=5)

    agents_parser = subparsers.add_parser("agents", help="Show agent performance.")
    agents_parser.add_argument("--lookback", type=int, default=100)

    return parser


def _cmd_history(db_path: str, ticker: str | None, signal: str | None, limit: int) -> None:
    async def _run() -> None:
        store = SignalStore(db_path)
        rows = await store.get_signal_history(ticker=ticker, signal=signal, limit=limit)
        if not rows:
            print("No signal history found.")
            return
        print(f"Signal History (last {limit}):")
        for r in rows:
            ts = str(r["created_at"])[:16].replace("T", " ")
            outcome_str = f"→ {r['outcome']}" if r["outcome"] else "→  —"
            ret_str = f"  {r['outcome_return_pct']:+.1%}" if r["outcome_return_pct"] is not None else "  —"
            regime = r.get("regime") or "—"
            print(
                f"  {ts}  {r['final_signal']:<5} {r['final_confidence']:.1f}%  "
                f"{r['ticker']:<6} {r['asset_type']:<6} {regime:<10} "
                f"{outcome_str:<12}{ret_str}"
            )

    asyncio.run(_run())


def _cmd_stats(db_path: str, lookback: int) -> None:
    async def _run() -> None:
        store = SignalStore(db_path)
        tracker = SignalTracker(store)
        stats = await tracker.compute_accuracy_stats(lookback=lookback)

        pending = stats["total_signals"] - stats["resolved_count"]
        wr = f"{stats['win_rate']:.1%}" if stats["win_rate"] is not None else "N/A"
        avg_conf = f"{stats['avg_confidence']:.1f}%" if stats["avg_confidence"] is not None else "N/A"

        print("=" * 64)
        print("  SIGNAL ACCURACY REPORT")
        print(f"  Last {lookback} signals")
        print("=" * 64)
        print()
        print(f"  Resolved: {stats['resolved_count']} / {stats['total_signals']} signals ({pending} pending/skipped)")
        print(f"  Win Rate: {wr} ({stats['win_count']} wins / {stats['resolved_count']} resolved)")
        print(f"  Avg Confidence: {avg_conf}")
        print()
        print("  By Signal:")
        for sig, d in stats["by_signal"].items():
            if d["count"] > 0:
                wr_s = f"{d['win_rate']:.1%}" if d["win_rate"] is not None else "N/A"
                print(f"    {sig:<6} {d['count']} signals → {wr_s} win rate")
        print()
        print("  By Asset Type:")
        for asset, d in stats["by_asset_type"].items():
            if d["count"] > 0:
                wr_s = f"{d['win_rate']:.1%}" if d["win_rate"] is not None else "N/A"
                print(f"    {asset:<8} {d['count']} signals → {wr_s} win rate")
        print()
        print("  By Regime:")
        for regime, d in stats["by_regime"].items():
            if d["count"] > 0:
                wr_s = f"{d['win_rate']:.1%}" if d["win_rate"] is not None else "N/A"
                print(f"    {regime:<12} {d['count']} signals → {wr_s} win rate")
        print("=" * 64)

    asyncio.run(_run())


def _cmd_calibration(db_path: str, lookback: int, min_bucket: int) -> None:
    async def _run() -> None:
        store = SignalStore(db_path)
        tracker = SignalTracker(store)
        buckets = await tracker.compute_calibration_data(
            lookback=lookback, min_bucket_size=min_bucket
        )
        print("=" * 64)
        print("  CONFIDENCE CALIBRATION")
        print("  (ideal: expected ≈ actual)")
        print("=" * 64)
        print()
        print(f"  {'Bucket':<12} {'Expected':>8}   {'Actual':>6}   {'Samples':>7}   {'Delta':>6}")
        print(f"  {'──────────':<12} {'────────':>8}   {'──────':>6}   {'───────':>7}   {'─────':>6}")
        for b in buckets:
            delta = b["actual_win_rate"] - b["expected_win_rate"]
            delta_str = f"{delta:+.1f}%"
            print(
                f"  {b['confidence_bucket']:<12} {b['expected_win_rate']:>6.1f}%   "
                f"{b['actual_win_rate']:>5.1f}%   {b['sample_size']:>7}   {delta_str:>6}"
            )
        print()
        print("  Interpretation:")
        print("    Delta > 0: under-confident (good — conservative)")
        print("    Delta < 0: over-confident (bad — predictions too rosy)")
        print()
        print(f"  ⚠ Buckets with < {min_bucket} samples excluded.")
        print("=" * 64)

    asyncio.run(_run())


def _cmd_agents(db_path: str, lookback: int) -> None:
    async def _run() -> None:
        store = SignalStore(db_path)
        tracker = SignalTracker(store)
        perf = await tracker.compute_agent_performance(lookback=lookback)
        print("=" * 64)
        print("  AGENT PERFORMANCE")
        print(f"  Last {lookback} signals")
        print("=" * 64)
        for name, d in perf.items():
            agreement = f"{d['agreement_rate']:.1%}"
            da = f"{d['directional_accuracy']:.1%}" if d["directional_accuracy"] is not None else "N/A"
            print()
            print(f"  {name}:")
            print(f"    Signals: {d['total_signals']} | Agreement w/ final: {agreement}")
            print(f"    Directional accuracy: {da}")
            print(f"    Avg confidence: {d['avg_confidence']}")
            buy_d = d["by_signal"]["BUY"]
            sell_d = d["by_signal"]["SELL"]
            hold_d = d["by_signal"]["HOLD"]
            buy_acc = f"{buy_d['accuracy']:.1%}" if buy_d.get("accuracy") is not None else "N/A"
            sell_acc = f"{sell_d['accuracy']:.1%}" if sell_d.get("accuracy") is not None else "N/A"
            print(
                f"    BUY: {buy_d['count']} ({buy_acc} acc) | "
                f"SELL: {sell_d['count']} ({sell_acc} acc) | "
                f"HOLD: {hold_d['count']}"
            )
        print("=" * 64)

    asyncio.run(_run())


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    db_path = str(DEFAULT_DB_PATH)

    if args.command == "history":
        _cmd_history(db_path, args.ticker, args.signal, args.limit)
    elif args.command == "stats":
        _cmd_stats(db_path, args.lookback)
    elif args.command == "calibration":
        _cmd_calibration(db_path, args.lookback, args.min_bucket)
    elif args.command == "agents":
        _cmd_agents(db_path, args.lookback)


if __name__ == "__main__":
    main()
