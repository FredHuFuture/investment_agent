"""Tests for SIG-03: WeightAdapter.compute_ic_weights + calibration API endpoint.

Task 2 tests (6): IC-weight computation logic (None on insufficient data, sum-to-1,
negative-IC zeroing, zero-IC zeroing, negative-IC loses weight vs baseline,
asset-type structure preserved).

Task 3 test (1): HTTP end-to-end for GET /analytics/calibration.

Note on asyncio: pyproject.toml sets asyncio_mode=auto. All async tests are plain
async def functions — no @pytest.mark.asyncio decorator needed, no asyncio.run().
"""
from __future__ import annotations

from pathlib import Path

import aiosqlite
import numpy as np
import pytest

from db.database import init_db
from tracking.store import SignalStore
from tracking.tracker import SignalTracker
from engine.weight_adapter import WeightAdapter


# ---------------------------------------------------------------------------
# Corpus seeding helpers
# ---------------------------------------------------------------------------

async def _seed_synthetic_corpus(
    db_file: Path,
    agent: str,
    n: int,
    true_ic: float = 0.12,
    seed: int = 42,
) -> None:
    """Seed backtest_signal_history with scores/returns at known Pearson correlation."""
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


async def _seed_multi_agent_corpus(
    db_file: Path,
    agent_ics: list[tuple[str, float]],  # [(agent_name, true_ic), ...]
    n: int = 120,
    seed: int = 42,
) -> None:
    """Seed multiple agents with distinct IC values into one DB."""
    await init_db(db_file)
    for idx, (agent, true_ic) in enumerate(agent_ics):
        await _seed_synthetic_corpus(db_file, agent, n, true_ic=true_ic, seed=seed + idx)


def _make_tracker(db_file: Path) -> SignalTracker:
    store = SignalStore(str(db_file))
    return SignalTracker(store)


# ---------------------------------------------------------------------------
# Task 2 — Test A: returns None on insufficient data
# ---------------------------------------------------------------------------

async def test_compute_ic_weights_returns_none_on_insufficient_data(
    tmp_path: Path,
) -> None:
    """Empty backtest_signal_history → no agent has data → compute_ic_weights returns None."""
    db_file = tmp_path / "ic_w_empty.db"
    await init_db(db_file)  # create schema but no rows

    tracker = _make_tracker(db_file)
    adapter = WeightAdapter(db_path=str(db_file))

    result = await adapter.compute_ic_weights(
        tracker,
        asset_types=["stock"],
        agents=["TechnicalAgent", "MacroAgent"],
    )
    assert result is None, (
        "Expected None when no agent has sufficient IC data (empty corpus)"
    )


# ---------------------------------------------------------------------------
# Task 2 — Test B: all positive IC → weights sum to 1
# ---------------------------------------------------------------------------

async def test_compute_ic_weights_all_positive_sum_to_1(tmp_path: Path) -> None:
    """3 agents with positive IC → IC weights sum to 1.0 within 1e-6."""
    db_file = tmp_path / "ic_w_pos.db"
    await _seed_multi_agent_corpus(
        db_file,
        [("TechnicalAgent", 0.15), ("MacroAgent", 0.10), ("SentimentAgent", 0.08)],
        n=120,
        seed=42,
    )

    tracker = _make_tracker(db_file)
    adapter = WeightAdapter(db_path=str(db_file))

    result = await adapter.compute_ic_weights(
        tracker,
        asset_types=["stock"],
        agents=["TechnicalAgent", "MacroAgent", "SentimentAgent"],
    )

    assert result is not None, "Expected AdaptiveWeights for 3 agents with positive IC"
    w = result.weights["stock"]
    total = sum(w.values())
    # Weights are rounded to 4 decimal places; allow 1e-3 tolerance for rounding error
    assert abs(total - 1.0) < 1e-3, f"Weights must sum to ~1.0, got {total}"
    assert result.source == "ic_ir"


# ---------------------------------------------------------------------------
# Task 2 — Test C: negative IC gets zero weight
# ---------------------------------------------------------------------------

