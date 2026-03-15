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
                "profit_factor": None,
                "expectancy": None,
                "max_consecutive_wins": 0,
                "max_consecutive_losses": 0,
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

        # --- Advanced metrics (Sprint 26) ---
        # Profit factor = gross wins / abs(gross losses)
        gross_wins = sum(
            (row["realized_pnl"] or 0.0) for row in rows if (row["realized_pnl"] or 0.0) > 0
        )
        gross_losses = abs(
            sum((row["realized_pnl"] or 0.0) for row in rows if (row["realized_pnl"] or 0.0) < 0)
        )
        profit_factor: float | None = (
            round(gross_wins / gross_losses, 2) if gross_losses > 0 else None
        )

        # Expectancy = avg_win * win_rate_frac - avg_loss * loss_rate_frac
        win_rate_frac = win_count / total_trades if total_trades > 0 else 0.0
        loss_rate_frac = loss_count / total_trades if total_trades > 0 else 0.0
        expectancy: float | None = round(
            avg_win_pct * win_rate_frac - abs(avg_loss_pct) * loss_rate_frac, 2
        ) if total_trades > 0 else None

        # Max consecutive wins / losses
        max_consec_wins = 0
        max_consec_losses = 0
        cur_wins = 0
        cur_losses = 0
        for row in rows:
            pnl_val = row["realized_pnl"] or 0.0
            if pnl_val > 0:
                cur_wins += 1
                cur_losses = 0
                max_consec_wins = max(max_consec_wins, cur_wins)
            else:
                cur_losses += 1
                cur_wins = 0
                max_consec_losses = max(max_consec_losses, cur_losses)

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
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "max_consecutive_wins": max_consec_wins,
            "max_consecutive_losses": max_consec_losses,
        }

    async def get_monthly_returns(self) -> list[dict]:
        """Monthly P&L breakdown from closed positions.

        Returns list of ``{month, pnl, trade_count, return_pct}`` dicts.
        ``return_pct`` is the monthly P&L as a percentage of the portfolio
        value at the start of that month (from ``portfolio_snapshots``).
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

            # Get portfolio value at the start of each month for return_pct
            snapshot_rows = await (
                await conn.execute(
                    """
                    SELECT month, total_value FROM (
                        SELECT strftime('%Y-%m', timestamp) AS month,
                               total_value,
                               ROW_NUMBER() OVER (
                                   PARTITION BY strftime('%Y-%m', timestamp)
                                   ORDER BY timestamp ASC
                               ) AS rn
                        FROM portfolio_snapshots
                    ) WHERE rn = 1
                    """
                )
            ).fetchall()

        month_start_values: dict[str, float] = {}
        for sr in snapshot_rows:
            month_start_values[sr["month"]] = sr["total_value"]

        result = []
        for row in rows:
            return_pct = 0.0
            start_val = month_start_values.get(row["month"])
            if start_val and start_val > 0:
                return_pct = round((row["pnl"] / start_val) * 100, 2)
            result.append(
                {
                    "month": row["month"],
                    "pnl": round(row["pnl"], 2),
                    "trade_count": row["trade_count"],
                    "return_pct": return_pct,
                }
            )
        return result

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

    async def get_benchmark_comparison(
        self,
        provider,  # DataProvider
        benchmark_ticker: str = "SPY",
        days: int = 90,
    ) -> dict:
        """Compare portfolio performance against a benchmark (e.g., SPY).

        Returns indexed series (base=100) for both portfolio and benchmark,
        plus return/alpha metrics.
        """
        _EMPTY = {
            "series": [],
            "benchmark_ticker": benchmark_ticker,
            "portfolio_return_pct": 0.0,
            "benchmark_return_pct": 0.0,
            "alpha_pct": 0.0,
            "data_points": 0,
        }

        # 1. Get portfolio snapshots
        portfolio_data = await self.get_value_history(days=days)
        if len(portfolio_data) < 2:
            return _EMPTY

        # 2. Fetch benchmark price history — choose a period slightly wider than
        #    `days` so we always have enough trading-day coverage.
        if days <= 30:
            period = "2mo"
        elif days <= 90:
            period = "4mo"
        elif days <= 180:
            period = "7mo"
        else:
            period = "2y"

        try:
            bench_df = await provider.get_price_history(
                benchmark_ticker, period=period, interval="1d"
            )
        except Exception:
            return _EMPTY

        if bench_df is None or bench_df.empty or "Close" not in bench_df.columns:
            return _EMPTY

        # 3. Build date-indexed lookup dicts (YYYY-MM-DD keys)
        port_by_date: dict[str, float] = {}
        for pt in portfolio_data:
            date_str = pt["date"][:10]
            port_by_date[date_str] = pt["total_value"]

        bench_close = bench_df["Close"].dropna()
        bench_by_date: dict[str, float] = {}
        for idx, val in bench_close.items():
            date_str = str(idx)[:10]
            bench_by_date[date_str] = float(val)

        # 4. Find overlapping dates; fall back to all portfolio dates if needed
        common_dates = sorted(set(port_by_date.keys()) & set(bench_by_date.keys()))
        if len(common_dates) < 2:
            common_dates = sorted(port_by_date.keys())

        if len(common_dates) < 2:
            return _EMPTY

        # 5. Normalize to base 100 from the first common date
        first_date = common_dates[0]
        port_base = port_by_date.get(first_date) or 1.0
        bench_base = bench_by_date.get(first_date) or 1.0

        series: list[dict] = []
        last_bench = bench_base
        for date_str in common_dates:
            port_val = port_by_date.get(date_str)
            bench_val = bench_by_date.get(date_str, last_bench)
            if bench_val:
                last_bench = bench_val

            if port_val is not None:
                series.append(
                    {
                        "date": date_str,
                        "portfolio_indexed": round(port_val / port_base * 100, 2),
                        "benchmark_indexed": round(bench_val / bench_base * 100, 2),
                    }
                )

        # 6. Compute total returns and alpha
        if len(series) >= 2:
            portfolio_return = (series[-1]["portfolio_indexed"] / 100 - 1) * 100
            benchmark_return = (series[-1]["benchmark_indexed"] / 100 - 1) * 100
        else:
            portfolio_return = 0.0
            benchmark_return = 0.0

        alpha = portfolio_return - benchmark_return

        return {
            "series": series,
            "benchmark_ticker": benchmark_ticker,
            "portfolio_return_pct": round(portfolio_return, 2),
            "benchmark_return_pct": round(benchmark_return, 2),
            "alpha_pct": round(alpha, 2),
            "data_points": len(series),
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

    async def get_cumulative_pnl(self) -> list[dict]:
        """Cumulative realized P&L curve, one point per trade exit date.

        Returns list of ``{date, cumulative_pnl, trade_count}`` dicts ordered
        by exit_date ascending.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute(
                    """
                    SELECT exit_date, realized_pnl
                    FROM active_positions
                    WHERE status = 'closed' AND exit_date IS NOT NULL
                    ORDER BY exit_date ASC
                    """
                )
            ).fetchall()

        result: list[dict] = []
        cumulative = 0.0
        count = 0
        for row in rows:
            cumulative += row["realized_pnl"] or 0.0
            count += 1
            result.append({
                "date": row["exit_date"],
                "cumulative_pnl": round(cumulative, 2),
                "trade_count": count,
            })
        return result

    async def get_position_pnl_history(self, ticker: str) -> list[dict]:
        """Daily P&L history for a specific position using price snapshots.

        Returns list of ``{date, price, cost_basis, unrealized_pnl,
        unrealized_pnl_pct}`` dicts ordered by date ascending.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            # Get position cost basis
            pos_row = await (
                await conn.execute(
                    """
                    SELECT avg_cost, quantity, entry_date
                    FROM active_positions
                    WHERE ticker = ?
                    LIMIT 1
                    """,
                    (ticker.upper(),),
                )
            ).fetchone()

            if not pos_row:
                return []

            avg_cost = pos_row["avg_cost"] or 0.0
            quantity = pos_row["quantity"] or 0
            entry_date = pos_row["entry_date"] or ""

            # Get price history from portfolio snapshots
            # We'll use the signal history timestamps as price reference points
            price_rows = await (
                await conn.execute(
                    """
                    SELECT DISTINCT
                        s.created_at AS date,
                        s.raw_score
                    FROM signal_history s
                    WHERE s.ticker = ?
                    ORDER BY s.created_at ASC
                    """,
                    (ticker.upper(),),
                )
            ).fetchall()

        if not price_rows and avg_cost > 0:
            # Fallback: return a single point with entry data
            return [{
                "date": entry_date,
                "price": avg_cost,
                "cost_basis": round(avg_cost * quantity, 2),
                "unrealized_pnl": 0.0,
                "unrealized_pnl_pct": 0.0,
            }]

        # Build P&L history using signal dates (we don't have daily prices in DB)
        # This is a simplified version - will be enhanced when we add price snapshots
        result: list[dict] = []
        for row in price_rows:
            result.append({
                "date": row["date"][:10] if row["date"] else "",
                "price": avg_cost,  # placeholder - price data not in DB
                "cost_basis": round(avg_cost * quantity, 2),
                "unrealized_pnl": 0.0,
                "unrealized_pnl_pct": 0.0,
            })
        return result
