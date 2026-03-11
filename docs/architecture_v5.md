# Investment Analysis Agent -- Architecture v5

## 0. v4 -> v5 Changes

| Dimension | v4 (Design Spec) | v5 (Reflects Actual + Forward Plan) |
|-----------|-------------------|-------------------------------------|
| Document purpose | Forward-looking design spec | **Living architecture doc: actual state + roadmap** |
| Phase 1 status | Planned | **COMPLETE (Tasks 001-011, 95 tests)** |
| Sprint 3 status | Planned | **COMPLETE (Tasks 012-013, charts + backtesting)** |
| Sprint 4 status | Planned | **COMPLETE (Task 014 daemon + 014.5 detail mode)** |
| Sprint 4.5 status | N/A | **COMPLETE (Task 015.5 FundamentalAgent enhancement)** |
| Sprint 7 status | Planned | **COMPLETE (Tasks 018-019, CryptoAgent + Sector/Correlation)** |
| Agent design | 5 agents (incl LLM-based) | **4 rule-based agents implemented; 2 LLM agents deferred** |
| Data schema | 8 tables (speculative) | **9 tables (actual, tested, in production)** |
| Learning system | L1/L2/L3 planned | **Data collection in place; adaptation deferred to Sprint 5** |
| Report format | Simple summary | **Standard + Detail mode (--detail flag)** |

-----

## 1. Product Overview

### 1.1 Positioning

"The investment journal that fights back -- tracks your thesis, monitors positions, tells you when reality diverges from your plan."

### 1.2 Requirements

| Dimension | Decision |
|-----------|----------|
| Assets | US stocks + BTC/Crypto |
| Capital scale | $200K-500K |
| Tool positioning | Continuous monitoring + analysis advice, manual trading |
| Investment cycle | Flexible per asset |
| US stock strategy | Experimental: fundamental / technical / multi-factor parallel testing |
| BTC strategy | Experimental: technical + macro / mixed parallel testing |
| Data sources | Phase 1-2: yfinance + ccxt + FRED (free) -> Phase 3+: FMP upgrade by ROI |
| Learning priority | L1 weight adaptation -> L2 regime switching -> (deferred) L3 reasoning |

### 1.3 Competitive Advantages

| vs Competitor | Our Edge |
|---------------|----------|
| ai-hedge-fund (47K stars) | Continuous monitoring, thesis tracking, drift analysis, portfolio persistence |
| TradingAgents (~5K stars) | Portfolio persistence, not just one-shot research |
| PortfolioPilot (commercial) | Self-hosted, transparent, free |
| OpenBB (~35K stars) | Analysis agent with signal generation, not data workspace |

Core moat: Expected vs Actual ROI dual-track + thesis accountability feedback loop.

-----

## 2. System Architecture

```
+-----------------------------------------------------------------------+
|                         CLI Layer                                      |
| analyze_cli  portfolio_cli  monitor_cli  signal_cli  daemon_cli       |
| backtest_cli  charts_cli                                              |
+--------+----------+-----------+-----------+-----------+---------------+
         |          |           |           |           |
    +----v----+ +---v----+ +---v-----+ +---v----+ +---v---------+
    | Analysis | |Portfolio| |Monitoring| |Signal  | | Monitoring  |
    | Pipeline | |Manager | |Monitor   | |Tracker | | Daemon      |
    +----+----+ +---+----+ +----+----+ +---+----+ | (APScheduler)|
         |          |           |           |      +---+---------+
    +----v----------v-----------v-----------v----------v---------+
    |                     Engine Layer                            |
    | Agents (Technical, Fundamental, Macro)                     |
    | SignalAggregator | DriftAnalyzer | SignalComparator         |
    +--------+--------------------------------------------------+
             |
    +--------v--------------------------------------------------+
    |                   Data Layer                               |
    | DataProviders (YFinance, CCXT, FRED)                      |
    | SQLite (WAL mode, 9 tables, aiosqlite)                    |
    +-----------------------------------------------------------+
```

Tech stack:

- **Runtime**: Python 3.11+ / asyncio
- **Data**: yfinance + ccxt + FRED + pandas_ta (Phase 1-2, $0/mo)
- **Store**: SQLite (WAL mode, aiosqlite, single-file, zero-ops)
- **Charts**: plotly (dark theme, HTML export)
- **Scheduler**: APScheduler 3.x (cron-based async daemon)
- **Frontend**: React + TypeScript (Phase 3, not started)
- **LLM**: Claude API via Anthropic SDK (Phase 3, Task 017)

-----

## 3. Package Structure (Actual)

