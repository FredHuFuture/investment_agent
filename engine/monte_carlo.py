"""Monte Carlo simulation engine for portfolio risk projection."""
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
    """

    MIN_DATA_POINTS = 10

    def __init__(self, daily_returns: list[float]) -> None:
        if len(daily_returns) < self.MIN_DATA_POINTS:
            raise ValueError(
                f"Need at least {self.MIN_DATA_POINTS} daily returns, "
                f"got {len(daily_returns)}"
            )
        self._returns = np.array(daily_returns, dtype=np.float64)

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
            ``horizon_days``, ``simulations``, ``dates``, ``current_value``.
        """
        if current_value <= 0:
            raise ValueError("current_value must be positive")
        if horizon_days < 1:
            raise ValueError("horizon_days must be >= 1")
        if n_simulations < 1:
            raise ValueError("n_simulations must be >= 1")

        rng = np.random.default_rng()

        # Sample daily returns with replacement → shape (n_simulations, horizon_days)
        sampled = rng.choice(self._returns, size=(n_simulations, horizon_days), replace=True)

        # Compound returns to build value paths
        # cumulative_growth[i, j] = product of (1 + r) for days 0..j
        cumulative_growth = np.cumprod(1.0 + sampled, axis=1)

        # Paths include day-0 (current_value) through day-N
        # Prepend a column of 1.0 for the starting point
        ones = np.ones((n_simulations, 1))
        cumulative_growth = np.hstack([ones, cumulative_growth])

        paths = current_value * cumulative_growth  # shape (n_simulations, horizon_days+1)

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
        }