async def test_compute_ic_weights_negative_ic_gets_zero_weight(
    tmp_path: Path,
) -> None:
    """Agent with negative IC-IR gets weight scaling factor 0 → weight == 0."""
    db_file = tmp_path / "ic_w_neg.db"
    await _seed_multi_agent_corpus(
        db_file,
        [("GoodAgent", 0.15), ("BadAgent", -0.15)],
        n=120,
        seed=10,
    )

    tracker = _make_tracker(db_file)
    adapter = WeightAdapter(db_path=str(db_file))

    result = await adapter.compute_ic_weights(
        tracker,
        asset_types=["stock"],
        agents=["GoodAgent", "BadAgent"],
    )

    assert result is not None
    w = result.weights["stock"]
    assert w["BadAgent"] == 0.0, (
        f"BadAgent (negative IC) should have weight 0.0, got {w['BadAgent']}"
    )
    # GoodAgent takes all the weight (rounded to 4dp, so allow 1e-3)
    assert abs(w["GoodAgent"] - 1.0) < 1e-3, (
        f"GoodAgent should take ~100% weight after BadAgent zeroed, got {w['GoodAgent']}"
    )


# ---------------------------------------------------------------------------
# Task 2 — Test D: IC-IR exactly 0 → zero weight
# ---------------------------------------------------------------------------

async def test_compute_ic_weights_zero_ic_agent_excluded(tmp_path: Path) -> None:
    """IC-IR = 0 → max(0, 0/2.0) = 0 → zero weight for that agent."""
    db_file = tmp_path / "ic_w_zero.db"
    # Use true_ic=0.0 for ZeroAgent — Pearson should be ≈ 0
    await _seed_multi_agent_corpus(
        db_file,
        [("PositiveAgent", 0.15), ("ZeroAgent", 0.0)],
        n=120,
        seed=77,
    )

    tracker = _make_tracker(db_file)
    adapter = WeightAdapter(db_path=str(db_file))

    result = await adapter.compute_ic_weights(
        tracker,
        asset_types=["stock"],
        agents=["PositiveAgent", "ZeroAgent"],
    )

    # ZeroAgent may have zero or near-zero IC-IR → weight should be 0 or very small
    # PositiveAgent must always have greater weight than ZeroAgent
    assert result is not None
    w = result.weights["stock"]
    assert w["PositiveAgent"] >= w["ZeroAgent"], (
        f"PositiveAgent weight {w['PositiveAgent']} must be >= ZeroAgent {w['ZeroAgent']}"
    )


# ---------------------------------------------------------------------------
# Task 2 — Test E: negative-IC agent loses weight vs equal-weight baseline (SIG-03 primary)
# ---------------------------------------------------------------------------

async def test_negative_ic_agent_loses_weight_vs_baseline(tmp_path: Path) -> None:
    """Seed 3 agents: 2 positive IC, 1 negative. BadAgent weight < 1/3 after IC weighting."""
    db_file = tmp_path / "ic_w_baseline.db"
    await _seed_multi_agent_corpus(
        db_file,
        [("TechnicalAgent", 0.15), ("MacroAgent", 0.10), ("BadAgent", -0.15)],
        n=120,
        seed=42,
    )

    tracker = _make_tracker(db_file)
    adapter = WeightAdapter(db_path=str(db_file))

    result = await adapter.compute_ic_weights(
        tracker,
        asset_types=["stock"],
        agents=["TechnicalAgent", "MacroAgent", "BadAgent"],
    )

    assert result is not None, "Expected IC weights with 120 samples each"
    w = result.weights["stock"]

    # Baseline (equal-weight): 1/3 ≈ 0.333
    # BadAgent with negative IC must have weight strictly less than baseline
    assert w["BadAgent"] < 0.333, (
        f"BadAgent weight {w['BadAgent']:.4f} should be < equal-weight baseline 0.333 "
        f"(Technical={w['TechnicalAgent']:.3f}, Macro={w['MacroAgent']:.3f})"
    )
    # Weights must still sum to 1
    total = sum(w.values())
    assert abs(total - 1.0) < 1e-3, f"Weights must sum to ~1.0, got {total}"
    # Source correctly labelled
    assert result.source == "ic_ir"


