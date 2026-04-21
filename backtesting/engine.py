"""Backtester: walk-forward simulation engine."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import aiosqlite
import pandas as pd

from agents.models import AgentInput, AgentOutput, Signal
from agents.technical import TechnicalAgent
from backtesting.data_slicer import HistoricalDataProvider
from backtesting.metrics import compute_metrics
from backtesting.models import BacktestConfig, BacktestResult, SimulatedTrade, default_cost_per_trade
from db.database import DEFAULT_DB_PATH
from engine.aggregator import AggregatedSignal, SignalAggregator

# Lock imported from yfinance_provider for thread-safe downloads
from data_providers.yfinance_provider import YFinanceProvider, _yfinance_lock

_NON_PIT_AGENTS = {"FundamentalAgent"}

_REBALANCE_FREQS = {
    "daily": "B",          # every business day
    "weekly": "W-MON",     # every Monday
    "monthly": "BMS",      # first business day of month
}


async def cache_price_data(
    ticker: str,
    start_date: str,
    end_date: str,
    asset_type: str = "stock",
    db_path: str = str(DEFAULT_DB_PATH),
) -> pd.DataFrame:
    """Fetch full OHLCV and cache to price_history_cache. Returns DataFrame."""
    # Calculate start with sufficient lookback for SMA200 (300 calendar days)
    fetch_start = (
        datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=300)
    ).strftime("%Y-%m-%d")

    # Check cache
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cached = await (
            await conn.execute(
                """
                SELECT date, open, high, low, close, volume
                FROM price_history_cache
                WHERE ticker = ? AND date >= ? AND date <= ?
                ORDER BY date ASC
                """,
                (ticker, fetch_start, end_date),
            )
        ).fetchall()

        if cached:
            df = pd.DataFrame(
                [
                    {
                        "Open": row["open"],
                        "High": row["high"],
                        "Low": row["low"],
                        "Close": row["close"],
                        "Volume": row["volume"],
                    }
                    for row in cached
                ],
                index=pd.to_datetime([row["date"] for row in cached]),
            )
            return df

    # Cache miss: fetch from yfinance.
    # WR-03 fix: route through YFinanceProvider._limiter (shared class-level
    # AsyncRateLimiter) so backtest downloads respect the 2-calls/s budget.
    # The date-range overload of yf.download requires start/end params that
    # get_price_history() doesn't expose, so we call yf.download directly but
    # inside the provider's rate-limiter context and _yfinance_lock.
    provider = YFinanceProvider()

    def _download() -> pd.DataFrame:
        import yfinance as yf
        with _yfinance_lock:
            return yf.download(
                ticker,
                start=fetch_start,
                end=end_date,
                interval="1d",
                progress=False,
                auto_adjust=False,
            )

    async with provider._limiter:
        raw = await asyncio.to_thread(_download)
    if raw is None or raw.empty:
        raise ValueError(f"No price data for {ticker} ({fetch_start} to {end_date})")

    # Normalize MultiIndex columns
    if isinstance(raw.columns, pd.MultiIndex):
        if ticker in raw.columns.get_level_values(1):
            raw = raw.droplevel(1, axis=1)
        elif ticker in raw.columns.get_level_values(0):
            raw = raw[ticker]
        else:
            raw = raw.droplevel(0, axis=1)

    raw = raw.rename(columns={col: str(col).title() for col in raw.columns})
    if "Adj Close" in raw.columns:
        raw = raw.drop(columns=["Adj Close"])

    expected = ["Open", "High", "Low", "Close", "Volume"]
    raw = raw[[c for c in expected if c in raw.columns]]

    # Store to cache
    async with aiosqlite.connect(db_path) as conn:
        await conn.executemany(
            """
            INSERT OR IGNORE INTO price_history_cache
                (ticker, date, open, high, low, close, volume, asset_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    ticker,
                    str(idx.date()),
                    float(row["Open"]),
                    float(row["High"]),
                    float(row["Low"]),
                    float(row["Close"]),
                    float(row["Volume"]),
                    asset_type,
                )
                for idx, row in raw.iterrows()
            ],
        )
        await conn.commit()

    return raw