```
investment_agent/
  agents/                      # Analysis agents
    __init__.py                #   exports: BaseAgent, AgentInput, AgentOutput, Signal, Regime
    base.py                    #   BaseAgent ABC
    models.py                  #   AgentInput, AgentOutput, Signal, Regime dataclasses
    technical.py               #   TechnicalAgent (rule-based, 17 metrics)
    fundamental.py             #   FundamentalAgent (rule-based, 20 metrics)
    macro.py                   #   MacroAgent (rule-based, 11 metrics)
    crypto.py                  #   CryptoAgent (7-factor, crypto-native scoring)

  backtesting/                 # Walk-forward backtesting engine
    __init__.py
    models.py                  #   BacktestConfig, SimulatedTrade, BacktestResult, BacktestMetrics
    data_slicer.py             #   HistoricalDataProvider (no lookahead bias)
    engine.py                  #   Backtester.run_backtest()
    metrics.py                 #   Sharpe, Sortino, max drawdown, Calmar, win rate, profit factor

  charts/                      # Plotly chart generators (pure functions)
    __init__.py
    analysis_charts.py         #   create_price_chart(), create_agent_breakdown_chart(), create_crypto_factor_chart(), add_signal_markers()
    portfolio_charts.py        #   create_allocation_chart(), create_sector_chart()
    tracking_charts.py         #   create_calibration_chart(), create_drift_scatter()

  cli/                         # CLI entry points
    analyze_cli.py             #   python -m cli.analyze_cli AAPL [--detail] [--json]
    portfolio_cli.py           #   add/remove/show/set-cash/scale/split
    monitor_cli.py             #   check/alerts
    signal_cli.py              #   history/stats/calibration/agents
    backtest_cli.py            #   run (ticker + date range + config -> metrics)
    charts_cli.py              #   analysis (interactive HTML + signals)/portfolio/calibration/drift
    daemon_cli.py              #   start/run-once/status
    report.py                  #   Report formatter (standard + detail mode)

  daemon/                      # Monitoring daemon (APScheduler)
    __init__.py
    config.py                  #   DaemonConfig dataclass
    scheduler.py               #   MonitoringDaemon (lifecycle, signal handlers)
    jobs.py                    #   run_daily_check, run_weekly_revaluation, catalyst_stub
    signal_comparator.py       #   compare_signals() pure function

  data_providers/              # Data abstraction layer
    __init__.py
    base.py                    #   DataProvider ABC
    yfinance_provider.py       #   Stocks + crypto via yfinance
    ccxt_provider.py           #   Crypto via Binance (preserved for Phase 2)
    fred_provider.py           #   Macro data (FRED API)
    factory.py                 #   get_provider(asset_type) factory

  db/
    database.py                #   init_db(), 9 tables, WAL mode, indexes

  engine/                      # Core analysis engine
    __init__.py
    aggregator.py              #   SignalAggregator, AggregatedSignal
    pipeline.py                #   AnalysisPipeline (parallel agent execution)
    drift_analyzer.py          #   DriftAnalyzer (entry/return/hold drift)
    sector.py                  #   Sector rotation matrix + get_sector_modifier()
    correlation.py             #   Portfolio pairwise correlation tracker

  monitoring/                  # Position monitoring
    __init__.py
    models.py                  #   Alert dataclass
    checker.py                 #   Pure rule-based exit trigger checks
    store.py                   #   AlertStore (db persistence)
    monitor.py                 #   PortfolioMonitor.run_check()

  portfolio/                   # Portfolio management
    __init__.py
    models.py                  #   Position, Portfolio dataclasses
    manager.py                 #   PortfolioManager (CRUD + snapshots)

  tracking/                    # Signal tracking & calibration
    __init__.py
    store.py                   #   SignalStore (persist + query signals)
    tracker.py                 #   SignalTracker (accuracy, calibration, agent perf)

  tests/                       # 162 tests, 1 skipped (network)
    test_001_database.py       #   5 tests
    test_002_drift.py          #   5 tests
    test_003_portfolio.py      #   8 tests
    test_004_data_providers.py #   8 tests
    test_005_technical_agent.py#   8 tests
    test_006_fundamental.py    #   8 tests
    test_007_macro_agent.py    #   9 tests
    test_008_aggregator.py     #   8 tests
    test_008_5_drift_enhancements.py # 7 tests
    test_009_cli_report.py     #   12 tests (8 original + 4 detail mode)
    test_010_monitoring.py     #   11 tests
    test_011_signal_tracking.py#   10 tests
    test_012_charts.py         #   8 tests
    test_013_backtesting.py    #   12 tests
    test_014_daemon.py         #   10 tests
    test_015_5_fundamental.py  #   4 tests
    test_018_crypto_agent.py   #   14 tests
    test_019_sector_correlation.py # 15 tests

  docs/
    architecture_v5.md         #   This document
    AGENT_SYNC.md              #   Dev agent communication log
    DEVELOPER_INSTRUCTIONS.md  #   Dev guidelines
  tasks/                       #   Task specs (001-014.5)
  data/                        #   SQLite DB + daemon logs (gitignored)
  pyproject.toml               #   Project config
```

-----

## 4. Data Layer

### 4.1 SQLite Schema (9 Tables)

```sql
-- 1. Analysis thesis (expected signal at analysis time)
CREATE TABLE positions_thesis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    expected_signal TEXT NOT NULL,       -- 'BUY' | 'HOLD' | 'SELL'
    expected_confidence REAL NOT NULL,   -- 0-100
    expected_entry_price REAL NOT NULL,
    expected_target_price REAL,
    expected_return_pct REAL,
    expected_stop_loss REAL,
    expected_hold_days INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Trade execution log (actual fills)
CREATE TABLE trade_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thesis_id INTEGER NOT NULL REFERENCES positions_thesis(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('BUY', 'SELL')),
    quantity REAL NOT NULL,
    executed_price REAL NOT NULL,
    executed_at TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN ('manual', 'target_hit', 'stop_loss'))
);

-- 3. Portfolio snapshots (auto-captured on trades, daily checks, weekly revals)
CREATE TABLE portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    total_value REAL NOT NULL,
    cash REAL NOT NULL,
    positions_json TEXT NOT NULL,
    trigger_event TEXT NOT NULL          -- 'trade' | 'daily_check' | 'weekly_revaluation' | 'manual'
);

-- 4. Active positions (current holdings)
CREATE TABLE active_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('stock', 'btc', 'eth')),
    quantity REAL NOT NULL,
    avg_cost REAL NOT NULL,
    sector TEXT,
    industry TEXT,
    entry_date TEXT NOT NULL,
    original_analysis_id INTEGER REFERENCES positions_thesis(id),
    expected_return_pct REAL,
    expected_hold_days INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 5. Portfolio metadata (cash balance, settings)
CREATE TABLE portfolio_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. Monitoring alerts (exit triggers, signal reversals, catalysts)
CREATE TABLE monitoring_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    alert_type TEXT NOT NULL,            -- 'STOP_LOSS_HIT' | 'TRAILING_STOP' | 'TARGET_HIT'
                                         -- | 'TIME_OVERRUN' | 'SIGNAL_REVERSAL' | 'HEALTH_CHECK'
    severity TEXT NOT NULL CHECK (severity IN ('CRITICAL', 'HIGH', 'WARNING', 'INFO')),
    message TEXT NOT NULL,
    recommended_action TEXT,
    current_price REAL,
    trigger_price REAL,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 7. Signal history (every analysis result, with outcome tracking)
CREATE TABLE signal_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    final_signal TEXT NOT NULL CHECK (final_signal IN ('BUY', 'HOLD', 'SELL')),
    final_confidence REAL NOT NULL,
    regime TEXT,
    raw_score REAL NOT NULL,
    consensus_score REAL NOT NULL,
    agent_signals_json TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    warnings_json TEXT,
    thesis_id INTEGER REFERENCES positions_thesis(id),
    outcome TEXT CHECK (outcome IS NULL OR outcome IN ('WIN', 'LOSS', 'OPEN', 'SKIPPED')),
    outcome_return_pct REAL,
    outcome_resolved_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 8. Daemon execution history (job audit trail)
CREATE TABLE daemon_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,              -- 'daily_check' | 'weekly_revaluation' | 'catalyst_scan'
    status TEXT NOT NULL CHECK (status IN ('success', 'error', 'skipped')),
    started_at TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    result_json TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 9. Price history cache (backtesting offline replay)
CREATE TABLE price_history_cache (
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
```

