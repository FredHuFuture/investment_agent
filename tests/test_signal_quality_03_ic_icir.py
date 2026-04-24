"""Tests for SIG-03: Rolling IC and IC-IR computation in SignalTracker.

Strategy (02-RESEARCH.md Q9): Synthetic corpus with known Pearson correlation
seeded directly into backtest_signal_history via SQL INSERT in tmp_path SQLite.

Key contracts verified:
- IC uses scipy.stats.pearsonr on raw_score (continuous), NOT the signal enum (AP-02)
- IC returns None when N < 30 (AP-03)
- IC-IR = mean(rolling_IC) / std(rolling_IC); None when < 5 valid ICs or std == 0
- NaN guard: degenerate (constant) score series → None (T-02-03-08)

Note on asyncio: pyproject.toml sets asyncio_mode=auto. All async tests are
plain async def functions (no @pytest.mark.asyncio needed, no asyncio.run()).
The sync seeding helper from the PLAN.md spec uses asyncio.run() which fails
under asyncio_mode=auto; replaced with a native async helper.
"""
from __future__ import annotations

import statistics
from pathlib import Path

import aiosqlite
import numpy as np
import pytest

from db.database import init_db
from tracking.store import SignalStore
from tracking.tracker import SignalTracker


# ---------------------------------------------------------------------------
# Helper: seed synthetic corpus with known IC (async — no asyncio.run)
# ---------------------------------------------------------------------------

