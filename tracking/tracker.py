from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any

from tracking.store import SignalStore

# ---------------------------------------------------------------------------
# Note on scipy: pearsonr is imported lazily inside compute_rolling_ic
# to keep the module importable even if scipy is absent at test collection time.
# (scipy IS installed per 02-RESEARCH.md; lazy import is a defensive pattern.)
# ---------------------------------------------------------------------------


def _adaptive_bin_count(
    n_samples: int, min_per_bin: int = 10, max_bins: int = 10
) -> int:
    """Phase 8 SIG-v2-01 (Pitfall 2 mitigation) — bin count adapted to sample size.

    Formula: ``max(2, min(max_bins, n_samples // min_per_bin))``

    - N=15 → 2 bins (floor at 2 to keep diagonal interpretable)
    - N=50 → 5 bins
    - N=200 → 10 bins (capped)

    The floor at 2 keeps the reliability plot visually meaningful even at
    extreme low N (the diagonal y=x reference still produces a 2-point line).
    The cap at 10 caps render cost on large corpora.
    """
    return max(2, min(max_bins, n_samples // min_per_bin))


class SignalTracker:
    """Compute signal accuracy and agent performance metrics."""

    def __init__(self, store: SignalStore) -> None:
        self._store = store

    async def compute_accuracy_stats(
        self, lookback: int = 100
    ) -> dict[str, Any]:
        """Compute overall signal accuracy statistics."""
        total_signals = await self._store.get_signal_count(lookback=lookback)
        resolved = await self._store.get_resolved_signals(lookback=lookback)

        win_count = sum(1 for r in resolved if r["outcome"] == "WIN")
        loss_count = sum(1 for r in resolved if r["outcome"] == "LOSS")
        resolved_count = win_count + loss_count

        win_rate = win_count / resolved_count if resolved_count > 0 else None
        avg_confidence = (
            sum(r["final_confidence"] for r in resolved) / len(resolved)
            if resolved else None
        )

        by_signal: dict[str, dict[str, Any]] = {
            "BUY": {"count": 0, "win_count": 0},
            "SELL": {"count": 0, "win_count": 0},
            "HOLD": {"count": 0, "win_count": 0},
        }
        by_asset: dict[str, dict[str, Any]] = {}
        by_regime: dict[str, dict[str, Any]] = {
            "RISK_ON": {"count": 0, "win_count": 0},
            "RISK_OFF": {"count": 0, "win_count": 0},
            "NEUTRAL": {"count": 0, "win_count": 0},
        }

        for r in resolved:
            sig = r["final_signal"]
            if sig in by_signal:
                by_signal[sig]["count"] += 1
                if r["outcome"] == "WIN":
                    by_signal[sig]["win_count"] += 1

            asset = r["asset_type"]
            if asset not in by_asset:
                by_asset[asset] = {"count": 0, "win_count": 0}
            by_asset[asset]["count"] += 1
            if r["outcome"] == "WIN":
                by_asset[asset]["win_count"] += 1

            regime = r.get("regime")
            if regime and regime in by_regime:
                by_regime[regime]["count"] += 1
                if r["outcome"] == "WIN":
                    by_regime[regime]["win_count"] += 1

        def _win_rate(d: dict) -> float | None:
            c = d["count"]
            return d["win_count"] / c if c > 0 else None

        return {
            "total_signals": total_signals,
            "resolved_count": resolved_count,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": win_rate,
            "avg_confidence": avg_confidence,
            "by_signal": {
                k: {"count": v["count"], "win_rate": _win_rate(v)}
                for k, v in by_signal.items()
            },
            "by_asset_type": {
                k: {"count": v["count"], "win_rate": _win_rate(v)}
                for k, v in by_asset.items()
            },
            "by_regime": {
                k: {"count": v["count"], "win_rate": _win_rate(v)}
                for k, v in by_regime.items()
            },
        }

    async def compute_calibration_data(
        self,
        lookback: int = 100,
        bucket_width: int = 10,
        min_bucket_size: int = 5,
    ) -> list[dict[str, Any]]:
        """Generate confidence calibration chart data.

        Buckets with fewer than min_bucket_size samples are excluded.
        """
        resolved = await self._store.get_resolved_signals(lookback=lookback)

        # Build buckets: each bucket starts at 30, 40, 50, ... 80 (max confidence=90)
        buckets: dict[int, dict[str, Any]] = {}
        for r in resolved:
            conf = r["final_confidence"]
            bucket_start = int(conf // bucket_width) * bucket_width
            if bucket_start not in buckets:
                buckets[bucket_start] = {"wins": 0, "total": 0}
            buckets[bucket_start]["total"] += 1
            if r["outcome"] == "WIN":
                buckets[bucket_start]["wins"] += 1

        result: list[dict[str, Any]] = []
        for bucket_start in sorted(buckets):
            data = buckets[bucket_start]
            if data["total"] < min_bucket_size:
                continue
            bucket_end = bucket_start + bucket_width
            midpoint = bucket_start + bucket_width / 2
            actual_win_rate = (data["wins"] / data["total"]) * 100
            result.append({
                "confidence_bucket": f"{bucket_start}-{bucket_end}",
                "bucket_midpoint": float(midpoint),
                "expected_win_rate": float(midpoint),  # simplification: expected = midpoint
                "actual_win_rate": round(actual_win_rate, 1),
                "sample_size": data["total"],
            })

        return result

    async def compute_agent_performance(
        self, lookback: int = 100
    ) -> dict[str, dict[str, Any]]:
        """Compute per-agent accuracy metrics from resolved signal history."""
        resolved = await self._store.get_resolved_signals(lookback=lookback)

        agents: dict[str, dict[str, Any]] = {}

        for r in resolved:
            outcome = r["outcome"]
            final_signal = r["final_signal"]
            agent_signals = r.get("agent_signals", [])

            for agent_sig in agent_signals:
                name = agent_sig.get("agent_name", "Unknown")
                if name not in agents:
                    agents[name] = {
                        "total_signals": 0,
                        "agreement_count": 0,
                        "confidences": [],
                        "by_signal": {
                            "BUY": {"count": 0, "wins": 0},
                            "SELL": {"count": 0, "wins": 0},
                            "HOLD": {"count": 0},
                        },
                    }

                a = agents[name]
                a["total_signals"] += 1
                a["confidences"].append(float(agent_sig.get("confidence", 0)))

                agent_signal = agent_sig.get("signal", "")
                if agent_signal == final_signal:
                    a["agreement_count"] += 1

                if agent_signal in ("BUY", "SELL"):
                    a["by_signal"][agent_signal]["count"] += 1
                    if outcome == "WIN":
                        a["by_signal"][agent_signal]["wins"] += 1
                elif agent_signal == "HOLD":
                    a["by_signal"]["HOLD"]["count"] += 1

        result: dict[str, dict[str, Any]] = {}
        for name, data in agents.items():
            total = data["total_signals"]
            agreement_rate = (
                data["agreement_count"] / total if total > 0 else 0.0
            )
            avg_conf = (
                sum(data["confidences"]) / len(data["confidences"])
                if data["confidences"] else 0.0
            )

            # Directional accuracy: weighted avg of BUY and SELL accuracy
            buy_data = data["by_signal"]["BUY"]
            sell_data = data["by_signal"]["SELL"]
            buy_acc = buy_data["wins"] / buy_data["count"] if buy_data["count"] > 0 else None
            sell_acc = sell_data["wins"] / sell_data["count"] if sell_data["count"] > 0 else None

            directional_total = buy_data["count"] + sell_data["count"]
            directional_wins = buy_data["wins"] + sell_data["wins"]
            directional_accuracy = (
                directional_wins / directional_total if directional_total > 0 else None
            )

            result[name] = {
                "total_signals": total,
                "agreement_rate": round(agreement_rate, 4),
                "directional_accuracy": (
                    round(directional_accuracy, 4) if directional_accuracy is not None else None
                ),
                "avg_confidence": round(avg_conf, 2),
                "by_signal": {
                    "BUY": {
                        "count": buy_data["count"],
                        "accuracy": round(buy_acc, 4) if buy_acc is not None else None,
                    },
                    "SELL": {
                        "count": sell_data["count"],
                        "accuracy": round(sell_acc, 4) if sell_acc is not None else None,
                    },
                    "HOLD": {"count": data["by_signal"]["HOLD"]["count"]},
                },
            }

        return result

    async def compute_accuracy_trend(
        self, window: int = 30
    ) -> list[dict[str, Any]]:
        """Rolling accuracy trend computed from resolved signals.

        Query resolved signals ordered by created_at (ascending). For each
        signal that has been resolved (has outcome WIN/LOSS), compute a
        rolling window accuracy.
        Return [{date, accuracy_pct, sample_size}]
        """
        # Get all resolved signals (large lookback to capture full history)
        resolved = await self._store.get_resolved_signals(lookback=10_000)

        if len(resolved) < window:
            return []

        # Resolved signals come back in DESC order; reverse to ascending
        resolved.sort(key=lambda r: r["created_at"])

        trend: list[dict[str, Any]] = []
        for i in range(window, len(resolved) + 1):
            window_slice = resolved[i - window : i]
            wins = sum(1 for r in window_slice if r["outcome"] == "WIN")
            accuracy = (wins / len(window_slice)) * 100
            last_entry = window_slice[-1]
            # Extract just the date portion from created_at
            date_str = str(last_entry["created_at"])[:10]
            trend.append({
                "date": date_str,
                "accuracy_pct": round(accuracy, 1),
                "sample_size": len(window_slice),
            })

        return trend

    async def compute_agent_agreement(
        self, lookback: int = 100
    ) -> list[dict[str, Any]]:
        """Pairwise agreement rates between agents.

        Parse agent_signals from the most recent ``lookback`` signals.
        For each pair of agents, compute what percentage they gave the same
        signal direction.
        Return [{agent_a, agent_b, agreement_pct, sample_size}]
        """
        # Use get_signal_history (all signals, not just resolved)
        signals = await self._store.get_signal_history(limit=lookback)

        if not signals:
            return []

        # For each signal row, extract per-agent direction
        pair_counts: dict[tuple[str, str], dict[str, int]] = defaultdict(
            lambda: {"agree": 0, "total": 0}
        )

        for row in signals:
            agent_signals = row.get("agent_signals", [])
            if not agent_signals or not isinstance(agent_signals, list):
                continue

            # Build map: agent_name -> signal direction
            agent_dirs: dict[str, str] = {}
            for asig in agent_signals:
                name = asig.get("agent_name", "")
                sig = asig.get("signal", "")
                if name and sig:
                    agent_dirs[name] = sig

            # Compare all pairs
            agent_names = sorted(agent_dirs.keys())
            for a, b in combinations(agent_names, 2):
                pair_key = (a, b)
                pair_counts[pair_key]["total"] += 1
                if agent_dirs[a] == agent_dirs[b]:
                    pair_counts[pair_key]["agree"] += 1

        result: list[dict[str, Any]] = []
        for (agent_a, agent_b), counts in sorted(pair_counts.items()):
            total = counts["total"]
            if total == 0:
                continue
            agreement_pct = (counts["agree"] / total) * 100
            result.append({
                "agent_a": agent_a,
                "agent_b": agent_b,
                "agreement_pct": round(agreement_pct, 1),
                "sample_size": total,
            })

        return result

    # -----------------------------------------------------------------------
    # SIG-02: Brier Score  (Plan 02-03)
    # -----------------------------------------------------------------------

    async def compute_brier_score(
        self,
        agent_name: str,
        horizon: str = "5d",
        min_samples: int = 20,
    ) -> float | None:
        """One-vs-rest binary Brier score for directional signals only.

        HOLD signals are excluded (AP-05).
        Returns None when N < min_samples (AP-03).
        Lower is better: 0.0 = perfect, 0.25 = random, 1.0 = perfectly wrong.

        Confidence is stored as 0-100 in backtest_signal_history; divided by 100
        here to normalise to [0, 1] probability space.
        """
        rows = await self._store.get_backtest_signals_by_agent(agent_name, horizon)
        directional = [
            r for r in rows
            if r["signal"] in ("BUY", "SELL") and r["forward_return"] is not None
        ]
        if len(directional) < min_samples:
            return None
        squared_errors: list[float] = []
        for r in directional:
            prob = float(r["confidence"]) / 100.0  # normalise 0-100 → 0-1
            if r["signal"] == "BUY":
                outcome = 1.0 if r["forward_return"] > 0 else 0.0
            else:  # SELL
                outcome = 1.0 if r["forward_return"] < 0 else 0.0
            squared_errors.append((prob - outcome) ** 2)
        return round(sum(squared_errors) / len(squared_errors), 4)

    # -----------------------------------------------------------------------
    # SIG-03: Rolling IC + IC-IR  (Plan 02-03)
    # -----------------------------------------------------------------------

    async def compute_rolling_ic(
        self,
        agent_name: str,
        horizon: str = "5d",
        window: int = 60,
        min_samples: int = 30,
    ) -> tuple[float | None, list[float | None]]:
        """Time-series Pearson IC + rolling IC series (SIG-03).

        Returns (overall_ic, rolling_ics).
        Both components are None / [] when total N < min_samples.

        Uses raw_score (continuous), NOT the signal enum string (AP-02 guard).
        NaN produced by pearsonr (degenerate/constant series) is treated as None
        (T-02-03-08 threat mitigated via NaN-check trick: NaN != NaN).

        Semantics of raw_score in backtest_signal_history (WR-01 fix):
            raw_score is the *aggregated* bar-level score from the backtester
            engine (stored at entry["raw_score"] in agent_signals_log, not
            per-agent). IC therefore measures each agent's timing correlation
            with the aggregate signal score for that bar, which is a defensible
            measure of how well each agent aligns with the overall consensus
            direction. It is NOT a per-agent proprietary score.
        """
        rows = await self._store.get_backtest_signals_by_agent(agent_name, horizon)
        scored = [
            (r["raw_score"], r["forward_return"])
            for r in rows
            if r["raw_score"] is not None and r["forward_return"] is not None
        ]
        if len(scored) < min_samples:
            return None, []

        from scipy.stats import pearsonr  # noqa: PLC0415 — lazy import

        scores_all = [s for s, _ in scored]
        returns_all = [ret for _, ret in scored]

        # Overall IC: single Pearson across full series
        try:
            raw_ic, _ = pearsonr(scores_all, returns_all)
            overall_ic: float | None = (
                float(raw_ic) if raw_ic == raw_ic else None  # NaN guard
            )
        except Exception:
            overall_ic = None

        # Rolling IC — 60-observation sliding window
        rolling: list[float | None] = []
        n = len(scored)
        for i in range(n):
            if i < window - 1:
                rolling.append(None)
                continue
            s_win = scores_all[i - window + 1 : i + 1]
            r_win = returns_all[i - window + 1 : i + 1]
            if len(s_win) < min_samples:
                rolling.append(None)
                continue
            try:
                ic_val, _ = pearsonr(s_win, r_win)
                rolling.append(
                    float(ic_val) if ic_val == ic_val else None  # NaN guard
                )
            except Exception:
                rolling.append(None)

        rounded_ic = round(overall_ic, 4) if overall_ic is not None else None
        return rounded_ic, rolling

    @staticmethod
    def compute_icir(rolling_ics: list[float | None]) -> float | None:
        """IC-IR = mean(IC) / std(IC) over the supplied rolling IC series.

        Returns None when:
        - fewer than 5 valid IC values (insufficient history — AP-03)
        - std(IC) == 0 (degenerate series — T-02-03-04 mitigation)
        """
        valid = [ic for ic in rolling_ics if ic is not None]
        if len(valid) < 5:
            return None
        import statistics  # noqa: PLC0415 — stdlib, lazy for clarity
        mean_ic = statistics.mean(valid)
        std_ic = statistics.stdev(valid)
        if std_ic == 0:
            return None
        return round(mean_ic / std_ic, 4)

    # -----------------------------------------------------------------------
    # Phase 8 SIG-v2-01: Reliability bins + adaptive bin count + Wilson 95% CI
    # -----------------------------------------------------------------------

    async def compute_reliability_bins(
        self,
        agent_name: str,
        horizon: str = "5d",
        min_per_bin: int = 10,
        max_bins: int = 10,
        fundamentals_provider: str | None = "yfinance",
    ) -> dict[str, Any]:
        """Phase 8 SIG-v2-01: per-agent reliability bins for calibration plot.

        Reads from ``backtest_signal_history`` (consistent with Brier/IC).
        Excludes HOLD signals (one-vs-rest binary; mirrors compute_brier_score).
        Bins predicted-confidence × observed-win-rate via quantile binning so
        each bin holds approximately equal sample count (sklearn 'quantile'
        strategy). Per-bin Wilson 95% CI (z = 1.96) provides binomial-proportion
        error bars without bootstrap cost.

        Returns:
            {
                "bins": [{bin_lo, bin_hi, n, predicted, observed,
                          ci_low, ci_high, ece_contrib}, ...],
                "n_samples": int,
                "n_bins_used": int,
                "preliminary_calibration": bool,
                "ece": float | None,
            }

        Empty / low-N cases:
            - n_samples == 0 → empty bins, ece=None, preliminary_calibration=True
            - n_samples < min_per_bin * 2 → empty bins, ece=None, preliminary=True
            - duplicate-quantile collapse to <2 bins → empty bins, preliminary=True

        Mitigations:
            - Pitfall 2 (Swiss-cheese binning at small N) → adaptive bin count +
              ``preliminary_calibration`` flag set when n_bins_used < 5 OR any
              bin has n < min_per_bin
            - Pitfall 4 (provider-mixed corpus) → filter rows by
              ``fundamentals_provider`` (default 'yfinance'); pass None for
              cross-provider audit
        """
        import numpy as np  # noqa: PLC0415 — lazy import (matches scipy pattern)
        # noqa: PLC0415 — lazy import; sklearn is a direct dep but mirror the
        # compute_rolling_ic lazy-import pattern for collection-time safety.
        from sklearn.calibration import calibration_curve  # noqa: F401, PLC0415

        rows = await self._store.get_backtest_signals_by_agent(
            agent_name,
            horizon,
            fundamentals_provider=fundamentals_provider,
        )

        # Translate signal rows to (y_true, y_prob) pairs (HOLD excluded).
        # BUY wins when forward_return > 0; SELL wins when forward_return < 0.
        y_true_list: list[int] = []
        y_prob_list: list[float] = []
        for r in rows:
            if r.get("signal") == "HOLD":
                continue
            fwd = r.get("forward_return")
            # Some test fixtures pass forward_return_5d/forward_return_21d
            # explicitly without flattening; keep the fallback for parity.
            if fwd is None:
                fwd = r.get(f"forward_return_{horizon}")
            if fwd is None:
                continue
            confidence = r.get("confidence")
            if confidence is None:
                continue
            y_prob = float(confidence) / 100.0
            if r.get("signal") == "BUY":
                y_true_list.append(1 if fwd > 0 else 0)
            elif r.get("signal") == "SELL":
                y_true_list.append(1 if fwd < 0 else 0)
            else:
                # Unknown signal direction — skip
                continue
            y_prob_list.append(y_prob)

        n_samples = len(y_true_list)

        # Defensive: zero/very-low samples → empty result with preliminary=True.
        if n_samples == 0 or n_samples < min_per_bin * 2:
            return {
                "bins": [],
                "n_samples": n_samples,
                "n_bins_used": 0,
                "preliminary_calibration": True,
                "ece": None,
            }

        n_bins = _adaptive_bin_count(n_samples, min_per_bin, max_bins)

        y_true_arr = np.asarray(y_true_list, dtype=int)
        y_prob_arr = np.asarray(y_prob_list, dtype=float)

        # Compute bin edges via quantiles for equal-N bins (mirrors sklearn
        # calibration_curve(strategy='quantile') behavior). De-duplicate edges
        # to handle constant-confidence corner cases.
        edges = np.quantile(y_prob_arr, np.linspace(0, 1, n_bins + 1))
        edges = np.unique(edges)
        if len(edges) - 1 < 2:
            return {
                "bins": [],
                "n_samples": n_samples,
                "n_bins_used": 0,
                "preliminary_calibration": True,
                "ece": None,
            }

        # Assign each sample to a bin index 0..len(edges)-2.
        # np.digitize with edges[1:-1] yields 0..len(edges)-2 inclusive.
        bin_indices = np.digitize(y_prob_arr, edges[1:-1])

        z = 1.96  # Wilson 95% CI z-value (scipy.stats.norm.ppf(0.975))
        bins_out: list[dict[str, Any]] = []
        for k in range(len(edges) - 1):
            mask = bin_indices == k
            n_k = int(mask.sum())
            if n_k == 0:
                continue
            observed = float(y_true_arr[mask].mean())
            predicted = float(y_prob_arr[mask].mean())

            # Wilson 95% CI (binomial proportion):
            # center = (p + z²/2n) / (1 + z²/n)
            # half_width = z * sqrt(p(1-p)/n + z²/4n²) / (1 + z²/n)
            p_hat = observed
            denom = 1.0 + (z**2) / n_k
            center = (p_hat + (z**2) / (2 * n_k)) / denom
            half = (
                z
                * np.sqrt(p_hat * (1 - p_hat) / n_k + (z**2) / (4 * n_k**2))
                / denom
            )
            ci_low = max(0.0, float(center - half))
            ci_high = min(1.0, float(center + half))

            ece_contrib = (n_k / n_samples) * abs(predicted - observed)
            bins_out.append(
                {
                    "bin_lo": float(edges[k]),
                    "bin_hi": float(edges[k + 1]),
                    "n": n_k,
                    "predicted": predicted,
                    "observed": observed,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "ece_contrib": float(ece_contrib),
                }
            )

        ece = sum(b["ece_contrib"] for b in bins_out) if bins_out else 0.0
        min_bin_n = min((b["n"] for b in bins_out), default=0)
        preliminary = len(bins_out) < 5 or min_bin_n < min_per_bin
        return {
            "bins": bins_out,
            "n_samples": n_samples,
            "n_bins_used": len(bins_out),
            "preliminary_calibration": preliminary,
            "ece": float(ece) if bins_out else None,
        }

    # -----------------------------------------------------------------------
    # Phase 8 SIG-v2-02: Murphy 3-component Brier decomposition
    # -----------------------------------------------------------------------

    @staticmethod
    def compute_murphy_decomposition(bins_response: dict) -> dict:
        """Phase 8 SIG-v2-02: Murphy exact-bin decomposition (REL - RES + UNC ≈ Brier).

        Reads predicted/observed/n from the output of ``compute_reliability_bins``
        (no duplicate corpus query). Vectorized numpy math.

        Exact-bin formulas (Murphy 1973 / Wikipedia 'Brier score'):
            N    = sum(n_k)
            o_bar = sum(n_k * o_k) / N        # base rate
            REL  = (1/N) * sum(n_k * (f_k - o_k)^2)   # reliability (lower better)
            RES  = (1/N) * sum(n_k * (o_k - o_bar)^2) # resolution (higher better)
            UNC  = o_bar * (1 - o_bar)                 # uncertainty
            Brier ≈ REL - RES + UNC                    # invariant ("verified_sum")

        Bias-corrected exact-bin is stable at N ≥ 60 per bin (Ferro & Fricker 2012).
        Below that threshold, the bins_response.preliminary_calibration flag
        already surfaces — consumers should respect it for interpretation.

        Args:
            bins_response: output of compute_reliability_bins, with key 'bins'
                           containing list of {n, predicted, observed, ...} dicts.

        Returns:
            {rel, res, unc, verified_sum} all floats in [0, 1] or all None when
            bins is empty / total N is zero.
        """
        import numpy as np  # noqa: PLC0415 — lazy import (matches scipy pattern)

        bins = bins_response.get("bins", [])
        if not bins:
            return {"rel": None, "res": None, "unc": None, "verified_sum": None}

        n_arr = np.asarray([b["n"] for b in bins], dtype=float)
        f_arr = np.asarray([b["predicted"] for b in bins], dtype=float)
        o_arr = np.asarray([b["observed"] for b in bins], dtype=float)
        N = float(n_arr.sum())
        if N == 0:
            return {"rel": None, "res": None, "unc": None, "verified_sum": None}

        o_bar = float((n_arr * o_arr).sum() / N)
        rel = float((n_arr * (f_arr - o_arr) ** 2).sum() / N)
        res = float((n_arr * (o_arr - o_bar) ** 2).sum() / N)
        unc = float(o_bar * (1.0 - o_bar))
        return {
            "rel": rel,
            "res": res,
            "unc": unc,
            # ≈ Brier — sanity invariant: REL - RES + UNC == Brier exactly under
            # the exact-bin formulation. Consumer can cross-check against
            # compute_brier_score for the same corpus / horizon / provider.
            "verified_sum": rel - res + unc,
        }
