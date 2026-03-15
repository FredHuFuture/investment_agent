"""Regime history storage — save and query regime detection snapshots."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import aiosqlite

logger = logging.getLogger(__name__)


class RegimeHistoryStore:
    """Persist regime detection results and query history with duration info."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def save_regime(
        self,
        regime: str,
        confidence: float,
        vix: float | None = None,
        yield_spread: float | None = None,
    ) -> int:
        """Insert a regime snapshot and return the new row id."""
        async with aiosqlite.connect(self._db_path) as conn:
            cursor = await conn.execute(
                """
                INSERT INTO regime_history (regime, confidence, vix, yield_spread)
                VALUES (?, ?, ?, ?)
                """,
                (regime, confidence, vix, yield_spread),
            )
            await conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]

    async def get_history(self, days: int = 90) -> list[dict]:
        """Return regime history with consecutive-duration calculation.

        Each entry contains:
            date          — ISO date string of the detection
            regime        — regime label
            confidence    — detection confidence (0-100)
            duration_days — number of consecutive days this regime persisted
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute(
                    """
                    SELECT regime, confidence, detected_at
                    FROM regime_history
                    WHERE detected_at >= ?
                    ORDER BY detected_at ASC
                    """,
                    (cutoff_str,),
                )
            ).fetchall()

        if not rows:
            return []

        # Build segments: group consecutive entries with the same regime
        segments: list[dict] = []
        prev_regime: str | None = None
        segment_start: str | None = None

        for row in rows:
            regime = row["regime"]
            detected_at = row["detected_at"]
            confidence = row["confidence"]

            if regime != prev_regime:
                # Close previous segment
                if prev_regime is not None and segment_start is not None:
                    duration = self._days_between(segment_start, detected_at)
                    segments[-1]["duration_days"] = max(1, duration)

                # Start new segment
                segments.append(
                    {
                        "date": detected_at,
                        "regime": regime,
                        "confidence": confidence,
                        "duration_days": 1,
                    }
                )
                segment_start = detected_at
                prev_regime = regime
            else:
                # Update confidence to the latest value in this streak
                segments[-1]["confidence"] = confidence

        # Compute duration for the last segment (up to now)
        if segments and segment_start is not None:
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            duration = self._days_between(segment_start, now_str)
            segments[-1]["duration_days"] = max(1, duration)

        return segments

    @staticmethod
    def _days_between(start: str, end: str) -> int:
        """Return the number of days between two datetime strings."""
        fmt_candidates = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
        start_dt = None
        end_dt = None
        for fmt in fmt_candidates:
            try:
                start_dt = datetime.strptime(start, fmt)
                break
            except ValueError:
                continue
        for fmt in fmt_candidates:
            try:
                end_dt = datetime.strptime(end, fmt)
                break
            except ValueError:
                continue
        if start_dt is None or end_dt is None:
            return 1
        delta = (end_dt - start_dt).days
        return max(1, delta)
