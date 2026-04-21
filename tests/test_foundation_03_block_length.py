"""Tests for FOUND-03: MonteCarloSimulator auto-selects block_size via
arch.bootstrap.optimal_block_length (Patton-Politis-White 2004).

TDD file: RED written before the implementation is patched into monte_carlo.py.
"""
from __future__ import annotations

import inspect
from unittest.mock import patch

import numpy as np
import pytest

from engine.monte_carlo import MonteCarloSimulator


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

def _make_returns(n: int = 250, seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    return rng.normal(0, 0.01, n).tolist()


def _make_ar1_returns(n: int = 250, phi: float = 0.3, seed: int = 42) -> list[float]:
    """AR(1) returns with a known autocorrelation structure."""
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 0.01, n)
    returns = [noise[0]]
    for i in range(1, n):
        returns.append(phi * returns[-1] + noise[i])
    return returns


# ---------------------------------------------------------------------------
# Test A: Explicit override is preserved
# ---------------------------------------------------------------------------

def test_explicit_block_size_override_preserved() -> None:
    """MonteCarloSimulator(returns, block_size=7) sets _block_size == 7."""
    returns = _make_returns()
    sim = MonteCarloSimulator(returns, block_size=7)
    assert sim._block_size == 7


# ---------------------------------------------------------------------------
# Test B: Auto-selection is invoked when block_size is not supplied
# ---------------------------------------------------------------------------

def test_auto_block_size_in_valid_range() -> None:
    """MonteCarloSimulator(returns) sets _block_size in [3, len(returns)-1]."""
    returns = _make_returns()
    sim = MonteCarloSimulator(returns)
    assert 3 <= sim._block_size <= len(returns) - 1, (
        f"auto block_size={sim._block_size} out of [3, {len(returns)-1}]"
    )


def test_auto_block_size_calls_optimal_block_length_once() -> None:
    """When block_size is None, _auto_select_block_size is called exactly once."""
    returns = _make_returns()
    with patch(
        "engine.monte_carlo.MonteCarloSimulator._auto_select_block_size",
        wraps=MonteCarloSimulator._auto_select_block_size,
    ) as mock_method:
        MonteCarloSimulator(returns)
        assert mock_method.call_count == 1


# ---------------------------------------------------------------------------
# Test C: Sanity band on a deterministic AR(1) series
# ---------------------------------------------------------------------------

def test_ar1_auto_block_size_sanity_band() -> None:
    """For AR(1) phi=0.3, 250 points, auto block_size must be in [3, 30]."""
    returns = _make_ar1_returns()
    sim = MonteCarloSimulator(returns)
    assert 3 <= sim._block_size <= 30, (
        f"auto block_size out of sanity band: {sim._block_size}"
    )


# ---------------------------------------------------------------------------
# Test D: Graceful fallback when arch raises
# ---------------------------------------------------------------------------

def test_fallback_on_arch_error_returns_five() -> None:
    """When arch.bootstrap.optimal_block_length raises, _block_size falls back to 5."""
    returns = _make_returns()
    with patch(
        "arch.bootstrap.optimal_block_length",
        side_effect=ValueError("simulated arch failure"),
    ):
        sim = MonteCarloSimulator(returns)
    assert sim._block_size == 5, (
        f"Expected fallback block_size=5, got {sim._block_size}"
    )


def test_fallback_on_arch_error_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    """When arch raises, a WARNING is logged (not silently swallowed)."""
    import logging
    returns = _make_returns()
    with caplog.at_level(logging.WARNING, logger="engine.monte_carlo"):
        with patch(
            "arch.bootstrap.optimal_block_length",
            side_effect=ValueError("boom"),
        ):
            MonteCarloSimulator(returns)
    assert any("WARNING" in r.levelname or r.levelno >= logging.WARNING for r in caplog.records), (
        "Expected a WARNING log record when arch raises"
    )


# ---------------------------------------------------------------------------
# Test E: simulate() output shape is regression-safe
# ---------------------------------------------------------------------------

def test_simulate_output_shape_unchanged() -> None:
    """simulate() returns same percentile keys and shape as before."""
    returns = _make_returns()
    sim = MonteCarloSimulator(returns)
    result = sim.simulate(current_value=10_000.0, horizon_days=10, n_simulations=50)
    assert set(result["percentiles"].keys()) == {"p5", "p25", "p50", "p75", "p95"}
    for key, values in result["percentiles"].items():
        assert len(values) == 11, f"{key} should have horizon_days+1=11 values"


# ---------------------------------------------------------------------------
# Test F: block_size key in returned dict matches _block_size
# ---------------------------------------------------------------------------

def test_simulate_returns_block_size_key() -> None:
    """simulate() result dict contains 'block_size' matching _block_size."""
    returns = _make_returns()
    sim = MonteCarloSimulator(returns)
    result = sim.simulate(current_value=5_000.0, horizon_days=5, n_simulations=10)
    assert "block_size" in result
    assert result["block_size"] == sim._block_size


# ---------------------------------------------------------------------------
# Test G: optimal_block_length is called with the full returns array
# ---------------------------------------------------------------------------

def test_auto_select_called_with_full_array() -> None:
    """_auto_select_block_size receives the full _returns array (not a slice)."""
    returns = _make_returns(n=250)
    call_args: list = []

    original = MonteCarloSimulator._auto_select_block_size

    def capturing_wrapper(arr: np.ndarray, fallback: int = 5) -> int:
        call_args.append(len(arr))
        return original(arr, fallback)

    with patch(
        "engine.monte_carlo.MonteCarloSimulator._auto_select_block_size",
        side_effect=capturing_wrapper,
    ):
        MonteCarloSimulator(returns)

    assert call_args, "wrapper was never called"
    assert call_args[0] == len(returns), (
        f"Expected full array length {len(returns)}, got {call_args[0]}"
    )


# ---------------------------------------------------------------------------
# Test H: block_size default is None (not 5)
# ---------------------------------------------------------------------------

def test_block_size_parameter_default_is_none() -> None:
    """block_size parameter default must be None (not 5)."""
    sig = inspect.signature(MonteCarloSimulator.__init__)
    default = sig.parameters["block_size"].default
    assert default is None, f"Expected default=None, got default={default!r}"
