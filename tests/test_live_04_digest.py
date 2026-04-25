"""Tests for engine/digest.py — LIVE-04 weekly digest renderer.

Test coverage:
  1. test_digest_has_all_5_h2_headers   — empty DB → all 5 H2 headers present
  2. test_digest_perf_section_empty      — data_points < 2 → "No portfolio snapshots" note
  3. test_digest_signal_flips_grouped_by_ticker — AAPL HOLD→BUY → section (b) row
  4. test_digest_icir_movers_from_drift_log    — triggered=1 → "DRIFT DETECTED"
  5. test_digest_icir_empty_message           — empty drift_log → EMPTY_ICIR_MSG
  6. test_digest_open_alerts_only_unacknowledged — ack=0 shown, ack=1 not shown
  7. test_digest_pii_clamp_strips_dollar_and_thesis — no $ in rendered body
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import aiosqlite
import pytest

from engine.digest import (
    EMPTY_ICIR_MSG,
    HEADER_ACTIONS,
    HEADER_ALERTS,
    HEADER_FLIPS,
    HEADER_ICIR,
    HEADER_PERF,
    render_weekly_digest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def empty_db(tmp_path):
    """Initialized empty DB with all schema tables."""
    db_path = str(tmp_path / "test_digest.db")
    from db.database import init_db
    await init_db(db_path)
    return db_path


@pytest.fixture
async def seeded_db(tmp_path):
    """DB with signal_history, drift_log, and monitoring_alerts seeded."""
    db_path = str(tmp_path / "test_digest_seeded.db")
    from db.database import init_db
    await init_db(db_path)
    return db_path


# ---------------------------------------------------------------------------
# Test 1: All 5 H2 headers present in empty DB output
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_digest_has_all_5_h2_headers(empty_db):
    """render_weekly_digest on empty DB returns string with all 5 required H2 headers."""
    body = await render_weekly_digest(empty_db)

    assert isinstance(body, str)
    assert HEADER_PERF in body
    assert HEADER_FLIPS in body
    assert HEADER_ICIR in body
    assert HEADER_ALERTS in body
    assert HEADER_ACTIONS in body

    # Verify ordering: each header appears exactly once, in order
    positions = [
        body.index(HEADER_PERF),
        body.index(HEADER_FLIPS),
        body.index(HEADER_ICIR),
        body.index(HEADER_ALERTS),
        body.index(HEADER_ACTIONS),
    ]
    assert positions == sorted(positions), "H2 headers must appear in document order"


# ---------------------------------------------------------------------------
# Test 2: Performance section empty — portfolio has no snapshots
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_digest_perf_section_empty(empty_db):
    """With no portfolio snapshots, section (a) shows 'No portfolio snapshots' note."""
    body = await render_weekly_digest(empty_db)
    # When data_points < 2, _render_perf returns the empty fallback message
    assert "No portfolio snapshots" in body or "No portfolio" in body


# ---------------------------------------------------------------------------
# Test 3: Signal flips grouped by ticker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_digest_signal_flips_grouped_by_ticker(seeded_db):
    """Seed 2 AAPL rows with HOLD then BUY → section (b) row mentions AAPL HOLD→BUY."""
    now = datetime.now(timezone.utc)
    day1 = (now - timedelta(days=5)).isoformat()
    day2 = (now - timedelta(days=1)).isoformat()

    async with aiosqlite.connect(seeded_db) as conn:
        await conn.execute(
            """
            INSERT INTO signal_history
              (ticker, asset_type, final_signal, final_confidence,
               raw_score, consensus_score, agent_signals_json, reasoning, created_at)
            VALUES (?, 'stock', 'HOLD', 60.0, 0.1, 0.1, '{}', 'test', ?)
            """,
            ("AAPL", day1),
        )
        await conn.execute(
            """
            INSERT INTO signal_history
              (ticker, asset_type, final_signal, final_confidence,
               raw_score, consensus_score, agent_signals_json, reasoning, created_at)
            VALUES (?, 'stock', 'BUY', 75.0, 0.5, 0.5, '{}', 'test', ?)
            """,
            ("AAPL", day2),
        )
        await conn.commit()

    body = await render_weekly_digest(seeded_db)
    section_b = body[body.index(HEADER_FLIPS):]
    # Find end of section
    next_h2 = section_b.find("## ", 3)
    if next_h2 > 0:
        section_b = section_b[:next_h2]

    assert "AAPL" in section_b
    assert "HOLD" in section_b
    assert "BUY" in section_b


# ---------------------------------------------------------------------------
# Test 4: IC-IR movers from drift_log
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_digest_icir_movers_from_drift_log(seeded_db):
    """Seed drift_log with triggered=1 TechnicalAgent row → section (c) shows DRIFT DETECTED."""
    now = datetime.now(timezone.utc)
    evaluated_at = (now - timedelta(days=2)).isoformat()

    async with aiosqlite.connect(seeded_db) as conn:
        await conn.execute(
            """
            INSERT INTO drift_log
              (agent_name, asset_type, evaluated_at, current_icir, avg_icir_60d,
               delta_pct, threshold_type, triggered, preliminary_threshold,
               weight_before, weight_after)
            VALUES (?, 'stock', ?, 0.30, 0.55, -24.0, 'drop_pct', 1, 0, 0.25, 0.14)
            """,
            ("TechnicalAgent", evaluated_at),
        )
        await conn.commit()

    body = await render_weekly_digest(seeded_db)
    section_c = body[body.index(HEADER_ICIR):]
    next_h2 = section_c.find("## ", 3)
    if next_h2 > 0:
        section_c = section_c[:next_h2]

    assert "TechnicalAgent" in section_c
    assert "DRIFT DETECTED" in section_c
    assert "-24.0%" in section_c or "-24" in section_c
    assert "stock" in section_c


# ---------------------------------------------------------------------------
# Test 5: IC-IR empty — empty drift_log shows EMPTY_ICIR_MSG
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_digest_icir_empty_message(empty_db):
    """Empty drift_log → section (c) contains the EMPTY_ICIR_MSG constant."""
    body = await render_weekly_digest(empty_db)
    assert EMPTY_ICIR_MSG in body


# ---------------------------------------------------------------------------
# Test 6: Open alerts — only unacknowledged (ack=0) appear
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_digest_open_alerts_only_unacknowledged(seeded_db):
    """Seed two alerts: one ack=0 (NVDA), one ack=1 (MSFT) → only NVDA in section (d)."""
    now = datetime.now(timezone.utc)
    created = (now - timedelta(days=3)).isoformat()

    async with aiosqlite.connect(seeded_db) as conn:
        # Unacknowledged — should appear
        await conn.execute(
            """
            INSERT INTO monitoring_alerts
              (ticker, alert_type, severity, message, recommended_action,
               acknowledged, created_at)
            VALUES ('NVDA', 'SIGNAL_REVERSAL', 'HIGH',
                    'Signal flipped to SELL', 'Review', 0, ?)
            """,
            (created,),
        )
        # Acknowledged — should NOT appear
        await conn.execute(
            """
            INSERT INTO monitoring_alerts
              (ticker, alert_type, severity, message, recommended_action,
               acknowledged, created_at)
            VALUES ('MSFT', 'SIGNAL_REVERSAL', 'HIGH',
                    'Signal flipped to SELL', 'Review', 1, ?)
            """,
            (created,),
        )
        await conn.commit()

    body = await render_weekly_digest(seeded_db)
    section_d = body[body.index(HEADER_ALERTS):]
    next_h2 = section_d.find("## ", 3)
    if next_h2 > 0:
        section_d = section_d[:next_h2]

    assert "NVDA" in section_d
    assert "MSFT" not in section_d


# ---------------------------------------------------------------------------
# Test 7: PII clamp — no dollar amounts, no thesis text in body
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_digest_pii_clamp_strips_dollar_and_thesis(seeded_db):
    """Alert with dollar-amount message → rendered body has no $NNN patterns."""
    now = datetime.now(timezone.utc)
    created = (now - timedelta(days=1)).isoformat()

    async with aiosqlite.connect(seeded_db) as conn:
        await conn.execute(
            """
            INSERT INTO monitoring_alerts
              (ticker, alert_type, severity, message, recommended_action,
               acknowledged, created_at)
            VALUES ('AAPL', 'SIGNAL_REVERSAL', 'HIGH',
                    'Position lost $1,234,567 -- thesis: My secret thesis', 'Review', 0, ?)
            """,
            (created,),
        )
        await conn.commit()

    body = await render_weekly_digest(seeded_db)

    # PII clamp assertions
    assert "$1,234,567" not in body, "Raw dollar amount must be stripped from body"
    assert "secret thesis" not in body, "Thesis text must not appear in body"

    # Regex sweep: no $NNNNN patterns remain
    dollar_matches = re.findall(r"\$[0-9,]+\.?[0-9]*", body)
    assert dollar_matches == [], (
        f"Dollar amount pattern found in digest body: {dollar_matches}"
    )


# ---------------------------------------------------------------------------
# Test 8: WR-03 regression — "position" word must NOT be redacted by _clamp_pii
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_digest_pii_clamp_position_word_not_redacted(seeded_db):
    """WR-03: Alert messages containing the word 'position' must NOT be fully
    redacted. Only 'thesis' and 'secret' keywords trigger redaction.

    Before fix: _THESIS_RE matched 'position' → entire SIGNAL_REVERSAL message
    was replaced with '[redacted]', making the digest useless for operators.
    After fix: 'position' passes through; only thesis/secret content is stripped.
    """
    now = datetime.now(timezone.utc)
    created = (now - timedelta(days=1)).isoformat()

    async with aiosqlite.connect(seeded_db) as conn:
        # Typical SIGNAL_REVERSAL message from daemon/jobs.py
        await conn.execute(
            """
            INSERT INTO monitoring_alerts
              (ticker, alert_type, severity, message, recommended_action,
               acknowledged, created_at)
            VALUES ('NVDA', 'SIGNAL_REVERSAL', 'HIGH',
                    'Review position -- original signal was BUY, re-analysis now signals SELL.',
                    'Review', 0, ?)
            """,
            (created,),
        )
        # Also seed a message that DOES contain 'thesis' — should still be redacted
        await conn.execute(
            """
            INSERT INTO monitoring_alerts
              (ticker, alert_type, severity, message, recommended_action,
               acknowledged, created_at)
            VALUES ('AAPL', 'THESIS_DRIFT', 'WARNING',
                    'Thesis drift detected: original thesis was long-term growth.',
                    'Review', 0, ?)
            """,
            (created,),
        )
        await conn.commit()

    body = await render_weekly_digest(seeded_db)

    section_d = body[body.index("## ") :]  # find alerts section
    # "position" word must be preserved in the output
    assert "position" in body, (
        "The word 'position' must NOT be redacted from SIGNAL_REVERSAL alert messages"
    )
    # "BUY" and "SELL" signal words must survive (actionable content)
    assert "BUY" in body or "SELL" in body, (
        "Signal direction words must not be redacted from alert messages"
    )
    # thesis content must still be stripped
    assert "long-term growth" not in body, (
        "Thesis narrative text after 'thesis' keyword must still be redacted"
    )
