# cli/decision_cli.py
"""Decision Layer CLI: propose / list / approve / reject / execute / audit / verify.

Invoke as: python -m cli.decision_cli <verb> [...]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

import aiosqlite

from api.deps import map_ticker, resolve_asset_type
from db.database import DEFAULT_DB_PATH, init_db
from decisions.audit import verify_chain
from decisions.manager import DecisionManager
from decisions.models import DecisionError
from engine.pipeline import AnalysisPipeline
from execution.paper import PaperExecutionAdapter


def _print_proposal(pa) -> None:
    print(
        f"[{pa.id}] {pa.ticker} {pa.action} qty={pa.quantity} "
        f"status={pa.status} valid_until={pa.valid_until}"
    )


async def _handle_propose(args: argparse.Namespace) -> None:
    await init_db(args.db_path)
    asset_type = resolve_asset_type(args.ticker, args.asset_type)
    yf_ticker = map_ticker(args.ticker, asset_type)
    pipeline = AnalysisPipeline(db_path=args.db_path, use_adaptive_weights=False)
    signal = await pipeline.analyze_ticker(yf_ticker, asset_type, portfolio=None)
    mgr = DecisionManager(args.db_path)
    pa = await mgr.create_proposal(signal, quantity=args.qty)
    print("Proposed:")
    _print_proposal(pa)


async def _handle_list(args: argparse.Namespace) -> None:
    await init_db(args.db_path)
    mgr = DecisionManager(args.db_path)
    items = await mgr.list(status=args.status)
    if not items:
        print("(no decisions)")
        return
    for pa in items:
        _print_proposal(pa)


async def _handle_approve(args: argparse.Namespace) -> None:
    await init_db(args.db_path)
    mgr = DecisionManager(args.db_path)
    try:
        pa = await mgr.approve(args.id, actor=args.by)
    except DecisionError as err:
        print(f"ERROR {err.code}: {err.message}", file=sys.stderr)
        sys.exit(1)
    print("Approved:")
    _print_proposal(pa)


async def _handle_reject(args: argparse.Namespace) -> None:
    await init_db(args.db_path)
    mgr = DecisionManager(args.db_path)
    try:
        pa = await mgr.reject(args.id, actor=args.by, note=args.note or "")
    except DecisionError as err:
        print(f"ERROR {err.code}: {err.message}", file=sys.stderr)
        sys.exit(1)
    print("Rejected:")
    _print_proposal(pa)


async def _handle_execute(args: argparse.Namespace) -> None:
    await init_db(args.db_path)
    mgr = DecisionManager(args.db_path)
    adapter = PaperExecutionAdapter()
    try:
        pa = await mgr.execute(args.id, adapter)
    except DecisionError as err:
        print(f"ERROR {err.code}: {err.message}", file=sys.stderr)
        sys.exit(1)
    report = json.loads(pa.execution_report_json) if pa.execution_report_json else {}
    print("Executed (paper fill):")
    _print_proposal(pa)
    print(f"  fill_price={report.get('fill_price')} venue={report.get('venue')}")


async def _handle_audit(args: argparse.Namespace) -> None:
    await init_db(args.db_path)
    conn = await aiosqlite.connect(args.db_path)
    conn.row_factory = aiosqlite.Row
    try:
        rows = await (await conn.execute(
            "SELECT id, event_type, actor, entry_hash, created_at FROM decision_audit "
            "WHERE decision_id=? ORDER BY id", (args.id,),
        )).fetchall()
    finally:
        await conn.close()
    if not rows:
        print(f"(no audit rows for decision {args.id})")
        return
    for r in rows:
        print(f"  #{r['id']} {r['event_type']:<9} actor={r['actor']} "
              f"hash={r['entry_hash'][:12]}... at={r['created_at']}")


async def _handle_verify(args: argparse.Namespace) -> None:
    await init_db(args.db_path)
    conn = await aiosqlite.connect(args.db_path)
    conn.row_factory = aiosqlite.Row
    try:
        result = await verify_chain(conn)
    finally:
        await conn.close()
    if result["valid"]:
        print(f"Chain integrity OK ({result['checked']} entries verified).")
    else:
        print(f"Chain INVALID at id={result['broken_at_id']}: {result['reason']}",
              file=sys.stderr)
        sys.exit(1)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Human-in-the-loop Decision Layer CLI.")
    parser.add_argument("--db", dest="db_path", default=str(DEFAULT_DB_PATH),
                        help="Path to SQLite database.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("propose", help="Analyze a ticker and create a pending proposal.")
    p.add_argument("ticker")
    p.add_argument("--qty", type=float, default=None)
    p.add_argument("--asset-type", dest="asset_type", default="stock",
                   choices=["stock", "btc", "eth"])
    p.set_defaults(func=_handle_propose)

    p = sub.add_parser("list", help="List proposals.")
    p.add_argument("--status", default=None,
                   choices=["pending", "approved", "rejected", "executed", "expired"])
    p.set_defaults(func=_handle_list)

    p = sub.add_parser("approve", help="Approve a proposal.")
    p.add_argument("id", type=int)
    p.add_argument("--by", required=True)
    p.set_defaults(func=_handle_approve)

    p = sub.add_parser("reject", help="Reject a proposal.")
    p.add_argument("id", type=int)
    p.add_argument("--by", required=True)
    p.add_argument("--note", default="")
    p.set_defaults(func=_handle_reject)

    p = sub.add_parser("execute", help="Execute an approved proposal (paper fill).")
    p.add_argument("id", type=int)
    p.set_defaults(func=_handle_execute)

    p = sub.add_parser("audit", help="Show a decision's audit trail.")
    p.add_argument("id", type=int)
    p.set_defaults(func=_handle_audit)

    p = sub.add_parser("verify", help="Verify global audit-chain integrity.")
    p.set_defaults(func=_handle_verify)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