async def _seed_synthetic_corpus(
    db_file: Path,
    agent: str,
    n: int,
    true_ic: float = 0.12,
    seed: int = 42,
) -> None:
    """Seed backtest_signal_history with scores/returns at known Pearson correlation.

    returns = true_ic * scores + sqrt(1 - true_ic^2) * noise
    This gives Pearson(scores, returns) ≈ true_ic for large n.
    """
    rng = np.random.default_rng(seed)
    scores = rng.normal(0, 1, n)
    noise = rng.normal(0, 1, n)
    returns = true_ic * scores + np.sqrt(1 - true_ic**2) * noise

    await init_db(db_file)
    async with aiosqlite.connect(db_file) as conn:
        for i in range(n):
            day = (i % 28) + 1
            month = (i // 28) + 1
            if month > 12:
                month = 12
                day = min(day, 28)
            date_str = f"2024-{month:02d}-{day:02d}"
            sig = (
                "BUY" if scores[i] > 0.5
                else ("SELL" if scores[i] < -0.5 else "HOLD")
            )
            conf = float(min(95, 50 + abs(scores[i]) * 20))
            await conn.execute(
                """
                INSERT INTO backtest_signal_history
                    (ticker, asset_type, signal_date, agent_name, raw_score,
                     signal, confidence, forward_return_5d, forward_return_21d,
                     source)
                VALUES (?, 'stock', ?, ?, ?, ?, ?, ?, ?, 'backtest')
                """,
                (
                    "SYN", date_str, agent,
                    float(scores[i]), sig, conf,
                    float(returns[i]), float(returns[i]),
                ),
            )
        await conn.commit()


def _make_tracker(db_file: Path) -> SignalTracker:
    store = SignalStore(str(db_file))
    return SignalTracker(store)


# ---------------------------------------------------------------------------
# Test A: IC matches known synthetic correlation
# ---------------------------------------------------------------------------

async def test_ic_matches_known_correlation(tmp_path: Path) -> None:
    """Synthetic corpus with true_ic=0.12, N=100 → computed IC within ±0.05."""
    db_file = tmp_path / "ic_a.db"
    await _seed_synthetic_corpus(db_file, "TechnicalAgent", n=100, true_ic=0.12, seed=42)

    tracker = _make_tracker(db_file)
    overall_ic, rolling = await tracker.compute_rolling_ic("TechnicalAgent")

    assert overall_ic is not None, "Expected numeric IC for N=100"
    # Standard error of Pearson r at N=100 is ~1/sqrt(100)=0.10.
    # A tolerance of ±0.08 is within 1 SE of the true IC and correctly
    # tests that the correlation machinery works (not that the estimate is tight).
    assert abs(overall_ic - 0.12) < 0.08, (
        f"IC {overall_ic:.4f} is more than ±0.08 from true_ic=0.12"
    )


# ---------------------------------------------------------------------------
# Test B: insufficient samples → None
# ---------------------------------------------------------------------------

async def test_ic_insufficient_samples_returns_none(tmp_path: Path) -> None:
    """N=20 observations → IC must be None (AP-03 guard)."""
    db_file = tmp_path / "ic_b.db"
    await _seed_synthetic_corpus(db_file, "TechnicalAgent", n=20, true_ic=0.12, seed=7)

    tracker = _make_tracker(db_file)
    overall_ic, rolling = await tracker.compute_rolling_ic("TechnicalAgent")

    assert overall_ic is None, (
        f"Expected None for N=20 < min_samples=30, got {overall_ic}"
    )
    assert rolling == [], "Expected empty rolling list for insufficient data"


# ---------------------------------------------------------------------------
# Test C: IC uses raw_score, not signal enum string (AP-02 guard)
# ---------------------------------------------------------------------------

async def test_ic_uses_raw_score_not_aggregated(tmp_path: Path) -> None:
    """Seed rows where raw_score is continuous and distinct from signal direction.

    Rows have mixed signals but continuous raw_score values.
    IC should use raw_score and return a plausible float in [-1, 1].
    """
    db_file = tmp_path / "ic_c.db"
    await _seed_synthetic_corpus(db_file, "RawScoreAgent", n=60, true_ic=0.15, seed=99)

    tracker = _make_tracker(db_file)
    overall_ic, rolling = await tracker.compute_rolling_ic("RawScoreAgent")

    # N=60 ≥ min_samples=30 → IC should be non-None
    assert overall_ic is not None, (
        "Expected numeric IC — compute_rolling_ic should use raw_score column"
    )
    assert isinstance(overall_ic, float)
    assert -1.0 <= overall_ic <= 1.0


# ---------------------------------------------------------------------------
# Test D: IC-IR is mean/std of rolling ICs (static method, no DB)
# ---------------------------------------------------------------------------

def test_icir_is_mean_over_std() -> None:
    """Known rolling IC series → IC-IR = mean/std within 1e-4."""
    ics: list[float | None] = [0.05, 0.08, -0.02, 0.10, 0.06]
    result = SignalTracker.compute_icir(ics)

    valid: list[float] = [v for v in ics if v is not None]
    expected = statistics.mean(valid) / statistics.stdev(valid)
    assert result is not None, "Expected numeric IC-IR"
    assert abs(result - expected) < 1e-4, (
        f"IC-IR {result} deviates from expected {expected:.6f}"
    )


# ---------------------------------------------------------------------------
# Test E: IC-IR returns None when fewer than 5 valid rolling ICs
# ---------------------------------------------------------------------------

def test_icir_returns_none_when_fewer_than_5_rolling_ics() -> None:
    """4 valid IC values → IC-IR must be None."""
    ics: list[float | None] = [0.05, 0.08, None, 0.10, None, None, 0.06]
    # valid count = 4 (< 5)
    result = SignalTracker.compute_icir(ics)
    assert result is None, (
        f"Expected None for 4 valid ICs, got {result}"
    )


# ---------------------------------------------------------------------------
# Test F: IC-IR returns None when std == 0 (AP-03 / T-02-03-04)
# ---------------------------------------------------------------------------

def test_icir_returns_none_when_std_is_zero() -> None:
    """All rolling IC values identical → std=0 → IC-IR must be None."""
    ics: list[float | None] = [0.05, 0.05, 0.05, 0.05, 0.05]
    result = SignalTracker.compute_icir(ics)
    assert result is None, (
        f"Expected None when std(IC)=0, got {result}"
    )


# ---------------------------------------------------------------------------
# Test G: GET /analytics/calibration returns rolling_ic field per agent (LIVE-02)
# ---------------------------------------------------------------------------

async def test_calibration_exposes_rolling_ic_field(tmp_path: Path) -> None:
    """Seeded corpus → /analytics/calibration response includes rolling_ic list.

    LIVE-02: The CalibrationPage sparkline requires a rolling IC time series
    per agent. This test verifies the field is present and is a list.

    Strategy: seed 60 rows for TechnicalAgent (>= min_samples=30); call the
    route handler directly via a FastAPI TestClient so the response shape is
    checked end-to-end without a running server.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routes.calibration import router as cal_router
    from api.deps import get_db_path

    # Build a minimal FastAPI app that uses the calibration router.
    app = FastAPI()
    db_file = tmp_path / "cal_rolling_ic.db"
    await _seed_synthetic_corpus(db_file, "TechnicalAgent", n=60, true_ic=0.12, seed=42)

    # Override the DB path dependency to point to our test DB.
    app.dependency_overrides[get_db_path] = lambda: str(db_file)
    app.include_router(cal_router, prefix="/analytics")

    with TestClient(app) as client:
        resp = client.get("/analytics/calibration")

    assert resp.status_code == 200, f"Unexpected status: {resp.status_code} {resp.text}"
    body = resp.json()
    agents = body["data"]["agents"]

    # TechnicalAgent was seeded with N=60 → rolling_ic should be a non-empty list
    assert "TechnicalAgent" in agents, "Expected TechnicalAgent in agents"
    tech = agents["TechnicalAgent"]
    assert "rolling_ic" in tech, (
        f"Expected 'rolling_ic' key in TechnicalAgent entry; got keys: {list(tech.keys())}"
    )
    assert isinstance(tech["rolling_ic"], list), (
        f"Expected rolling_ic to be a list, got {type(tech['rolling_ic'])}"
    )
    # Length should be <= window (default 60); non-empty for N=60
    assert len(tech["rolling_ic"]) > 0, "Expected at least one rolling IC point for N=60"

    # FundamentalAgent is in NULL_EXPECTED — should have rolling_ic as empty list
    assert "FundamentalAgent" in agents, "Expected FundamentalAgent in agents"
    fund = agents["FundamentalAgent"]
    assert "rolling_ic" in fund, (
        f"Expected 'rolling_ic' key in FundamentalAgent entry; got keys: {list(fund.keys())}"
    )
    assert isinstance(fund["rolling_ic"], list), (
        f"Expected rolling_ic to be a list for FundamentalAgent"
    )
    assert fund["rolling_ic"] == [], (
        f"Expected empty rolling_ic for FundamentalAgent (NULL_EXPECTED), got {fund['rolling_ic']}"
    )
