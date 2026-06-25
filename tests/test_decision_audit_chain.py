# tests/test_decision_audit_chain.py
from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite

from db.database import init_db
from decisions.audit import append_audit, verify_chain
from decisions.models import now_utc_iso


async def _connect(db_file: Path) -> aiosqlite.Connection:
    # isolation_level=None at connect time -> manual BEGIN/COMMIT.
    # (Setting it after connect raises a cross-thread ProgrammingError.)
    conn = await aiosqlite.connect(db_file, isolation_level=None)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA busy_timeout=5000;")
    await conn.execute("PRAGMA foreign_keys=ON;")
    return conn


async def _seed_decision(conn: aiosqlite.Connection) -> int:
    await conn.execute("BEGIN IMMEDIATE;")
    cur = await conn.execute(
        "INSERT INTO decisions (ticker, asset_type, action, source_signal_json, reasoning, "
        "proposal_hash, valid_until, created_at) "
        "VALUES ('AAPL','stock','BUY','{}','r','hash','2099-01-01T00:00:00+00:00', ?)",
        (now_utc_iso(),),
    )
    did = cur.lastrowid
    await conn.commit()
    return int(did)


async def _append(conn: aiosqlite.Connection, decision_id: int, event_type: str) -> None:
    await conn.execute("BEGIN IMMEDIATE;")
    await append_audit(
        conn, decision_id=decision_id, event_type=event_type,
        actor="tester", payload={"k": event_type}, created_at=now_utc_iso(),
    )
    await conn.commit()


async def test_append_then_verify_passes(tmp_path: Path) -> None:
    db_file = tmp_path / "chain.db"
    await init_db(db_file)
    conn = await _connect(db_file)
    try:
        did = await _seed_decision(conn)
        for evt in ("PROPOSED", "APPROVED", "EXECUTED"):
            await _append(conn, did, evt)
        result = await verify_chain(conn)
        assert result["valid"] is True
        assert result["checked"] == 3
    finally:
        await conn.close()


async def test_genesis_links_to_zeroes(tmp_path: Path) -> None:
    db_file = tmp_path / "genesis.db"
    await init_db(db_file)
    conn = await _connect(db_file)
    try:
        did = await _seed_decision(conn)
        await _append(conn, did, "PROPOSED")
        row = await (await conn.execute(
            "SELECT prev_hash FROM decision_audit ORDER BY id ASC LIMIT 1"
        )).fetchone()
        assert row["prev_hash"] == "0" * 64
    finally:
        await conn.close()


async def test_mutating_past_payload_breaks_chain(tmp_path: Path) -> None:
    db_file = tmp_path / "tamper.db"
    await init_db(db_file)
    conn = await _connect(db_file)
    try:
        did = await _seed_decision(conn)
        for evt in ("PROPOSED", "APPROVED", "EXECUTED"):
            await _append(conn, did, evt)
        # Tamper with the middle row's payload (simulating an attacker edit).
        await conn.execute("BEGIN IMMEDIATE;")
        await conn.execute(
            "UPDATE decision_audit SET payload_json='{\"k\":\"FORGED\"}' WHERE id=2"
        )
        await conn.commit()
        result = await verify_chain(conn)
        assert result["valid"] is False
        assert result["broken_at_id"] == 2
    finally:
        await conn.close()


async def test_mutating_identity_column_breaks_chain(tmp_path: Path) -> None:
    db_file = tmp_path / "coltamper.db"
    await init_db(db_file)
    conn = await _connect(db_file)
    try:
        did = await _seed_decision(conn)
        for evt in ("PROPOSED", "APPROVED", "EXECUTED"):
            await _append(conn, did, evt)
        # Rewrite a DISPLAYED column without touching payload_json -> hash still
        # matches, but the column no longer agrees with the hashed payload.
        await conn.execute("BEGIN IMMEDIATE;")
        await conn.execute("UPDATE decision_audit SET actor='FORGED' WHERE id=2")
        await conn.commit()
        result = await verify_chain(conn)
        assert result["valid"] is False
        assert result["broken_at_id"] == 2
        assert "column" in result["reason"].lower()
    finally:
        await conn.close()


async def test_concurrent_appends_keep_chain_intact(tmp_path: Path) -> None:
    db_file = tmp_path / "concurrent.db"
    await init_db(db_file)
    seed_conn = await _connect(db_file)
    try:
        did = await _seed_decision(seed_conn)
    finally:
        await seed_conn.close()

    async def worker(n: int) -> None:
        conn = await _connect(db_file)
        try:
            await _append(conn, did, "PROPOSED")
        finally:
            await conn.close()

    await asyncio.gather(*(worker(i) for i in range(5)))

    verify_conn = await _connect(db_file)
    try:
        result = await verify_chain(verify_conn)
        assert result["valid"] is True
        assert result["checked"] == 5
    finally:
        await verify_conn.close()