Database configuration:
- **WAL mode**: concurrent reads during daemon/CLI operations
- **busy_timeout=5000**: 5s retry before "database locked" error
- **synchronous=NORMAL**: performance vs durability balance (acceptable for non-financial-critical data)
- **foreign_keys=ON**: referential integrity enforced

### 4.2 Data Provider Abstraction

```python
class DataProvider(ABC):
    @abstractmethod
    async def get_price_history(self, ticker, period, interval) -> pd.DataFrame: ...

    @abstractmethod
    async def get_current_price(self, ticker) -> float: ...

    @abstractmethod
    async def get_key_stats(self, ticker) -> dict: ...

    @abstractmethod
    async def get_financials(self, ticker) -> dict: ...

    @abstractmethod
    def is_point_in_time(self) -> bool: ...

    @abstractmethod
    def supported_asset_types(self) -> list[str]: ...
```

Provider routing:

| Asset type | Provider | Notes |
|-----------|----------|-------|
| stock | YFinanceProvider | Price + financials + key stats |
| btc, eth | YFinanceProvider | BTC-USD/ETH-USD via yfinance (Binance geo-restricted in US) |
| macro | FredProvider | M2, DXY, yield curve, VIX, fed funds |

CcxtProvider preserved for Phase 2 exchange-specific features (funding rates, order book depth).

### 4.3 Data Quality Notes

yfinance limitations (accepted for Phase 1-2):
- Financial statements NOT Point-in-Time (returns latest revision, not as-published)
- No SLA, occasional Yahoo rate limits
- Backtesting reports auto-labeled with non-PIT disclaimer when FundamentalAgent used

Mitigation:
- TechnicalAgent backtests unaffected (price data IS point-in-time)
- FundamentalAgent backtests carry "non-PIT data" warning
- Phase 3 upgrade to FMP ($20-50/mo) eliminates this limitation

-----

## 5. Analysis Engine

### 5.1 Agent Framework

```python
@dataclass
class AgentInput:
    ticker: str
    asset_type: str                          # 'stock' | 'btc' | 'eth'
    portfolio: Portfolio | None = None       # Phase 2: portfolio-aware analysis
    regime: Regime | None = None
    learned_weights: dict[str, Any] = field(default_factory=dict)   # Phase 2
    approved_rules: list[str] = field(default_factory=list)         # Phase 2

@dataclass
class AgentOutput:
    agent_name: str
    ticker: str
    signal: Signal                           # BUY | HOLD | SELL
    confidence: float                        # 0-100, validated in __post_init__
    reasoning: str                           # Human-readable analysis narrative
    metrics: dict[str, Any]                  # All computed indicators (17+ keys)
    timestamp: str                           # ISO format UTC
    warnings: list[str]
```

### 5.2 Implemented Agents

| Agent | Assets | Metrics computed | Signal logic |
|-------|--------|-----------------|--------------|
| TechnicalAgent | All | 17: SMA 20/50/200, RSI, MACD (line/signal/hist), BB (upper/mid/lower), ATR, volume_ratio, trend/momentum/volatility/composite scores, weekly_trend_confirms | Sub-score weighted composite -> threshold mapping |
| FundamentalAgent | Stock only | 20: P/E trailing/forward, P/B, EV/EBITDA, PEG ratio, ROE, profit_margin, debt_equity, current_ratio, FCF yield, revenue_growth, earnings_growth, analyst_rating, market_cap, dividend_yield, sector, pct_from_52w_high, value/quality/growth/composite scores | Value + quality + growth sub-scores -> composite |
| MacroAgent | All | 11: VIX current/SMA20, treasury 10Y/2Y, yield_curve_spread, fed_funds_rate/trend, M2 YoY growth, regime, net_score, risk_on/off points | Point-based scoring -> regime classification |
| CryptoAgent | BTC/ETH | 7 factors (34 sub-metrics): market_structure, momentum_trend, volatility_risk, liquidity_volume, macro_correlation, network_adoption, cycle_timing, composite_score | Weighted 7-factor composite: Market Structure 15%, Momentum 20%, Volatility 15%, Liquidity 10%, Macro 15%, Network 10%, Cycle 15% |

