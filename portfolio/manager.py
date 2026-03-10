from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import aiosqlite

from portfolio.models import Portfolio, Position


class PortfolioManager:
    def __init__(self, db: str | Path | aiosqlite.Connection) -> None:
        if isinstance(db, aiosqlite.Connection):
            self._connection: aiosqlite.Connection | None = db
            self._db_path: Path | None = None
            return

        self._connection = None
        self._db_path = Path(db)

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
    ) -> int:
        async def _op(conn: aiosqlite.Connection) -> int:
            existing = await (
                await conn.execute(
                    "SELECT 1 FROM active_positions WHERE ticker = ?",
                    (ticker,),
                )
            ).fetchone()
            if existing:
                raise ValueError(f"Position for ticker '{ticker}' already exists.")

            cursor = await conn.execute(
                """
                INSERT INTO active_positions (
                    ticker,
                    asset_type,
                    quantity,
                    avg_cost,
                    sector,
                    industry,
                    entry_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ticker, asset_type, quantity, avg_cost, sector, industry, entry_date),
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
            row = await (
                await conn.execute(
                    """
                    SELECT
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
                    FROM active_positions
                    WHERE ticker = ?
                    """,
                    (ticker,),
                )
            ).fetchone()
            if row is None:
                return None
            return Position.from_db_row(row)

        return await self._with_conn(_op)

    async def get_all_positions(self) -> list[Position]:
        async def _op(conn: aiosqlite.Connection) -> list[Position]:
            rows = await (
                await conn.execute(
                    """
                    SELECT
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
                    FROM active_positions
                    ORDER BY ticker ASC
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
            await conn.commit()
            return cursor.rowcount > 0

        return await self._with_conn(_op)

    async def load_portfolio(self) -> Portfolio:
        async def _op(conn: aiosqlite.Connection) -> Portfolio:
            rows = await (
                await conn.execute(
                    """
                    SELECT
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
                    FROM active_positions
                    ORDER BY ticker ASC
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

            # TODO: replace cost_basis with market_value when DataProvider is available.
            effective_values = [position.cost_basis for position in positions]
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
                if position.asset_type in {"btc", "eth"}
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
                if position.asset_type != "stock" or not position.sector:
                    continue
                sector_values[position.sector] = sector_values.get(position.sector, 0.0) + value

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
