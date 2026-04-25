"""Tests for AN-02: drift detector — DDL, preliminary flag, triggered logic,
auto-scale, and never-zero-all guard.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import aiosqlite
import pytest

from db.database import init_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_agent_weights(db_path: str, weights: dict) -> None:
    """Seed agent_weights with custom values for testing.

    weights: {(agent_name, asset_type): weight}
    """
    async with aiosqlite.connect(db_path) as conn:
        # Clear existing weights for the test
        await conn.execute("DELETE FROM agent_weights")
        for (agent, asset_type), w in weights.items():
            await conn.execute(
                """
                INSERT INTO agent_weights (agent_name, asset_type, weight, source, manual_override, excluded)
                VALUES (?, ?, ?, 'default', 0, 0)
                """,
                (agent, asset_type, w),
            )
        await conn.commit()


async def _seed_drift_log_rows(db_path: str, agent: str, asset_type: str, icir_values: list[float]) -> None:
    """Seed drift_log with historical IC-IR values for 60d baseline testing."""
    async with aiosqlite.connect(db_path) as conn:
        for i, icir in enumerate(icir_values):
            ts = f"2026-03-{(i % 28) + 1:02d}T12:00:00Z"
            await conn.execute(
                """
                INSERT INTO drift_log (agent_name, asset_type, evaluated_at, current_icir,
                    threshold_type, triggered, preliminary_threshold)
                VALUES (?, ?, ?, ?, 'none', 0, 0)
                """,
                (agent, asset_type, ts, icir),
            )
        await conn.commit()


# ---------------------------------------------------------------------------
# DDL test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_drift_log_ddl_idempotent(tmp_path):
    """drift_log table is created by init_db and DDL is idempotent (IF NOT EXISTS)."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    # Verify table exists
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='drift_log'"
            )
        ).fetchone()
    assert row is not None, "drift_log table must exist after init_db"

    # Second init_db must not raise (idempotent)
    await init_db(db_path)

    # Verify columns
    async with aiosqlite.connect(db_path) as conn:
        cols = await (await conn.execute("PRAGMA table_info(drift_log)")).fetchall()
    col_names = {c[1] for c in cols}
    expected = {
        "id", "agent_name", "asset_type", "evaluated_at",
        "current_icir", "avg_icir_60d", "delta_pct", "threshold_type",
        "triggered", "preliminary_threshold", "weight_before", "weight_after",
        "created_at",
    }
    assert expected <= col_names, f"Missing columns: {expected - col_names}"


