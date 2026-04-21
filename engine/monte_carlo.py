"""Monte Carlo simulation engine for portfolio risk projection.

v2: Added block bootstrap to preserve volatility clustering (serial
dependence in variance).  Plain i.i.d. resampling underestimates tail risk
because it destroys the tendency for high-vol days to cluster together.

v3 (FOUND-03): Auto-select block_size via arch.bootstrap.optimal_block_length
(Patton-Politis-White 2004) when the caller does not explicitly supply one.
Falls back to block_size=5 on any exception and logs a WARNING.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import numpy as np

logger = logging.getLogger(__name__)


class MonteCarloSimulator:
    """Run Monte Carlo simulations using historical daily return distribution.

    Parameters
    ----------
    daily_returns : list[float]
        Historical daily percentage returns expressed as decimals
        (e.g. 0.01 for +1%).
    block_size : int | None
        Block length for block bootstrap.  Larger blocks preserve more
        serial dependence (volatility clustering).  When None (default),
        the optimal block length is computed automatically via
        ``arch.bootstrap.optimal_block_length`` (Patton-Politis-White 2004)
        and clamped to ``[3, len(returns)-1]``.  Set to 1 to revert to
        plain i.i.d. resampling.
    """

    MIN_DATA_POINTS = 10

    def __init__(
        self,
        daily_returns: list[float],
        block_size: int | None = None,
    ) -> None:
        if len(daily_returns) < self.MIN_DATA_POINTS:
            raise ValueError(
                f"Need at least {self.MIN_DATA_POINTS} daily returns, "
                f"got {len(daily_returns)}"
            )
        self._returns = np.array(daily_returns, dtype=np.float64)

        # Guard against degenerate data (all zeros → flat projection)
        if np.all(self._returns == 0):
            self._returns = np.zeros_like(self._returns)

        # FOUND-03: auto-select block size via Patton-Politis-White
        # if caller did not explicitly set one.
        if block_size is None:
            self._block_size = self._auto_select_block_size(self._returns)
        else:
            self._block_size = max(1, min(block_size, len(daily_returns)))

    @staticmethod
    def _auto_select_block_size(returns: np.ndarray, fallback: int = 5) -> int:
        """Return the stationary-bootstrap optimal block length per Politis-White (2004).

        Uses ``arch.bootstrap.optimal_block_length``.  On any exception (arch not
        installed, degenerate input, numerical error), returns ``fallback``
        and logs a WARNING.
        """
        try:
            import pandas as pd
            from arch.bootstrap import optimal_block_length

            series = pd.Series(returns)
            res = optimal_block_length(series)
            # arch>=6 returns a DataFrame with columns ('stationary', 'circular').
            raw = float(res["stationary"].iloc[0])
            if not np.isfinite(raw) or raw < 1:
                raise ValueError(f"non-finite or <1 block length: {raw}")
            block = int(round(raw))
        except Exception as exc:
            logger.warning(
                "optimal_block_length failed (%s); falling back to block_size=%d",
                exc,
                fallback,
            )
            return max(1, min(fallback, len(returns) - 1))
        return max(3, min(block, len(returns) - 1))

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
