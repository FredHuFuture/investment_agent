"""Walk-forward backtesting scaffold (SIG-05).

Generates rolling (train_start, train_end, oos_start, oos_end) windows with a
purge gap and runs the Backtester on each OOS window. Returns per-window
Sharpe, total_return, and n_trades for consumption by BacktestResult
and the analytics calibration layer (Plan 02-03).

Window sizing (02-RESEARCH.md Q4): 30-day train, 10-day OOS, 1-day purge.
Preliminary calibration: signal_history has 10 rows (single day) as of 2026-04-21;
these window sizes are defensive and should scale to qlib standard 252/63 once
live history accumulates.

Phase 1 FOUND-04 contract: Backtester.run internally sets backtest_mode=True on
every AgentInput — walk_forward.py never constructs AgentInput directly.

Phase 1 FOUND-02 contract: when run via populate_signal_corpus, the provider
passed in reads from CachedProvider / price_history_cache — no new caching logic
is needed here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any


@dataclass
class WalkForwardWindow:
    """Single train/OOS window with a purge gap between them."""

    train_start: date
    train_end: date
    oos_start: date
    oos_end: date
    window_idx: int


@dataclass
class WalkForwardResult:
    """Results from a full walk-forward run across all windows."""

    windows: list[WalkForwardWindow]
    per_window_metrics: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    preliminary_calibration: bool = True  # per 02-RESEARCH.md Q4: mark as preliminary
    config_train_days: int = 30
    config_oos_days: int = 10
    config_purge_days: int = 1


def generate_walk_forward_windows(
    start: date,
    end: date,
    train_days: int = 30,
    oos_days: int = 10,
    step_days: int = 10,
    purge_days: int = 1,
) -> list[WalkForwardWindow]:
    """Generate rolling train/OOS windows with purge gap.

    Invariants enforced for every returned window:
        - oos_start > train_end  (AP-01 guard — no label leakage at the boundary)
        - (oos_start - train_end).days >= purge_days + 1
        - windows step forward by step_days
        - windows never extend past `end`

    Args:
        start:      First date for the first training window.
        end:        Hard deadline — no window's oos_end may exceed this date.
        train_days: Calendar days in the training window (default 30).
        oos_days:   Calendar days in the OOS window (default 10).
        step_days:  How far each successive window advances (default 10).
        purge_days: Minimum calendar days between train_end and oos_start
                    (default 1 for Sharpe-only use; set to 5 for IC-feeding
                    per 02-RESEARCH.md Q4 label-leakage prevention).

    Returns:
        List of WalkForwardWindow objects in chronological order.
    """
    windows: list[WalkForwardWindow] = []
    idx = 0
    train_start = start
    while True:
        train_end = train_start + timedelta(days=train_days - 1)
        # Gap: purge_days + 1 ensures oos_start is strictly after train_end
        # even when purge_days=0 is requested.
        oos_start = train_end + timedelta(days=purge_days + 1)
        oos_end = oos_start + timedelta(days=oos_days - 1)
        if oos_end > end:
            break
        windows.append(
            WalkForwardWindow(
                train_start=train_start,
                train_end=train_end,
                oos_start=oos_start,
                oos_end=oos_end,
                window_idx=idx,
            )
        )
        train_start += timedelta(days=step_days)
        idx += 1
    return windows


async def run_walk_forward(
    ticker: str,
    asset_type: str,
    start: date,
    end: date,
    provider: Any,  # DataProvider — duck-typed to avoid circular import
    train_days: int = 30,
    oos_days: int = 10,
    step_days: int = 10,
    purge_days: int = 5,  # BLOCKER 4 fix: IC-feeding path requires 5-day purge gap
    agents: list[str] | None = None,
    cost_per_trade: float | None = None,
) -> WalkForwardResult:
    """Run the Backtester on each OOS window and collect per-window metrics.

    Honors Phase 1 FOUND-04 contract: Backtester.run internally sets
    backtest_mode=True on every AgentInput — no special handling needed here.

    purge_days default = 5 for IC-feeding corpus per 02-RESEARCH.md Q4
    "Overlap and Label Leakage Prevention": the 5-day forward return horizon
    used downstream in IC computation (Plan 02-03 SIG-03) requires the training
    window's last-day signal NOT to see any OOS price data, hence a 5-day gap.
    `generate_walk_forward_windows` keeps purge_days=1 as its default (the
    Sharpe-only minimum-viable gap); this IC-feeding wrapper bumps to 5.

    Args:
        ticker:         Ticker symbol.
        asset_type:     'stock' | 'btc' | 'eth' | 'crypto'.
        start:          Walk-forward start date.
        end:            Walk-forward end date.
        provider:       DataProvider instance; Backtester will call
                        provider.get_price_history(ticker) for OHLCV data.
        train_days:     Calendar days per training window.
        oos_days:       Calendar days per OOS window.
        step_days:      Window step size.
        purge_days:     Purge gap between train_end and oos_start (default 5).
        agents:         Agent list to run (default: ['TechnicalAgent']).
        cost_per_trade: Per-side transaction cost; None → asset-type default.

    Returns:
        WalkForwardResult with per_window_metrics populated for each window.
    """
    from backtesting.engine import Backtester
    from backtesting.models import BacktestConfig

    windows = generate_walk_forward_windows(
        start, end, train_days, oos_days, step_days, purge_days
    )
    result = WalkForwardResult(
        windows=windows,
        config_train_days=train_days,
        config_oos_days=oos_days,
        config_purge_days=purge_days,
    )

    for w in windows:
        cfg = BacktestConfig(
            ticker=ticker,
            start_date=w.oos_start.isoformat(),
            end_date=w.oos_end.isoformat(),
            asset_type=asset_type,
            agents=agents,
            cost_per_trade=cost_per_trade,
        )
        try:
            bt_result = await Backtester(provider).run(cfg)
            result.per_window_metrics.append(
                {
                    "window_idx": w.window_idx,
                    "oos_start": w.oos_start.isoformat(),
                    "oos_end": w.oos_end.isoformat(),
                    "sharpe": bt_result.metrics.get("sharpe_ratio"),
                    "total_return": bt_result.metrics.get("total_return_pct"),
                    "n_trades": bt_result.metrics.get("n_trades", 0),
                    "total_costs_paid": bt_result.metrics.get("total_costs_paid", 0.0),
                }
            )
        except Exception as exc:  # skip bad windows, keep walk-forward going
            result.warnings.append(
                f"window {w.window_idx} ({w.oos_start}→{w.oos_end}) failed: {exc}"
            )

    return result
