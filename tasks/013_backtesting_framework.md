# Task 013: Backtesting Framework

## Goal

Build a backtesting engine that replays historical price data through the analysis agents, simulates trades based on signals, and computes performance metrics (Sharpe, win rate, drawdown, etc.). This validates the rule-based signal quality before investing in LLM integration.

## Context

- `engine/pipeline.py` (Task 008) -- `AnalysisPipeline.analyze_ticker()` orchestrates agents and returns `AggregatedSignal`.
- `agents/technical.py` (Task 005) -- `TechnicalAgent` accepts OHLCV via DataProvider. This is the primary backtest-safe agent (OHLCV is point-in-time).
- `agents/fundamental.py` (Task 006) -- `FundamentalAgent` is NOT point-in-time (yfinance restates fundamentals). Use with disclaimer only.
- `agents/macro.py` (Task 007) -- `MacroAgent` uses FRED (point-in-time) + VIX (market data, point-in-time). Safe for backtests.
- `data_providers/yfinance_provider.py` -- `get_price_history(ticker, period, interval)` returns OHLCV DataFrame.
- `data_providers/base.py` -- `DataProvider` ABC with `is_point_in_time()` method.
- `agents/models.py` -- `Signal` enum (BUY/HOLD/SELL), `AgentInput`, `AgentOutput`.
- Thread-safety: `_yfinance_lock` serializes all yfinance calls.

## Requirements

### 1. Schema Addition (`db/database.py`)

Add `price_history_cache` table for offline replay:

```python
await conn.execute(
    """
    CREATE TABLE IF NOT EXISTS price_history_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        date TEXT NOT NULL,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        volume REAL NOT NULL,
        asset_type TEXT NOT NULL DEFAULT 'stock',
        fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ticker, date)
    );
    """
)

await conn.execute(
    """
    CREATE INDEX IF NOT EXISTS idx_price_cache_ticker_date
    ON price_history_cache(ticker, date);
    """
)
```

### 2. Package Structure

```
backtesting/
    __init__.py         # Exports: Backtester, BacktestConfig, BacktestResult, compute_metrics
    models.py           # BacktestConfig, BacktestResult, SimulatedTrade dataclasses
    data_slicer.py      # HistoricalDataProvider -- serves windowed data with no lookahead
    engine.py           # Backtester class -- main backtest loop
    metrics.py          # Pure metric computation functions
```

Add `backtesting` to hatch packages in `pyproject.toml`.

### 3. Data Models (`backtesting/models.py`)

```python
@dataclass
class BacktestConfig:
    ticker: str
    asset_type: str = "stock"
    start_date: str  # "YYYY-MM-DD"
    end_date: str    # "YYYY-MM-DD"
    initial_capital: float = 100_000.0
    rebalance_frequency: str = "weekly"  # "daily" | "weekly" | "monthly"
    agents: list[str] | None = None      # None = ["TechnicalAgent"] (safe default)
    position_size_pct: float = 0.10      # 10% of capital per trade
    stop_loss_pct: float | None = 0.10   # 10% stop loss
    take_profit_pct: float | None = 0.20 # 20% take profit

@dataclass
class SimulatedTrade:
    entry_date: str
    entry_price: float
    exit_date: str | None          # None if still open
    exit_price: float | None
    exit_reason: str | None        # "signal_sell" | "stop_loss" | "take_profit" | "end_of_period"
    signal: str                    # "BUY" | "SELL" | "HOLD"
    confidence: float
    shares: float
    pnl: float | None              # realized P&L
    pnl_pct: float | None          # realized return %
    holding_days: int | None

@dataclass
class BacktestResult:
    config: BacktestConfig
    trades: list[SimulatedTrade]
    equity_curve: list[dict]       # [{"date": "2024-01-15", "equity": 100500.0}, ...]
    metrics: dict                  # Output of compute_metrics()
    warnings: list[str]            # Non-PIT disclaimers, data gaps, etc.
    agent_signals_log: list[dict]  # [{"date": ..., "signal": ..., "confidence": ...}, ...]
```

