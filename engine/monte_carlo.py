"""Monte Carlo simulation engine for portfolio risk projection.

v2: Added block bootstrap to preserve volatility clustering (serial
dependence in variance).  Plain i.i.d. resampling underestimates tail risk
because it destroys the tendency for high-vol days to cluster together.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np


class MonteCarloSimulator:
    """Run Monte Carlo simulations using historical daily return distribution.

    Parameters
    ----------
    daily_returns : list[float]
        Historical daily percentage returns expressed as decimals
        (e.g. 0.01 for +1%).
    block_size : int
        Block length for block bootstrap.  Larger blocks preserve more
        serial dependence (volatility clustering).  Default 5 (one
        trading week).  Set to 1 to revert to plain i.i.d. resampling.
    """

    MIN_DATA_POINTS = 10

    def __init__(
        self,
        daily_returns: list[float],
        block_size: int = 5,
    ) -> None:
        if len(daily_returns) < self.MIN_DATA_POINTS:
            raise ValueError(
                f"Need at least {self.MIN_DATA_POINTS} daily returns, "
                f"got {len(daily_returns)}"
            )
        self._returns = np.array(daily_returns, dtype=np.float64)
        self._block_size = max(1, min(block_size, len(daily_returns)))

        # Guard against degenerate data (all zeros → flat projection)
        if np.all(self._returns == 0):
            self._returns = np.zeros_like(self._returns)

    # ------------------------------------------------------------------
    def simulate(
        self,
        current_value: float,
        horizon_days: int = 30,
        n_simulations: int = 1000,
    ) -> dict:
        """Generate *n_simulations* random price paths and return percentile bands.

        Uses block bootstrap: consecutive blocks of ``block_size`` days are
        sampled from the historical return series, preserving within-block
        serial dependence (volatility clustering, mean reversion).

        Parameters
        ----------
        current_value : float
            Starting portfolio value.
        horizon_days : int
            Number of trading days to project forward.
        n_simulations : int
            Number of simulation paths.

        Returns
        -------
        dict
            ``percentiles`` – mapping of p5/p25/p50/p75/p95 to value arrays,
            ``horizon_days``, ``simulations``, ``dates``, ``current_value``,
            ``block_size``.
        """
        if current_value <= 0:
            raise ValueError("current_value must be positive")
        if horizon_days < 1:
            raise ValueError("horizon_days must be >= 1")
        if n_simulations < 1:
            raise ValueError("n_simulations must be >= 1")

        rng = np.random.default_rng()
        bs = self._block_size
        n_data = len(self._returns)

        if bs <= 1 or n_data < bs:
            # Fallback: plain i.i.d. resampling
            sampled = rng.choice(
                self._returns, size=(n_simulations, horizon_days), replace=True
            )
        else:
            # Block bootstrap: sample contiguous blocks and concatenate
            # Number of blocks needed to cover horizon_days (may overshoot)
            n_blocks = (horizon_days + bs - 1) // bs
            max_start = n_data - bs  # inclusive upper bound for block start

            # Sample random block start indices
            # shape: (n_simulations, n_blocks)
            starts = rng.integers(0, max_start + 1, size=(n_simulations, n_blocks))

            # Build the sampled return matrix by stacking blocks
            sampled = np.empty((n_simulations, n_blocks * bs), dtype=np.float64)
            for b in range(n_blocks):
                for sim in range(n_simulations):
                    s = starts[sim, b]
                    sampled[sim, b * bs : (b + 1) * bs] = self._returns[s : s + bs]

            # Trim to exact horizon_days
            sampled = sampled[:, :horizon_days]

        # Compound returns to build value paths
        cumulative_growth = np.cumprod(1.0 + sampled, axis=1)

        # Prepend a column of 1.0 for the starting point
        ones = np.ones((n_simulations, 1))
        cumulative_growth = np.hstack([ones, cumulative_growth])

        paths = current_value * cumulative_growth

        # Compute percentile bands across simulations at each time step
        percentile_keys = [5, 25, 50, 75, 95]
        bands: dict[str, list[float]] = {}
        for p in percentile_keys:
            values = np.percentile(paths, p, axis=0)
            bands[f"p{p}"] = [round(float(v), 2) for v in values]

        # Build date strings starting from today
        today = date.today()
        dates = [(today + timedelta(days=i)).isoformat() for i in range(horizon_days + 1)]

        return {
            "percentiles": bands,
            "horizon_days": horizon_days,
            "simulations": n_simulations,
            "dates": dates,
            "current_value": round(float(current_value), 2),
            "block_size": bs,
        }
