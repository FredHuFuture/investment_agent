"""Tests for TTWROR + IRR math functions and PortfolioAnalytics.get_ttwror_irr().

Unit tests (pure math) + integration test against a seeded tmp_path SQLite DB.
All tests use asyncio_mode=auto (pytest-asyncio); no asyncio.run() wrappers.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite
import pytest

from db.database import init_db
from engine.analytics import (
    PortfolioAnalytics,
    compute_irr_closed_form,
    compute_irr_multi,
    compute_ttwror,
)


# ---------------------------------------------------------------------------
# 1. compute_ttwror — empty / single value → 0.0
# ---------------------------------------------------------------------------


def test_ttwror_empty_returns_zero() -> None:
    assert compute_ttwror([]) == 0.0


def test_ttwror_single_value_returns_zero() -> None:
    assert compute_ttwror([100.0]) == 0.0


# ---------------------------------------------------------------------------
# 2. compute_ttwror — simple uptrend (100 → 110) = +10%
# ---------------------------------------------------------------------------


def test_ttwror_simple_uptrend() -> None:
    result = compute_ttwror([100.0, 110.0])
    assert abs(result - 0.10) < 1e-9


# ---------------------------------------------------------------------------
# 3. compute_ttwror — 3-point with intermediate zero value skipped safely
# ---------------------------------------------------------------------------


def test_ttwror_skips_zero_prev() -> None:
    # prev=0 should not raise; that sub-period is skipped
    # 100 → 0 → 110 : only the final step counts (0→110 skipped because prev=0)
    result = compute_ttwror([100.0, 0.0, 110.0])
    # Geometric linking: 0/100 first period, then 0 prev skipped → linked=0.0*...
    # Actually first period: 0.0/100.0 = 0, linked = 0; second period prev=0, skip
    # So linked = 0.0, return = -1.0  ... but wait: the check is `prev > 0`
    # First sub-period: prev=100 (ok), cur=0 → linked *= 0/100 = 0
    # Second sub-period: prev=0 → skip
    # result = 0.0 - 1.0 = -1.0
    assert result == pytest.approx(-1.0, abs=1e-9)


def test_ttwror_skips_none_prev() -> None:
    # None values should not raise; check None handling
    result = compute_ttwror([100.0, None, 110.0])  # type: ignore[list-item]
    # sub-period 1: prev=100, cur=None → skip (None is not > 0)
    # sub-period 2: prev=None → skip
    # linked stays at 1.0 → result = 0.0
    assert result == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# 4. compute_ttwror — downtrend (100 → 50) ≈ -0.50
# ---------------------------------------------------------------------------


def test_ttwror_downtrend() -> None:
    result = compute_ttwror([100.0, 50.0])
    assert abs(result - (-0.5)) < 1e-9


# ---------------------------------------------------------------------------
# 5. compute_irr_closed_form — canonical example 100→121 over 365d ≈ 0.21
# ---------------------------------------------------------------------------


def test_irr_closed_form_one_year() -> None:
    result = compute_irr_closed_form(100.0, 121.0, 365)
    assert result is not None
    assert abs(result - 0.21) < 1e-4


# ---------------------------------------------------------------------------
# 6. compute_irr_closed_form — 100→121 over 730d (2 years) ≈ 0.10
# ---------------------------------------------------------------------------


def test_irr_closed_form_two_years() -> None:
    result = compute_irr_closed_form(100.0, 121.0, 730)
    assert result is not None
    # (121/100)^(365/730) - 1 = 1.21^0.5 - 1 ≈ 0.10
    assert abs(result - 0.10) < 1e-4


# ---------------------------------------------------------------------------
# 7. compute_irr_closed_form — degenerate inputs return None
# ---------------------------------------------------------------------------


def test_irr_closed_form_zero_cost_returns_none() -> None:
    assert compute_irr_closed_form(0.0, 121.0, 365) is None


def test_irr_closed_form_zero_days_returns_none() -> None:
    assert compute_irr_closed_form(100.0, 121.0, 0) is None


def test_irr_closed_form_negative_days_returns_none() -> None:
    assert compute_irr_closed_form(100.0, 121.0, -5) is None


# ---------------------------------------------------------------------------
# 8. compute_irr_multi — 2-CF case matches closed-form within 1e-4
# ---------------------------------------------------------------------------


def test_irr_multi_matches_closed_form_for_two_cfs() -> None:
    # Entry: -100 at day 0, Exit: +121 at day 365
    cash_flows = [(0, -100.0), (365, 121.0)]
    result = compute_irr_multi(cash_flows)
    assert result is not None
    expected = compute_irr_closed_form(100.0, 121.0, 365)
    assert expected is not None
    assert abs(result - expected) < 1e-4


def test_irr_multi_fewer_than_two_flows_returns_none() -> None:
    assert compute_irr_multi([(0, -100.0)]) is None
    assert compute_irr_multi([]) is None


# ---------------------------------------------------------------------------
# 9. PortfolioAnalytics.get_ttwror_irr — integration against seeded DB
# ---------------------------------------------------------------------------


@pytest.fixture
async def analytics_db(tmp_path: Path) -> str:
    """Create a fresh DB with 3 portfolio_snapshots (100 → 105 → 110)."""
    db_path = str(tmp_path / "test_ttwror.db")
    await init_db(db_path)

    now = datetime.now(timezone.utc)
    async with aiosqlite.connect(db_path) as conn:
        for i, value in enumerate([100_000.0, 105_000.0, 110_000.0]):
            ts = (now - timedelta(days=3 - i)).isoformat()
            await conn.execute(
                """
                INSERT INTO portfolio_snapshots
                    (timestamp, total_value, cash, positions_json, trigger_event)
                VALUES (?, ?, ?, ?, 'test')
                """,
                (ts, value, 10_000.0, json.dumps([]), ),
            )
        await conn.commit()
    return db_path


async def test_get_ttwror_irr_returns_positive_ttwror(analytics_db: str) -> None:
    analytics = PortfolioAnalytics(analytics_db)
    result = await analytics.get_ttwror_irr(days=30)

    agg = result["aggregate"]
    assert agg["snapshot_count"] == 3
    assert agg["ttwror"] is not None
    assert agg["ttwror"] > 0, "Upward snapshots should yield positive TTWROR"
    assert "irr" in agg
    assert "positions" in result


async def test_get_ttwror_irr_empty_db(tmp_path: Path) -> None:
    """With no snapshots, aggregate fields should be None and positions empty."""
    db_path = str(tmp_path / "empty.db")
    await init_db(db_path)

    analytics = PortfolioAnalytics(db_path)
    result = await analytics.get_ttwror_irr(days=30)

    agg = result["aggregate"]
    assert agg["ttwror"] is None
    assert agg["irr"] is None
    assert agg["snapshot_count"] == 0
    assert result["positions"] == []


async def test_get_ttwror_irr_single_snapshot_returns_none(tmp_path: Path) -> None:
    """One snapshot < 2 → ttwror/irr both None."""
    db_path = str(tmp_path / "single.db")
    await init_db(db_path)

    now = datetime.now(timezone.utc)
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO portfolio_snapshots (timestamp, total_value, cash, positions_json, trigger_event) VALUES (?, ?, ?, ?, 'test')",
            (now.isoformat(), 100_000.0, 10_000.0, "[]"),
        )
        await conn.commit()

    analytics = PortfolioAnalytics(db_path)
    result = await analytics.get_ttwror_irr(days=30)

    assert result["aggregate"]["ttwror"] is None
    assert result["aggregate"]["snapshot_count"] == 1
