"""Signal accuracy tracking and calibration metrics.

Queries the ``signal_history`` table to compute prediction calibration,
per-agent accuracy, and accuracy breakdowns by regime / signal type.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

_DEFAULT_DB = Path("data/investment_agent.db")


class AccuracyTracker:
    """Compute prediction calibration metrics from resolved signal history."""

    def __init__(self, db_path: str | Path = _DEFAULT_DB) -> None:
        self._db_path = Path(db_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def calibration_report(self, lookback: int = 200) -> dict[str, Any]:
        """Return a comprehensive accuracy / calibration report.

        Keys returned:
        - ``overall_accuracy``: win_count / resolved_count
        - ``resolved_count``: number of resolved signals
        - ``accuracy_by_signal``: {BUY: rate, SELL: rate, HOLD: rate}
        - ``accuracy_by_agent``: {agent_name: {accuracy, count, avg_confidence}}
        - ``calibration_curve``: list of {bin, predicted, actual, count}
        - ``accuracy_by_regime``: {RISK_ON: rate, ...}
        - ``recent_trend``: rolling 20-signal accuracy
        """
        rows = await self._fetch_resolved(lookback)
        if not rows:
            return self._empty_report()

        # Overall
        wins = sum(1 for r in rows if r["outcome"] == "WIN")
        total = len(rows)
        overall_accuracy = wins / total if total else 0.0

        # By signal
        accuracy_by_signal = self._group_accuracy(rows, key="final_signal")

        # By regime
        accuracy_by_regime = self._group_accuracy(rows, key="regime")

        # By agent
        accuracy_by_agent = self._per_agent_accuracy(rows)

        # Calibration curve (10-point bins)
        calibration_curve = self._calibration_curve(rows)

        # Recent trend (last 20)
        recent = rows[:20]
        recent_wins = sum(1 for r in recent if r["outcome"] == "WIN")
        recent_trend = recent_wins / len(recent) if recent else 0.0

        return {
            "overall_accuracy": round(overall_accuracy, 4),
            "resolved_count": total,
            "accuracy_by_signal": accuracy_by_signal,
            "accuracy_by_agent": accuracy_by_agent,
            "calibration_curve": calibration_curve,
            "accuracy_by_regime": accuracy_by_regime,
            "recent_trend": round(recent_trend, 4),
        }

    async def agent_calibration(
        self, agent_name: str, lookback: int = 200,
    ) -> dict[str, Any]:
        """Per-agent calibration: does 80% confidence actually win 80%?"""
        rows = await self._fetch_resolved(lookback)
        agent_rows = []
        for r in rows:
            for agent in self._parse_agent_signals(r["agent_signals_json"]):
                if agent.get("agent_name") == agent_name:
                    agent_rows.append({
                        "confidence": agent.get("confidence", 50),
                        "outcome": r["outcome"],
                    })
        return {
            "agent_name": agent_name,
            "count": len(agent_rows),
            "calibration_curve": self._calibration_curve(
                [{"final_confidence": ar["confidence"], "outcome": ar["outcome"]}
                 for ar in agent_rows]
            ),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _fetch_resolved(self, lookback: int) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT final_signal, final_confidence, regime, outcome,
                       agent_signals_json, created_at
                FROM signal_history
                WHERE outcome IN ('WIN', 'LOSS')
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (lookback,),
            )
            return [dict(row) for row in await cursor.fetchall()]

    @staticmethod
    def _group_accuracy(rows: list[dict], key: str) -> dict[str, float]:
        groups: dict[str, list[bool]] = {}
        for r in rows:
            val = r.get(key) or "UNKNOWN"
            groups.setdefault(val, []).append(r["outcome"] == "WIN")
        return {
            k: round(sum(v) / len(v), 4) if v else 0.0
            for k, v in groups.items()
        }

    @staticmethod
    def _parse_agent_signals(json_str: str | None) -> list[dict]:
        if not json_str:
            return []
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return []

    def _per_agent_accuracy(self, rows: list[dict]) -> dict[str, dict[str, Any]]:
        agent_data: dict[str, list[dict]] = {}
        for r in rows:
            is_win = r["outcome"] == "WIN"
            for agent in self._parse_agent_signals(r["agent_signals_json"]):
                name = agent.get("agent_name", "unknown")
                agent_data.setdefault(name, []).append({
                    "win": is_win,
                    "confidence": agent.get("confidence", 50),
                })
        result = {}
        for name, entries in agent_data.items():
            wins = sum(1 for e in entries if e["win"])
            avg_conf = sum(e["confidence"] for e in entries) / len(entries)
            result[name] = {
                "accuracy": round(wins / len(entries), 4),
                "count": len(entries),
                "avg_confidence": round(avg_conf, 2),
            }
        return result

    @staticmethod
    def _calibration_curve(rows: list[dict]) -> list[dict[str, Any]]:
        bins: dict[str, list[bool]] = {}
        for r in rows:
            conf = r.get("final_confidence", 50)
            bucket = int(conf // 10) * 10
            label = f"{bucket}-{bucket + 10}"
            bins.setdefault(label, []).append(r["outcome"] == "WIN")
        curve = []
        for label, outcomes in sorted(bins.items()):
            lo = int(label.split("-")[0])
            curve.append({
                "bin": label,
                "predicted": lo + 5,  # midpoint
                "actual": round(sum(outcomes) / len(outcomes) * 100, 1),
                "count": len(outcomes),
            })
        return curve

    @staticmethod
    def _empty_report() -> dict[str, Any]:
        return {
            "overall_accuracy": 0.0,
            "resolved_count": 0,
            "accuracy_by_signal": {},
            "accuracy_by_agent": {},
            "calibration_curve": [],
            "accuracy_by_regime": {},
            "recent_trend": 0.0,
        }