class Backtester:
    """Walk-forward backtesting engine.

    Supports TechnicalAgent only by default (PIT-safe).
    Other agents can be opted-in with disclaimer warnings.

    Two calling conventions are supported:
      Classic:  Backtester(config).run()
      Provider: Backtester(provider).run(config)  — used by walk_forward + signal_corpus
    """

    def __init__(self, config_or_provider: "BacktestConfig | Any") -> None:
        # Detect whether caller passed a BacktestConfig or a DataProvider.
        if isinstance(config_or_provider, BacktestConfig):
            self._config: BacktestConfig | None = config_or_provider
            self._provider: Any = None
        else:
            # Assume it's a DataProvider (duck-typed)
            self._config = None
            self._provider = config_or_provider

    async def run(
        self,
        config: BacktestConfig | None = None,
        full_data: pd.DataFrame | None = None,
        db_path: str = str(DEFAULT_DB_PATH),
    ) -> BacktestResult:
        """Execute the backtest.

        Args:
            config: BacktestConfig. Required when Backtester was constructed with a
                    provider; ignored (uses self._config) when constructed with config.
            full_data: Pre-loaded OHLCV DataFrame (for testing/offline use).
                       If None, fetches from yfinance and caches.
            db_path: SQLite DB path for price cache.
        """
        # Resolve config
        if config is not None:
            cfg = config
        elif self._config is not None:
            cfg = self._config
        else:
            raise ValueError(
                "BacktestConfig must be provided either to Backtester.__init__ "
                "or to Backtester.run(config=...)"
            )
        warnings: list[str] = []

        # Resolve agent list
        agent_names = cfg.agents if cfg.agents is not None else ["TechnicalAgent"]

        # Non-PIT warning
        non_pit = [a for a in agent_names if a in _NON_PIT_AGENTS]
        if non_pit:
            warnings.append(
                f"WARNING: Non-PIT agents used ({', '.join(non_pit)}). "
                "Backtest results may be overly optimistic due to look-ahead bias in "
                "restated financial data."
            )

        # 1. Fetch / use provided data
        if full_data is None:
            if self._provider is not None:
                # Provider-mode: fetch from injected DataProvider (used by walk_forward + signal_corpus)
                full_data = await self._provider.get_price_history(cfg.ticker)
            else:
                full_data = await cache_price_data(
                    cfg.ticker, cfg.start_date, cfg.end_date, cfg.asset_type, db_path
                )

        # 2. Generate rebalance dates within [start_date, end_date]
        freq = _REBALANCE_FREQS.get(cfg.rebalance_frequency, "W-MON")
        rebalance_dates = pd.bdate_range(
            start=cfg.start_date, end=cfg.end_date, freq=freq
        )
        # Filter to dates that exist in our data
        available_dates = set(full_data.index.normalize())
        rebalance_dates = [
            d for d in rebalance_dates if d.normalize() in available_dates
        ]

        if not rebalance_dates:
            warnings.append("No rebalance dates in price data range.")
            return BacktestResult(
                config=cfg,
                metrics=compute_metrics([], [], cfg.initial_capital),
                warnings=warnings,
            )

        # Resolve effective transaction cost (SIG-04)
        effective_cost = (
            cfg.cost_per_trade
            if cfg.cost_per_trade is not None
            else default_cost_per_trade(cfg.asset_type)
        )
        total_costs_paid = 0.0
        n_trades = 0

        # 3. Walk-forward loop
        cash = cfg.initial_capital
        position: dict[str, Any] | None = None  # current open position
        trades: list[SimulatedTrade] = []
        equity_curve: list[dict] = []
        signals_log: list[dict] = []

        # Build backtest-aware aggregator weights: re-normalize to only the
        # agents actually being used.  With unnormalized raw_score, a single
        # TechnicalAgent at stock weight 0.30 would max out at raw_score=0.30,
        # making the default buy_threshold(0.30) nearly unreachable.
        _bt_weights = dict(SignalAggregator.DEFAULT_WEIGHTS)
        at_key = cfg.asset_type or "stock"
        current = dict(_bt_weights.get(at_key, _bt_weights["stock"]))

        # Keep only weights for agents being used, re-normalize to sum=1.0
        used_weights = {a: current.get(a, 0.0) for a in agent_names}
        total_w = sum(used_weights.values())
        if total_w > 0 and any(used_weights[a] > 0 for a in agent_names):
            current = {a: w / total_w for a, w in used_weights.items()}
        else:
            # Fallback: equal-weight all requested agents
            equal_w = round(1.0 / len(agent_names), 4)
            current = {a: equal_w for a in agent_names}
        _bt_weights[at_key] = current
        aggregator = SignalAggregator(
            weights=_bt_weights,
            buy_threshold=cfg.buy_threshold,
            sell_threshold=cfg.sell_threshold,
        )

        # Build set of rebalance dates for O(1) lookup
        rebalance_set = {d.normalize() for d in rebalance_dates}

        # Iterate ALL trading days for daily mark-to-market equity curve,
        # but only run agents / execute trades on rebalance dates.
        all_trading_days = sorted(
            d for d in full_data.index
            if pd.Timestamp(cfg.start_date) <= d <= pd.Timestamp(cfg.end_date)
        )

        for date in all_trading_days:
            date_str = str(date.date())

            # Get current close price
            mask = full_data.index.normalize() == date.normalize()
            if not mask.any():
                continue
            current_price = float(full_data.loc[mask, "Close"].iloc[-1])

            is_rebalance = date.normalize() in rebalance_set

            if is_rebalance:
                # Check stop-loss / take-profit on open position
                if position is not None:
                    entry_price = position["entry_price"]
                    pnl_pct = (current_price - entry_price) / entry_price

                    exit_reason = None
                    if cfg.stop_loss_pct is not None and pnl_pct <= -cfg.stop_loss_pct:
                        exit_reason = "stop_loss"
                        exit_price = entry_price * (1 - cfg.stop_loss_pct)
                    elif cfg.take_profit_pct is not None and pnl_pct >= cfg.take_profit_pct:
                        exit_reason = "take_profit"
                        exit_price = entry_price * (1 + cfg.take_profit_pct)

                    if exit_reason:
                        exit_value = position["shares"] * exit_price
                        exit_tx_cost = exit_value * effective_cost
                        trade = _close_trade(
                            position, exit_price, date_str, exit_reason,
                            entry_tx_cost=position.get("entry_tx_cost", 0.0),
                            exit_tx_cost=exit_tx_cost,
                        )
                        trades.append(trade)
                        cash += (exit_value - exit_tx_cost)
                        total_costs_paid += exit_tx_cost
                        position = None
                        current_price = exit_price  # use exit price for equity calc this bar

                # Run agents to get signal
                provider = HistoricalDataProvider(full_data, date_str)
                agent_input = AgentInput(
                    ticker=cfg.ticker,
                    asset_type=cfg.asset_type,
                    backtest_mode=True,
                )

                agent_outputs: list[AgentOutput] = []
                for agent_name in agent_names:
                    try:
                        agent = _make_agent(agent_name, provider)
                        if agent is not None:
                            out = await agent.analyze(agent_input)
                            agent_outputs.append(out)
                    except Exception as exc:
                        warnings.append(f"{agent_name} failed on {date_str}: {exc}")

                # Aggregate signals
                agg: AggregatedSignal = aggregator.aggregate(
                    agent_outputs, cfg.ticker, cfg.asset_type
                )
                final_signal = agg.final_signal
                confidence = agg.final_confidence

                # Use agent's own confidence when single agent
                # (aggregated confidence degenerates to constant ±90% with 1 agent)
                log_confidence = (
                    agent_outputs[0].confidence
                    if len(agent_outputs) == 1
                    else confidence
                )

                signals_log.append({
                    "date": date_str,
                    "signal": final_signal.value,
                    "confidence": log_confidence,
                    "raw_score": agg.metrics.get("raw_score", 0.0),
                    "agent_signals": [
                        {
                            "agent": o.agent_name,
                            "signal": o.signal.value,
                            "confidence": o.confidence,
                        }
                        for o in agent_outputs
                    ],
                })

                # Trade logic
                position_value = position["shares"] * current_price if position else 0.0

                if final_signal == Signal.BUY and position is None:
                    trade_value = cash * cfg.position_size_pct
                    shares = trade_value / current_price
                    cost = shares * current_price
                    entry_tx_cost = cost * effective_cost  # SIG-04: 10 bps equity / 25 bps crypto
                    if cost + entry_tx_cost <= cash:
                        position = {
                            "entry_date": date_str,
                            "entry_price": current_price,
                            "shares": shares,
                            "signal": final_signal.value,
                            "confidence": confidence,
                            "entry_tx_cost": entry_tx_cost,   # stored for round-trip accounting
                        }
                        cash -= (cost + entry_tx_cost)
                        total_costs_paid += entry_tx_cost
                        n_trades += 1
                        position_value = shares * current_price

                elif final_signal == Signal.SELL and position is not None:
                    exit_value = position["shares"] * current_price
                    exit_tx_cost = exit_value * effective_cost
                    trade = _close_trade(
                        position, current_price, date_str, "signal_sell",
                        entry_tx_cost=position.get("entry_tx_cost", 0.0),
                        exit_tx_cost=exit_tx_cost,
                    )
                    trades.append(trade)
                    cash += (exit_value - exit_tx_cost)
                    total_costs_paid += exit_tx_cost
                    position = None
                    position_value = 0.0

            # Record daily equity (mark-to-market)
            position_value = position["shares"] * current_price if position else 0.0
            equity = cash + position_value
            equity_curve.append({"date": date_str, "equity": equity, "price": current_price})

        # 4. Close remaining open position at last date
        if position is not None and rebalance_dates:
            last_date_str = str(rebalance_dates[-1].date())
            mask = full_data.index.normalize() == pd.Timestamp(last_date_str).normalize()
            if mask.any():
                last_price = float(full_data.loc[mask, "Close"].iloc[-1])
            else:
                last_price = position["entry_price"]
            exit_value = position["shares"] * last_price
            exit_tx_cost = exit_value * effective_cost
            trade = _close_trade(
                position, last_price, last_date_str, "end_of_period",
                entry_tx_cost=position.get("entry_tx_cost", 0.0),
                exit_tx_cost=exit_tx_cost,
            )
            trades.append(trade)
            cash += (exit_value - exit_tx_cost)
            total_costs_paid += exit_tx_cost
            position = None
            # Update last equity curve entry
            if equity_curve:
                equity_curve[-1]["equity"] = cash
                equity_curve[-1]["price"] = last_price

        # 5. Compute metrics
        metrics = compute_metrics(trades, equity_curve, cfg.initial_capital)

        # SIG-04: Add transaction cost metrics for Phase 4 TTWROR
        metrics["total_costs_paid"] = round(total_costs_paid, 4)
        metrics["n_trades"] = n_trades
        metrics["cost_drag_pct"] = (
            round(total_costs_paid / cfg.initial_capital * 100, 4)
            if cfg.initial_capital > 0 else 0.0
        )
        metrics["effective_cost_per_trade"] = effective_cost

        return BacktestResult(
            config=cfg,
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
            warnings=warnings,
            agent_signals_log=signals_log,
        )


