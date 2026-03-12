"""Pure backtest performance metric computation functions."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from backtesting.models import SimulatedTrade


def compute_metrics(
    trades: list[SimulatedTrade],
    equity_curve: list[dict],
    initial_capital: float,
    risk_free_rate: float = 0.04,
) -> dict[str, Any]:
    """Compute all backtest performance metrics.

    Args:
        trades: List of SimulatedTrade objects (only closed trades with pnl).
        equity_curve: List of {"date": ..., "equity": ...} dicts, chronological.
        initial_capital: Starting capital.
        risk_free_rate: Annual risk-free rate (default 4%).

    Returns:
        Dict with all performance metrics.
    """
    # ---- Equity / Return metrics ----
    if not equity_curve:
        return _empty_metrics()

    final_equity = equity_curve[-1]["equity"]
    total_return = (final_equity - initial_capital) / initial_capital if initial_capital > 0 else 0.0

    # Annualized return (geometric) -- use actual calendar dates
    first_date_str = equity_curve[0]["date"]
    last_date_str = equity_curve[-1]["date"]
    try:
        d1 = datetime.strptime(first_date_str, "%Y-%m-%d")
        d2 = datetime.strptime(last_date_str, "%Y-%m-%d")
        years = (d2 - d1).days / 365.25
    except (ValueError, TypeError):
        years = max(len(equity_curve) - 1, 1) / 252.0
    if years <= 0:
        years = 1.0
    annualized_return = (1 + total_return) ** (1.0 / years) - 1

    # Daily returns from equity curve
    equities = [e["equity"] for e in equity_curve]
    daily_returns: list[float] = []
    for i in range(1, len(equities)):
        prev = equities[i - 1]
        if prev > 0:
            daily_returns.append((equities[i] - prev) / prev)

    # Sharpe ratio
    sharpe = _sharpe(daily_returns, risk_free_rate)

    # Sortino ratio
    sortino = _sortino(daily_returns, risk_free_rate)

    # Max drawdown
    max_dd = _max_drawdown(equities)

    # Calmar ratio
    calmar = (annualized_return / abs(max_dd)) if max_dd < 0 else None

    # ---- Trade metrics ----
    closed_trades = [t for t in trades if t.pnl is not None]
    total_trades = len(closed_trades)

    if total_trades == 0:
        win_rate = None
        profit_factor = None
        avg_win = None
        avg_loss = None
        avg_hold = None
        max_consec_wins = 0
        max_consec_losses = 0
    else:
        pnl_pcts = [t.pnl_pct for t in closed_trades if t.pnl_pct is not None]
        wins = [p for p in pnl_pcts if p > 0]
        losses = [p for p in pnl_pcts if p <= 0]

        win_rate = len(wins) / total_trades

        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        avg_win = (sum(wins) / len(wins)) if wins else None
        avg_loss = (sum(losses) / len(losses)) if losses else None

        hold_days = [t.holding_days for t in closed_trades if t.holding_days is not None]
        avg_hold = sum(hold_days) / len(hold_days) if hold_days else None

        max_consec_wins, max_consec_losses = _consecutive_runs(pnl_pcts)

    return {
        "total_return_pct": round(total_return * 100, 2),
        "annualized_return_pct": round(annualized_return * 100, 2),
        "sharpe_ratio": round(sharpe, 3) if sharpe is not None else None,
        "sortino_ratio": round(sortino, 3) if sortino is not None else None,
        "max_drawdown_pct": round(max_dd * 100, 2),
        "calmar_ratio": round(calmar, 3) if calmar is not None else None,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "profit_factor": (
            None if profit_factor is None or profit_factor == float("inf")
            else round(profit_factor, 3)
        ),
        "avg_win_pct": round(avg_win * 100, 2) if avg_win is not None else None,
        "avg_loss_pct": round(avg_loss * 100, 2) if avg_loss is not None else None,
        "total_trades": total_trades,
        "avg_holding_days": round(avg_hold, 1) if avg_hold is not None else None,
        "max_consecutive_wins": max_consec_wins,
        "max_consecutive_losses": max_consec_losses,
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "total_return_pct": 0.0,
        "annualized_return_pct": 0.0,
        "sharpe_ratio": None,
        "sortino_ratio": None,
        "max_drawdown_pct": 0.0,
        "calmar_ratio": None,
        "win_rate": None,
        "profit_factor": None,
        "avg_win_pct": None,
        "avg_loss_pct": None,
        "total_trades": 0,
        "avg_holding_days": None,
        "max_consecutive_wins": 0,
        "max_consecutive_losses": 0,
    }


def _sharpe(daily_returns: list[float], risk_free_rate: float) -> float | None:
    """Annualized Sharpe ratio."""
    if len(daily_returns) < 2:
        return None
    rf_daily = (1 + risk_free_rate) ** (1 / 252) - 1
    excess = [r - rf_daily for r in daily_returns]
    mean_excess = sum(excess) / len(excess)
    variance = sum((r - mean_excess) ** 2 for r in excess) / (len(excess) - 1)
    std = math.sqrt(variance)
    if std == 0:
        return None
    return mean_excess / std * math.sqrt(252)


def _sortino(daily_returns: list[float], risk_free_rate: float) -> float | None:
    """Annualized Sortino ratio (downside deviation denominator)."""
    if len(daily_returns) < 2:
        return None
    rf_daily = (1 + risk_free_rate) ** (1 / 252) - 1
    excess = [r - rf_daily for r in daily_returns]
    mean_excess = sum(excess) / len(excess)
    downside = [min(0.0, e) ** 2 for e in excess]
    downside_var = sum(downside) / len(downside)
    downside_dev = math.sqrt(downside_var)
    if downside_dev == 0:
        return None
    return mean_excess / downside_dev * math.sqrt(252)


def _max_drawdown(equities: list[float]) -> float:
    """Maximum peak-to-trough drawdown as a negative fraction."""
    if not equities:
        return 0.0
    peak = equities[0]
    max_dd = 0.0
    for eq in equities:
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (eq - peak) / peak
            if dd < max_dd:
                max_dd = dd
    return max_dd


def _consecutive_runs(pnl_pcts: list[float]) -> tuple[int, int]:
    """Return (max_consecutive_wins, max_consecutive_losses)."""
    if not pnl_pcts:
        return 0, 0
    max_wins = max_losses = cur_wins = cur_losses = 0
    for p in pnl_pcts:
        if p > 0:
            cur_wins += 1
            cur_losses = 0
        else:
            cur_losses += 1
            cur_wins = 0
        max_wins = max(max_wins, cur_wins)
        max_losses = max(max_losses, cur_losses)
    return max_wins, max_losses
