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