def _close_trade(
    position: dict[str, Any],
    exit_price: float,
    exit_date: str,
    exit_reason: str,
    entry_tx_cost: float = 0.0,
    exit_tx_cost: float = 0.0,
) -> SimulatedTrade:
    """Build a closed SimulatedTrade from an open position dict.

    pnl is net of transaction costs (entry + exit) per SIG-04 round-trip model.
    """
    shares = position["shares"]
    entry_price = position["entry_price"]
    entry_date = position["entry_date"]

    gross_pnl = (exit_price - entry_price) * shares
    total_tx_costs = entry_tx_cost + exit_tx_cost
    pnl = gross_pnl - total_tx_costs
    # pnl_pct based on gross cost basis (entry_price * shares) for comparability
    cost_basis = entry_price * shares
    pnl_pct = pnl / cost_basis if cost_basis > 0 else 0.0

    try:
        d1 = datetime.strptime(entry_date, "%Y-%m-%d")
        d2 = datetime.strptime(exit_date, "%Y-%m-%d")
        holding_days = (d2 - d1).days
    except ValueError:
        holding_days = None

    return SimulatedTrade(
        entry_date=entry_date,
        entry_price=entry_price,
        exit_date=exit_date,
        exit_price=exit_price,
        exit_reason=exit_reason,
        signal=position.get("signal", "BUY"),
        confidence=position.get("confidence", 0.0),
        shares=shares,
        pnl=round(pnl, 4),
        pnl_pct=round(pnl_pct, 6),
        holding_days=holding_days,
    )


def _make_agent(agent_name: str, provider: HistoricalDataProvider):
    """Instantiate an agent by name. Returns None for unknown names."""
    if agent_name == "TechnicalAgent":
        return TechnicalAgent(provider)
    if agent_name == "FundamentalAgent":
        from agents.fundamental import FundamentalAgent
        return FundamentalAgent(provider)
    if agent_name == "MacroAgent":
        try:
            from data_providers.fred_provider import FredProvider
            from data_providers.yfinance_provider import YFinanceProvider
            from agents.macro import MacroAgent
            return MacroAgent(FredProvider(), YFinanceProvider())
        except Exception:
            return None
    if agent_name == "CryptoAgent":
        from agents.crypto import CryptoAgent
        return CryptoAgent(provider)
    return None
