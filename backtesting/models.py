"""Data models for backtesting framework."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""

    ticker: str
    start_date: str                          # "YYYY-MM-DD"
    end_date: str                            # "YYYY-MM-DD"
    asset_type: str = "stock"
    initial_capital: float = 100_000.0
    rebalance_frequency: str = "weekly"      # "daily" | "weekly" | "monthly"
    agents: list[str] | None = None          # None → ["TechnicalAgent"]
    position_size_pct: float = 0.10          # 10% of capital per trade
    stop_loss_pct: float | None = 0.10       # 10% stop loss
    take_profit_pct: float | None = 0.20     # 20% take profit
    buy_threshold: float = 0.30              # aggregator buy threshold
    sell_threshold: float = -0.30            # aggregator sell threshold


@dataclass
class SimulatedTrade:
    """A single simulated trade (entry + exit)."""

    entry_date: str
    entry_price: float
    signal: str                              # "BUY" | "SELL" | "HOLD"
    confidence: float
    shares: float
    exit_date: str | None = None
    exit_price: float | None = None
    exit_reason: str | None = None          # "signal_sell" | "stop_loss" | "take_profit" | "end_of_period"
    pnl: float | None = None               # Realized P&L
    pnl_pct: float | None = None           # Realized return %
    holding_days: int | None = None


@dataclass
class BacktestResult:
    """Full results from a backtest run."""

    config: BacktestConfig
    trades: list[SimulatedTrade] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)   # [{"date": ..., "equity": ...}, ...]
    metrics: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    agent_signals_log: list[dict] = field(default_factory=list)  # [{"date": ..., "signal": ..., "confidence": ...}, ...]
