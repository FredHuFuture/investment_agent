from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from db.database import init_db


async def _columns(conn: aiosqlite.Connection, table: str) -> set[str]:
    info = await (await conn.execute(f"PRAGMA table_info({table});")).fetchall()
    return {row[1] for row in info}


@pytest.mark.asyncio
async def test_decisions_tables_created(tmp_path: Path) -> None:
    db_file = tmp_path / "schema.db"
    await init_db(db_file)
    async with aiosqlite.connect(db_file) as conn:
        decisions_cols = await _columns(conn, "decisions")
        assert {
            "id", "ticker", "asset_type", "action", "quantity", "source_signal_json",
            "reasoning", "proposal_hash", "status", "valid_until", "actor", "decided_at",
            "decision_note", "approved_proposal_hash", "execution_report_json", "created_at",
        } <= decisions_cols

        audit_cols = await _columns(conn, "decision_audit")
        assert {
            "id", "decision_id", "event_type", "actor", "payload_json",
            "prev_hash", "entry_hash", "created_at",
        } <= audit_cols


@pytest.mark.asyncio
async def test_decisions_action_check_constraint(tmp_path: Path) -> None:
    db_file = tmp_path / "schema2.db"
    await init_db(db_file)
    async with aiosqlite.connect(db_file) as conn:
        await conn.execute("PRAGMA foreign_keys=ON;")
        # invalid action rejected by CHECK
        try:
            await conn.execute(
                "INSERT INTO decisions (ticker, asset_type, action, source_signal_json, "
                "reasoning, proposal_hash, valid_until, created_at) "
                "VALUES ('AAPL','stock','WAT','{}','r','h','2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00')"
            )
            raised = False
        except aiosqlite.IntegrityError:
            raised = True
        assert raised, "CHECK(action) did not reject an invalid action"


@pytest.mark.asyncio
async def test_init_db_is_idempotent(tmp_path: Path) -> None:
    db_file = tmp_path / "schema3.db"
    await init_db(db_file)
    await init_db(db_file)  # must not raise
