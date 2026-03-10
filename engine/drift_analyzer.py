"""Core drift analysis logic for expected vs actual trade outcomes."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import aiosqlite


class DriftAnalyzer:
    """Analyze entry/return drift for one thesis."""

    def __init__(self, db: str | Path | aiosqlite.Connection) -> None:
        if isinstance(db, aiosqlite.Connection):
            self._connection: aiosqlite.Connection | None = db
            self._db_path: Path | None = None
            return

        self._connection = None
        self._db_path = Path(db)

    async def compute_position_drift(self, thesis_id: int) -> dict[str, Any]:
        """Compute drift metrics for a single thesis."""
        if thesis_id <= 0:
            raise ValueError("thesis_id must be a positive integer.")

        if self._connection is not None:
            return await self._compute_with_conn(self._connection, thesis_id)

        if self._db_path is None:
            raise RuntimeError("DriftAnalyzer is missing both connection and database path.")

        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute("PRAGMA foreign_keys=ON;")
            return await self._compute_with_conn(conn, thesis_id)

    async def _compute_with_conn(
        self, conn: aiosqlite.Connection, thesis_id: int
    ) -> dict[str, Any]:
        thesis_row = await (
            await conn.execute(
                """
                SELECT expected_entry_price, expected_target_price, expected_return_pct, expected_hold_days
                FROM positions_thesis
                WHERE id = ?
                """,
                (thesis_id,),
            )
        ).fetchone()

        if thesis_row is None:
            raise ValueError(f"Thesis id {thesis_id} not found.")

        expected_entry_price = float(thesis_row[0])
        expected_target_price = (
            float(thesis_row[1]) if thesis_row[1] is not None else None
        )
        expected_return_pct = float(thesis_row[2]) if thesis_row[2] is not None else None
        expected_hold_days = thesis_row[3]
        if (
            expected_return_pct is None
            and expected_target_price is not None
            and expected_entry_price != 0
        ):
            expected_return_pct = (
                expected_target_price - expected_entry_price
            ) / expected_entry_price

        execution_rows = await (
            await conn.execute(
                """
                SELECT action, quantity, executed_price, executed_at
                FROM trade_executions
                WHERE thesis_id = ?
                ORDER BY id ASC
                """,
                (thesis_id,),
            )
        ).fetchall()

        if not execution_rows:
            return {
                "thesis_id": thesis_id,
                "expected_entry_price": expected_entry_price,
                "expected_return_pct": expected_return_pct,
                "weighted_avg_entry_price": None,
                "entry_drift_pct": None,
                "weighted_avg_exit_price": None,
                "actual_return_pct": None,
                "return_drift_pct": None,
                "actual_hold_days": None,
                "hold_drift_days": None,
                "total_buy_qty": 0.0,
                "total_sell_qty": 0.0,
                "position_status": "no_executions",
            }

        buy_value_sum = 0.0
        buy_qty_sum = 0.0
        sell_value_sum = 0.0
        sell_qty_sum = 0.0
        first_buy_date: date | None = None
        last_sell_date: date | None = None

        for action, quantity, executed_price, executed_at in execution_rows:
            normalized_action = str(action).upper()
            qty = float(quantity)
            price = float(executed_price)
            exec_date = _parse_date(executed_at)

            if normalized_action == "BUY":
                buy_qty_sum += qty
                buy_value_sum += qty * price
                if exec_date is not None and first_buy_date is None:
                    first_buy_date = exec_date
            elif normalized_action == "SELL":
                sell_qty_sum += qty
                sell_value_sum += qty * price
                if exec_date is not None:
                    last_sell_date = exec_date

        weighted_avg_entry_price = (
            buy_value_sum / buy_qty_sum if buy_qty_sum > 0 else None
        )
        entry_drift_pct = None
        if weighted_avg_entry_price is not None and expected_entry_price != 0:
            entry_drift_pct = (
                weighted_avg_entry_price - expected_entry_price
            ) / expected_entry_price

        position_status = "open"
        weighted_avg_exit_price = None
        actual_return_pct = None
        return_drift_pct = None
        actual_hold_days: int | None = None
        hold_drift_days: int | None = None

        if buy_qty_sum > 0 and sell_qty_sum >= buy_qty_sum and sell_qty_sum > 0:
            position_status = "closed"
            weighted_avg_exit_price = sell_value_sum / sell_qty_sum

            if weighted_avg_entry_price not in (None, 0):
                actual_return_pct = (
                    weighted_avg_exit_price - weighted_avg_entry_price
                ) / weighted_avg_entry_price

            if actual_return_pct is not None and expected_return_pct is not None:
                return_drift_pct = actual_return_pct - expected_return_pct

        if first_buy_date is not None:
            end_date = last_sell_date if position_status == "closed" else date.today()
            actual_hold_days = (end_date - first_buy_date).days
            if expected_hold_days is not None:
                hold_drift_days = actual_hold_days - int(expected_hold_days)

        return {
            "thesis_id": thesis_id,
            "expected_entry_price": expected_entry_price,
            "expected_return_pct": expected_return_pct,
            "weighted_avg_entry_price": weighted_avg_entry_price,
            "entry_drift_pct": entry_drift_pct,
            "weighted_avg_exit_price": weighted_avg_exit_price,
            "actual_return_pct": actual_return_pct,
            "return_drift_pct": return_drift_pct,
            "actual_hold_days": actual_hold_days,
            "hold_drift_days": hold_drift_days,
            "total_buy_qty": buy_qty_sum,
            "total_sell_qty": sell_qty_sum,
            "position_status": position_status,
        }

    async def get_thesis_ids(self, lookback: int = 50) -> list[int]:
        async def _op(conn: aiosqlite.Connection) -> list[int]:
            rows = await (
                await conn.execute(
                    """
                    SELECT id
                    FROM positions_thesis
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (lookback,),
                )
            ).fetchall()
            return [int(row[0]) for row in rows]

        if self._connection is not None:
            return await _op(self._connection)

        if self._db_path is None:
            raise RuntimeError("DriftAnalyzer is missing both connection and database path.")

        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute("PRAGMA foreign_keys=ON;")
            return await _op(conn)

    async def compute_drift_summary(
        self, lookback: int = 50, include_open: bool = False
    ) -> dict[str, Any]:
        thesis_ids = await self.get_thesis_ids(lookback=lookback)
        drifts = [await self.compute_position_drift(thesis_id) for thesis_id in thesis_ids]

        closed = [d for d in drifts if d["position_status"] == "closed"]
        open_pos = [d for d in drifts if d["position_status"] == "open"]
        no_exec = [d for d in drifts if d["position_status"] == "no_executions"]

        entry_pool = closed if not include_open else closed + open_pos
        entry_drifts = [d["entry_drift_pct"] for d in entry_pool if d["entry_drift_pct"] is not None]
        avg_entry_drift_pct = _mean(entry_drifts)

        return_drifts = [d["return_drift_pct"] for d in closed if d["return_drift_pct"] is not None]
        avg_return_drift_pct = _mean(return_drifts)

        actual_returns = [d["actual_return_pct"] for d in closed if d["actual_return_pct"] is not None]
        avg_actual_return_pct = _mean(actual_returns)

        win_rate = None
        if actual_returns:
            win_rate = sum(1 for r in actual_returns if r > 0) / len(actual_returns)

        hold_drifts = [d["hold_drift_days"] for d in closed if d["hold_drift_days"] is not None]
        avg_hold_drift_days = _mean(hold_drifts)

        return {
            "total_theses": len(drifts),
            "closed_count": len(closed),
            "open_count": len(open_pos),
            "no_exec_count": len(no_exec),
            "avg_entry_drift_pct": avg_entry_drift_pct,
            "avg_return_drift_pct": avg_return_drift_pct,
            "avg_actual_return_pct": avg_actual_return_pct,
            "win_rate": win_rate,
            "avg_hold_drift_days": avg_hold_drift_days,
            "individual_drifts": drifts,
        }


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)
