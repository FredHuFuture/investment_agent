"""Populates backtest_signal_history for Plan 02-03 (Brier/IC/ICIR calibration).

Strategy: Run the Backtester in pure-signal mode over available OHLCV history,
extract per-bar per-agent signal records from agent_signals_log, compute
forward_return_5d and forward_return_21d by advancing +5 / +21 rows in the
OHLCV DataFrame (AP-01 guard: row-offset, not calendar math), and INSERT
each record into backtest_signal_history.

Phase 1 FOUND-04 contract: Backtester.run internally sets backtest_mode=True
on every AgentInput — this module never constructs AgentInput directly.

AP-01 guard (02-RESEARCH.md Q8): forward returns are computed via iloc row
offset on the OHLCV DataFrame, NOT via timedelta(days=5) calendar arithmetic.
This avoids off-by-one errors on non-trading-day boundaries (holidays, weekends)
that would silently bias IC estimates.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import aiosqlite
import pandas as pd

from backtesting.engine import Backtester
from backtesting.models import BacktestConfig

logger = logging.getLogger(__name__)


async def populate_signal_corpus(
    db_path: str,
    ticker: str,
    asset_type: str,
    provider: Any,  # DataProvider — duck-typed to avoid circular import
    start_date: str,
    end_date: str,
    agents: list[str] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run backtester, compute forward returns, insert into backtest_signal_history.

    Args:
        db_path:    Path to SQLite database.
        ticker:     Ticker symbol.
        asset_type: 'stock' | 'btc' | 'eth' | 'crypto'.
        provider:   DataProvider instance; Backtester will call
                    provider.get_price_history(ticker) for OHLCV data.
        start_date: Backtest start date 'YYYY-MM-DD'.
        end_date:   Backtest end date 'YYYY-MM-DD'.
        agents:     Agent list (default: ['TechnicalAgent']).
        run_id:     Opaque run identifier stored as backtest_run_id on every
                    INSERT row. Enables the daemon wrapper's atomic DELETE rollback
                    guard (BLOCKER 3 fix). If None, a fresh UUID hex is generated
                    for ad-hoc / non-daemon use.

    Returns:
        Summary dict: {"rows_inserted": N, "n_bars": N, "n_agents": N, "run_id": str}
    """
    if run_id is None:
        run_id = uuid.uuid4().hex

    cfg = BacktestConfig(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        asset_type=asset_type,
        agents=agents,
    )
    bt = Backtester(provider)
    result = await bt.run(cfg)

    # Fetch full OHLCV to compute forward returns via row-offset (AP-01 guard).
    # Use the provider's price history which covers the full available range.
    price_df = await provider.get_price_history(ticker, period="max", interval="1d")
    if price_df is None or price_df.empty:
        logger.warning(
            "populate_signal_corpus: empty price_df for %s — no rows inserted", ticker
        )
        return {
            "rows_inserted": 0,
            "n_bars": 0,
            "n_agents": 0,
            "run_id": run_id,
        }

    # Normalize date index to ISO date strings for matching with signals_log
    price_df = price_df.copy()
    if isinstance(price_df.index, pd.DatetimeIndex):
        price_df.index = price_df.index.strftime("%Y-%m-%d")
    close = price_df["Close"]

    def _fwd_return(date_str: str, offset: int) -> float | None:
        """Return (close[idx+offset] - close[idx]) / close[idx] using row-index offset.

        AP-01 guard: uses positional iloc offset on the OHLCV DataFrame, NOT
        calendar-date arithmetic, to avoid off-by-one errors on non-trading days.
        """
        if date_str not in close.index:
            return None
        try:
            idx = close.index.get_loc(date_str)
        except KeyError:
            return None
        # get_loc on a non-unique index returns a slice; skip those rows
        if isinstance(idx, slice):
            return None
        if idx + offset >= len(close):
            return None
        p0 = float(close.iloc[idx])
        p1 = float(close.iloc[idx + offset])
        if p0 <= 0:
            return None
        return (p1 - p0) / p0

    rows_to_insert: list[tuple] = []
    for entry in result.agent_signals_log:
        signal_date = entry["date"]
        fr5 = _fwd_return(signal_date, 5)
        fr21 = _fwd_return(signal_date, 21)
        # WR-01 fix: raw_score is the aggregated bar-level score stored at the
        # top-level entry (engine.py line 358), NOT per-agent sub-dict.
        # Per-agent sub-dicts only carry "agent", "signal", and "confidence".
        # Using entry["raw_score"] means backtest_signal_history.raw_score holds
        # the aggregated score for the bar, which is what compute_rolling_ic
        # correlates with forward_return (IC measures agent-timing-correlation
        # with the aggregate score — defensible as the aggregate IS the signal).
        agg_raw_score = entry.get("raw_score", 0.0)
        for agent_sig in entry.get("agent_signals", []):
            rows_to_insert.append(
                (
                    ticker,
                    asset_type,
                    signal_date,
                    agent_sig["agent"],
                    agg_raw_score,
                    agent_sig["signal"],
                    agent_sig.get("confidence"),
                    fr5,
                    fr21,
                    "backtest",
                    run_id,
                )
            )

    if not rows_to_insert:
        logger.info(
            "populate_signal_corpus: no agent signals in backtester output for %s "
            "(%s → %s) — 0 rows inserted",
            ticker,
            start_date,
            end_date,
        )
        return {
            "rows_inserted": 0,
            "n_bars": len(result.agent_signals_log),
            "n_agents": 0,
            "run_id": run_id,
        }

    async with aiosqlite.connect(db_path) as conn:
        await conn.executemany(
            """
            INSERT INTO backtest_signal_history
              (ticker, asset_type, signal_date, agent_name, raw_score,
               signal, confidence, forward_return_5d, forward_return_21d,
               source, backtest_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_insert,
        )
        await conn.commit()

    n_agents = len({r[3] for r in rows_to_insert})
    logger.info(
        "populate_signal_corpus: inserted %d rows (%d agents) for %s",
        len(rows_to_insert),
        n_agents,
        ticker,
    )
    return {
        "rows_inserted": len(rows_to_insert),
        "n_bars": len(result.agent_signals_log),
        "n_agents": n_agents,
        "run_id": run_id,
    }