**Planned agents (Task 017+):**
- SentimentAgent: Web search + Claude API for news/catalyst evaluation
- OnChainAgent: BTC-specific on-chain metrics (Phase 3)
- ValidationAgent: Cross-agent logic consistency check

### 5.3 Signal Aggregation

```python
class SignalAggregator:
    DEFAULT_WEIGHTS = {
        "stock": {"TechnicalAgent": 0.30, "FundamentalAgent": 0.45, "MacroAgent": 0.25},
        "btc":   {"CryptoAgent": 1.0},
        "eth":   {"CryptoAgent": 1.0},
    }
```

Aggregation algorithm:
1. For each agent: `effective_weight = agent_weight * (confidence / 100)`
2. `weighted_sum = SUM(signal_value * effective_weight)` where BUY=+1, HOLD=0, SELL=-1
3. `raw_score = weighted_sum / total_effective_weight`
4. Signal determination: raw_score >= +0.30 -> BUY, <= -0.30 -> SELL, else HOLD
5. Confidence: base from raw_score distance to threshold, clamped [30, 90]
6. Consensus check: if < 50% agents agree -> confidence *= 0.8 (penalty)

Output: `AggregatedSignal` containing final_signal, final_confidence, regime, agent_signals list, reasoning, metrics (raw_score, consensus_score, weights_used, agent_contributions), ticker_info, warnings.

### 5.4 Analysis Pipeline

```python
class AnalysisPipeline:
    async def analyze_ticker(self, ticker, asset_type, portfolio=None) -> AggregatedSignal:
        # 1. Resolve providers
        # 2. Fetch data (prices, financials, macro) via DataProvider
        # 3. Run agents in parallel via asyncio.gather (graceful degradation)
        # 4. Fetch ticker_info in parallel with agents
        # 5. Aggregate signals via SignalAggregator
        # 6. Return AggregatedSignal
```

Agent selection by asset type:
- stock: TechnicalAgent + FundamentalAgent + MacroAgent (weights 0.30/0.45/0.25)
- btc/eth: CryptoAgent (weight 1.0)

Graceful degradation: if FRED_API_KEY not set, MacroAgent skipped with warning (analysis continues with remaining agents).

### 5.5 Analysis Report Format

**Standard mode** (`python -m cli.analyze_cli AAPL`):
```
================================================================
  ANALYSIS REPORT: Apple Inc (AAPL)
================================================================

  Price:      $182.30
  Market Cap: $2.85T
  52W Range:  $142.00 - $199.62
  vs 52W High: -8.7%
  Sector:     Technology / Consumer Electronics

  SIGNAL:     BUY
  CONFIDENCE: 68%
  REGIME:     RISK_ON

----------------------------------------------------------------
  AGENT BREAKDOWN
----------------------------------------------------------------

  Technical:    BUY  (72%)
    RSI: 45.2 | Trend: +8 | Momentum: +6 | Volatility: -2

  Fundamental:  BUY  (65%)
    P/E: 28.3 | ROE: 147.3% | Rev Growth: +4.2% | D/E: 1.87

  Macro:        HOLD (58%)
    Regime: RISK_ON | VIX: 18.5 | Yield Curve: +0.32% | Score: +2

----------------------------------------------------------------
  CONSENSUS: 2/3 agents agree
----------------------------------------------------------------

  WARNINGS:
    (none)

================================================================
```

**Detail mode** (`python -m cli.analyze_cli AAPL --detail`):

Expands each agent block to show:
- All sub-scores with decomposition
- All computed indicators grouped logically
- Full reasoning narrative (wrapped, `> ` prefixed)
- Weight contribution math: `weight x signal(value) x confidence = contribution`

Adds AGGREGATION DETAIL section:
- Weights used per agent
- Raw score with threshold reference
- Consensus breakdown (N/M agents, dominant signal, strength)
- Consensus adjustment note
- Final signal + confidence

-----

## 6. Portfolio Context Manager

### 6.1 Data Model

```python
@dataclass
class Position:
    ticker: str
    asset_type: str                    # 'stock' | 'btc' | 'eth'
    quantity: float
    avg_cost: float
    sector: str | None = None          # GICS sector (stocks only)
    industry: str | None = None
    entry_date: str = ""
    original_analysis_id: int | None = None   # FK to positions_thesis
    expected_return_pct: float | None = None
    expected_hold_days: int | None = None

    @property
    def cost_basis(self) -> float:     # quantity * avg_cost
    @property
    def holding_days(self) -> int:     # (today - entry_date).days

@dataclass
class Portfolio:
    positions: list[Position]
    cash: float
    total_value: float                 # sum(cost_basis) + cash
    stock_exposure_pct: float
    crypto_exposure_pct: float
    cash_pct: float
    sector_breakdown: dict[str, float] # {"Technology": 0.35, ...}
    top_concentration: list[tuple[str, float]]  # sorted by weight
```

### 6.2 CLI Operations

```bash
# Add position
python -m cli.portfolio_cli add --ticker MSFT --asset-type stock \
    --quantity 200 --avg-cost 415.50 --entry-date 2026-02-10 --sector Technology

# Remove position
python -m cli.portfolio_cli remove --ticker MSFT

# View portfolio
python -m cli.portfolio_cli show

# Set cash balance
python -m cli.portfolio_cli set-cash 150000

# Scale all positions (e.g., capital doubled)
python -m cli.portfolio_cli scale --multiplier 2.0

# Apply stock split
python -m cli.portfolio_cli split --ticker AAPL --ratio 4
```

### 6.3 Phase 2 Enhancement: Portfolio-Aware Analysis

Currently, agents analyze tickers in isolation. Phase 2 will:
- Pass `portfolio` to `AgentInput` so agents can consider portfolio context
- Add concentration checks (sector cap at 40%)
- Add correlation check (warn if new position rho > 0.8 with existing)
- Adjust position sizing based on portfolio constraints
- Show before/after exposure impact in report