### 4. Historical Data Provider (`backtesting/data_slicer.py`)

**`HistoricalDataProvider(DataProvider)`** -- a DataProvider wrapper that serves only data up to a given simulation date. This prevents lookahead bias.

```python
class HistoricalDataProvider(DataProvider):
    """Wraps a full OHLCV DataFrame, serves only data up to current_date."""

    def __init__(self, full_data: pd.DataFrame, current_date: str, ticker_info: dict | None = None):
        self._full_data = full_data
        self._current_date = pd.Timestamp(current_date)
        self._ticker_info = ticker_info or {}

    async def get_price_history(self, ticker, period="1y", interval="1d") -> pd.DataFrame:
        # Return only rows where index <= self._current_date
        mask = self._full_data.index <= self._current_date
        sliced = self._full_data.loc[mask].copy()
        if sliced.empty:
            raise ValueError(f"No data available for {ticker} up to {self._current_date}")
        return sliced

    async def get_current_price(self, ticker) -> float:
        # Return the Close price on current_date (or last available before it)
        mask = self._full_data.index <= self._current_date
        sliced = self._full_data.loc[mask]
        if sliced.empty:
            raise ValueError(f"No price for {ticker} on {self._current_date}")
        return float(sliced.iloc[-1]["Close"])

    async def get_key_stats(self, ticker) -> dict:
        return self._ticker_info  # Static or empty -- not used for technical backtest

    async def get_financials(self, ticker, period="annual") -> dict:
        raise NotImplementedError("Financials not available in backtest mode (non-PIT)")

    def is_point_in_time(self) -> bool:
        return True  # We've sliced to current_date, so it's PIT by construction

    def supported_asset_types(self) -> list[str]:
        return ["stock", "btc", "eth"]
```

### 5. Backtester Engine (`backtesting/engine.py`)

**`Backtester`** class:

```python
class Backtester:
    def __init__(self, config: BacktestConfig):
        self._config = config

    async def run(self) -> BacktestResult:
        """Execute backtest."""
        # 1. Fetch full price history (or load from cache)
        # 2. Generate rebalance dates
        # 3. Walk forward through dates
        # 4. At each rebalance date: create HistoricalDataProvider, run agents, get signal
        # 5. Execute trade logic based on signal
        # 6. Track equity curve
        # 7. Close any open position at end
        # 8. Compute metrics
        # 9. Return BacktestResult
```

**Detailed algorithm:**

1. **Data fetch**: Download full OHLCV for `[start_date - 252 trading days, end_date]` (need 252 days lookback for SMA200). Cache to `price_history_cache` table for reuse.

2. **Rebalance schedule**: Generate dates based on `rebalance_frequency`:
   - `"daily"`: every trading day in `[start_date, end_date]`
   - `"weekly"`: every Monday (or first trading day of week)
   - `"monthly"`: first trading day of each month

3. **Walk-forward loop** (for each rebalance date):
   ```
   position = None  # Current open position
   cash = initial_capital
   equity_curve = []

   for date in rebalance_dates:
       # Check stop loss / take profit on open position
       if position is not None:
           current_price = data_at_date.close
           if stop_loss hit or take_profit hit:
               close position, record trade

       # Create windowed provider
       provider = HistoricalDataProvider(full_data, date)

       # Run selected agents
       signal = await _run_agents(provider, date)

       # Trade logic:
       if signal == BUY and position is None:
           # Open long position
           shares = (cash * position_size_pct) / current_price
           position = {entry_date, entry_price, shares}
           cash -= shares * current_price

       elif signal == SELL and position is not None:
           # Close position
           cash += position.shares * current_price
           record trade with pnl
           position = None

       # Record equity: cash + position_value
       equity = cash + (position.shares * current_price if position else 0)
       equity_curve.append({"date": date, "equity": equity})

   # Close any remaining position at end
   if position is not None:
       close at last date price, record trade
   ```

