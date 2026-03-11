"""Batch backtest runner -- sweep tickers x agent combinations."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from backtesting.engine import Backtester, cache_price_data
from backtesting.models import BacktestConfig, BacktestResult
from db.database import DEFAULT_DB_PATH

# Crypto auto-detect sets
_CRYPTO_TICKERS = {"BTC", "ETH", "BTC-USD", "ETH-USD"}
_CRYPTO_YF_MAP = {"BTC": "BTC-USD", "ETH": "ETH-USD"}


@dataclass
class BatchConfig:
    """Configuration for a batch backtest sweep."""

    tickers: list[str]
    agent_combos: list[list[str]]  # e.g. [["TechnicalAgent"], ["TechnicalAgent","CryptoAgent"]]
    start_date: str
    end_date: str
    initial_capital: float = 100_000.0
    position_size_pct: float = 1.0
    rebalance_frequency: str = "weekly"
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None


@dataclass
class BatchResult:
    """Results from a batch backtest sweep.

    results[ticker][combo_key] = BacktestResult
    e.g. results["AAPL"]["TechnicalAgent"] = BacktestResult(...)
    """

    results: dict[str, dict[str, BacktestResult]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_summary_dict(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Flat summary of key metrics per ticker x combo for CLI display."""
        summary: dict[str, dict[str, dict[str, Any]]] = {}
        for ticker, combos in self.results.items():
            summary[ticker] = {}
            for combo_key, result in combos.items():
                m = result.metrics
                summary[ticker][combo_key] = {
                    "total_return_pct": m.get("total_return_pct"),
                    "annualized_return_pct": m.get("annualized_return_pct"),
                    "sharpe_ratio": m.get("sharpe_ratio"),
                    "sortino_ratio": m.get("sortino_ratio"),
                    "max_drawdown_pct": m.get("max_drawdown_pct"),
                    "calmar_ratio": m.get("calmar_ratio"),
                    "win_rate": m.get("win_rate"),
                    "profit_factor": m.get("profit_factor"),
                    "total_trades": m.get("total_trades"),
                    "avg_holding_days": m.get("avg_holding_days"),
                }
        return summary

    def to_json(self) -> str:
        """Serialize all results to JSON for charts and persistence."""
        data: dict[str, dict[str, dict[str, Any]]] = {}
        for ticker, combos in self.results.items():
            data[ticker] = {}
            for combo_key, result in combos.items():
                trades_list = []
                for t in result.trades:
                    trades_list.append({
                        "entry_date": t.entry_date,
                        "entry_price": t.entry_price,
                        "exit_date": t.exit_date,
                        "exit_price": t.exit_price,
                        "exit_reason": t.exit_reason,
                        "pnl_pct": t.pnl_pct,
                        "holding_days": t.holding_days,
                    })
                data[ticker][combo_key] = {
                    "config": {
                        "ticker": result.config.ticker,
                        "start_date": result.config.start_date,
                        "end_date": result.config.end_date,
                        "agents": result.config.agents,
                        "asset_type": result.config.asset_type,
                        "rebalance_frequency": result.config.rebalance_frequency,
                        "position_size_pct": result.config.position_size_pct,
                    },
                    "metrics": result.metrics,
                    "equity_curve": result.equity_curve,
                    "trades": trades_list,
                    "trades_count": len(result.trades),
                    "warnings": result.warnings,
                }
        output: dict[str, Any] = {"results": data}
        if self.errors:
            output["errors"] = self.errors
        return json.dumps(output, indent=2, default=str)


class BatchRunner:
    """Run backtests across tickers x agent combinations.

    Strategy:
    1. Pre-fetch and cache price data for all tickers (shared).
    2. For each ticker x agent_combo, run a Backtester sequentially.
    3. Collect results into BatchResult, isolating errors.
    """

    def __init__(self, config: BatchConfig) -> None:
        self._config = config

    async def run(
        self,
        db_path: str = str(DEFAULT_DB_PATH),
        progress_callback: Any = None,
    ) -> BatchResult:
        """Execute all backtest permutations.

        Args:
            db_path: SQLite DB path for price cache.
            progress_callback: Optional callable(ticker, combo_key) for progress reporting.

        Returns:
            BatchResult with all results and any errors.
        """
        cfg = self._config
        batch_result = BatchResult()
        price_cache: dict[str, pd.DataFrame] = {}

        # Phase 1: Pre-fetch price data for all tickers
        for ticker in cfg.tickers:
            asset_type = _detect_asset_type(ticker)
            yf_ticker = _map_ticker(ticker, asset_type)
            try:
                df = await cache_price_data(
                    yf_ticker, cfg.start_date, cfg.end_date,
                    asset_type, db_path,
                )
                price_cache[ticker] = df
            except Exception as exc:
                batch_result.errors.append(f"Price fetch failed for {ticker}: {exc}")

        # Phase 2: Run backtests -- sequential to avoid yfinance thread-safety issues
        for ticker in cfg.tickers:
            if ticker not in price_cache:
                continue
            df = price_cache[ticker]
            asset_type = _detect_asset_type(ticker)
            yf_ticker = _map_ticker(ticker, asset_type)
            batch_result.results.setdefault(ticker, {})

            for agents in cfg.agent_combos:
                combo_key = combo_key_from_agents(agents)

                if progress_callback:
                    progress_callback(ticker, combo_key)

                bt_config = BacktestConfig(
                    ticker=yf_ticker,
                    start_date=cfg.start_date,
                    end_date=cfg.end_date,
                    asset_type=asset_type,
                    initial_capital=cfg.initial_capital,
                    rebalance_frequency=cfg.rebalance_frequency,
                    agents=agents,
                    position_size_pct=cfg.position_size_pct,
                    stop_loss_pct=cfg.stop_loss_pct,
                    take_profit_pct=cfg.take_profit_pct,
                )
                try:
                    backtester = Backtester(bt_config)
                    result = await backtester.run(full_data=df, db_path=db_path)
                    batch_result.results[ticker][combo_key] = result
                except Exception as exc:
                    batch_result.errors.append(
                        f"Backtest failed: {ticker} [{combo_key}]: {exc}"
                    )

        return batch_result


def combo_key_from_agents(agents: list[str]) -> str:
    """Human-readable key: 'CryptoAgent+TechnicalAgent' (sorted for determinism)."""
    return "+".join(sorted(agents))


def _detect_asset_type(ticker: str) -> str:
    """Auto-detect asset type from ticker symbol."""
    upper = ticker.upper()
    if upper in ("BTC", "BTC-USD"):
        return "btc"
    if upper in ("ETH", "ETH-USD"):
        return "eth"
    return "stock"


def _map_ticker(ticker: str, asset_type: str) -> str:
    """Map bare crypto tickers to yfinance symbols."""
    upper = ticker.upper()
    if asset_type in ("btc", "eth"):
        return _CRYPTO_YF_MAP.get(upper, upper)
    return upper