-----

## 7. Monitoring System

### 7.1 Position Monitor (Real-time Checks)

`PortfolioMonitor.run_check()` performs:

1. Load portfolio via PortfolioManager
2. Fetch current prices via DataProvider
3. For each position, run rule-based exit trigger checks:
   - **Stop loss**: current_price <= expected_stop_loss
   - **Target hit**: current_price >= expected_target_price
   - **Time overrun**: holding_days > expected_hold_days * 1.5
   - **Health check**: any data anomalies or warnings
4. Generate Alert objects (severity: CRITICAL/HIGH/WARNING/INFO)
5. Persist alerts via AlertStore
6. Save portfolio snapshot (trigger_event="daily_check")

Returns: `{checked_positions, alerts, snapshot_saved, warnings}`

### 7.2 Alert Model

```python
@dataclass
class Alert:
    ticker: str
    alert_type: str          # STOP_LOSS_HIT | TARGET_HIT | TIME_OVERRUN | SIGNAL_REVERSAL | HEALTH_CHECK
    severity: str            # CRITICAL | HIGH | WARNING | INFO
    message: str
    recommended_action: str | None = None
    current_price: float | None = None
    trigger_price: float | None = None
```

Alert lifecycle:
- Phase 1: SQLite persistence + CLI viewing (`python -m cli.monitor_cli alerts`)
- Phase 2: Email dispatch (SendGrid/SES)
- Phase 3: Push notifications (Telegram/Slack webhook)

### 7.3 CLI

```bash
# Run daily check immediately
python -m cli.monitor_cli check

# View recent alerts
python -m cli.monitor_cli alerts [--ticker AAPL] [--severity HIGH] [--limit 20]
```

-----

## 8. Monitoring Daemon

### 8.1 Architecture

APScheduler 3.x `AsyncIOScheduler` with cron-based triggers. Three scheduled jobs:

| Job | Schedule | Status | Description |
|-----|----------|--------|-------------|
| Daily Check | Mon-Fri 5:00 PM ET | **Implemented** | Wraps PortfolioMonitor.run_check() |
| Weekly Revaluation | Sat 10:00 AM ET | **Implemented** | Full re-analysis per position |
| Catalyst Scan | Every 4 hours | **Stub** (Task 017) | Requires LLM for news evaluation |

### 8.2 Configuration

```python
@dataclass
class DaemonConfig:
    db_path: str = str(DEFAULT_DB_PATH)
    daily_hour: int = 17
    daily_minute: int = 0
    daily_days: str = "mon-fri"
    daily_enabled: bool = True          # Toggle daily job on/off
    weekly_day: str = "sat"
    weekly_hour: int = 10
    weekly_minute: int = 0
    weekly_enabled: bool = True         # Toggle weekly job on/off
    catalyst_enabled: bool = False      # Stub until Task 017
    timezone: str = "US/Eastern"
    log_file: str = "data/daemon.log"
    log_level: str = "INFO"             # DEBUG | INFO | WARNING | ERROR
```

### 8.3 Daily Check Job

```python
async def run_daily_check(db_path, logger):
    # 1. PortfolioMonitor(db_path).run_check()
    # 2. Log results (positions checked, alerts generated)
    # 3. Record in daemon_runs table (status, duration_ms, result_json)
    # Never raises -- catches all exceptions, logs error, records status="error"
```

### 8.4 Weekly Revaluation Job

```python
async def run_weekly_revaluation(db_path, logger):
    # 1. Load portfolio via PortfolioManager
    # 2. For each position (individual try/except -- one failure doesn't block others):
    #    a. Run AnalysisPipeline.analyze_ticker(ticker, asset_type)
    #    b. Load original thesis from positions_thesis (via position.original_analysis_id)
    #    c. Compare via compare_signals() -- detect BUY<->SELL reversals
    #    d. If reversal: create SIGNAL_REVERSAL alert (severity=HIGH) via AlertStore
    #    e. Save new signal via SignalStore.save_signal()
    # 3. Save portfolio snapshot (trigger_event="weekly_revaluation")
    # 4. Record in daemon_runs
    # Returns: {positions_analyzed, signal_reversals, alerts_generated, signals_saved, errors}
```

### 8.5 Signal Comparator (Pure Function)

```python
@dataclass
class SignalComparison:
    original_signal: str
    current_signal: str
    direction_reversed: bool    # True only for BUY<->SELL (not BUY->HOLD)
    confidence_delta: float
    summary: str

def compare_signals(original_signal, original_confidence, current_signal, current_confidence) -> SignalComparison
```

Reversal definition: BUY -> SELL or SELL -> BUY only. BUY -> HOLD is "weakening", not reversal.

### 8.6 CLI

```bash
# Start long-running daemon
python -m cli.daemon_cli start [--daily-hour 17] [--weekly-day sat] [--no-daily] [--no-weekly]

# Run single job immediately
python -m cli.daemon_cli run-once daily
python -m cli.daemon_cli run-once weekly

# View execution history
python -m cli.daemon_cli status
```

### 8.7 Logging

