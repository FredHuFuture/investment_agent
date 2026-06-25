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
    ttl_hours,
)

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
