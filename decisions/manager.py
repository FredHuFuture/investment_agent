# decisions/manager.py
"""DecisionManager: DB-backed lifecycle for proposed actions.

Every state-changing method opens its own connection, issues BEGIN IMMEDIATE
(acquiring SQLite's write lock up front), performs the row change AND its audit
append on the same connection, and commits once — so a state change can never
exist without its audit row, and concurrent writers cannot fork the audit chain.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import aiosqlite

from decisions.audit import append_audit
from decisions.models import (
    DecisionError,
    ProposedAction,
    compute_proposal_hash,
    default_quantity,
    is_past,
    now_utc_iso,
    recompute_proposal_hash_from_row,
    ttl_hours,
)
from execution.adapter import ExecutionAdapter, Order, OrderSide

logger = logging.getLogger("investment_agent.decisions")


class DecisionManager:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    async def _connect(self) -> aiosqlite.Connection:
        # isolation_level=None MUST be passed at connect time for manual
        # transaction control. Setting conn.isolation_level AFTER connect raises
        # `SQLite objects created in a thread can only be used in that same
        # thread` (aiosqlite's setter proxies to the worker-thread connection
        # from the caller thread). Verified on Python 3.12.10 / aiosqlite 0.20.0.
        conn = await aiosqlite.connect(self._db_path, isolation_level=None)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute("PRAGMA synchronous=NORMAL;")
        await conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    @staticmethod
    async def _get_row(conn: aiosqlite.Connection, decision_id: int) -> aiosqlite.Row | None:
        cur = await conn.execute("SELECT * FROM decisions WHERE id=?", (decision_id,))
        return await cur.fetchone()

    async def get(self, decision_id: int) -> ProposedAction | None:
        conn = await self._connect()
        try:
            row = await self._get_row(conn, decision_id)
            return ProposedAction.from_row(row) if row is not None else None
        finally:
            await conn.close()

    async def create_proposal(
        self, signal: Any, quantity: float | None = None
    ) -> ProposedAction:
        action = signal.final_signal.value
        if action in ("BUY", "SELL"):
            qty: float | None = float(quantity) if quantity is not None else default_quantity()
            if qty <= 0:
                # The API model enforces gt=0, but the CLI / direct-manager path
                # bypasses it — a non-positive qty would become an executable fill.
                raise DecisionError(
                    "INVALID_QUANTITY",
                    f"quantity must be > 0 for a {action} proposal, got {qty}", 400,
                )
        else:  # HOLD — stored for audit, never executable
            qty = None

        proposal_hash = compute_proposal_hash(signal.ticker, action, qty, signal)
        created_at = now_utc_iso()
        valid_until = (
            datetime.fromisoformat(created_at) + timedelta(hours=ttl_hours())
        ).isoformat()
        source_signal_json = json.dumps(signal.to_dict())

        conn = await self._connect()
        try:
            await conn.execute("BEGIN IMMEDIATE;")
            cur = await conn.execute(
                "INSERT INTO decisions "
                "(ticker, asset_type, action, quantity, source_signal_json, reasoning, "
                " proposal_hash, status, valid_until, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                (signal.ticker, signal.asset_type, action, qty, source_signal_json,
                 signal.reasoning, proposal_hash, valid_until, created_at),
            )
            decision_id = int(cur.lastrowid)
            await append_audit(
                conn, decision_id=decision_id, event_type="PROPOSED", actor=None,
                payload={"ticker": signal.ticker, "action": action, "quantity": qty,
                         "proposal_hash": proposal_hash},
                created_at=created_at,
            )
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            await conn.close()

        created = await self.get(decision_id)
        assert created is not None
        return created

    async def expire_stale(self) -> int:
        conn = await self._connect()
        try:
            await conn.execute("BEGIN IMMEDIATE;")
            rows = await (await conn.execute(
                "SELECT id, valid_until FROM decisions WHERE status='pending'"
            )).fetchall()
            expired = 0
            for row in rows:
                if not is_past(row["valid_until"]):
                    continue
                ts = now_utc_iso()
                await conn.execute(
                    "UPDATE decisions SET status='expired' WHERE id=? AND status='pending'",
                    (row["id"],),
                )
                await append_audit(
                    conn, decision_id=row["id"], event_type="EXPIRED", actor=None,
                    payload={"reason": "valid_until passed"}, created_at=ts,
                )
                expired += 1
            await conn.commit()
            return expired
        except Exception:
            await conn.rollback()
            raise
        finally:
            await conn.close()

    async def list(self, status: str | None = None) -> list[ProposedAction]:
        await self.expire_stale()
        conn = await self._connect()
        try:
            if status is not None:
                cur = await conn.execute(
                    "SELECT * FROM decisions WHERE status=? ORDER BY id DESC", (status,)
                )
            else:
                cur = await conn.execute("SELECT * FROM decisions ORDER BY id DESC")
            rows = await cur.fetchall()
            return [ProposedAction.from_row(r) for r in rows]
        finally:
            await conn.close()

    async def approve(self, decision_id: int, actor: str) -> ProposedAction:
        conn = await self._connect()
        try:
            await conn.execute("BEGIN IMMEDIATE;")
            row = await self._get_row(conn, decision_id)
            if row is None:
                raise DecisionError(
                    "DECISION_NOT_FOUND", f"No decision with id {decision_id}", 404
                )
            if row["status"] == "pending" and is_past(row["valid_until"]):
                ts = now_utc_iso()
                await conn.execute(
                    "UPDATE decisions SET status='expired' WHERE id=? AND status='pending'",
                    (decision_id,),
                )
                await append_audit(
                    conn, decision_id=decision_id, event_type="EXPIRED", actor=None,
                    payload={"reason": "valid_until passed"}, created_at=ts,
                )
                await conn.commit()
                raise DecisionError(
                    "DECISION_EXPIRED", "Proposal is stale; cannot approve", 409
                )
            if row["status"] != "pending":
                raise DecisionError(
                    "DECISION_NOT_PENDING",
                    f"Cannot approve a {row['status']} decision", 409,
                )
            ts = now_utc_iso()
            await conn.execute(
                "UPDATE decisions SET status='approved', "
                "approved_proposal_hash=proposal_hash, actor=?, decided_at=? WHERE id=?",
                (actor, ts, decision_id),
            )
            await append_audit(
                conn, decision_id=decision_id, event_type="APPROVED", actor=actor,
                payload={"approved_proposal_hash": row["proposal_hash"]}, created_at=ts,
            )
            await conn.commit()
        except DecisionError:
            try:
                await conn.rollback()
            except Exception:
                pass
            raise
        except Exception:
            try:
                await conn.rollback()
            except Exception:
                pass
            raise
        finally:
            await conn.close()

        result = await self.get(decision_id)
        assert result is not None
        return result

    async def reject(self, decision_id: int, actor: str, note: str = "") -> ProposedAction:
        conn = await self._connect()
        try:
            await conn.execute("BEGIN IMMEDIATE;")
            row = await self._get_row(conn, decision_id)
            if row is None:
                raise DecisionError(
                    "DECISION_NOT_FOUND", f"No decision with id {decision_id}", 404
                )
            if row["status"] != "pending":
                raise DecisionError(
                    "DECISION_NOT_PENDING",
                    f"Cannot reject a {row['status']} decision", 409,
                )
            ts = now_utc_iso()
            await conn.execute(
                "UPDATE decisions SET status='rejected', actor=?, decided_at=?, "
                "decision_note=? WHERE id=?",
                (actor, ts, note, decision_id),
            )
            await append_audit(
                conn, decision_id=decision_id, event_type="REJECTED", actor=actor,
                payload={"note": note}, created_at=ts,
            )
            await conn.commit()
        except DecisionError:
            try:
                await conn.rollback()
            except Exception:
                pass
            raise
        finally:
            await conn.close()

        result = await self.get(decision_id)
        assert result is not None
        return result

    async def _record_failure(self, decision_id: int, error: str) -> None:
        conn = await self._connect()
        try:
            await conn.execute("BEGIN IMMEDIATE;")
            await append_audit(
                conn, decision_id=decision_id, event_type="FAILED", actor=None,
                payload={"error": error}, created_at=now_utc_iso(),
            )
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            await conn.close()

    async def execute(
        self, decision_id: int, adapter: ExecutionAdapter
    ) -> ProposedAction:
        # Friendly pre-check (no lock) for not-found / HOLD.
        pre = await self.get(decision_id)
        if pre is None:
            raise DecisionError(
                "DECISION_NOT_FOUND", f"No decision with id {decision_id}", 404
            )
        if pre.action == "HOLD":
            raise DecisionError(
                "HOLD_NOT_EXECUTABLE", "HOLD proposals are not executable", 400
            )

        conn = await self._connect()
        try:
            await conn.execute("BEGIN IMMEDIATE;")  # write lock taken up front
            row = await self._get_row(conn, decision_id)
            if row is None:
                raise DecisionError(
                    "DECISION_NOT_FOUND", f"No decision with id {decision_id}", 404
                )
            if row["status"] == "executed":
                raise DecisionError(
                    "DECISION_ALREADY_EXECUTED", "Decision already executed", 409
                )
            if row["status"] != "approved":
                raise DecisionError(
                    "DECISION_NOT_APPROVED", "Decision is not approved", 409
                )
            if is_past(row["valid_until"]):
                raise DecisionError(
                    "DECISION_EXPIRED", "Approved proposal is stale", 409
                )
            # The approval is bound to the EXACT proposal: recompute the hash
            # from the row's current binding fields and require it to match the
            # hash captured at approval. This catches post-approval tampering of
            # ticker/action/quantity/source_signal even if the cached
            # proposal_hash column was not updated (the column comparison alone
            # would miss that). Both checks together = defense in depth.
            if (
                row["approved_proposal_hash"] != row["proposal_hash"]
                or recompute_proposal_hash_from_row(row) != row["approved_proposal_hash"]
            ):
                raise DecisionError(
                    "PROPOSAL_HASH_MISMATCH",
                    "Approval is not bound to the current proposal", 409,
                )

            order = Order(
                ticker=row["ticker"], asset_type=row["asset_type"],
                side=OrderSide(row["action"]), quantity=row["quantity"],
            )
            try:
                report = await adapter.submit(order)
            except Exception as exc:  # adapter failure: no state change
                await conn.rollback()
                await self._record_failure(decision_id, str(exc))
                raise DecisionError(
                    "EXECUTION_FAILED", f"Execution adapter failed: {exc}", 500
                )

            ts = now_utc_iso()
            try:
                cur = await conn.execute(
                    "UPDATE decisions SET status='executed', execution_report_json=?, "
                    "decided_at=? WHERE id=? AND status='approved' "
                    "AND approved_proposal_hash=proposal_hash",
                    (json.dumps(report.to_dict()), ts, decision_id),
                )
                if cur.rowcount != 1:  # lost race / changed under us
                    await conn.rollback()
                    raise DecisionError(
                        "DECISION_ALREADY_EXECUTED", "Execution race lost", 409
                    )
                await append_audit(
                    conn, decision_id=decision_id, event_type="EXECUTED",
                    actor=row["actor"],
                    payload={"fill_price": report.fill_price, "quantity": report.quantity,
                             "venue": report.venue, "status": report.status},
                    created_at=ts,
                )
                await conn.commit()
            except DecisionError:
                raise
            except Exception as exc:
                # The (paper) fill already happened but persisting the executed
                # state failed. Roll back the half-written tx and record the fill
                # in a separate FAILED audit so it is never silently lost. The
                # decision stays 'approved'; because a retry would re-fill, a real
                # (non-paper) ExecutionAdapter MUST use an idempotency key
                # (paper-only milestone trade-off — see execution/adapter.py).
                await conn.rollback()
                await self._record_failure(
                    decision_id,
                    f"paper fill succeeded but recording executed state failed: {exc}; "
                    f"report={json.dumps(report.to_dict())}",
                )
                raise DecisionError(
                    "EXECUTION_RECORD_FAILED",
                    f"Fill occurred but could not be recorded: {exc}", 500
                )
        except DecisionError:
            try:
                await conn.rollback()
            except Exception:
                pass
            raise
        finally:
            await conn.close()

        result = await self.get(decision_id)
        assert result is not None
        return result