4. **Agent execution** (`_run_agents`):
   - Select agents based on `config.agents` list. Default: `["TechnicalAgent"]`.
   - If `"TechnicalAgent"` in agents: create `TechnicalAgent(provider)`, call `analyze()`.
   - If `"MacroAgent"` in agents: create `MacroAgent(fred_provider, provider)`, call `analyze()`. FredProvider is real (FRED IS point-in-time).
   - If `"FundamentalAgent"` in agents: add warning `"Non-PIT: FundamentalAgent uses restated financials"`. Create with provider, call `analyze()`.
   - Aggregate signals via `SignalAggregator`.
   - Return aggregated signal.

5. **Non-PIT handling**:
   - Check `config.agents`. If any non-PIT agent included, add prominent warning to `BacktestResult.warnings`.
   - Default agents list: `["TechnicalAgent"]` (clean PIT results).
   - If user passes `--agents all`, include all agents WITH disclaimer.

### 6. Metrics (`backtesting/metrics.py`)

Pure functions, no I/O:

```python
def compute_metrics(trades: list[SimulatedTrade], equity_curve: list[dict],
                    initial_capital: float, risk_free_rate: float = 0.04) -> dict:
    """Compute all backtest performance metrics."""
    return {
        "total_return_pct": ...,       # (final_equity - initial) / initial
        "annualized_return_pct": ...,  # geometric annualized
        "sharpe_ratio": ...,           # (ann_return - rf) / ann_volatility
        "sortino_ratio": ...,          # (ann_return - rf) / downside_deviation
        "max_drawdown_pct": ...,       # largest peak-to-trough
        "calmar_ratio": ...,           # ann_return / max_drawdown
        "win_rate": ...,               # winning_trades / total_trades
        "profit_factor": ...,          # gross_profit / gross_loss
        "avg_win_pct": ...,            # average winning trade return
        "avg_loss_pct": ...,           # average losing trade return
        "total_trades": ...,
        "avg_holding_days": ...,
        "max_consecutive_wins": ...,
        "max_consecutive_losses": ...,
    }
```

**Individual metric formulas:**

- **Sharpe**: `(mean_daily_return - rf_daily) / std_daily_return * sqrt(252)`. rf_daily = `(1 + risk_free_rate) ** (1/252) - 1`.
- **Sortino**: Same as Sharpe but denominator = `sqrt(mean(min(0, daily_return - rf_daily)^2)) * sqrt(252)`.
- **Max Drawdown**: `max((peak - trough) / peak)` over equity curve.
- **Calmar**: `annualized_return / abs(max_drawdown)`.
- **Profit Factor**: `sum(positive_pnls) / abs(sum(negative_pnls))`. Return `inf` if no losses.
- **Win Rate**: `count(pnl > 0) / count(all_trades)`. Return None if 0 trades.

### 7. Price Cache Helper

Add to `backtesting/engine.py` or separate `backtesting/cache.py`:

```python
async def cache_price_data(ticker: str, start_date: str, end_date: str,
                           asset_type: str = "stock", db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Fetch price data and cache in SQLite. Return DataFrame."""
    # 1. Check cache first
    # 2. If miss: fetch from yfinance via YFinanceProvider
    # 3. Insert into price_history_cache (INSERT OR IGNORE for dedup)
    # 4. Return DataFrame
```

### 8. CLI (`cli/backtest_cli.py`)

```bash
# Basic backtest (TechnicalAgent only, clean PIT)
python -m cli.backtest_cli run AAPL --start 2024-01-01 --end 2025-12-31

# Include macro agent
python -m cli.backtest_cli run AAPL --start 2024-01-01 --end 2025-12-31 --agents technical,macro

# All agents (with non-PIT warning)
python -m cli.backtest_cli run AAPL --start 2024-01-01 --end 2025-12-31 --agents all

# Custom parameters
python -m cli.backtest_cli run AAPL --start 2024-01-01 --end 2025-12-31 \
    --capital 50000 --position-size 0.15 --stop-loss 0.08 --take-profit 0.25 \
    --frequency monthly

# Crypto
python -m cli.backtest_cli run BTC-USD --asset-type btc --start 2024-01-01 --end 2025-12-31
```

