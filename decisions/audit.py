# decisions/audit.py
"""Append-only, globally hash-chained audit trail for decisions.

Each row links to the previous row's entry_hash. The payload embeds row
identity (decision_id, event_type, actor, created_at) so rows cannot be
reordered or reattributed without breaking verification.

Transaction contract: append_audit assumes the CALLER has already issued
``BEGIN IMMEDIATE`` and will commit. This serializes the read-latest-then-insert
sequence under SQLite's write lock so concurrent appends cannot fork the chain.
"""
from __future__ import annotations

import json
from typing import Any

import aiosqlite

from decisions.models import GENESIS_HASH, canonical_json, sha256_hex


async def append_audit(
    conn: aiosqlite.Connection,
    *,
    decision_id: int,
    event_type: str,
    actor: str | None,
    payload: dict[str, Any],
    created_at: str,
) -> str:
    full_payload = {
        "decision_id": decision_id,
        "event_type": event_type,
        "actor": actor,
        "created_at": created_at,
        **payload,
    }
    payload_json = canonical_json(full_payload)

    row = await (
        await conn.execute(
            "SELECT entry_hash FROM decision_audit ORDER BY id DESC LIMIT 1"
        )
    ).fetchone()
    prev_hash = row[0] if row is not None else GENESIS_HASH
    entry_hash = sha256_hex(prev_hash + payload_json)

    await conn.execute(
        "INSERT INTO decision_audit "
        "(decision_id, event_type, actor, payload_json, prev_hash, entry_hash, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (decision_id, event_type, actor, payload_json, prev_hash, entry_hash, created_at),
    )
    return entry_hash


async def verify_chain(conn: aiosqlite.Connection) -> dict[str, Any]:
    cur = await conn.execute(
        "SELECT id, decision_id, event_type, actor, payload_json, prev_hash, "
        "entry_hash, created_at FROM decision_audit ORDER BY id ASC"
    )
    rows = await cur.fetchall()
    prev = GENESIS_HASH
    checked = 0
    for row in rows:
        checked += 1
        row_id = row["id"]
        payload_json = row["payload_json"]
        prev_hash = row["prev_hash"]
        entry_hash = row["entry_hash"]
        if prev_hash != prev:
            return {
                "valid": False, "checked": checked, "broken_at_id": row_id,
                "reason": "prev_hash does not link to previous entry_hash",
            }
        if sha256_hex(prev_hash + payload_json) != entry_hash:
            return {
                "valid": False, "checked": checked, "broken_at_id": row_id,
                "reason": "entry_hash does not match recomputed hash (payload tampered)",
            }
        try:
            payload = json.loads(payload_json)
        except Exception:
            return {
                "valid": False, "checked": checked, "broken_at_id": row_id,
                "reason": "payload_json is not valid JSON",
            }
        if (payload.get("decision_id") != row["decision_id"]
                or payload.get("event_type") != row["event_type"]
                or payload.get("actor") != row["actor"]
                or payload.get("created_at") != row["created_at"]):
            return {
                "valid": False, "checked": checked, "broken_at_id": row_id,
                "reason": "audit columns do not match hashed payload (column tampered)",
            }
        prev = entry_hash
    return {"valid": True, "checked": checked, "broken_at_id": None, "reason": None}