- RotatingFileHandler: 5 MB max, 3 backup files, `data/daemon.log`
- Console handler: stderr
- Format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`

### 8.8 Graceful Shutdown

- Linux/macOS: SIGINT/SIGTERM signal handlers via asyncio event loop
- Windows: KeyboardInterrupt catch in CLI (`asyncio.WindowsSelectorEventLoopPolicy` set at CLI entry)

-----

## 9. Signal Tracking & Calibration

### 9.1 Signal Persistence

Every analysis generates a `signal_history` row with:
- Signal details (final_signal, confidence, regime, raw_score, consensus_score)
- Agent breakdown (agent_signals_json)
- Reasoning narrative
- Link to thesis (thesis_id FK)
- Outcome tracking (outcome, outcome_return_pct, outcome_resolved_at)

### 9.2 Calibration Metrics

`SignalTracker` computes:

| Metric | Description |
|--------|-------------|
| `compute_accuracy_stats(lookback)` | Win rate, correct/total signals by asset_type, regime, agent |
| `compute_calibration_data(bins)` | Confidence bucket vs actual win rate (ideal = diagonal) |
| `compute_agent_performance()` | Per-agent accuracy breakdown by asset/regime |

### 9.3 CLI

```bash
python -m cli.signal_cli history [--ticker AAPL] [--limit 20]
python -m cli.signal_cli stats [--lookback 50]
python -m cli.signal_cli calibration [--bins 5]
python -m cli.signal_cli agents
```

-----

## 10. Expected vs Actual Drift Tracking

### 10.1 Drift Types

| Drift | Formula | Interpretation |
|-------|---------|---------------|
| Entry Drift | (actual_entry - expected_entry) / expected_entry | Execution gap (slippage, timing) |
| Return Drift | actual_return - expected_return | Forecast accuracy (positive = system was conservative) |
| Hold Drift | actual_hold_days - expected_hold_days | Timing calibration |

### 10.2 Implementation

`DriftAnalyzer` computes position-level and rolling aggregate drift:

```python
# Single position drift
compute_position_drift(thesis_id) -> {entry_drift_pct, return_drift_pct, hold_drift_days, outcome}

# Rolling summary
compute_drift_summary(lookback=50) -> {
    avg_entry_drift, avg_return_drift, avg_hold_drift_days,
    win_rate, total_trades, consensus_stats,
    by_asset_type: {...}, by_regime: {...}
}
```

### 10.3 Phase 2 Enhancement

Current schema stores expected vs actual in separate tables (positions_thesis + trade_executions). Phase 2 will consolidate into a unified `trade_records` table with full dual-track columns for richer drift analysis and UI visualization.

-----

## 11. Backtesting Framework

### 11.1 Walk-Forward Engine

```python
@dataclass
class BacktestConfig:
    ticker: str
    asset_type: str = "stock"
    start_date: str                     # YYYY-MM-DD
    end_date: str
    initial_capital: float = 100_000
    position_size_pct: float = 0.10     # 10% of capital per trade
    rebalance_freq: str = "weekly"      # daily | weekly | monthly
    agent_names: list[str]              # ["technical"] | ["technical", "fundamental", "macro"]
    stop_loss_pct: float | None = 0.10
    take_profit_pct: float | None = 0.20
```

Walk-forward loop:
1. Slice price data up to current date (no lookahead via `HistoricalDataProvider`)
2. Run selected agents on sliced data
3. Aggregate signals -> generate trade decision
4. Execute trade simulation (entry, stop loss, take profit checks)
5. Advance to next rebalance date
6. Compute final metrics

### 11.2 Metrics

| Metric | Formula |
|--------|---------|
| Sharpe Ratio | (mean_return - risk_free) / std_return * sqrt(252) |
| Sortino Ratio | (mean_return - risk_free) / downside_deviation * sqrt(252) |
| Max Drawdown | max peak-to-trough decline |
| Calmar Ratio | CAGR / abs(max_drawdown) |
| Win Rate | winning_trades / total_trades |
| Profit Factor | gross_profit / gross_loss |
| CAGR | (final_value/initial_value)^(1/years) - 1 |

### 11.3 CLI

```bash
python -m cli.backtest_cli run AAPL --start 2024-01-01 --end 2025-12-31 \
    --agents technical --rebalance weekly --capital 100000