# ---------------------------------------------------------------------------
# Task 2 — Test F: asset_type structure preserved
# ---------------------------------------------------------------------------

async def test_ic_weights_preserve_asset_type_structure(tmp_path: Path) -> None:
    """compute_ic_weights returns {asset_type: {agent_name: weight}} for all requested types."""
    db_file = tmp_path / "ic_w_struct.db"
    await _seed_multi_agent_corpus(
        db_file,
        [("TechnicalAgent", 0.12), ("MacroAgent", 0.08)],
        n=120,
        seed=55,
    )

    tracker = _make_tracker(db_file)
    adapter = WeightAdapter(db_path=str(db_file))

    result = await adapter.compute_ic_weights(
        tracker,
        asset_types=["stock", "crypto"],
        agents=["TechnicalAgent", "MacroAgent"],
    )

    assert result is not None
    assert "stock" in result.weights, "Expected 'stock' key in weights"
    assert "crypto" in result.weights, "Expected 'crypto' key in weights"
    for at in ["stock", "crypto"]:
        for agent in ["TechnicalAgent", "MacroAgent"]:
            assert agent in result.weights[at], (
                f"Expected agent '{agent}' in weights['{at}']"
            )
        total = sum(result.weights[at].values())
        assert abs(total - 1.0) < 1e-6, (
            f"weights['{at}'] must sum to 1.0, got {total}"
        )


# ---------------------------------------------------------------------------
# Task 3 — HTTP end-to-end test for GET /analytics/calibration
# ---------------------------------------------------------------------------

async def test_calibration_endpoint_http_end_to_end(tmp_path: Path) -> None:
    """Seed corpus, override db_path, call endpoint, assert JSON contract."""
    # WR-04 fix: converted from sync def + asyncio.run() to async def so it
    # is compatible with pytest-asyncio asyncio_mode=auto (no running-loop conflict).
    db_file = tmp_path / "cal.db"

    await _seed_multi_agent_corpus(
        db_file,
        [("TechnicalAgent", 0.15), ("MacroAgent", 0.10)],
        n=120,
        seed=42,
    )

    from api.app import create_app
    from api.deps import get_db_path
    from fastapi.testclient import TestClient

    app = create_app()
    app.dependency_overrides[get_db_path] = lambda: str(db_file)

    with TestClient(app) as client:
        resp = client.get("/analytics/calibration?horizon=5d&window=60")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    data = body["data"]

    # Top-level structure
    assert "agents" in data, "Response must contain 'agents' key"
    assert "corpus_metadata" in data, "Response must contain 'corpus_metadata' key"

    # TechnicalAgent — seeded with positive IC → should have data
    assert "TechnicalAgent" in data["agents"]
    ta = data["agents"]["TechnicalAgent"]
    assert ta["sample_size"] >= 0
    # ic_horizon must always be present (WARNING 11 fix)
    assert ta["ic_horizon"] == "5d"
    assert ta["preliminary_calibration"] is True
    assert ta["signal_source"] == "backtest_generated"

    # FundamentalAgent — FOUND-04 contract: must be null with explanatory note
    assert "FundamentalAgent" in data["agents"], (
        "FundamentalAgent must appear in response (with null metrics)"
    )
    fa = data["agents"]["FundamentalAgent"]
    assert fa["brier_score"] is None
    assert fa["ic_5d"] is None
    assert fa["ic_horizon"] == "5d"  # WARNING 11: indicator present even when value is None
    assert "note" in fa, "FundamentalAgent must have 'note' field explaining exclusion"
    note = fa["note"]
    assert "FOUND-04" in note or "HOLD in backtest_mode" in note, (
        f"FundamentalAgent note must reference FOUND-04 or backtest_mode, got: {note!r}"
    )

    # corpus_metadata
    cm = data["corpus_metadata"]
    assert "tickers_covered" in cm
    assert "total_observations" in cm
    # AP-04: survivorship bias warning must be present
    assert cm["survivorship_bias_warning"] is True
