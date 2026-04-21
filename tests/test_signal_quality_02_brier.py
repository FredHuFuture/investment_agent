"""Tests for SIG-02: Brier score computation in SignalTracker.

Strategy (02-RESEARCH.md Q9): Seed backtest_signal_history directly via SQL
INSERT in an isolated tmp_path SQLite.  This gives deterministic, fast tests
with no network dependency.

Formulation (02-RESEARCH.md Q2, AP-05):
- One-vs-rest binary Brier on BUY/SELL only; HOLD excluded.
- confidence is 0-100 (divided by 100 inside compute_brier_score).
- Returns None when directional N < 20 (AP-03).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Sequence

import aiosqlite
import pytest

from db.database import init_db
from tracking.store import SignalStore
from tracking.tracker import SignalTracker


# ---------------------------------------------------------------------------
# Helper: seed backtest_signal_history rows
# ---------------------------------------------------------------------------

async def _seed_signals(
    db_file: Path,
    agent: str,
    signals: Sequence[tuple[str, float, float]],  # (signal, confidence, forward_return)
) -> None:
    """Insert synthetic rows into backtest_signal_history."""
    await init_db(db_file)
    async with aiosqlite.connect(db_file) as conn:
        for i, (sig, conf, fr) in enumerate(signals):
            # Generate a unique date per row to avoid date collisions
            day = (i % 28) + 1
            month = (i // 28) + 1
            if month > 12:
                month = 12
                day = min(day, 28)
            date_str = f"2024-{month:02d}-{day:02d}"
            await conn.execute(
                """
                INSERT INTO backtest_signal_history
                    (ticker, asset_type, signal_date, agent_name, raw_score,
                     signal, confidence, forward_return_5d, forward_return_21d,
                     source)
                VALUES (?, 'stock', ?, ?, ?, ?, ?, ?, ?, 'backtest')
                """,
                ("AAPL", date_str, agent, 0.5, sig, conf, fr, fr),
            )
        await conn.commit()


def _make_tracker(db_file: Path) -> SignalTracker:
    store = SignalStore(str(db_file))
    return SignalTracker(store)


# ---------------------------------------------------------------------------
# Test A: perfect predictor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_brier_perfect_predictor(tmp_path: Path) -> None:
    """30 BUY signals, confidence=95%, all forward_return > 0 → Brier ≈ 0.0025."""
    db_file = tmp_path / "brier_a.db"
    signals = [("BUY", 95.0, 0.01)] * 30
    await _seed_signals(db_file, "TechnicalAgent", signals)

    tracker = _make_tracker(db_file)
    result = await tracker.compute_brier_score("TechnicalAgent")

    assert result is not None, "Expected numeric Brier, got None"
    # prob=0.95, outcome=1 → (0.95-1)^2 = 0.0025
    assert abs(result - 0.0025) < 1e-4, f"Expected ~0.0025, got {result}"


# ---------------------------------------------------------------------------
# Test B: random predictor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_brier_random_predictor(tmp_path: Path) -> None:
    """100 BUY, conf=50%, half correct → Brier ≈ 0.25."""
    db_file = tmp_path / "brier_b.db"
    # 50 correct (forward_return > 0), 50 wrong (forward_return < 0)
    signals = (
        [("BUY", 50.0, 0.01)] * 50
        + [("BUY", 50.0, -0.01)] * 50
    )
    await _seed_signals(db_file, "TechnicalAgent", signals)

    tracker = _make_tracker(db_file)
    result = await tracker.compute_brier_score("TechnicalAgent")

    assert result is not None
    # prob=0.50; correct: (0.5-1)^2=0.25; wrong: (0.5-0)^2=0.25  → avg=0.25
    assert abs(result - 0.25) < 0.01, f"Expected ~0.25, got {result}"


# ---------------------------------------------------------------------------
# Test C: perfectly wrong predictor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_brier_wrong_predictor(tmp_path: Path) -> None:
    """30 BUY, conf=95%, all forward_return < 0 → Brier ≈ 0.9025."""
    db_file = tmp_path / "brier_c.db"
    signals = [("BUY", 95.0, -0.01)] * 30
    await _seed_signals(db_file, "TechnicalAgent", signals)

    tracker = _make_tracker(db_file)
    result = await tracker.compute_brier_score("TechnicalAgent")

    assert result is not None
    # prob=0.95, outcome=0 → (0.95-0)^2 = 0.9025
    assert abs(result - 0.9025) < 1e-4, f"Expected ~0.9025, got {result}"


# ---------------------------------------------------------------------------
# Test D: HOLD signals are excluded (AP-05)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_brier_hold_signals_excluded(tmp_path: Path) -> None:
    """50 HOLD + 20 BUY correct → Brier computed from BUY rows only ≈ 0.0025."""
    db_file = tmp_path / "brier_d.db"
    hold_signals = [("HOLD", 60.0, 0.01)] * 50
    buy_signals = [("BUY", 95.0, 0.01)] * 20  # all correct
    await _seed_signals(db_file, "TechnicalAgent", hold_signals + buy_signals)

    tracker = _make_tracker(db_file)
    result = await tracker.compute_brier_score("TechnicalAgent", min_samples=20)

    assert result is not None, "Expected numeric result — 20 directional rows should pass min_samples=20"
    # Only 20 BUY rows scored; prob=0.95, outcome=1 → (0.95-1)^2=0.0025
    assert abs(result - 0.0025) < 1e-4, (
        f"Expected ~0.0025 (HOLD excluded), got {result}"
    )


# ---------------------------------------------------------------------------
# Test E: insufficient directional samples → None (AP-03)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_brier_insufficient_directional_samples_returns_none(
    tmp_path: Path,
) -> None:
    """10 BUY signals (< min_samples=20) → Brier must be None, not 0.0."""
    db_file = tmp_path / "brier_e.db"
    signals = [("BUY", 75.0, 0.01)] * 10
    await _seed_signals(db_file, "TechnicalAgent", signals)

    tracker = _make_tracker(db_file)
    result = await tracker.compute_brier_score("TechnicalAgent")

    assert result is None, (
        f"Expected None for N=10 < min_samples=20, got {result}"
    )


# ---------------------------------------------------------------------------
# Test F: reads from backtest_signal_history (integration sanity)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_brier_reads_from_backtest_signal_history(tmp_path: Path) -> None:
    """25 rows seeded directly; compute_brier_score returns a numeric result (no crash)."""
    db_file = tmp_path / "brier_f.db"
    # Mix of BUY and SELL, enough to exceed min_samples=20 directional rows
    signals = (
        [("BUY", 70.0, 0.02)] * 10   # correct BUY
        + [("BUY", 70.0, -0.02)] * 5  # wrong BUY
        + [("SELL", 65.0, -0.01)] * 10  # correct SELL
    )
    await _seed_signals(db_file, "TestAgent", signals)

    tracker = _make_tracker(db_file)
    result = await tracker.compute_brier_score("TestAgent", min_samples=20)

    assert result is not None, "Expected numeric Brier from 25 directional rows"
    assert 0.0 <= result <= 1.0, f"Brier must be in [0,1], got {result}"
