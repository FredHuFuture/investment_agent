"""Portfolio performance analytics engine."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite


class PortfolioAnalytics:
    """Compute portfolio performance metrics from historical data."""

    def __init__(self, db_path: str | Path):
        self._db_path = str(Path(db_path))

    async def get_value_history(self, days: int = 90) -> list[dict]:
        """Get portfolio value snapshots for chart.

        Returns list of ``{date, total_value, cash, invested}`` dicts ordered
        by date ascending.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute(
                    """
                    SELECT timestamp, total_value, cash
                    FROM portfolio_snapshots
                    WHERE timestamp >= ?
                    ORDER BY timestamp ASC
                    """,
                    (cutoff,),
                )
            ).fetchall()

        return [
            {
                "date": row["timestamp"],
                "total_value": row["total_value"],
                "cash": row["cash"],
                "invested": row["total_value"] - row["cash"],
            }
            for row in rows
        ]

    async def get_performance_summary(self) -> dict:
        """Calculate overall performance metrics from closed positions.

        Returns dict with: total_realized_pnl, win_count, loss_count,
        win_rate, avg_win_pct, avg_loss_pct, best_trade, worst_trade,
        avg_hold_days, total_trades.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute(
                    """
                    SELECT ticker, avg_cost, exit_price, realized_pnl,
                           entry_date, exit_date
                    FROM active_positions
                    WHERE status = 'closed'
                    """
                )
            ).fetchall()

        total_trades = len(rows)
        if total_trades == 0:
            return {
                "total_realized_pnl": 0.0,
                "win_count": 0,
                "loss_count": 0,
                "win_rate": 0.0,
                "avg_win_pct": 0.0,
                "avg_loss_pct": 0.0,
                "best_trade": None,
                "worst_trade": None,
                "avg_hold_days": 0.0,
                "total_trades": 0,
            }

        total_realized_pnl = 0.0
        win_count = 0
        loss_count = 0
        win_pcts: list[float] = []
        loss_pcts: list[float] = []
        hold_days_list: list[float] = []
        best_trade: dict | None = None
        worst_trade: dict | None = None
        best_return_pct = float("-inf")
        worst_return_pct = float("inf")

        for row in rows:
            pnl = row["realized_pnl"] or 0.0
            avg_cost = row["avg_cost"] or 1.0
            exit_price = row["exit_price"] or avg_cost
            return_pct = ((exit_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0.0

            total_realized_pnl += pnl

            if pnl > 0:
                win_count += 1
                win_pcts.append(return_pct)
            else:
                loss_count += 1
                loss_pcts.append(return_pct)

            trade_info = {
                "ticker": row["ticker"],
                "return_pct": round(return_pct, 2),
                "pnl": round(pnl, 2),
            }
            if return_pct > best_return_pct:
                best_return_pct = return_pct
                best_trade = trade_info
            if return_pct < worst_return_pct:
                worst_return_pct = return_pct
                worst_trade = trade_info

            # Calculate holding days
            try:
                entry_dt = datetime.fromisoformat(row["entry_date"])
                exit_dt = datetime.fromisoformat(row["exit_date"])
                hold_days_list.append((exit_dt - entry_dt).days)
            except (TypeError, ValueError):
                pass

        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0
        avg_win_pct = (sum(win_pcts) / len(win_pcts)) if win_pcts else 0.0
        avg_loss_pct = (sum(loss_pcts) / len(loss_pcts)) if loss_pcts else 0.0
        avg_hold_days = (sum(hold_days_list) / len(hold_days_list)) if hold_days_list else 0.0

        return {
            "total_realized_pnl": round(total_realized_pnl, 2),
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": round(win_rate, 2),
            "avg_win_pct": round(avg_win_pct, 2),
            "avg_loss_pct": round(avg_loss_pct, 2),
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "avg_hold_days": round(avg_hold_days, 1),
            "total_trades": total_trades,
        }

    async def get_monthly_returns(self) -> list[dict]:
        """Monthly P&L breakdown from closed positions.

        Returns list of ``{month, pnl, trade_count}`` dicts.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute(
                    """
                    SELECT strftime('%Y-%m', exit_date) AS month,
                           SUM(realized_pnl) AS pnl,
                           COUNT(*) AS trade_count
                    FROM active_positions
                    WHERE status = 'closed' AND exit_date IS NOT NULL
                    GROUP BY month
                    ORDER BY month ASC
                    """
                )
            ).fetchall()

        return [
            {
                "month": row["month"],
                "pnl": round(row["pnl"], 2),
                "trade_count": row["trade_count"],
            }
            for row in rows
        ]

    async def get_top_performers(self, limit: int = 5) -> dict:
        """Best and worst trades by return percentage.

        Returns ``{best: [...], worst: [...]}``.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row

            # Best trades
            best_rows = await (
                await conn.execute(
                    """
                    SELECT ticker, avg_cost, exit_price, realized_pnl,
                           entry_date, exit_date
                    FROM active_positions
                    WHERE status = 'closed' AND avg_cost > 0
                    ORDER BY ((exit_price - avg_cost) / avg_cost) DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            ).fetchall()

            # Worst trades
            worst_rows = await (
                await conn.execute(
                    """
                    SELECT ticker, avg_cost, exit_price, realized_pnl,
                           entry_date, exit_date
                    FROM active_positions
                    WHERE status = 'closed' AND avg_cost > 0
                    ORDER BY ((exit_price - avg_cost) / avg_cost) ASC
                    LIMIT ?
                    """,
                    (limit,),
                )
            ).fetchall()

        def _row_to_dict(row: aiosqlite.Row) -> dict:
            avg_cost = row["avg_cost"] or 1.0
            exit_price = row["exit_price"] or avg_cost
            return_pct = ((exit_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0.0
            return {
                "ticker": row["ticker"],
                "return_pct": round(return_pct, 2),
                "pnl": round(row["realized_pnl"] or 0.0, 2),
                "entry_date": row["entry_date"],
                "exit_date": row["exit_date"],
            }

        return {
            "best": [_row_to_dict(r) for r in best_rows],
            "worst": [_row_to_dict(r) for r in worst_rows],
        }