@pytest.mark.asyncio
async def test_drift_log_index_created(tmp_path):
    """Composite index on (agent_name, asset_type, evaluated_at) must exist."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name='idx_drift_log_agent_asset_evaluated'"
            )
        ).fetchone()
    assert row is not None, "drift_log composite index must exist"


# ---------------------------------------------------------------------------
# Preliminary threshold flag
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preliminary_flag_when_corpus_empty(tmp_path):
    """evaluate_drift sets preliminary_threshold=True when backtest corpus is empty."""
    from engine.drift_detector import evaluate_drift

    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    entries = await evaluate_drift(db_path)

    # With empty corpus, ALL entries must be preliminary
    assert len(entries) > 0, "evaluate_drift must return at least one entry"
    for entry in entries:
        assert entry["preliminary_threshold"] is True, (
            f"{entry['agent_name']}/{entry['asset_type']} must be preliminary "
            f"when corpus is empty"
        )
        assert entry["triggered"] is False, (
            "No drift trigger fires when preliminary_threshold=True"
        )


@pytest.mark.asyncio
async def test_preliminary_threshold_constant_value():
    """MIN_SAMPLES_FOR_REAL_THRESHOLD must be 60 (plan spec)."""
    from engine.drift_detector import MIN_SAMPLES_FOR_REAL_THRESHOLD
    assert MIN_SAMPLES_FOR_REAL_THRESHOLD == 60


# ---------------------------------------------------------------------------
# Triggered logic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_drift_triggered_on_pct_drop(tmp_path, monkeypatch):
    """triggered=True when IC-IR drops > 20% from 60-day average."""
    from engine import drift_detector

    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    agent = "TechnicalAgent"
    asset_type = "stock"

    # Seed 60-day history with consistent IC-IR of 0.80
    await _seed_drift_log_rows(db_path, agent, asset_type, [0.80] * 60)

    # Seed agent_weights
    await _seed_agent_weights(db_path, {(agent, asset_type): 0.4})

    # Override compute_rolling_ic to return 60 valid IC values (exits preliminary)
    # and simulate a current IC-IR of 0.55 (31% drop from 0.80)
    async def mock_compute_rolling_ic(self, agent_name, horizon="5d", window=60):
        # Return enough valid ICs so compute_icir produces 0.55
        # compute_icir = mean/std; we fake 60 values around 0.55
        import statistics
        vals = [0.55] * 60
        # mean=0.55, stdev would be 0 → returns None; use slight variation
        vals[0] = 0.56
        vals[1] = 0.54
        return 0.55, vals

    # Override compute_icir to return 0.55 (below 0.80 * 0.80 = 0.64 threshold)
    original_compute_icir = drift_detector.SignalTracker if hasattr(drift_detector, 'SignalTracker') else None

    from tracking.tracker import SignalTracker
    original_icir = SignalTracker.compute_icir

    @staticmethod
    def mock_icir(rolling_ics):
        valid = [ic for ic in rolling_ics if ic is not None]
        if len(valid) >= 60:
            return 0.55  # simulate degraded IC-IR
        return None

    monkeypatch.setattr(SignalTracker, "compute_rolling_ic", mock_compute_rolling_ic)
    monkeypatch.setattr(SignalTracker, "compute_icir", mock_icir)

    entries = await drift_detector.evaluate_drift(db_path)
    tech_stock = next(
        (e for e in entries if e["agent_name"] == agent and e["asset_type"] == asset_type),
        None,
    )
    assert tech_stock is not None
    assert tech_stock["preliminary_threshold"] is False, "Should exit preliminary with 60 history rows"
    assert tech_stock["triggered"] is True, (
        f"Expected triggered=True for IC-IR 0.55 vs avg 0.80 (drop={((0.55-0.80)/0.80*100):.1f}%)"
    )
    assert tech_stock["threshold_type"] == "drop_pct"


@pytest.mark.asyncio
async def test_drift_triggered_on_absolute_floor(tmp_path, monkeypatch):
    """triggered=True when IC-IR < ICIR_FLOOR (0.5) regardless of delta."""
    from engine import drift_detector
    from engine.drift_detector import ICIR_FLOOR
    from tracking.tracker import SignalTracker

    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    agent = "MacroAgent"
    asset_type = "stock"

    # 60d history at 0.45 (already below floor, avg matches — pct_drop won't trigger)
    await _seed_drift_log_rows(db_path, agent, asset_type, [0.45] * 60)
    await _seed_agent_weights(db_path, {(agent, asset_type): 0.3})

    async def mock_compute_rolling_ic(self, agent_name, horizon="5d", window=60):
        vals = [0.45] * 60
        vals[0] = 0.46
        vals[1] = 0.44
        return 0.45, vals

    @staticmethod
    def mock_icir(rolling_ics):
        valid = [ic for ic in rolling_ics if ic is not None]
        if len(valid) >= 60:
            return 0.40  # below ICIR_FLOOR
        return None

    monkeypatch.setattr(SignalTracker, "compute_rolling_ic", mock_compute_rolling_ic)
    monkeypatch.setattr(SignalTracker, "compute_icir", mock_icir)

    entries = await drift_detector.evaluate_drift(db_path)
    macro_stock = next(
        (e for e in entries if e["agent_name"] == agent and e["asset_type"] == asset_type),
        None,
    )
    assert macro_stock is not None
    assert macro_stock["triggered"] is True
    # absolute_low triggers when floor condition is met
    assert macro_stock["threshold_type"] in ("absolute_low", "drop_pct")


# ---------------------------------------------------------------------------
# Auto-scale weight test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weight_scale_writes_to_agent_weights(tmp_path):
    """_apply_drift_scale UPSERTs new weight with source='ic_ir' where manual_override=0."""
    from engine.drift_detector import _apply_drift_scale

    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    # Seed a simple stock scenario: TechnicalAgent=0.6, MacroAgent=0.4
    await _seed_agent_weights(db_path, {
        ("TechnicalAgent", "stock"): 0.6,
        ("MacroAgent", "stock"): 0.4,
    })

    # Scale TechnicalAgent with IC-IR = 1.0 (factor=0.5 since divisor=2.0)
    new_w = await _apply_drift_scale(db_path, "TechnicalAgent", "stock", current_icir=1.0)

    assert new_w is not None, "Should return new weight"

    # Verify weights were updated in DB
    async with aiosqlite.connect(db_path) as conn:
        rows = await (
            await conn.execute(
                "SELECT agent_name, weight, source FROM agent_weights WHERE asset_type='stock'"
            )
        ).fetchall()

    weights_map = {r[0]: (r[1], r[2]) for r in rows}
    assert "TechnicalAgent" in weights_map
    assert weights_map["TechnicalAgent"][1] == "ic_ir", "source must be 'ic_ir'"
    # Sum must be close to 1.0 (renormalized)
    total = sum(r[0] for r in weights_map.values())
    assert abs(total - 1.0) < 1e-4, f"Weights must sum to 1.0 after renorm, got {total}"


@pytest.mark.asyncio
async def test_manual_override_preserved_during_scale(tmp_path):
    """Agent with manual_override=1 must NOT have its weight changed by drift scale."""
    from engine.drift_detector import _apply_drift_scale

    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    # Seed: TechnicalAgent with manual_override=1 (user override), MacroAgent without
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("DELETE FROM agent_weights")
        await conn.execute(
            "INSERT INTO agent_weights (agent_name, asset_type, weight, source, manual_override, excluded) "
            "VALUES ('TechnicalAgent', 'stock', 0.7, 'manual', 1, 0)"
        )
        await conn.execute(
            "INSERT INTO agent_weights (agent_name, asset_type, weight, source, manual_override, excluded) "
            "VALUES ('MacroAgent', 'stock', 0.3, 'default', 0, 0)"
        )
        await conn.commit()

    # Scale MacroAgent
    await _apply_drift_scale(db_path, "MacroAgent", "stock", current_icir=0.8)

    # TechnicalAgent weight should be unchanged (manual_override=1 guard)
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT weight, manual_override FROM agent_weights "
                "WHERE agent_name='TechnicalAgent' AND asset_type='stock'"
            )
        ).fetchone()

    assert row is not None
    assert row[1] == 1, "manual_override must remain 1"
    assert abs(row[0] - 0.7) < 1e-6, "Weight must be unchanged for manual_override=1"


# ---------------------------------------------------------------------------
# Never-zero-all guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_never_zero_all_guard(tmp_path):
    """If all agents would be zeroed, _apply_drift_scale returns None and skips write."""
    from engine.drift_detector import _apply_drift_scale

    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    # Seed a single agent for this asset_type (so scale would zero it)
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("DELETE FROM agent_weights")
        await conn.execute(
            "INSERT INTO agent_weights (agent_name, asset_type, weight, source, manual_override, excluded) "
            "VALUES ('TechnicalAgent', 'stock', 0.5, 'default', 0, 0)"
        )
        await conn.commit()

    # IC-IR = 0.0 → scale_factor=0 → new_weight=0 → all zero
    result = await _apply_drift_scale(db_path, "TechnicalAgent", "stock", current_icir=0.0)

    assert result is None, "Never-zero-all guard must return None when all would be zero"

    # Verify original weight is preserved
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT weight FROM agent_weights WHERE agent_name='TechnicalAgent' AND asset_type='stock'"
            )
        ).fetchone()
    assert row is not None
    assert abs(row[0] - 0.5) < 1e-6, "Original weight must be preserved by never-zero-all guard"


@pytest.mark.asyncio
async def test_never_zero_all_guard_with_multiple_agents(tmp_path):
    """Never-zero-all guard only fires when ALL agents in asset_type would be zero."""
    from engine.drift_detector import _apply_drift_scale

    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    # Two agents: scale one to 0, but the other stays > 0
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("DELETE FROM agent_weights")
        await conn.execute(
            "INSERT INTO agent_weights (agent_name, asset_type, weight, source, manual_override, excluded) "
            "VALUES ('TechnicalAgent', 'stock', 0.5, 'default', 0, 0)"
        )
        await conn.execute(
            "INSERT INTO agent_weights (agent_name, asset_type, weight, source, manual_override, excluded) "
            "VALUES ('MacroAgent', 'stock', 0.5, 'default', 0, 0)"
        )
        await conn.commit()

    # Scale TechnicalAgent to 0 — MacroAgent remains > 0, so guard does NOT fire
    result = await _apply_drift_scale(db_path, "TechnicalAgent", "stock", current_icir=0.0)

    # Guard should NOT fire because MacroAgent keeps total > 0
    # Result is the new renormalized weight for TechnicalAgent (0.0) — guard allows it
    assert result is not None, (
        "Guard should not fire when at least one other agent remains non-zero"
    )
    # After renorm: TechnicalAgent=0, MacroAgent=1.0
    async with aiosqlite.connect(db_path) as conn:
        rows = await (
            await conn.execute(
                "SELECT agent_name, weight FROM agent_weights WHERE asset_type='stock'"
            )
        ).fetchall()
    weights = {r[0]: r[1] for r in rows}
    # MacroAgent should be 1.0 after renorm (it was the only non-zero)
    assert abs(weights.get("MacroAgent", 0) - 1.0) < 1e-4


# ---------------------------------------------------------------------------
# WR-02 regression: renorm denominator must exclude manual_override rows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_renorm_denominator_excludes_manual_override_rows(tmp_path):
    """WR-02: Non-manual weights must sum to ~1.0 after _apply_drift_scale when
    manual_override=1 rows coexist.

    Scenario:
      TechnicalAgent  weight=0.4  manual_override=1  (NOT written by UPSERT)
      FundamentalAgent weight=0.4 manual_override=0
      MacroAgent       weight=0.2 manual_override=0  ← drifts, scale_factor=0.5

    Before fix: denominator=0.4+0.4+0.2*0.5=0.9, renorm writes Fundamental=0.444,
      Macro=0.111 → non-manual DB sum = 0.555 (wrong).
    After fix: denominator=0.4+0.2*0.5=0.5, renorm writes Fundamental=0.8,
      Macro=0.1 → non-manual DB sum = 1.0 (correct).
    """
    from engine.drift_detector import _apply_drift_scale, SCALE_DIVISOR

    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("DELETE FROM agent_weights")
        # manual_override=1 — must NOT be touched by drift scale
        await conn.execute(
            "INSERT INTO agent_weights "
            "(agent_name, asset_type, weight, source, manual_override, excluded) "
            "VALUES ('TechnicalAgent', 'stock', 0.4, 'manual', 1, 0)"
        )
        # auto rows — these will be renorm'd
        await conn.execute(
            "INSERT INTO agent_weights "
            "(agent_name, asset_type, weight, source, manual_override, excluded) "
            "VALUES ('FundamentalAgent', 'stock', 0.4, 'default', 0, 0)"
        )
        await conn.execute(
            "INSERT INTO agent_weights "
            "(agent_name, asset_type, weight, source, manual_override, excluded) "
            "VALUES ('MacroAgent', 'stock', 0.2, 'default', 0, 0)"
        )
        await conn.commit()

    # ic_ir=1.0 → scale_factor = 1.0 / SCALE_DIVISOR = 0.5
    result = await _apply_drift_scale(
        db_path, "MacroAgent", "stock", current_icir=1.0
    )
    assert result is not None, "_apply_drift_scale should return a weight, not None"

    # Read back only non-manual rows
    async with aiosqlite.connect(db_path) as conn:
        rows = await (
            await conn.execute(
                "SELECT agent_name, weight FROM agent_weights "
                "WHERE asset_type='stock' AND manual_override=0"
            )
        ).fetchall()

    non_manual_weights = {r[0]: r[1] for r in rows}
    total = sum(non_manual_weights.values())

    assert abs(total - 1.0) < 1e-6, (
        f"Non-manual weights must sum to 1.0 after renorm, got {total}. "
        f"Weights: {non_manual_weights}"
    )

    # manual_override row must be untouched
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT weight FROM agent_weights "
                "WHERE agent_name='TechnicalAgent' AND asset_type='stock'"
            )
        ).fetchone()
    assert row is not None
    assert abs(row[0] - 0.4) < 1e-6, (
        f"manual_override=1 weight must remain 0.4, got {row[0]}"
    )


# ---------------------------------------------------------------------------
# evaluate_drift writes to drift_log
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_drift_writes_drift_log(tmp_path):
    """evaluate_drift must insert rows into drift_log for each agent evaluated."""
    from engine.drift_detector import evaluate_drift

    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    entries = await evaluate_drift(db_path)

    async with aiosqlite.connect(db_path) as conn:
        rows = await (await conn.execute("SELECT COUNT(*) FROM drift_log")).fetchone()

    assert rows is not None
    assert rows[0] >= len(entries), "drift_log must have at least as many rows as entries returned"
    assert rows[0] > 0, "drift_log must have at least one row after evaluate_drift"