```

### 11.4 Non-PIT Disclaimer

When FundamentalAgent is included in backtest, results automatically carry:
```
NOTE: Backtest used non-PIT fundamental data (yfinance). Results may be optimistic.
```

-----

## 12. Charts & Visualization

### 12.1 Chart Functions (Pure, Plotly)

All chart functions return `plotly.graph_objects.Figure`. Dark theme (`plotly_dark`). Export to HTML (opens in browser).

| Function | Package | Description |
|----------|---------|-------------|
| `create_price_chart(ohlcv, ticker, indicators)` | analysis_charts | Candlestick + SMA + BB + RSI subplot |
| `create_agent_breakdown_chart(agent_signals)` | analysis_charts | Horizontal bars (agent x confidence, color by signal) |
| `create_crypto_factor_chart(crypto_output)` | analysis_charts | 7 horizontal bars for CryptoAgent factor scores |
| `add_signal_markers(fig, signals, ohlcv, min_confidence)` | analysis_charts | BUY/SELL triangle markers on price chart |
| `create_allocation_chart(portfolio)` | portfolio_charts | Pie chart (position weights + cash) |
| `create_sector_chart(portfolio)` | portfolio_charts | Horizontal bar (sector exposure) |
| `create_calibration_chart(calibration_data)` | tracking_charts | Confidence bucket vs win rate + ideal diagonal |
| `create_drift_scatter(drift_data)` | tracking_charts | Expected vs actual return scatter + reference line |

### 12.2 Interactive Analysis HTML

The `analysis` subcommand generates a single-page interactive HTML application:

**Architecture:**
- Price chart + agent breakdown chart rendered on one page via `Plotly.newPlot()` from JSON
- Walk-forward TechnicalAgent signals computed at weekly intervals (PIT-safe, no API calls)
- BUY/SELL triangle markers overlaid on price chart
- Signal data embedded as `<script type="application/json">` for offline support
- plotly.js bundled offline via `plotly.offline.get_plotlyjs()`

**Interactive Features:**
- **Confidence Threshold Slider**: 0-100% range, dynamically filters signal markers via `Plotly.restyle()`
- **Click-to-Detail Panel**: 340px right-side panel populated on marker click with:
  - Date + signal badge (BUY/SELL) + confidence %
  - Sub-score bars (Trend, Momentum, Volatility) with visual bar chart
  - Composite score
  - Indicators table (RSI, MACD, Volume Ratio, Price, SMAs)
  - Full reasoning text
- **Crypto Support**: BTC/ETH auto-detected, 7-factor chart for CryptoAgent, ticker mapped to BTC-USD/ETH-USD

**Walk-Forward Signal Generation:**
- Uses TechnicalAgent only (applies to all asset types)
- `HistoricalDataProvider` slices OHLCV at each date (no lookahead)
- Default: weekly frequency, 2-year data with SMA200 warmup
- Configurable: `--signal-freq daily|weekly|monthly`, `--min-confidence`, `--no-signals`

### 12.3 CLI

```bash
python -m cli.charts_cli analysis AAPL [--min-confidence 70] [--signal-freq weekly] [--no-signals]
python -m cli.charts_cli analysis BTC     # auto-detects crypto, maps to BTC-USD
python -m cli.charts_cli portfolio
python -m cli.charts_cli calibration [--lookback 100]
python -m cli.charts_cli drift
```

-----

## 13. Dependencies

```toml
[project]
requires-python = ">=3.11"
dependencies = [
    "aiosqlite>=0.19",         # Async SQLite
    "yfinance>=0.2",           # Stock + crypto prices
    "ccxt>=4.0",               # Crypto exchange data (Phase 2)
    "fredapi>=0.5",            # FRED macro data
    "pandas>=2.0",             # Data manipulation
    "pandas-ta>=0.4.67b0",     # Technical indicators (pre-release pin)
    "httpx>=0.27",             # Async HTTP
    "plotly>=5.0",             # Chart generation
    "apscheduler>=3.10,<4.0",  # Daemon scheduler (3.x only, not 4.x alpha)
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]
```

Monthly cost: **$0** (all data sources free). LLM costs ($5-10/mo) start at Task 017.

-----

## 14. Runtime Notes

### 14.1 Windows Compatibility

- CLI entry points set `asyncio.WindowsSelectorEventLoopPolicy` for aiodns/aiohttp compatibility
- No em dashes in output (ASCII `--` only) -- Windows CMD encoding issues
- Daemon signal handlers: POSIX (SIGINT/SIGTERM) on Linux, KeyboardInterrupt on Windows

### 14.2 Thread Safety

- `_yfinance_lock` (threading.Lock) serializes all yfinance calls -- concurrent `asyncio.gather` calls corrupt yfinance's MultiIndex column headers
- yfinance `droplevel(1)` fix for modern multi-ticker response format

### 14.3 Graceful Degradation

- MacroAgent skipped (with warning) if FRED_API_KEY not set
- Pipeline continues with remaining agents
- Each position in weekly revaluation has individual try/except -- one failure doesn't block others
- Daemon jobs never raise -- all exceptions caught, logged, recorded as status="error"

-----

## 15. Phase Roadmap

### Completed

| Phase | Tasks | Delivered | Tests |
|-------|-------|-----------|-------|
| Phase 1 | 001-011 | DB, portfolio, 3 agents, pipeline, aggregator, drift, monitoring, signal tracking, CLI | 95 |
| Sprint 3 | 012-013 | Charts (plotly), backtesting (walk-forward) | +20 |
| Sprint 4 | 014, 014.5 | Monitoring daemon, analysis detail mode | +14 |
| Sprint 4.5 | 015.5 | FundamentalAgent enhancement (PEG, earnings growth, analyst rating) | +4 |
| Sprint 7 | 018, 019 | CryptoAgent (7-factor), sector rotation + correlation | +29 |
| Post-019 | Architect | Interactive chart system (signals, click-to-detail, slider), crypto support fixes | +0 (UI) |
| **Total** | **19 tasks** | **13 packages, 7 CLIs, 9 tables** | **162 passed, 1 skipped** |

### In Progress / Planned

| Sprint | Tasks | Focus | Status |
|--------|-------|-------|--------|
| Sprint 5 | 015 + 016 | FastAPI backend + Adaptive weight (EWMA) | PLANNED |
| Sprint 6 | 017 | LLM integration (Claude API): SentimentAgent + catalyst scanner | PLANNED |
| Sprint 8 | 020+ | React frontend | DEFERRED |

### Sprint 5: FastAPI + Adaptive Weights

**Task 015 (FastAPI Backend)**:
- REST API wrapping existing CLI functionality
- Endpoints: `/analyze/{ticker}`, `/portfolio`, `/alerts`, `/signals`, `/backtest`
- WebSocket for daemon status push
- Serves data to future React frontend
- No new business logic -- pure API layer over existing engine

**Task 016 (Regime-Aware Weight Adaptation)**:
- EWMA tracking of agent accuracy by regime
- `agent_performance` table stores rolling win_rate per agent/asset/regime
- SignalAggregator reads learned weights instead of DEFAULT_WEIGHTS
- Cold start: 10 signals minimum, uses defaults below threshold
- Enable via config flag (off by default until sufficient signal history)

### Sprint 6: LLM Integration

**Task 017 (Claude API)**:
- SentimentAgent: web search + Claude for news/catalyst evaluation
- Catalyst scanner: activate daemon's 4-hour catalyst scan job
- ValidationAgent: cross-check agent logic consistency
- Cost: ~$5-10/mo for typical usage (5 positions, daily scan)
- Uses Anthropic SDK, structured output for reliable parsing

### Sprint 8+: Frontend

**Task 020+ (React)**:
- React + TypeScript + TanStack Query
- Pages: /dashboard, /analyze/:ticker, /monitor, /performance, /backtest, /settings
- Charts: reuse plotly figures from charts/ package via API
- Tailwind CSS styling
- Optional Phase 4: Tauri wrapper for desktop app

-----

## 16. Known Tech Debt

| Item | Impact | Resolution |
|------|--------|------------|
| SHORT position drift sign inversion | drift_analyzer returns wrong sign for shorts | Phase 2 |
| Stock split price invalidation | Expected prices become invalid after splits | Phase 3 |
| Trading days vs calendar days ambiguity | hold_drift_days may be off by weekends | Documented, acceptable |
| Dividend exclusion from return drift | Return drift doesn't account for dividends | Phase 3 |
| pandas_ta Pandas 3.x deprecation warning | Cosmetic console noise | Non-fatal, upstream fix pending |
| FredProvider RuntimeWarning without API key | Warning on import when FRED_API_KEY not set | Non-fatal, by design |
| Single-agent aggregation edge case | Confidence can reach 90 from single signal | Acceptable behavior |
| Portfolio exposure uses cost_basis | Should use market_value when live prices wired | Phase 2 (live price refresh) |
| Expected/Actual data fragmented | Spread across 3 tables instead of unified trade_records | Phase 2 consolidation |

-----

## 17. v4 -> v5 Gap Summary

Features spec'd in v4 that are **deferred** (not cancelled):

| v4 Section | Feature | Deferred To | Rationale |
|-----------|---------|-------------|-----------|
| 4.4 | Portfolio-Aware Analysis (overlay, constraints) | Sprint 5 | Need live prices + FastAPI first |
| 6.4 | Catalyst Scanner (LLM news eval) | Sprint 6 (Task 017) | Requires Claude API integration |
| 6.6 | Alert Dispatcher (email, push) | Sprint 6+ | SQLite-only sufficient for Phase 1 |
| 8.1 | SentimentAgent | Sprint 6 (Task 017) | LLM-dependent |
| 8.1 | OnChainAgent | Phase 3 | Binance geo-restriction, lower priority |
| 9.2 | ValidationAgent | Sprint 6 (Task 017) | LLM-dependent |
| 10 | L1 Weight Adaptation | Sprint 5 (Task 016) | Need sufficient signal history |
| 10 | L2 Regime Switching | Sprint 5 (Task 016) | Paired with adaptive weights |
| 10 | L3 Reasoning Self-Optimize | Phase 4+ | Lowest priority, LLM-dependent |
| 12 | React Frontend | Sprint 7+ | Backend API required first |

Features **added** that were not in v4:

| Feature | Task | Description |
|---------|------|-------------|
| Backtesting framework | 013 | Walk-forward engine with no-lookahead guarantee |
| Price history cache | 013 | SQLite table for offline backtest replay |
| Chart generation | 012 | 6 plotly chart functions + CLI |
| Analysis detail mode | 014.5 | `--detail` flag for full agent metric breakdown |
| Daemon job toggle | Architect patch | `--no-daily` / `--no-weekly` CLI flags |
| Signal tracking & calibration | 011 | Accuracy stats, confidence calibration, agent performance |
| daemon_runs audit table | 014 | Full job execution history with duration + result |
| FundamentalAgent PEG/earnings/analyst | 015.5 | 3 new metrics + dividend yield scoring + equity weights rebalance |
| CryptoAgent 7-factor model | 018 | Market structure, momentum, volatility, liquidity, macro, network, cycle |
| Sector rotation matrix | 019 | 11-sector rotation scoring + portfolio modifier (applied post-aggregation) |
| Portfolio correlation tracker | 019 | Pairwise correlation analysis with rolling window |
| Interactive analysis charts | Architect | Walk-forward signals, click-to-detail panel, confidence slider, offline HTML |

-----

## 18. Architecture Decisions Log

| # | Decision | Rationale | Date |
|---|----------|-----------|------|
| 1 | Phase 1 agents are rule-based (no LLM) | Prove signal quality before spending API tokens | 2026-03-08 |
| 2 | pandas-ta pre-release pin (>=0.4.67b0) | No stable >=0.3 on PyPI, pragmatic choice | 2026-03-08 |
| 3 | Weighted aggregator (not LLM consensus) | Deterministic, testable, backtestable | 2026-03-08 |
| 4 | yfinance for crypto (not ccxt) | Binance API geo-restricted in US | 2026-03-08 |
| 5 | APScheduler 3.x (not 4.x) | 4.x is alpha rewrite, unstable | 2026-03-10 |
| 6 | Signal comparator is pure function | No I/O, fully testable, composable | 2026-03-10 |
| 7 | Daemon jobs never raise | Catch all, log error, record status="error" | 2026-03-10 |
| 8 | Detail mode via --detail flag | Data already in AgentOutput.metrics; display-only change | 2026-03-10 |
| 9 | Daemon toggles (--no-daily/--no-weekly) | User should control which jobs run | 2026-03-10 |
| 10 | Backtesting before LLM | Validate signal quality with rules first | 2026-03-10 |
| 11 | CryptoAgent as single agent (weight 1.0) for btc/eth | Crypto-native 7-factor model covers all aspects; stock agents not applicable | 2026-03-11 |
| 12 | Sector rotation modifier applied post-aggregation | Keeps agent scoring pure; sector context is portfolio-level concern | 2026-03-11 |
| 13 | Interactive HTML charts (not plotly pio.to_html) | Full lifecycle control for click handlers, dynamic trace updates, slider | 2026-03-11 |
| 14 | TechnicalAgent for walk-forward signals (all assets) | PIT-safe, no API calls, ~3-5s for 52 weekly dates; CryptoAgent too slow | 2026-03-11 |
| 15 | BTC/ETH ticker auto-detection + YF mapping | yf.Ticker("BTC") returns Grayscale ETF, not Bitcoin; must map to BTC-USD | 2026-03-11 |
