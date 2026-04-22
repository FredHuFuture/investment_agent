from __future__ import annotations

from datetime import date as date_cls
from pathlib import Path
from typing import Any, Iterable

import aiosqlite

from portfolio.models import Portfolio, Position, PositionStatus, validate_status_transition


class PortfolioManager:
    def __init__(self, db: str | Path | aiosqlite.Connection) -> None:
        if isinstance(db, aiosqlite.Connection):
            self._connection: aiosqlite.Connection | None = db
            self._db_path: Path | None = None
            return

        self._connection = None
        self._db_path = Path(db)

    @staticmethod
    async def _ensure_thesis_text_column(conn: aiosqlite.Connection) -> None:
        """Ensure positions_thesis has a thesis_text column (lightweight migration)."""
        info = await (await conn.execute("PRAGMA table_info(positions_thesis);")).fetchall()
        existing = {row[1] for row in info}
        if "thesis_text" not in existing:
            await conn.execute(
                "ALTER TABLE positions_thesis ADD COLUMN thesis_text TEXT;"
            )

    async def _with_conn(self, func):
        if self._connection is not None:
            return await func(self._connection)

        if self._db_path is None:
            raise RuntimeError("PortfolioManager is missing both connection and database path.")

        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute("PRAGMA foreign_keys=ON;")
            return await func(conn)

    async def add_position(
        self,
        ticker: str,
        asset_type: str,
        quantity: float,
        avg_cost: float,
        entry_date: str,
        sector: str | None = None,
        industry: str | None = None,
        thesis_text: str | None = None,
        expected_return_pct: float | None = None,
        expected_hold_days: int | None = None,
        target_price: float | None = None,
        stop_loss: float | None = None,
    ) -> int:
        async def _op(conn: aiosqlite.Connection) -> int:
            existing = await (
                await conn.execute(
                    "SELECT 1 FROM active_positions WHERE ticker = ? AND status = 'open'",
                    (ticker,),
                )
            ).fetchone()
            if existing:
                raise ValueError(f"An open position for ticker '{ticker}' already exists.")

            # Check if any thesis field is provided
            has_thesis = any(
                v is not None
                for v in (thesis_text, expected_return_pct, expected_hold_days, target_price, stop_loss)
            )

            thesis_id: int | None = None
            effective_return_pct = expected_return_pct
            if has_thesis:
                # Auto-compute expected_return_pct from target_price if not given
                if effective_return_pct is None and target_price is not None and avg_cost > 0:
                    effective_return_pct = (target_price - avg_cost) / avg_cost

                await self._ensure_thesis_text_column(conn)
                thesis_cursor = await conn.execute(
                    """
                    INSERT INTO positions_thesis (
                        ticker, asset_type, expected_signal, expected_confidence,
                        expected_entry_price, expected_target_price,
                        expected_return_pct, expected_stop_loss, expected_hold_days,
                        thesis_text
                    )
                    VALUES (?, ?, 'BUY', 0.7, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ticker, asset_type, avg_cost, target_price,
                        effective_return_pct, stop_loss, expected_hold_days,
                        thesis_text,
                    ),
                )
                thesis_id = int(thesis_cursor.lastrowid)

            cursor = await conn.execute(
                """
                INSERT INTO active_positions (
                    ticker,
                    asset_type,
                    quantity,
                    avg_cost,
                    sector,
                    industry,
                    entry_date,
                    original_analysis_id,
                    expected_return_pct,
                    expected_hold_days
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker, asset_type, quantity, avg_cost, sector, industry,
                    entry_date, thesis_id, effective_return_pct, expected_hold_days,
                ),
            )
            await conn.commit()
            return int(cursor.lastrowid)

        return await self._with_conn(_op)

    async def remove_position(self, ticker: str) -> bool:
        async def _op(conn: aiosqlite.Connection) -> bool:
            cursor = await conn.execute(
                "DELETE FROM active_positions WHERE ticker = ?",
                (ticker,),
            )
            await conn.commit()
            return cursor.rowcount > 0

        return await self._with_conn(_op)

    async def close_position(
        self,
        ticker: str,
        exit_price: float,
        exit_reason: str = "manual",
        exit_date: str | None = None,
    ) -> dict[str, Any]:
        """Close an open position: mark as closed, compute realized P&L, record trade."""
        if exit_date is None:
            exit_date = date_cls.today().isoformat()

        async def _op(conn: aiosqlite.Connection) -> dict[str, Any]:
            row = await (
                await conn.execute(
                    """
                    SELECT ticker, asset_type, quantity, avg_cost,
                           original_analysis_id, entry_date, status
                    FROM active_positions
                    WHERE ticker = ? AND status = 'open'
                    """,
                    (ticker,),
                )
            ).fetchone()
            if row is None:
                raise ValueError(f"No open position found for ticker '{ticker}'.")

            # UI-06 FSM guard: read actual status from DB row so the guard is
            # genuinely defensive against data inconsistencies, not just a
            # documentation comment (WR-02 fix).
            current_status = str(row[6])
            validate_status_transition(current_status, PositionStatus.CLOSED.value)

            quantity = float(row[2])
            avg_cost = float(row[3])
            thesis_id = row[4]
            entry_date_str = row[5]
            realized_pnl = (exit_price - avg_cost) * quantity

            # Mark position as closed
            await conn.execute(
                """
                UPDATE active_positions
                SET status = 'closed',
                    exit_price = ?,
                    exit_date = ?,
                    exit_reason = ?,
                    realized_pnl = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE ticker = ? AND status = 'open'
                """,
                (exit_price, exit_date, exit_reason, realized_pnl, ticker),
            )

            # Record trade execution
            if thesis_id is not None:
                await conn.execute(
                    """
                    INSERT INTO trade_executions
                        (thesis_id, action, quantity, executed_price, executed_at, reason)
                    VALUES (?, 'SELL', ?, ?, ?, ?)
                    """,
                    (thesis_id, quantity, exit_price, exit_date, exit_reason),
                )

            # Auto-resolve linked signal
            if thesis_id is not None:
                return_pct = (exit_price - avg_cost) / avg_cost if avg_cost > 0 else 0.0
                outcome = "WIN" if return_pct > 0 else "LOSS"
                await conn.execute(
                    """
                    UPDATE signal_history
                    SET outcome = ?,
                        outcome_return_pct = ?,
                        outcome_resolved_at = ?
                    WHERE thesis_id = ? AND outcome = 'OPEN'
                    """,
                    (outcome, return_pct, exit_date, thesis_id),
                )

            await conn.commit()

            return {
                "ticker": ticker,
                "quantity": quantity,
                "avg_cost": avg_cost,
                "exit_price": exit_price,
                "exit_date": exit_date,
                "exit_reason": exit_reason,
                "realized_pnl": realized_pnl,
                "return_pct": (exit_price - avg_cost) / avg_cost if avg_cost > 0 else 0.0,
            }

        return await self._with_conn(_op)

    async def set_target_weight(self, ticker: str, target_weight: float | None) -> bool:
        """UI-04: persist target_weight for an open position.

        Caller should enforce 0.0<=value<=1.0 at API layer — this method does
        not re-validate to keep DB layer focused.  Pass None to clear the field.
        Returns True if an open position was updated, False if not found.
        """
        async def _op(conn: aiosqlite.Connection) -> bool:
            cur = await conn.execute(
                "UPDATE active_positions SET target_weight = ? "
                "WHERE ticker = ? AND status = 'open'",
                (target_weight, ticker),
            )
            await conn.commit()
            return cur.rowcount > 0

        return await self._with_conn(_op)

    async def get_closed_positions(self) -> list[Position]:
        """Return all closed positions."""
        async def _op(conn: aiosqlite.Connection) -> list[Position]:
            await self._ensure_thesis_text_column(conn)
            rows = await (
                await conn.execute(
                    """
                    SELECT
                        ap.ticker,
                        ap.asset_type,
                        ap.quantity,
                        ap.avg_cost,
                        ap.sector,
                        ap.industry,
                        ap.entry_date,
                        ap.original_analysis_id,
                        ap.expected_return_pct,
                        ap.expected_hold_days,
                        pt.thesis_text,
                        pt.expected_target_price,
                        pt.expected_stop_loss,
                        ap.status,
                        ap.exit_price,
                        ap.exit_date,
                        ap.exit_reason,
                        ap.realized_pnl
                    FROM active_positions ap
                    LEFT JOIN positions_thesis pt ON ap.original_analysis_id = pt.id
                    WHERE ap.status = 'closed'
                    ORDER BY ap.exit_date DESC
                    """
                )
            ).fetchall()
            return [Position.from_db_row(row) for row in rows]

        return await self._with_conn(_op)

    async def update_position(self, ticker: str, **kwargs) -> bool:
        allowed_fields = {
            "quantity",
            "avg_cost",
            "sector",
            "industry",
            "entry_date",
            "expected_return_pct",
            "expected_hold_days",
        }

        updates: list[str] = []
        params: list[Any] = []

        for key, value in kwargs.items():
            if key not in allowed_fields:
                raise ValueError(f"Field '{key}' cannot be updated.")
            updates.append(f"{key} = ?")
            params.append(value)

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(ticker)

        async def _op(conn: aiosqlite.Connection) -> bool:
            cursor = await conn.execute(
                f"UPDATE active_positions SET {', '.join(updates)} WHERE ticker = ?",
                params,
            )
            await conn.commit()
            return cursor.rowcount > 0

        return await self._with_conn(_op)

    async def get_position(self, ticker: str) -> Position | None:
        async def _op(conn: aiosqlite.Connection) -> Position | None:
            await self._ensure_thesis_text_column(conn)
            row = await (
                await conn.execute(
                    """
                    SELECT
                        ap.ticker,
                        ap.asset_type,
                        ap.quantity,
                        ap.avg_cost,
                        ap.sector,
                        ap.industry,
                        ap.entry_date,
                        ap.original_analysis_id,
                        ap.expected_return_pct,
                        ap.expected_hold_days,
                        pt.thesis_text,
                        pt.expected_target_price,
                        pt.expected_stop_loss,
                        ap.status,
                        ap.exit_price,
                        ap.exit_date,
                        ap.exit_reason,
                        ap.realized_pnl
                    FROM active_positions ap
                    LEFT JOIN positions_thesis pt ON ap.original_analysis_id = pt.id
                    WHERE ap.ticker = ?
                    """,
                    (ticker,),
                )
            ).fetchone()
            if row is None:
                return None
            return Position.from_db_row(row)

        return await self._with_conn(_op)

    async def update_thesis(
        self,
        ticker: str,
        thesis_text: str | None = None,
        target_price: float | None = None,
        stop_loss: float | None = None,
        expected_hold_days: int | None = None,
        expected_return_pct: float | None = None,
    ) -> dict[str, Any]:
        """Update thesis fields for an existing position.

        If no thesis row exists yet, create one.
        Auto-computes expected_return_pct from target_price and avg_cost
        when expected_return_pct is not explicitly provided.
        """
        async def _op(conn: aiosqlite.Connection) -> dict[str, Any]:
            await self._ensure_thesis_text_column(conn)

            # Fetch the active position
            pos_row = await (
                await conn.execute(
                    """
                    SELECT ticker, asset_type, avg_cost, original_analysis_id
                    FROM active_positions
                    WHERE ticker = ? AND status = 'open'
                    """,
                    (ticker,),
                )
            ).fetchone()
            if pos_row is None:
                raise ValueError(f"No open position found for ticker '{ticker}'.")

            asset_type = pos_row[1]
            avg_cost = float(pos_row[2])
            thesis_id = pos_row[3]

            # Auto-compute expected_return_pct from target_price if not provided
            effective_return_pct = expected_return_pct
            if effective_return_pct is None and target_price is not None and avg_cost > 0:
                effective_return_pct = (target_price - avg_cost) / avg_cost

            if thesis_id is not None:
                # Update existing thesis row
                updates: list[str] = []
                params: list[Any] = []

                if thesis_text is not None:
                    updates.append("thesis_text = ?")
                    params.append(thesis_text)
                if target_price is not None:
                    updates.append("expected_target_price = ?")
                    params.append(target_price)
                if stop_loss is not None:
                    updates.append("expected_stop_loss = ?")
                    params.append(stop_loss)
                if expected_hold_days is not None:
                    updates.append("expected_hold_days = ?")
                    params.append(expected_hold_days)
                if effective_return_pct is not None:
                    updates.append("expected_return_pct = ?")
                    params.append(effective_return_pct)

                if updates:
                    params.append(thesis_id)
                    await conn.execute(
                        f"UPDATE positions_thesis SET {', '.join(updates)} WHERE id = ?",
                        params,
                    )

                # Also sync expected_return_pct / expected_hold_days on active_positions
                pos_updates: list[str] = []
                pos_params: list[Any] = []
                if effective_return_pct is not None:
                    pos_updates.append("expected_return_pct = ?")
                    pos_params.append(effective_return_pct)
                if expected_hold_days is not None:
                    pos_updates.append("expected_hold_days = ?")
                    pos_params.append(expected_hold_days)
                if pos_updates:
                    pos_updates.append("updated_at = CURRENT_TIMESTAMP")
                    pos_params.append(ticker)
                    await conn.execute(
                        f"UPDATE active_positions SET {', '.join(pos_updates)} WHERE ticker = ?",
                        pos_params,
                    )
            else:
                # Create a new thesis row
                thesis_cursor = await conn.execute(
                    """
                    INSERT INTO positions_thesis (
                        ticker, asset_type, expected_signal, expected_confidence,
                        expected_entry_price, expected_target_price,
                        expected_return_pct, expected_stop_loss, expected_hold_days,
                        thesis_text
                    )
                    VALUES (?, ?, 'BUY', 0.7, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ticker, asset_type, avg_cost, target_price,
                        effective_return_pct, stop_loss, expected_hold_days,
                        thesis_text,
                    ),
                )
                thesis_id = int(thesis_cursor.lastrowid)

                # Link to active_positions
                pos_updates_new: list[str] = ["original_analysis_id = ?"]
                pos_params_new: list[Any] = [thesis_id]
                if effective_return_pct is not None:
                    pos_updates_new.append("expected_return_pct = ?")
                    pos_params_new.append(effective_return_pct)
                if expected_hold_days is not None:
                    pos_updates_new.append("expected_hold_days = ?")
                    pos_params_new.append(expected_hold_days)
                pos_updates_new.append("updated_at = CURRENT_TIMESTAMP")
                pos_params_new.append(ticker)
                await conn.execute(
                    f"UPDATE active_positions SET {', '.join(pos_updates_new)} WHERE ticker = ?",
                    pos_params_new,
                )

            await conn.commit()

            # Return the updated thesis via get_thesis
            return await self._get_thesis_inner(conn, ticker)

        return await self._with_conn(_op)

    async def _get_thesis_inner(self, conn: aiosqlite.Connection, ticker: str) -> dict[str, Any]:
        """Internal helper to fetch thesis data using an existing connection."""
        await self._ensure_thesis_text_column(conn)
        row = await (
            await conn.execute(
                """
                SELECT
                    pt.id,
                    pt.ticker,
                    pt.expected_signal,
                    pt.expected_confidence,
                    pt.expected_entry_price,
                    pt.expected_target_price,
                    pt.expected_return_pct,
                    pt.expected_stop_loss,
                    pt.expected_hold_days,
                    pt.thesis_text,
                    pt.created_at,
                    ap.entry_date
                FROM active_positions ap
                JOIN positions_thesis pt ON ap.original_analysis_id = pt.id
                WHERE ap.ticker = ?
                """,
                (ticker,),
            )
        ).fetchone()
        if row is None:
            return {}

        entry_date_str = row[11]
        hold_days_elapsed: int | None = None
        hold_drift_days: int | None = None
        expected_hold = row[8]
        if entry_date_str:
            try:
                entry = date_cls.fromisoformat(entry_date_str)
                hold_days_elapsed = (date_cls.today() - entry).days
                if expected_hold is not None:
                    hold_drift_days = hold_days_elapsed - int(expected_hold)
            except ValueError:
                pass

        return {
            "thesis_id": row[0],
            "ticker": row[1],
            "expected_signal": row[2],
            "expected_confidence": float(row[3]),
            "expected_entry_price": float(row[4]),
            "expected_target_price": float(row[5]) if row[5] is not None else None,
            "expected_return_pct": float(row[6]) if row[6] is not None else None,
            "expected_stop_loss": float(row[7]) if row[7] is not None else None,
            "expected_hold_days": int(expected_hold) if expected_hold is not None else None,
            "thesis_text": row[9],
            "created_at": row[10],
            "hold_days_elapsed": hold_days_elapsed,
            "hold_drift_days": hold_drift_days,
            "return_drift_pct": None,  # requires current price
        }

    async def get_thesis(self, ticker: str) -> dict[str, Any] | None:
        """Get thesis data for a position. Returns None if no thesis recorded."""
        async def _op(conn: aiosqlite.Connection) -> dict[str, Any] | None:
            await self._ensure_thesis_text_column(conn)
            row = await (
                await conn.execute(
                    """
                    SELECT
                        pt.id,
                        pt.ticker,
                        pt.expected_signal,
                        pt.expected_confidence,
                        pt.expected_entry_price,
                        pt.expected_target_price,
                        pt.expected_return_pct,
                        pt.expected_stop_loss,
                        pt.expected_hold_days,
                        pt.thesis_text,
                        pt.created_at,
                        ap.entry_date
                    FROM active_positions ap
                    JOIN positions_thesis pt ON ap.original_analysis_id = pt.id
                    WHERE ap.ticker = ?
                    """,
                    (ticker,),
                )
            ).fetchone()
            if row is None:
                return None

            from datetime import date as date_cls
            entry_date_str = row[11]
            hold_days_elapsed: int | None = None
            hold_drift_days: int | None = None
            expected_hold_days = row[8]
            if entry_date_str:
                try:
                    entry = date_cls.fromisoformat(entry_date_str)
                    hold_days_elapsed = (date_cls.today() - entry).days
                    if expected_hold_days is not None:
                        hold_drift_days = hold_days_elapsed - int(expected_hold_days)
                except ValueError:
                    pass

            expected_return_pct = float(row[6]) if row[6] is not None else None
            expected_entry_price = float(row[4])
            # Compute return_drift_pct would require current price; leave as None here
            return {
                "thesis_id": row[0],
                "ticker": row[1],
                "expected_signal": row[2],
                "expected_confidence": float(row[3]),
                "expected_entry_price": expected_entry_price,
                "expected_target_price": float(row[5]) if row[5] is not None else None,
                "expected_return_pct": expected_return_pct,
                "expected_stop_loss": float(row[7]) if row[7] is not None else None,
                "expected_hold_days": int(expected_hold_days) if expected_hold_days is not None else None,
                "thesis_text": row[9],
                "created_at": row[10],
                "hold_days_elapsed": hold_days_elapsed,
                "hold_drift_days": hold_drift_days,
                "return_drift_pct": None,  # requires current price
            }

        return await self._with_conn(_op)

    async def get_all_positions(self) -> list[Position]:
        async def _op(conn: aiosqlite.Connection) -> list[Position]:
            await self._ensure_thesis_text_column(conn)
            rows = await (
                await conn.execute(
                    """
                    SELECT
                        ap.ticker,
                        ap.asset_type,
                        ap.quantity,
                        ap.avg_cost,
                        ap.sector,
                        ap.industry,
                        ap.entry_date,
                        ap.original_analysis_id,
                        ap.expected_return_pct,
                        ap.expected_hold_days,
                        pt.thesis_text,
                        pt.expected_target_price,
                        pt.expected_stop_loss,
                        ap.status,
                        ap.exit_price,
                        ap.exit_date,
                        ap.exit_reason,
                        ap.realized_pnl,
                        ap.target_weight
                    FROM active_positions ap
                    LEFT JOIN positions_thesis pt ON ap.original_analysis_id = pt.id
                    WHERE ap.status = 'open'
                    ORDER BY ap.ticker ASC
                    """
                )
            ).fetchall()
            return [Position.from_db_row(row) for row in rows]

        return await self._with_conn(_op)

    async def set_cash(self, amount: float) -> None:
        async def _op(conn: aiosqlite.Connection) -> None:
            await conn.execute(
                """
                INSERT INTO portfolio_meta (key, value)
                VALUES ('cash', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                             updated_at = CURRENT_TIMESTAMP
                """,
                (str(amount),),
            )
            await conn.commit()

        await self._with_conn(_op)

    async def get_cash(self) -> float:
        async def _op(conn: aiosqlite.Connection) -> float:
            row = await (
                await conn.execute(
                    "SELECT value FROM portfolio_meta WHERE key = 'cash'"
                )
            ).fetchone()
            if row is None:
                return 0.0
            try:
                return float(row[0])
            except (TypeError, ValueError):
                return 0.0

        return await self._with_conn(_op)

    async def scale_portfolio(self, multiplier: float) -> int:
        if multiplier <= 0:
            raise ValueError("Multiplier must be greater than 0.")

        async def _op(conn: aiosqlite.Connection) -> int:
            cursor = await conn.execute(
                """
                UPDATE active_positions
                SET quantity = quantity * ?,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (multiplier,),
            )
            await conn.commit()
            return cursor.rowcount

        return await self._with_conn(_op)

    async def apply_split(self, ticker: str, ratio: int) -> bool:
        if ratio <= 0:
            raise ValueError("Split ratio must be a positive integer.")

        async def _op(conn: aiosqlite.Connection) -> bool:
            cursor = await conn.execute(
                """
                UPDATE active_positions
                SET quantity = quantity * ?,
                    avg_cost = avg_cost / ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE ticker = ?
                """,
                (ratio, ratio, ticker),
            )
            if cursor.rowcount == 0:
                await conn.commit()
                return False

            # Also adjust thesis prices (target_price, stop_loss) for the split.
            # Fetch the linked thesis id from the position.
            row = await (
                await conn.execute(
                    "SELECT original_analysis_id FROM active_positions WHERE ticker = ?",
                    (ticker,),
                )
            ).fetchone()
            thesis_id = row[0] if row else None

            if thesis_id is not None:
                await conn.execute(
                    """
                    UPDATE positions_thesis
                    SET expected_target_price = expected_target_price / ?,
                        expected_stop_loss = expected_stop_loss / ?
                    WHERE id = ?
                    """,
                    (ratio, ratio, thesis_id),
                )

            await conn.commit()
            return True

        return await self._with_conn(_op)

    async def load_portfolio(self) -> Portfolio:
        async def _op(conn: aiosqlite.Connection) -> Portfolio:
            await self._ensure_thesis_text_column(conn)
            rows = await (
                await conn.execute(
                    """
                    SELECT
                        ap.ticker,
                        ap.asset_type,
                        ap.quantity,
                        ap.avg_cost,
                        ap.sector,
                        ap.industry,
                        ap.entry_date,
                        ap.original_analysis_id,
                        ap.expected_return_pct,
                        ap.expected_hold_days,
                        pt.thesis_text,
                        pt.expected_target_price,
                        pt.expected_stop_loss,
                        ap.status,
                        ap.exit_price,
                        ap.exit_date,
                        ap.exit_reason,
                        ap.realized_pnl,
                        ap.target_weight
                    FROM active_positions ap
                    LEFT JOIN positions_thesis pt ON ap.original_analysis_id = pt.id
                    WHERE ap.status = 'open'
                    ORDER BY ap.ticker ASC
                    """
                )
            ).fetchall()
            positions = [Position.from_db_row(row) for row in rows]

            cash_row = await (
                await conn.execute(
                    "SELECT value FROM portfolio_meta WHERE key = 'cash'"
                )
            ).fetchone()
            cash = float(cash_row[0]) if cash_row is not None else 0.0

            # Use market_value when current_price is available, fall back to cost_basis.
            effective_values = [
                position.market_value if position.current_price > 0 else position.cost_basis
                for position in positions
            ]
            total_positions_value = sum(effective_values)
            total_value = total_positions_value + cash

            stock_value = sum(
                value
                for position, value in zip(positions, effective_values)
                if position.asset_type == "stock"
            )
            crypto_value = sum(
                value
                for position, value in zip(positions, effective_values)
                if position.asset_type in {"btc", "eth", "crypto"}
            )

            if total_value > 0:
                stock_exposure_pct = stock_value / total_value
                crypto_exposure_pct = crypto_value / total_value
                cash_pct = cash / total_value
            else:
                stock_exposure_pct = 0.0
                crypto_exposure_pct = 0.0
                cash_pct = 0.0

            sector_values: dict[str, float] = {}
            for position, value in zip(positions, effective_values):
                if position.asset_type == "stock":
                    label = position.sector if position.sector else "Other"
                    sector_values[label] = sector_values.get(label, 0.0) + value
                elif position.asset_type in {"btc", "eth", "crypto"}:
                    sector_values["Crypto"] = sector_values.get("Crypto", 0.0) + value

            if total_value > 0:
                sector_breakdown = {
                    sector: value / total_value for sector, value in sector_values.items()
                }
            else:
                sector_breakdown = {}

            top_concentration = self._build_concentration(positions, effective_values, total_value)

            return Portfolio(
                positions=positions,
                cash=cash,
                total_value=total_value,
                stock_exposure_pct=stock_exposure_pct,
                crypto_exposure_pct=crypto_exposure_pct,
                cash_pct=cash_pct,
                sector_breakdown=sector_breakdown,
                top_concentration=top_concentration,
            )

        return await self._with_conn(_op)

    def recompute_with_prices(self, portfolio: Portfolio) -> Portfolio:
        """Recompute portfolio totals using market_value (requires current_price set)."""
        positions = portfolio.positions
        effective_values = [
            p.market_value if p.current_price > 0 else p.cost_basis
            for p in positions
        ]
        total_positions_value = sum(effective_values)
        total_value = total_positions_value + portfolio.cash

        stock_value = sum(
            v for p, v in zip(positions, effective_values) if p.asset_type == "stock"
        )
        crypto_value = sum(
            v for p, v in zip(positions, effective_values) if p.asset_type in {"btc", "eth", "crypto"}
        )

        if total_value > 0:
            stock_exposure_pct = stock_value / total_value
            crypto_exposure_pct = crypto_value / total_value
            cash_pct = portfolio.cash / total_value
        else:
            stock_exposure_pct = crypto_exposure_pct = cash_pct = 0.0

        sector_values: dict[str, float] = {}
        for p, v in zip(positions, effective_values):
            if p.asset_type == "stock":
                label = p.sector if p.sector else "Other"
                sector_values[label] = sector_values.get(label, 0.0) + v
            elif p.asset_type in {"btc", "eth", "crypto"}:
                sector_values["Crypto"] = sector_values.get("Crypto", 0.0) + v

        sector_breakdown = (
            {s: v / total_value for s, v in sector_values.items()} if total_value > 0 else {}
        )

        top_concentration = self._build_concentration(positions, effective_values, total_value)

        return Portfolio(
            positions=positions,
            cash=portfolio.cash,
            total_value=total_value,
            stock_exposure_pct=stock_exposure_pct,
            crypto_exposure_pct=crypto_exposure_pct,
            cash_pct=cash_pct,
            sector_breakdown=sector_breakdown,
            top_concentration=top_concentration,
        )

    def _build_concentration(
        self,
        positions: Iterable[Position],
        values: Iterable[float],
        total_value: float,
    ) -> list[tuple[str, float]]:
        concentration: list[tuple[str, float]] = []
        for position, value in zip(positions, values):
            pct = value / total_value if total_value > 0 else 0.0
            concentration.append((position.ticker, pct))
        return sorted(concentration, key=lambda item: item[1], reverse=True)

    async def cash_reconciliation_check(self) -> str | None:
        portfolio = await self.load_portfolio()
        if portfolio.total_value == 0 or not portfolio.positions:
            return None

        market_values_sum = sum(position.market_value for position in portfolio.positions)
        implied_cash = portfolio.total_value - market_values_sum
        stated_cash = portfolio.cash

        if portfolio.total_value == 0:
            return None

        diff = abs(stated_cash - implied_cash)
        if diff <= 0.02 * portfolio.total_value:
            return None

        pct = diff / portfolio.total_value * 100
        return (
            "Cash reconciliation warning: stated cash "
            f"{stated_cash:.2f} vs implied cash {implied_cash:.2f} "
            f"(diff {diff:.2f}, {pct:.2f}% of total value)."
        )
