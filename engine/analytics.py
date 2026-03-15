"""Portfolio performance analytics engine."""
from __future__ import annotations

import math
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

    async def get_portfolio_risk(self, days: int = 90) -> dict:
        """Compute portfolio-level risk metrics from snapshot history.

        Fetches ``portfolio_snapshots`` for the last *days* calendar days,
        derives daily returns from ``total_value``, and returns a dict with:

        daily_volatility, annualized_volatility, sharpe_ratio, sortino_ratio,
        max_drawdown_pct, current_drawdown_pct, var_95, cvar_95,
        best_day_pct, worst_day_pct, positive_days, negative_days,
        data_points.

        All ratio/percentage fields are rounded to 4 decimal places.
        Returns a zeroed dict when fewer than 2 data points are available.
        """
        _ZERO = {
            "daily_volatility": 0.0,
            "annualized_volatility": 0.0,
            "sharpe_ratio": None,
            "sortino_ratio": None,
            "max_drawdown_pct": 0.0,
            "current_drawdown_pct": 0.0,
            "var_95": 0.0,
            "cvar_95": 0.0,
            "best_day_pct": None,
            "worst_day_pct": None,
            "positive_days": 0,
            "negative_days": 0,
            "data_points": 0,
        }

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute(
                    """
                    SELECT timestamp, total_value
                    FROM portfolio_snapshots
                    WHERE timestamp >= ?
                    ORDER BY timestamp ASC
                    """,
                    (cutoff,),
                )
            ).fetchall()

        values = [row["total_value"] for row in rows if row["total_value"] is not None]

        if len(values) < 2:
            result = dict(_ZERO)
            result["data_points"] = len(values)
            return result

        # --- Daily returns ---
        daily_returns: list[float] = []
        for i in range(1, len(values)):
            prev = values[i - 1]
            if prev and prev > 0:
                daily_returns.append((values[i] - prev) / prev)

        n = len(daily_returns)
        if n < 1:
            result = dict(_ZERO)
            result["data_points"] = len(values)
            return result

        # --- Volatility ---
        mean_ret = sum(daily_returns) / n
        variance = sum((r - mean_ret) ** 2 for r in daily_returns) / max(n - 1, 1)
        daily_vol = math.sqrt(variance)
        annualized_vol = daily_vol * math.sqrt(252)

        # --- Sharpe ratio (rf = 4%) ---
        rf_daily = (1 + 0.04) ** (1 / 252) - 1
        excess = [r - rf_daily for r in daily_returns]
        mean_excess = sum(excess) / n
        ex_variance = sum((e - mean_excess) ** 2 for e in excess) / max(n - 1, 1)
        ex_std = math.sqrt(ex_variance)
        sharpe: float | None = (mean_excess / ex_std * math.sqrt(252)) if ex_std > 0 else None

        # --- Sortino ratio (rf = 4%) ---
        downside_sq = [min(0.0, e) ** 2 for e in excess]
        downside_var = sum(downside_sq) / n
        downside_dev = math.sqrt(downside_var)
        sortino: float | None = (mean_excess / downside_dev * math.sqrt(252)) if downside_dev > 0 else None

        # --- Max drawdown & current drawdown ---
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            if peak > 0:
                dd = (v - peak) / peak
                if dd < max_dd:
                    max_dd = dd

        # Current drawdown: distance from the most recent peak to last value
        running_peak = values[0]
        for v in values:
            if v > running_peak:
                running_peak = v
        last_value = values[-1]
        current_dd = ((last_value - running_peak) / running_peak) if running_peak > 0 else 0.0

        # --- VaR and CVaR at 95% confidence (parametric / Gaussian) ---
        # VaR_95 = -(mean - 1.645 * std)  expressed as a positive percentage
        Z_95 = 1.6449  # one-tailed 95% z-score
        var_95 = -(mean_ret - Z_95 * daily_vol)
        # CVaR_95 (expected shortfall): for normal distribution = mean - std * phi(z) / (1 - 0.95)
        # phi(1.6449) ≈ 0.10313
        PHI_Z95 = 0.10313
        cvar_95 = -(mean_ret - daily_vol * PHI_Z95 / 0.05)

        # --- Best/worst single day ---
        best_day = max(daily_returns)
        worst_day = min(daily_returns)

        # --- Positive / negative days ---
        positive_days = sum(1 for r in daily_returns if r > 0)
        negative_days = sum(1 for r in daily_returns if r <= 0)

        def _pct4(v: float | None) -> float | None:
            """Round to 4 decimal places, return None if None."""
            return round(v, 4) if v is not None else None

        return {
            "daily_volatility": _pct4(daily_vol),
            "annualized_volatility": _pct4(annualized_vol),
            "sharpe_ratio": _pct4(sharpe),
            "sortino_ratio": _pct4(sortino),
            "max_drawdown_pct": _pct4(max_dd * 100),
            "current_drawdown_pct": _pct4(current_dd * 100),
            "var_95": _pct4(var_95 * 100),
            "cvar_95": _pct4(cvar_95 * 100),
            "best_day_pct": _pct4(best_day * 100),
            "worst_day_pct": _pct4(worst_day * 100),
            "positive_days": positive_days,
            "negative_days": negative_days,
            "data_points": len(values),
        }
