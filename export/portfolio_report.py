"""Portfolio report export in CSV and JSON formats.

Sprint 12.3 – Export System.
Supports exporting portfolio positions, trade journal, signals, and alerts
in CSV and JSON formats using only Python built-in modules (csv, json).
"""
from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import aiosqlite

from engine.analytics import PortfolioAnalytics
from monitoring.store import AlertStore
from portfolio.manager import PortfolioManager

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    """Container for export output."""

    content: bytes
    filename: str
    content_type: str


class PortfolioExporter:
    """Export portfolio data in various formats."""

    def __init__(self, db_path: str = "investment_agent.db"):
        self._db_path = db_path

    # ------------------------------------------------------------------
    # Portfolio CSV (open positions)
    # ------------------------------------------------------------------

    async def export_portfolio_csv(self) -> ExportResult:
        """Export current portfolio positions as CSV."""
        mgr = PortfolioManager(self._db_path)
        portfolio = await mgr.load_portfolio()

        buf = io.StringIO()
        writer = csv.writer(buf)

        headers = [
            "Ticker",
            "Asset Type",
            "Quantity",
            "Avg Cost",
            "Current Price",
            "Market Value",
            "Cost Basis",
            "Unrealized P&L",
            "Unrealized P&L %",
            "Sector",
            "Entry Date",
            "Holding Days",
            "Status",
        ]
        writer.writerow(headers)

        for pos in portfolio.positions:
            writer.writerow([
                pos.ticker,
                pos.asset_type,
                pos.quantity,
                round(pos.avg_cost, 4),
                round(pos.current_price, 4),
                round(pos.market_value, 2),
                round(pos.cost_basis, 2),
                round(pos.unrealized_pnl, 2),
                round(pos.unrealized_pnl_pct * 100, 2),
                pos.sector or "",
                pos.entry_date,
                pos.holding_days,
                pos.status,
            ])

        today = date.today().isoformat()
        content = buf.getvalue().encode("utf-8")
        return ExportResult(
            content=content,
            filename=f"portfolio_{today}.csv",
            content_type="text/csv",
        )

    # ------------------------------------------------------------------
    # Closed positions CSV (trade journal)
    # ------------------------------------------------------------------

    async def export_closed_positions_csv(self) -> ExportResult:
        """Export trade journal (closed positions) as CSV."""
        mgr = PortfolioManager(self._db_path)
        closed = await mgr.get_closed_positions()

        buf = io.StringIO()
        writer = csv.writer(buf)

        headers = [
            "Ticker",
            "Asset Type",
            "Quantity",
            "Avg Cost",
            "Exit Price",
            "Entry Date",
            "Exit Date",
            "Exit Reason",
            "Realized P&L",
            "Return %",
            "Hold Days",
        ]
        writer.writerow(headers)

        for pos in closed:
            avg_cost = pos.avg_cost
            exit_price = pos.exit_price or 0.0
            return_pct = ((exit_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0.0

            # Compute hold days for closed position
            hold_days = 0
            if pos.entry_date and pos.exit_date:
                try:
                    entry = date.fromisoformat(pos.entry_date)
                    exit_d = date.fromisoformat(pos.exit_date)
                    hold_days = max((exit_d - entry).days, 0)
                except ValueError:
                    pass

            writer.writerow([
                pos.ticker,
                pos.asset_type,
                pos.quantity,
                round(avg_cost, 4),
                round(exit_price, 4),
                pos.entry_date,
                pos.exit_date or "",
                pos.exit_reason or "",
                round(pos.realized_pnl, 2) if pos.realized_pnl is not None else 0.0,
                round(return_pct, 2),
                hold_days,
            ])

        today = date.today().isoformat()
        content = buf.getvalue().encode("utf-8")
        return ExportResult(
            content=content,
            filename=f"trade_journal_{today}.csv",
            content_type="text/csv",
        )

    # ------------------------------------------------------------------
    # Comprehensive portfolio report JSON
    # ------------------------------------------------------------------

    async def export_portfolio_report_json(self) -> ExportResult:
        """Export comprehensive portfolio report as JSON."""
        mgr = PortfolioManager(self._db_path)
        portfolio = await mgr.load_portfolio()
        closed = await mgr.get_closed_positions()
        alert_store = AlertStore(self._db_path)
        recent_alerts = await alert_store.get_recent_alerts(limit=20)

        # Fetch recent signals
        recent_signals = await self._fetch_recent_signals(limit=20)

        # Build position dicts
        positions_data = []
        for pos in portfolio.positions:
            positions_data.append({
                "ticker": pos.ticker,
                "asset_type": pos.asset_type,
                "quantity": pos.quantity,
                "avg_cost": pos.avg_cost,
                "current_price": pos.current_price,
                "market_value": round(pos.market_value, 2),
                "cost_basis": round(pos.cost_basis, 2),
                "unrealized_pnl": round(pos.unrealized_pnl, 2),
                "unrealized_pnl_pct": round(pos.unrealized_pnl_pct * 100, 2),
                "sector": pos.sector,
                "entry_date": pos.entry_date,
                "holding_days": pos.holding_days,
                "status": pos.status,
            })

        closed_data = []
        for pos in closed:
            exit_price = pos.exit_price or 0.0
            avg_cost = pos.avg_cost
            return_pct = ((exit_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0.0
            closed_data.append({
                "ticker": pos.ticker,
                "asset_type": pos.asset_type,
                "quantity": pos.quantity,
                "avg_cost": avg_cost,
                "exit_price": exit_price,
                "entry_date": pos.entry_date,
                "exit_date": pos.exit_date,
                "exit_reason": pos.exit_reason,
                "realized_pnl": round(pos.realized_pnl, 2) if pos.realized_pnl is not None else 0.0,
                "return_pct": round(return_pct, 2),
            })

        report = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
                "report_type": "portfolio_report",
            },
            "summary": {
                "total_value": round(portfolio.total_value, 2),
                "cash": round(portfolio.cash, 2),
                "stock_exposure_pct": round(portfolio.stock_exposure_pct * 100, 2),
                "crypto_exposure_pct": round(portfolio.crypto_exposure_pct * 100, 2),
                "cash_pct": round(portfolio.cash_pct * 100, 2),
                "sector_breakdown": {
                    k: round(v * 100, 2) for k, v in portfolio.sector_breakdown.items()
                },
                "num_open_positions": len(portfolio.positions),
                "num_closed_positions": len(closed),
            },
            "positions": positions_data,
            "closed_positions": closed_data,
            "recent_alerts": recent_alerts,
            "recent_signals": recent_signals,
        }

        today = date.today().isoformat()
        content = json.dumps(report, indent=2, default=str).encode("utf-8")
        return ExportResult(
            content=content,
            filename=f"portfolio_report_{today}.json",
            content_type="application/json",
        )

    # ------------------------------------------------------------------
    # Signals CSV
    # ------------------------------------------------------------------

    async def export_signals_csv(
        self, ticker: str | None = None, limit: int = 100
    ) -> ExportResult:
        """Export signal history as CSV."""
        rows = await self._fetch_recent_signals(ticker=ticker, limit=limit)

        buf = io.StringIO()
        writer = csv.writer(buf)

        headers = [
            "Date",
            "Ticker",
            "Signal",
            "Confidence",
            "Raw Score",
            "Consensus",
            "Regime",
        ]
        writer.writerow(headers)

        for row in rows:
            writer.writerow([
                row.get("created_at", ""),
                row.get("ticker", ""),
                row.get("final_signal", ""),
                row.get("final_confidence", ""),
                row.get("raw_score", ""),
                row.get("consensus_score", ""),
                row.get("regime", ""),
            ])

        today = date.today().isoformat()
        suffix = f"_{ticker}" if ticker else ""
        content = buf.getvalue().encode("utf-8")
        return ExportResult(
            content=content,
            filename=f"signals{suffix}_{today}.csv",
            content_type="text/csv",
        )

    # ------------------------------------------------------------------
    # Alerts CSV
    # ------------------------------------------------------------------

    async def export_alerts_csv(self, limit: int = 100) -> ExportResult:
        """Export alert history as CSV."""
        alert_store = AlertStore(self._db_path)
        alerts = await alert_store.get_recent_alerts(limit=limit)

        buf = io.StringIO()
        writer = csv.writer(buf)

        headers = [
            "Date",
            "Ticker",
            "Type",
            "Severity",
            "Message",
            "Acknowledged",
        ]
        writer.writerow(headers)

        for alert in alerts:
            writer.writerow([
                alert.get("created_at", ""),
                alert.get("ticker", ""),
                alert.get("alert_type", ""),
                alert.get("severity", ""),
                alert.get("message", ""),
                alert.get("acknowledged", False),
            ])

        today = date.today().isoformat()
        content = buf.getvalue().encode("utf-8")
        return ExportResult(
            content=content,
            filename=f"alerts_{today}.csv",
            content_type="text/csv",
        )

    # ------------------------------------------------------------------
    # Performance CSV (summary + monthly returns)
    # ------------------------------------------------------------------

    async def export_performance_csv(self) -> ExportResult:
        """Export performance summary and monthly returns as CSV."""
        analytics = PortfolioAnalytics(self._db_path)
        summary = await analytics.get_performance_summary()
        monthly = await analytics.get_monthly_returns()

        buf = io.StringIO()
        writer = csv.writer(buf)

        # --- Summary section ---
        writer.writerow(["Performance Summary"])
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Realized P&L", summary.get("total_realized_pnl", 0.0)])
        writer.writerow(["Total Trades", summary.get("total_trades", 0)])
        writer.writerow(["Win Count", summary.get("win_count", 0)])
        writer.writerow(["Loss Count", summary.get("loss_count", 0)])
        writer.writerow(["Win Rate %", summary.get("win_rate", 0.0)])
        writer.writerow(["Avg Win %", summary.get("avg_win_pct", 0.0)])
        writer.writerow(["Avg Loss %", summary.get("avg_loss_pct", 0.0)])
        writer.writerow(["Avg Hold Days", summary.get("avg_hold_days", 0.0)])
        writer.writerow(["Profit Factor", summary.get("profit_factor", "")])
        writer.writerow(["Expectancy", summary.get("expectancy", "")])
        writer.writerow(["Max Consecutive Wins", summary.get("max_consecutive_wins", 0)])
        writer.writerow(["Max Consecutive Losses", summary.get("max_consecutive_losses", 0)])

        best = summary.get("best_trade")
        if best:
            writer.writerow(["Best Trade", f"{best['ticker']} ({best['return_pct']}%)"])
        worst = summary.get("worst_trade")
        if worst:
            writer.writerow(["Worst Trade", f"{worst['ticker']} ({worst['return_pct']}%)"])

        # Blank separator row
        writer.writerow([])

        # --- Monthly returns section ---
        writer.writerow(["Monthly Returns"])
        writer.writerow(["Month", "P&L", "Trade Count", "Return %"])
        for month in monthly:
            writer.writerow([
                month.get("month", ""),
                month.get("pnl", 0.0),
                month.get("trade_count", 0),
                month.get("return_pct", 0.0),
            ])

        today = date.today().isoformat()
        content = buf.getvalue().encode("utf-8")
        return ExportResult(
            content=content,
            filename=f"performance_{today}.csv",
            content_type="text/csv",
        )

    # ------------------------------------------------------------------
    # Risk CSV (risk metrics snapshot)
    # ------------------------------------------------------------------

    async def export_risk_csv(self, days: int = 90) -> ExportResult:
        """Export portfolio risk metrics snapshot as CSV."""
        analytics = PortfolioAnalytics(self._db_path)
        risk = await analytics.get_portfolio_risk(days=days)

        buf = io.StringIO()
        writer = csv.writer(buf)

        writer.writerow(["Risk Metrics Snapshot"])
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Daily Volatility", risk.get("daily_volatility", 0.0)])
        writer.writerow(["Annualized Volatility", risk.get("annualized_volatility", 0.0)])
        writer.writerow(["Sharpe Ratio", risk.get("sharpe_ratio", "")])
        writer.writerow(["Sortino Ratio", risk.get("sortino_ratio", "")])
        writer.writerow(["Max Drawdown %", risk.get("max_drawdown_pct", 0.0)])
        writer.writerow(["Current Drawdown %", risk.get("current_drawdown_pct", 0.0)])
        writer.writerow(["VaR 95%", risk.get("var_95", 0.0)])
        writer.writerow(["CVaR 95%", risk.get("cvar_95", 0.0)])
        writer.writerow(["Best Day %", risk.get("best_day_pct", "")])
        writer.writerow(["Worst Day %", risk.get("worst_day_pct", "")])
        writer.writerow(["Positive Days", risk.get("positive_days", 0)])
        writer.writerow(["Negative Days", risk.get("negative_days", 0)])
        writer.writerow(["Data Points", risk.get("data_points", 0)])

        today = date.today().isoformat()
        content = buf.getvalue().encode("utf-8")
        return ExportResult(
            content=content,
            filename=f"risk_{today}.csv",
            content_type="text/csv",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_recent_signals(
        self, ticker: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Query signal_history table directly via aiosqlite."""
        async with aiosqlite.connect(self._db_path) as conn:
            conditions: list[str] = []
            params: list[Any] = []
            if ticker is not None:
                conditions.append("ticker = ?")
                params.append(ticker)
            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            params.append(limit)
            rows = await (
                await conn.execute(
                    f"""
                    SELECT ticker, final_signal, final_confidence,
                           raw_score, consensus_score, regime, created_at
                    FROM signal_history
                    {where}
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    params,
                )
            ).fetchall()
            return [
                {
                    "ticker": row[0],
                    "final_signal": row[1],
                    "final_confidence": row[2],
                    "raw_score": row[3],
                    "consensus_score": row[4],
                    "regime": row[5],
                    "created_at": row[6],
                }
                for row in rows
            ]