**Output format** (follows existing report.py pattern):

```
================================================================
  BACKTEST REPORT: AAPL
  2024-01-01 to 2025-12-31 (Technical only)
================================================================

  PERFORMANCE
  Total Return:      +18.5%
  Annualized Return: +9.1%
  Sharpe Ratio:      1.23
  Sortino Ratio:     1.85
  Max Drawdown:      -12.3%
  Calmar Ratio:      0.74

----------------------------------------------------------------
  TRADE STATISTICS
----------------------------------------------------------------
  Total Trades:      24
  Win Rate:          62.5% (15W / 9L)
  Profit Factor:     2.1x
  Avg Win:           +4.2%
  Avg Loss:          -2.8%
  Avg Holding:       14 days

----------------------------------------------------------------
  TRADE LOG (last 5)
----------------------------------------------------------------
  2025-10-15  BUY  $182.50  -> 2025-11-02  $195.30  +7.0%  signal_sell
  ...

================================================================

  WARNINGS:
    (none)

================================================================
```

**Windows event loop:**
```python
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

## Tests (`tests/test_013_backtesting.py`)

10-12 test cases, all with synthetic data (no network):

1. **`test_data_slicer_no_lookahead`**: Create 100-row DataFrame, set current_date to row 50. Verify `get_price_history()` returns only rows 0-50.
2. **`test_data_slicer_current_price`**: Set current_date, verify `get_current_price()` returns Close of that date.
3. **`test_data_slicer_empty_raises`**: Set current_date before any data. Verify ValueError raised.
4. **`test_metrics_sharpe_ratio`**: Known daily returns -> verify Sharpe computation.
5. **`test_metrics_max_drawdown`**: Known equity curve [100, 110, 90, 95, 120] -> verify max_drawdown = (110-90)/110 = 18.2%.
6. **`test_metrics_win_rate`**: 3 trades (2 wins, 1 loss) -> verify 66.7%.
7. **`test_metrics_profit_factor`**: Known P&L list -> verify gross_profit / gross_loss.
8. **`test_metrics_no_trades`**: Empty trades list -> verify None/0 for all metrics.
9. **`test_backtest_engine_simple`**: Mock agent to always return BUY. Run backtest on 20 synthetic dates. Verify trades created, equity curve has entries, result is BacktestResult.
10. **`test_backtest_engine_sell_signal`**: Mock agent: BUY on date 5, SELL on date 10. Verify one complete trade with correct dates.
11. **`test_backtest_stop_loss`**: Mock agent: BUY. Price drops 15%. Verify stop_loss exit at correct price.
12. **`test_backtest_non_pit_warning`**: Config with `agents=["TechnicalAgent", "FundamentalAgent"]`. Verify warning about non-PIT data in result.

**Mocking strategy**: Create a `MockAgent(BaseAgent)` that returns configurable signals per date. Use synthetic OHLCV DataFrames with known prices for deterministic test results.

## Verification

```bash
# Run tests
pytest tests/test_013_backtesting.py -v

# Manual verification (requires network for price data)
python -m cli.backtest_cli run AAPL --start 2024-01-01 --end 2025-12-31
python -m cli.backtest_cli run AAPL --start 2024-01-01 --end 2025-12-31 --agents all
python -m cli.backtest_cli run BTC-USD --asset-type btc --start 2024-06-01 --end 2025-12-31
```

## Hints

- The `TechnicalAgent` needs ~200 bars of lookback for SMA200. When fetching data, request `start_date - 300 calendar days` to ensure sufficient history.
- For rebalance dates: use `pd.bdate_range(start, end, freq='W-MON')` for weekly, `pd.bdate_range(start, end, freq='BMS')` for monthly first business day.
- The `asyncio.gather` with yfinance lock means backtest agents run sequentially anyway. Don't try to parallelize agent calls within a single backtest step.
- Use `INSERT OR IGNORE INTO price_history_cache` for cache population (UNIQUE constraint on ticker+date handles dedup).
- For the equity curve daily returns: interpolate between rebalance dates using position mark-to-market.
