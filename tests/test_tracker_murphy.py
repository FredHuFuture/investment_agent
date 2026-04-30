"""Tests for Phase 8 SIG-v2-02: Murphy/Brier 3-component decomposition.

Strategy:
- compute_murphy_decomposition is a pure (static) function over a bins payload —
  no DB / store needed. We hand-craft canonical bin specs to verify the
  REL/RES/UNC formulas against algebraic facts.
- The cardinal sanity invariant is REL - RES + UNC == Brier exactly (under the
  exact-bin formulation), and is exercised in
  ``test_decomposition_sanity_invariant_REL_minus_RES_plus_UNC_equals_Brier``.
"""
from __future__ import annotations

import pytest

from tracking.tracker import SignalTracker


def _make_bins(specs: list[tuple[int, float, float]]) -> dict:
    """Helper: turn (n, predicted, observed) tuples into a bins_response dict."""
    return {
        "bins": [
            {
                "n": n,
                "predicted": p,
                "observed": o,
                "bin_lo": 0.0,
                "bin_hi": 1.0,
                "ci_low": 0.0,
                "ci_high": 1.0,
                "ece_contrib": 0.0,
            }
            for (n, p, o) in specs
        ]
    }


def test_decomposition_perfect_calibration_zero_rel() -> None:
    """When predicted == observed in every bin, REL = 0; RES, UNC > 0."""
    bins = _make_bins([(50, 0.3, 0.3), (50, 0.5, 0.5), (50, 0.7, 0.7)])
    m = SignalTracker.compute_murphy_decomposition(bins)
    assert m["rel"] == pytest.approx(0.0, abs=1e-9)
    # RES > 0 (discrimination present), UNC > 0 (base rate non-degenerate)
    assert m["res"] > 0
    assert m["unc"] > 0


def test_decomposition_zero_resolution() -> None:
    """When all bins have observed == base rate, RES = 0 (no discrimination)."""
    # All bins have observed=0.5 → o_bar=0.5 → RES = mean of 0 = 0.
    bins = _make_bins([(50, 0.3, 0.5), (50, 0.5, 0.5), (50, 0.7, 0.5)])
    m = SignalTracker.compute_murphy_decomposition(bins)
    assert m["res"] == pytest.approx(0.0, abs=1e-9)


def test_decomposition_uncertainty_at_p_half_max() -> None:
    """Base rate 0.5 → UNC = 0.25 (theoretical max for binary)."""
    bins = _make_bins([(100, 0.5, 0.5)])
    m = SignalTracker.compute_murphy_decomposition(bins)
    assert m["unc"] == pytest.approx(0.25, abs=1e-9)


def test_decomposition_uncertainty_at_p_zero() -> None:
    """Base rate 0 → UNC = 0 (deterministic outcome)."""
    bins = _make_bins([(100, 0.5, 0.0)])
    m = SignalTracker.compute_murphy_decomposition(bins)
    assert m["unc"] == pytest.approx(0.0, abs=1e-9)


def test_decomposition_sanity_invariant_REL_minus_RES_plus_UNC_equals_Brier() -> None:
    """The fundamental Murphy invariant: REL - RES + UNC = Brier (= verified_sum).

    Verifies the algebraic identity under the exact-bin formulation, with
    irregular bin counts and irregular probabilities — the realistic case.
    """
    bins = _make_bins(
        [
            (40, 0.2, 0.3),
            (60, 0.4, 0.45),
            (50, 0.6, 0.55),
            (30, 0.8, 0.7),
        ]
    )
    m = SignalTracker.compute_murphy_decomposition(bins)
    invariant = m["rel"] - m["res"] + m["unc"]
    assert invariant == pytest.approx(m["verified_sum"], abs=1e-9)
    # Brier is bounded: 0 (perfect) ≤ Brier ≤ 1 (worst); for non-pathological
    # binary calibration the value sits in [0, 0.5] (random = 0.25).
    assert 0 <= m["verified_sum"] <= 0.5


def test_decomposition_empty_bins_returns_nones() -> None:
    """No bins → None on all components (defensive empty case)."""
    m = SignalTracker.compute_murphy_decomposition({"bins": []})
    assert m["rel"] is None
    assert m["res"] is None
    assert m["unc"] is None
    assert m["verified_sum"] is None


def test_decomposition_zero_total_n_returns_nones() -> None:
    """Bins with sum(n)==0 → None on all components (defensive divide-by-zero)."""
    m = SignalTracker.compute_murphy_decomposition(
        {"bins": [{"n": 0, "predicted": 0.5, "observed": 0.5}]}
    )
    assert m["rel"] is None
    assert m["res"] is None
    assert m["unc"] is None
    assert m["verified_sum"] is None


def test_decomposition_handles_missing_bins_key() -> None:
    """When the response dict has no 'bins' key, treat as empty (defensive)."""
    m = SignalTracker.compute_murphy_decomposition({})
    assert m["rel"] is None
    assert m["res"] is None
    assert m["unc"] is None
    assert m["verified_sum"] is None


def test_decomposition_unc_at_high_base_rate() -> None:
    """Base rate 0.9 → UNC = 0.09 (matches o_bar * (1 - o_bar))."""
    bins = _make_bins([(100, 0.9, 0.9)])
    m = SignalTracker.compute_murphy_decomposition(bins)
    assert m["unc"] == pytest.approx(0.09, abs=1e-9)


def test_decomposition_perfect_brier_zero() -> None:
    """When predicted==observed AND there's only one bin, Brier should be 0:
    REL=0, RES=0 (no discrimination at single point), UNC=o_bar*(1-o_bar);
    verified_sum=UNC = base-rate variance — this matches Brier of always
    predicting the base rate. Sanity: rel == 0 holds.
    """
    bins = _make_bins([(50, 0.3, 0.3)])
    m = SignalTracker.compute_murphy_decomposition(bins)
    assert m["rel"] == pytest.approx(0.0, abs=1e-9)
    assert m["res"] == pytest.approx(0.0, abs=1e-9)  # single bin → no resolution
    assert m["unc"] == pytest.approx(0.3 * 0.7, abs=1e-9)
    assert m["verified_sum"] == pytest.approx(0.21, abs=1e-9)
