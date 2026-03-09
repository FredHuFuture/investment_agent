"""Core drift analysis logic for expected vs actual trade outcomes."""

from __future__ import annotations

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
                SELECT expected_entry_price, expected_target_price, expected_return_pct
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
                SELECT action, quantity, executed_price
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
                "actual_return_pct": None,
                "return_drift_pct": None,
                "position_status": "no_executions",
            }

        buy_value_sum = 0.0
        buy_qty_sum = 0.0
        sell_value_sum = 0.0
        sell_qty_sum = 0.0

        for action, quantity, executed_price in execution_rows:
            normalized_action = str(action).upper()
            qty = float(quantity)
            price = float(executed_price)

            if normalized_action == "BUY":
                buy_qty_sum += qty
                buy_value_sum += qty * price
            elif normalized_action == "SELL":
                sell_qty_sum += qty
                sell_value_sum += qty * price

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

        if buy_qty_sum > 0 and sell_qty_sum >= buy_qty_sum and sell_qty_sum > 0:
            position_status = "closed"
            weighted_avg_exit_price = sell_value_sum / sell_qty_sum

            if weighted_avg_entry_price not in (None, 0):
                actual_return_pct = (
                    weighted_avg_exit_price - weighted_avg_entry_price
                ) / weighted_avg_entry_price

            if actual_return_pct is not None and expected_return_pct is not None:
                return_drift_pct = actual_return_pct - expected_return_pct

        return {
            "thesis_id": thesis_id,
            "expected_entry_price": expected_entry_price,
            "expected_return_pct": expected_return_pct,
            "weighted_avg_entry_price": weighted_avg_entry_price,
            "entry_drift_pct": entry_drift_pct,
            "weighted_avg_exit_price": weighted_avg_exit_price,
            "actual_return_pct": actual_return_pct,
            "return_drift_pct": return_drift_pct,
            "total_buy_qty": buy_qty_sum,
            "total_sell_qty": sell_qty_sum,
            "position_status": position_status,
        }
