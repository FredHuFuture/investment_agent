"""Adaptive weight and threshold optimization from historical performance.

Computes optimal agent weights and signal thresholds from:
1. Backtest results (BatchResult) -- offline optimization
2. Production signal_history (via SignalStore) -- online adaptation

Weight computation uses EWMA-smoothed per-agent accuracy, normalized to sum=1.0.
Threshold optimization uses grid search over configurable range, maximizing Sharpe.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from backtesting.models import BacktestResult
from db.database import DEFAULT_DB_PATH
from engine.aggregator import SignalAggregator


@dataclass
class AdaptiveWeights:
    """Learned weights and thresholds."""

    weights: dict[str, dict[str, float]]  # asset_type -> {agent_name: weight}
    buy_threshold: float = 0.30
    sell_threshold: float = -0.30
    source: str = "default"               # "default" | "backtest" | "production"
    computed_at: str = ""
    sample_size: int = 0
    staleness_days: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "weights": self.weights,
            "buy_threshold": self.buy_threshold,
            "sell_threshold": self.sell_threshold,
            "source": self.source,
            "computed_at": self.computed_at,
            "sample_size": self.sample_size,
        }


class WeightAdapter:
    """Compute optimized agent weights and signal thresholds.

    Two data sources:
    1. Backtest results (dict[ticker][combo_key] = BacktestResult)
    2. Production signal_history (via signal_history table)
    """

    DEFAULT_EWMA_SPAN: int = 20     # ~20 signal lookback for smoothing
    MIN_SIGNALS: int = 10           # Minimum signals before adapting
    STALENESS_DAYS: int = 7         # Re-compute after 7 days

    def __init__(
        self,
        db_path: str = str(DEFAULT_DB_PATH),
        ewma_span: int | None = None,
    ) -> None:
        self._db_path = db_path
        self._ewma_span = ewma_span or self.DEFAULT_EWMA_SPAN

    # ----------------------------------------------------------------
    # From Backtest Results
    # ----------------------------------------------------------------

    def compute_weights_from_backtest(
        self,
        batch_results: dict[str, dict[str, BacktestResult]],
    ) -> AdaptiveWeights:
        """Compute optimal weights from batch backtest results.

        Strategy:
        1. For each single-agent backtest, extract Sharpe ratio as quality score.
        2. Group by asset_type, normalize to sum=1.0.
        3. Grid-search thresholds from the best single-agent runs.

        Args:
            batch_results: results[ticker][combo_key] = BacktestResult

        Returns:
            AdaptiveWeights with optimized weights and thresholds.
        """
        # Collect per-agent quality scores by asset_type
        # agent_scores[asset_type][agent_name] = list of Sharpe ratios
        agent_scores: dict[str, dict[str, list[float]]] = {}
        all_results: list[BacktestResult] = []

        for ticker, combos in batch_results.items():
            for combo_key, result in combos.items():
                all_results.append(result)
                agents = combo_key.split("+")
                at = result.config.asset_type or "stock"
                sharpe = result.metrics.get("sharpe_ratio")
                if sharpe is None:
                    continue

                # Only use single-agent runs for weight derivation
                if len(agents) == 1:
                    agent_name = agents[0]
                    agent_scores.setdefault(at, {}).setdefault(agent_name, []).append(
                        max(sharpe, 0.01)  # Floor at 0.01 to avoid zero weights
                    )

        # Compute weights per asset_type
        weights: dict[str, dict[str, float]] = {}
        total_samples = 0

        for at, agents_dict in agent_scores.items():
            avg_scores: dict[str, float] = {}
            for agent_name, scores in agents_dict.items():
                avg_scores[agent_name] = sum(scores) / len(scores)
                total_samples += len(scores)

            # Normalize to sum=1.0
            total = sum(avg_scores.values())
            if total > 0:
                weights[at] = {
                    name: round(score / total, 4)
                    for name, score in avg_scores.items()
                }
            else:
                # Fallback: equal weights
                n = len(agents_dict)
                weights[at] = {name: round(1.0 / n, 4) for name in agents_dict}

        if not weights:
            # No usable data -- return defaults
            return AdaptiveWeights(
                weights=dict(SignalAggregator.DEFAULT_WEIGHTS),
                source="default",
                computed_at=datetime.now(timezone.utc).isoformat(),
                sample_size=0,
            )

        # Grid-search thresholds
        buy_thresh, sell_thresh = self.optimize_thresholds(all_results)

        return AdaptiveWeights(
            weights=weights,
            buy_threshold=buy_thresh,
            sell_threshold=sell_thresh,
            source="backtest",
            computed_at=datetime.now(timezone.utc).isoformat(),
            sample_size=total_samples,
        )

    # ----------------------------------------------------------------
    # From Production Signal History
    # ----------------------------------------------------------------

    async def compute_weights_from_signals(
        self,
        asset_type: str = "stock",
        lookback: int = 100,
    ) -> AdaptiveWeights:
        """Compute weights from production signal_history using EWMA.

        Steps:
        1. Query resolved signals (WIN/LOSS) with agent_signals_json.
        2. Parse per-agent signals from JSON.
        3. Compute per-agent directional accuracy using EWMA.
        4. Normalize to weights summing to 1.0.

        Returns:
            AdaptiveWeights, or defaults if insufficient data.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute(
                    """
                    SELECT signal, agent_signals_json, outcome
                    FROM signal_history
                    WHERE asset_type = ? AND outcome IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (asset_type, lookback),
                )
            ).fetchall()

        if len(rows) < self.MIN_SIGNALS:
            return AdaptiveWeights(
                weights=dict(SignalAggregator.DEFAULT_WEIGHTS),
                source="default",
                computed_at=datetime.now(timezone.utc).isoformat(),
                sample_size=len(rows),
            )

        # Parse per-agent outcomes
        # agent_outcomes[agent_name] = [True/False, ...] in chronological order
        agent_outcomes: dict[str, list[bool]] = {}

        # Rows are DESC, reverse for chronological
        for row in reversed(rows):
            outcome = row["outcome"]  # "WIN" or "LOSS"
            is_win = outcome == "WIN"
            agent_json = row["agent_signals_json"]

            if agent_json:
                try:
                    agents_data = json.loads(agent_json)
                    # agents_data is list of dicts with agent_name, signal, confidence
                    for agent_entry in agents_data:
                        agent_name = agent_entry.get("agent_name", "")
                        if agent_name:
                            agent_outcomes.setdefault(agent_name, []).append(is_win)
                except (json.JSONDecodeError, TypeError):
                    pass

        if not agent_outcomes:
            return AdaptiveWeights(
                weights=dict(SignalAggregator.DEFAULT_WEIGHTS),
                source="default",
                computed_at=datetime.now(timezone.utc).isoformat(),
                sample_size=len(rows),
            )

        # Compute EWMA accuracy per agent
        agent_accuracy: dict[str, float] = {}
        for agent_name, outcomes in agent_outcomes.items():
            if len(outcomes) >= 3:  # Need at least 3 signals
                agent_accuracy[agent_name] = self._ewma_accuracy(outcomes)

        if not agent_accuracy:
            return AdaptiveWeights(
                weights=dict(SignalAggregator.DEFAULT_WEIGHTS),
                source="default",
                computed_at=datetime.now(timezone.utc).isoformat(),
                sample_size=len(rows),
            )

        # Normalize to sum=1.0
        total = sum(agent_accuracy.values())
        if total > 0:
            learned = {
                name: round(acc / total, 4)
                for name, acc in agent_accuracy.items()
            }
        else:
            n = len(agent_accuracy)
            learned = {name: round(1.0 / n, 4) for name in agent_accuracy}

        # Anti-overfitting: mean-revert toward defaults, enforce floor/ceiling,
        # and rate-limit changes to prevent chasing recent hot streaks.
        defaults = SignalAggregator.DEFAULT_WEIGHTS.get(asset_type, {})
        learned = self._apply_weight_constraints(learned, defaults)

        return AdaptiveWeights(
            weights={asset_type: learned},
            source="production",
            computed_at=datetime.now(timezone.utc).isoformat(),
            sample_size=len(rows),
        )

    # ----------------------------------------------------------------
    # EWMA
    # ----------------------------------------------------------------

    def _ewma_accuracy(self, outcomes: list[bool]) -> float:
        """Compute EWMA-smoothed accuracy from a sequence of outcomes.

        Uses exponential weighting: more recent outcomes weighted higher.
        span=20 means alpha = 2/(20+1) ~ 0.095.

        Args:
            outcomes: List of True (correct) / False (incorrect), chronological.

        Returns:
            Smoothed accuracy in [0, 1].
        """
        if not outcomes:
            return 0.5  # prior: 50% accuracy
        alpha = 2.0 / (self._ewma_span + 1)
        ewma = 0.5  # start at prior
        for outcome in outcomes:
            ewma = alpha * float(outcome) + (1 - alpha) * ewma
        return ewma

    # ----------------------------------------------------------------
    # Anti-overfitting constraints
    # ----------------------------------------------------------------

    # Prevents any single agent from dominating or being suppressed
    WEIGHT_FLOOR = 0.05
    WEIGHT_CEILING = 0.60
    # Maximum weight change per adaptation cycle
    MAX_WEIGHT_DELTA = 0.10
    # Blend factor pulling learned weights back toward defaults
    MEAN_REVERSION_ALPHA = 0.3

    def _apply_weight_constraints(
        self,
        learned: dict[str, float],
        defaults: dict[str, float],
    ) -> dict[str, float]:
        """Apply floor/ceiling, rate-limiting, and mean-reversion to learned weights."""
        constrained: dict[str, float] = {}
        for name, w in learned.items():
            # 1. Mean-reversion toward default
            default_w = defaults.get(name, 1.0 / max(len(learned), 1))
            w = (1 - self.MEAN_REVERSION_ALPHA) * w + self.MEAN_REVERSION_ALPHA * default_w
            # 2. Rate-limit change from default
            delta = w - default_w
            if abs(delta) > self.MAX_WEIGHT_DELTA:
                w = default_w + self.MAX_WEIGHT_DELTA * (1 if delta > 0 else -1)
            # 3. Floor/ceiling
            w = max(self.WEIGHT_FLOOR, min(self.WEIGHT_CEILING, w))
            constrained[name] = w
        # Re-normalize to sum=1.0, then re-apply floor/ceiling to handle
        # edge cases where normalization pushes values outside bounds.
        for _ in range(3):  # iterate to converge
            total = sum(constrained.values())
            if total > 0:
                constrained = {k: v / total for k, v in constrained.items()}
            constrained = {
                k: max(self.WEIGHT_FLOOR, min(self.WEIGHT_CEILING, v))
                for k, v in constrained.items()
            }
        # Final normalization
        total = sum(constrained.values())
        if total > 0:
            constrained = {k: round(v / total, 4) for k, v in constrained.items()}
        return constrained

    # ----------------------------------------------------------------
    # Threshold Optimization
    # ----------------------------------------------------------------

    def optimize_thresholds(
        self,
        backtest_results: list[BacktestResult],
        threshold_range: tuple[float, float] = (0.10, 0.50),
        step: float = 0.05,
    ) -> tuple[float, float]:
        """Grid search for optimal BUY/SELL thresholds.

        For each candidate threshold, re-classify signals from agent_signals_log
        and estimate impact on trade quality.

        Args:
            backtest_results: List of BacktestResult with agent_signals_log.
            threshold_range: (min_threshold, max_threshold).
            step: Grid step size.

        Returns:
            (buy_threshold, sell_threshold) -- currently symmetric.
        """
        if not backtest_results:
            return (0.30, -0.30)

        # Collect all signals with raw_scores and known outcomes
        signal_outcomes: list[tuple[float, bool]] = []
        for result in backtest_results:
            trades = result.trades
            signals_log = result.agent_signals_log
            if not trades or not signals_log:
                continue

            # Map dates to trade outcomes
            trade_outcomes: dict[str, bool] = {}
            for t in trades:
                if t.pnl_pct is not None:
                    trade_outcomes[t.entry_date] = t.pnl_pct > 0

            for sig in signals_log:
                raw_score = sig.get("raw_score")
                date_str = sig.get("date", "")
                if raw_score is not None and date_str in trade_outcomes:
                    signal_outcomes.append((raw_score, trade_outcomes[date_str]))

        if len(signal_outcomes) < 5:
            return (0.30, -0.30)

        # Grid search — optimise BUY and SELL thresholds independently.
        # BUY threshold: a signal above this triggers a long entry.
        # SELL threshold: a signal below the negative triggers an exit/short.
        best_buy_threshold = 0.30
        best_buy_score = -999.0
        best_sell_threshold = -0.30
        best_sell_score = -999.0

        low, high = threshold_range
        t = low
        while t <= high + 1e-9:
            # --- BUY side ---
            buy_correct = 0
            buy_total = 0
            for raw_score, is_win in signal_outcomes:
                if raw_score >= t:
                    buy_correct += int(is_win)
                    buy_total += 1

            buy_accuracy = buy_correct / buy_total if buy_total > 0 else 0.0
            buy_trade_ratio = buy_total / len(signal_outcomes) if signal_outcomes else 0
            buy_score = buy_accuracy * 0.7 + buy_trade_ratio * 0.3

            if buy_score > best_buy_score:
                best_buy_score = buy_score
                best_buy_threshold = round(t, 2)

            # --- SELL side ---
            sell_correct = 0
            sell_total = 0
            for raw_score, is_win in signal_outcomes:
                if raw_score <= -t:
                    # SELL signal correct when position would have lost
                    sell_correct += int(not is_win)
                    sell_total += 1

            sell_accuracy = sell_correct / sell_total if sell_total > 0 else 0.0
            sell_trade_ratio = sell_total / len(signal_outcomes) if signal_outcomes else 0
            sell_score = sell_accuracy * 0.7 + sell_trade_ratio * 0.3

            if sell_score > best_sell_score:
                best_sell_score = sell_score
                best_sell_threshold = round(-t, 2)

            t += step

        return (best_buy_threshold, best_sell_threshold)

    # ----------------------------------------------------------------
    # IC-IR based weights (SIG-03 — Plan 02-03)
    # ----------------------------------------------------------------

    async def compute_ic_weights(
        self,
        tracker: "SignalTracker",  # forward ref avoids circular import
        asset_types: list[str] | None = None,
        agents: list[str] | None = None,
        horizon: str = "5d",
        window: int = 60,
        scale_divisor: float = 2.0,
    ) -> AdaptiveWeights | None:
        """Compute per-agent weights from IC-IR (SIG-03).

        Scaling rule: ``new_weight = base_weight * max(0, ic_ir / scale_divisor)``.

        - Negative IC-IR → factor = 0 → agent removed from aggregation.
        - None IC-IR (insufficient data) → factor = None → agent weight = 0.
        - Returns None if NO agents have sufficient data → caller falls back to EWMA.
        - Equal-weight fallback applied if all agents zero-weighted after scaling.

        ``scale_divisor=2.0`` rescales typical IC-IR values (O(0.3–1.0)) into the
        O(0.15–0.5) multiplier range. source="ic_ir" distinguishes from EWMA weights.
        """
        # Avoid importing SignalTracker at module level (circular import risk).
        # The type annotation uses a string literal; runtime uses duck typing.

        if asset_types is None:
            asset_types = ["stock", "crypto"]
        if agents is None:
            agents = [
                "TechnicalAgent", "FundamentalAgent", "MacroAgent",
                "SentimentAgent", "CryptoAgent",
            ]

        weights: dict[str, dict[str, float]] = {at: {} for at in asset_types}
        any_valid = False
        total_sample_size = 0

        for agent in agents:
            _overall_ic, rolling = await tracker.compute_rolling_ic(
                agent, horizon=horizon, window=window,
            )
            icir = tracker.compute_icir(rolling) if rolling else None
            # max(0, ...) floors at 0: negative IC-IR → zero weight (T-02-03-05)
            factor = max(0.0, icir / scale_divisor) if icir is not None else None
            sample_size = sum(1 for ic in rolling if ic is not None) if rolling else 0
            total_sample_size += sample_size

            if factor is None:
                # Insufficient data — weight stays 0; renormalization will handle
                for at in asset_types:
                    weights[at][agent] = 0.0
                continue

            any_valid = True
            for at in asset_types:
                weights[at][agent] = factor

        if not any_valid:
            # No agents had sufficient IC data → caller falls back to EWMA
            return None

        # Renormalize each asset_type's weights to sum to 1.0
        for at in asset_types:
            total = sum(weights[at].values())
            if total <= 0:
                # All agents are zero/negative → equal-weight fallback
                n_agents = max(1, len(weights[at]))
                equal = 1.0 / n_agents
                weights[at] = {k: equal for k in weights[at]}
            else:
                weights[at] = {k: round(v / total, 4) for k, v in weights[at].items()}

        from datetime import datetime, timezone
        return AdaptiveWeights(
            weights=weights,
            source="ic_ir",  # new literal; source field is str, no change needed
            computed_at=datetime.now(timezone.utc).isoformat(),
            sample_size=total_sample_size,
            staleness_days=0,
        )

    # ----------------------------------------------------------------
    # Persistence
    # ----------------------------------------------------------------

    async def save_weights(self, weights: AdaptiveWeights) -> None:
        """Store learned weights to portfolio_meta as JSON."""
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO portfolio_meta (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (
                    "adaptive_weights",
                    json.dumps(weights.to_dict()),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            await conn.commit()

    async def load_weights(self) -> AdaptiveWeights | None:
        """Load cached weights from portfolio_meta.

        Returns:
            AdaptiveWeights if found, None if not stored.
            Sets staleness_days based on updated_at.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            row = await (
                await conn.execute(
                    "SELECT value, updated_at FROM portfolio_meta WHERE key = ?",
                    ("adaptive_weights",),
                )
            ).fetchone()
            if row is None:
                return None

            try:
                data = json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                return None

            updated_at = row[1]

            # Check staleness
            try:
                updated_dt = datetime.fromisoformat(updated_at)
                # Ensure timezone-aware comparison
                if updated_dt.tzinfo is None:
                    updated_dt = updated_dt.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                age_days = (now - updated_dt).days
            except (ValueError, TypeError):
                age_days = 999

            return AdaptiveWeights(
                weights=data.get("weights", {}),
                buy_threshold=data.get("buy_threshold", 0.30),
                sell_threshold=data.get("sell_threshold", -0.30),
                source=data.get("source", "unknown"),
                computed_at=data.get("computed_at", ""),
                sample_size=data.get("sample_size", 0),
                staleness_days=age_days,
            )
