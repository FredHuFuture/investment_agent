"""Tests for UI-03 daemon wiring: alert_rules.enabled respected by checker/monitor (04-02 plan).

Tests validate:
- Disabled rule type produces no alerts of that type from check_position
- Backward compat: no enabled_rule_types kwarg fires all rules
- _load_enabled_rules returns None when alert_rules table missing
- Hardcoded rules seeded by init_db (via _seed_default_alert_rules)
"""
from __future__ import annotations

import pytest
import pytest_asyncio


def _make_position(
    ticker: str = "AAPL",
    avg_cost: float = 120.0,
    quantity: float = 10.0,
    entry_date: str = "2020-01-01",  # deliberately old to trigger TIME_OVERRUN
    expected_hold_days: int = 10,
) -> object:
    from portfolio.models import Position

    pos = Position(
        ticker=ticker,
        asset_type="stock",
        quantity=quantity,
        avg_cost=avg_cost,
        entry_date=entry_date,
        expected_hold_days=expected_hold_days,
    )
    return pos


@pytest.mark.asyncio
async def test_disabled_rule_does_not_fire() -> None:
    """check_position with STOP_LOSS_HIT excluded produces no STOP_LOSS_HIT alerts."""
    from monitoring.checker import check_position

    pos = _make_position(avg_cost=120.0)
    # Price below stop_loss — would normally fire STOP_LOSS_HIT
    alerts = check_position(
        pos,
        current_price=90.0,
        expected_stop_loss=100.0,
        enabled_rule_types={"TARGET_HIT", "TIME_OVERRUN", "SIGNIFICANT_LOSS", "SIGNIFICANT_GAIN"},
    )
    types = {a.alert_type for a in alerts}
    assert "STOP_LOSS_HIT" not in types, "STOP_LOSS_HIT should be suppressed when excluded from enabled_rule_types"
    # SIGNIFICANT_LOSS should still fire (90 vs 120 = -25%)
    assert "SIGNIFICANT_LOSS" in types, "SIGNIFICANT_LOSS should fire even when STOP_LOSS_HIT is disabled"


@pytest.mark.asyncio
async def test_all_enabled_by_default_backward_compat() -> None:
    """check_position with no enabled_rule_types kwarg fires all applicable rules."""
    from monitoring.checker import check_position

    pos = _make_position(avg_cost=120.0)
    # Price below stop_loss — STOP_LOSS_HIT should fire with default (None)
    alerts = check_position(
        pos,
        current_price=90.0,
        expected_stop_loss=100.0,
    )
    types = {a.alert_type for a in alerts}
    assert "STOP_LOSS_HIT" in types, "STOP_LOSS_HIT should fire when enabled_rule_types=None (default)"


@pytest.mark.asyncio
async def test_empty_set_suppresses_all_rules() -> None:
    """check_position with empty set fires no alerts at all."""
    from monitoring.checker import check_position

    pos = _make_position(avg_cost=120.0)
    alerts = check_position(
        pos,
        current_price=90.0,
        expected_stop_loss=100.0,
        expected_target_price=150.0,
        enabled_rule_types=set(),
    )
    assert alerts == [], "Empty enabled_rule_types should suppress all alerts"


@pytest.mark.asyncio
async def test_load_enabled_rules_returns_none_when_table_missing(tmp_path) -> None:
    """_load_enabled_rules returns None gracefully when alert_rules table absent."""
    import aiosqlite
    from monitoring.monitor import _load_enabled_rules

    db_file = tmp_path / "bare.db"
    # Create DB without init_db — no alert_rules table
    async with aiosqlite.connect(str(db_file)) as conn:
        # Just create a minimal table to make the DB valid
        await conn.execute("CREATE TABLE dummy (id INTEGER PRIMARY KEY)")
        await conn.commit()

        result = await _load_enabled_rules(conn)

    assert result is None, "_load_enabled_rules should return None when alert_rules table missing"


@pytest.mark.asyncio
async def test_hardcoded_rules_seeded_on_init_db(tmp_path) -> None:
    """init_db seeds all 5 hardcoded rule types into alert_rules."""
    import aiosqlite
    from db.database import init_db

    db_file = tmp_path / "test.db"
    await init_db(db_file)

    expected_rules = {
        "STOP_LOSS_HIT", "TARGET_HIT", "TIME_OVERRUN", "SIGNIFICANT_LOSS", "SIGNIFICANT_GAIN"
    }

    async with aiosqlite.connect(str(db_file)) as conn:
        rows = await (
            await conn.execute(
                "SELECT name, metric, enabled FROM alert_rules WHERE metric = 'hardcoded'"
            )
        ).fetchall()

    seeded_names = {row[0] for row in rows}
    assert seeded_names == expected_rules, f"Missing seeded rules: {expected_rules - seeded_names}"

    for row in rows:
        assert row[2] == 1, f"Rule {row[0]} should be enabled=1 by default"


@pytest.mark.asyncio
async def test_seed_is_idempotent(tmp_path) -> None:
    """Calling init_db twice does not duplicate alert_rules rows."""
    import aiosqlite
    from db.database import init_db

    db_file = tmp_path / "test.db"
    await init_db(db_file)
    await init_db(db_file)  # second call

    async with aiosqlite.connect(str(db_file)) as conn:
        rows = await (
            await conn.execute(
                "SELECT name FROM alert_rules WHERE metric = 'hardcoded'"
            )
        ).fetchall()

    names = [row[0] for row in rows]
    assert len(names) == len(set(names)), "Duplicate alert_rules rows found after double init_db"
    assert len(names) == 5, f"Expected 5 seeded rules, got {len(names)}"


@pytest.mark.asyncio
async def test_load_enabled_rules_returns_set_from_seeded_db(tmp_path) -> None:
    """_load_enabled_rules returns all 5 rule names from a seeded DB."""
    import aiosqlite
    from db.database import init_db
    from monitoring.monitor import _load_enabled_rules

    db_file = tmp_path / "test.db"
    await init_db(db_file)

    async with aiosqlite.connect(str(db_file)) as conn:
        result = await _load_enabled_rules(conn)

    expected = {"STOP_LOSS_HIT", "TARGET_HIT", "TIME_OVERRUN", "SIGNIFICANT_LOSS", "SIGNIFICANT_GAIN"}
    assert result == expected, f"Expected {expected}, got {result}"


@pytest.mark.asyncio
async def test_load_enabled_rules_respects_disabled_flag(tmp_path) -> None:
    """_load_enabled_rules excludes rules with enabled=0."""
    import aiosqlite
    from db.database import init_db
    from monitoring.monitor import _load_enabled_rules

    db_file = tmp_path / "test.db"
    await init_db(db_file)

    # Disable STOP_LOSS_HIT
    async with aiosqlite.connect(str(db_file)) as conn:
        await conn.execute(
            "UPDATE alert_rules SET enabled=0 WHERE name='STOP_LOSS_HIT'"
        )
        await conn.commit()

        result = await _load_enabled_rules(conn)

    assert result is not None
    assert "STOP_LOSS_HIT" not in result
    assert "SIGNIFICANT_LOSS" in result
