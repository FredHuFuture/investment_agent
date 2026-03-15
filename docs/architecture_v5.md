# Investment Analysis Agent -- Architecture v5

## 0. v4 -> v5 Changes

| Dimension | v4 (Design Spec) | v5 (Reflects Actual + Forward Plan) |
|-----------|-------------------|-------------------------------------|
| Document purpose | Forward-looking design spec | **Living architecture doc: actual state + roadmap** |
| Phase 1 status | Planned | **COMPLETE (Tasks 001-011, 95 tests)** |
| Sprint 3 status | Planned | **COMPLETE (Tasks 012-013, charts + backtesting)** |
| Sprint 4 status | Planned | **COMPLETE (Task 014 daemon + 014.5 detail mode)** |
| Sprint 4.5 status | N/A | **COMPLETE (Task 015.5 FundamentalAgent enhancement + Tasks 018-019 CryptoAgent + Sector/Correlation)** |
| Sprint 5 status | Planned | **COMPLETE (Tasks 020-021, adaptive weights + batch backtesting)** |
| Sprint 6 status | Planned | **COMPLETE (Task 022, FastAPI REST API -- 22 endpoints)** |
| Sprint 7 status | Planned | **COMPLETE (Tasks 023-026, React frontend + thesis tracking + SummaryAgent)** |
| Agent design | 5 agents (incl LLM-based) | **5 agents: 4 rule-based + 1 LLM-based (SummaryAgent)** |
| Data schema | 8 tables (speculative) | **9 tables (actual, tested, in production)** |
| Learning system | L1/L2/L3 planned | **L1 COMPLETE: EWMA weight adaptation + Sharpe-based optimizer** |
| Report format | Simple summary | **Standard + Detail mode (--detail flag)** |
| API layer | Not planned | **COMPLETE: FastAPI + 8 route modules + Pydantic v2** |
| Frontend | Not planned | **COMPLETE: React 18 + TypeScript + Tailwind + Recharts, 7 pages** |

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
|                      React Frontend (Vite + TypeScript)                |
|  14 pages  |  60+ components  |  25+ UI primitives (design system)   |
|  Tailwind + Recharts  |  SWR cache  |  Command palette (Ctrl+K)      |
+---------------------------+-------------------------------------------+
                            | /api proxy (localhost:3000 -> :8000)
+---------------------------v-------------------------------------------+
|                      FastAPI REST API Layer                            |
|  55 endpoints across 12 route modules  |  Pydantic v2 validation     |
|  CORS  |  Error handlers  |  Lifespan DB init                        |
+--------+----------+-----------+-----------+-----------+---------------+
         |          |           |           |           |
+--------+----------+-----------+-----------+-----------+---------------+
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
    | Agents: Technical, Fundamental, Macro, Crypto, Sentiment,  |
    |         Summary (6 agents)                                  |
    | RegimeDetector | SignalAggregator | DriftAnalyzer            |
    | WeightAdapter | SectorRotation | CorrelationTracker         |
    +--------+--------------------------------------------------+
             |
    +--------v--------------------------------------------------+
    |                   Data Layer                               |
    | DataProviders (YFinance, CCXT, FRED, Google News)         |
    | SQLite (WAL mode, 10 tables, aiosqlite)                   |
    | Notifications (SMTP, Telegram) | Export (CSV, JSON)        |
    +-----------------------------------------------------------+
```

Tech stack:

- **Runtime**: Python 3.11+ / asyncio
- **Data**: yfinance + ccxt + FRED + Google News RSS + pandas_ta ($0/mo)
- **Store**: SQLite (WAL mode, aiosqlite, single-file, zero-ops)
- **Charts**: plotly (dark theme, HTML export) + Recharts (frontend)
- **Scheduler**: APScheduler 3.x (cron-based async daemon)
- **API**: FastAPI + uvicorn + Pydantic v2 (55 endpoints)
- **Frontend**: React 18 + Vite + TypeScript + Tailwind CSS + Recharts
- **Frontend perf**: In-memory SWR cache (stale-while-revalidate), TTL-based invalidation, route-based code splitting (React.lazy), component-level lazy loading (PriceHistoryChart, 86% chunk reduction), 60s auto-refresh with lastUpdated indicator, SPY benchmark comparison
- **Notifications**: SMTP email + Telegram Bot API (aiohttp)
- **LLM**: Claude API via Anthropic SDK (SentimentAgent, SummaryAgent, optional)

-----

## 3. Package Structure (Actual)

```
investment_agent/
  agents/                      # Analysis agents (6)
    __init__.py                #   exports: BaseAgent, AgentInput, AgentOutput, Signal, Regime
    base.py                    #   BaseAgent ABC
    models.py                  #   AgentInput, AgentOutput, Signal, Regime dataclasses
    technical.py               #   TechnicalAgent (rule-based, 17 metrics)
    fundamental.py             #   FundamentalAgent (rule-based, 20 metrics)
    macro.py                   #   MacroAgent (rule-based, 11 metrics)
    crypto.py                  #   CryptoAgent (7-factor, crypto-native scoring)
    sentiment.py               #   SentimentAgent (Claude API, news analysis)
    summary_agent.py           #   SummaryAgent (Claude API, weekly portfolio review)

  api/                         # FastAPI REST API (55 endpoints)
    app.py                     #   App factory, CORS, lifespan, error handlers
    models.py                  #   Pydantic v2 request/response schemas
    deps.py                    #   Shared dependencies (crypto detection, ticker mapping)
    routes/
      portfolio.py             #   /portfolio, /portfolio/positions, /portfolio/cash, etc.
      analyze.py               #   /analyze/{ticker}, /analyze/{ticker}/price-history
      alerts.py                #   /alerts, /alerts/test-email, /alerts/test-telegram
      signals.py               #   /signals/history, /signals/accuracy, /signals/agents, /signals/calibration
      backtest.py              #   /backtest, /backtest/batch
      daemon.py                #   /daemon/status, /daemon/run-once
      weights.py               #   /weights
      summary.py               #   /summary/generate, /summary/latest
      watchlist.py             #   /watchlist CRUD, /watchlist/analyze-all
      analytics.py             #   /analytics/value-history, /analytics/performance, /analytics/risk, /analytics/correlations, /analytics/cumulative-pnl, /analytics/position-pnl/{ticker}, etc.
      profiles.py              #   /portfolios CRUD, /portfolios/default
      export.py                #   /export/portfolio, /export/trades, /export/report, etc.
      regime.py                #   /regime/current

  backtesting/                 # Walk-forward backtesting engine
    __init__.py
    models.py                  #   BacktestConfig, SimulatedTrade, BacktestResult, BacktestMetrics
    data_slicer.py             #   HistoricalDataProvider (no lookahead bias)
    engine.py                  #   Backtester.run_backtest()
    metrics.py                 #   Sharpe, Sortino, max drawdown, Calmar, win rate, profit factor
    batch_runner.py            #   BatchRunner (multi-ticker x multi-agent sweep with caching)

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
    news_provider.py           #   Google News RSS headlines
    factory.py                 #   get_provider(asset_type) factory

  db/
    database.py                #   init_db(), 10 tables, WAL mode, indexes, migrations

  engine/                      # Core analysis engine
    __init__.py
    aggregator.py              #   SignalAggregator, AggregatedSignal, aggregate_with_regime()
    pipeline.py                #   AnalysisPipeline (parallel agent execution + regime integration)
    regime.py                  #   RegimeDetector (5 market regimes, weight adjustments)
    analytics.py               #   PortfolioAnalytics (value history, performance, monthly returns, risk metrics, cumulative P&L, position P&L)
    drift_analyzer.py          #   DriftAnalyzer (entry/return/hold drift)
    weight_adapter.py          #   WeightAdapter (EWMA + Sharpe-based adaptive weights)
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
    manager.py                 #   PortfolioManager (CRUD + snapshots + splits)
    profiles.py                #   PortfolioProfileManager (multi-portfolio CRUD)

  watchlist/                   # Ticker watchlist
    __init__.py
    manager.py                 #   WatchlistManager (CRUD + analysis integration)

  notifications/               # Alert dispatchers
    __init__.py
    email_dispatcher.py        #   SMTP email with HTML templates
    telegram_dispatcher.py     #   Telegram Bot API with severity formatting

  export/                      # Portfolio report export
    portfolio_report.py        #   PortfolioExporter (CSV + JSON streaming)

  tracking/                    # Signal tracking & calibration
    __init__.py
    store.py                   #   SignalStore (persist + query signals)
    tracker.py                 #   SignalTracker (accuracy, calibration, agent perf)

  tests/                       # 465+ tests, 1 skipped (network)
    test_001 - test_044        #   44 test files covering all packages + API routes

  frontend/                    # React frontend (Vite + TypeScript)
    src/
      pages/                   #   14 pages: Dashboard, Analyze, Portfolio, Journal,
                               #   PositionDetail, Performance, Risk,
                               #   Watchlist, Backtest, Signals, Monitoring,
                               #   Weights, Daemon, Settings
      components/
        ui/                    #   Design system: Button, Input, Card, Skeleton,
                               #   ErrorBoundary, Toast, ConfirmModal, CommandPalette (20+ primitives)
        shared/                #   DataTable (w/ pagination + search), Breadcrumb,
                               #   MetricCard, SignalBadge, etc.
        layout/                #   AppShell (responsive), Sidebar (mobile drawer)
        analysis/              #   AnalysisResult, AgentBreakdown, CatalystPanel, etc.
        portfolio/             #   PositionsTable, AddPositionForm, AllocationChart, etc.
        backtest/              #   BacktestForm, EquityCurveChart, BatchResults
        monitoring/            #   AlertsList, MonitorCheckButton
        signals/               #   AccuracyStats, CalibrationChart, AgentPerformance
        summary/               #   WeeklySummaryCard
      api/                     #   client.ts, endpoints.ts (40+ functions), types.ts
      hooks/                   #   useApi (SWR cache), useMobile, useHotkeys, usePageTitle
      lib/                     #   cache.ts (TTL), colors.ts, formatters.ts
      contexts/                #   ToastContext (global notifications)
      test/                    #   setup.ts (jest-dom matchers)
    vitest (305 tests)         #   formatters, cache, colors, client, 4 hooks, 8 UI + 12 shared + 14 page tests
    vite.config.ts             #   Port 3000, /api proxy -> localhost:8000

  docs/
    architecture_v5.md         #   This document
    ROADMAP.md                 #   Product roadmap + sprint history
    AGENT_SYNC.md              #   Dev agent communication log
    USAGE_GUIDE.md             #   User-facing usage instructions
  tasks/                       #   Task specs (001-026)
  data/                        #   SQLite DB + daemon logs (gitignored)
  demo.py                      #   7-step feature demo script (temp DB)
  seed.py                      #   Seed script for demo data
  run.ps1                      #   PowerShell launcher (Windows)
  pyproject.toml               #   Project config
```

-----

## 4. Data Layer

### 4.1 SQLite Schema (10 Tables)

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

-- 9. Watchlist (Sprint 13)
CREATE TABLE watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,
    asset_type TEXT NOT NULL DEFAULT 'stock',
    notes TEXT DEFAULT '',
    target_buy_price REAL,
    alert_below_price REAL,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_analysis_at TEXT,
    last_signal TEXT,
    last_confidence REAL
);

-- 10. Portfolio profiles (Sprint 13)
CREATE TABLE portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    cash REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_default INTEGER NOT NULL DEFAULT 0
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

| SummaryAgent | All | Portfolio-level: per-position thesis review, divergence detection, hold duration check | Claude API natural language evaluation, cost-tracked |

**Planned agents (future):**
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
    "fredapi>=0.5",            # FRED macro data
    "pandas>=2.0",             # Data manipulation
    "pandas-ta>=0.4.25b0",     # Technical indicators (pre-release pin)
    "httpx>=0.27",             # Async HTTP
    "plotly>=5.0",             # Chart generation
    "apscheduler>=3.10,<4.0",  # Daemon scheduler (3.x only, not 4.x alpha)
    "fastapi>=0.115",          # REST API framework
    "uvicorn[standard]>=0.30", # ASGI server
    "python-dotenv>=1.0",      # .env file loading
]

[project.optional-dependencies]
llm = ["anthropic>=0.42"]     # Claude API for SummaryAgent
exchange = ["ccxt>=4.0"]      # Crypto exchange data (Phase 2)
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]
```

Monthly cost: **$0** (core). SummaryAgent LLM costs ~$5-10/mo if enabled (Claude API, optional dependency).

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
| Sprint 4.5 | 015.5, 018-019 | FundamentalAgent enhancement, CryptoAgent (7-factor), sector rotation + correlation | +33 |
| Post-019 | Architect | Interactive chart system, crypto support fixes, 6-ticker backtest validation | +0 (UI/data) |
| Sprint 5 | 020-021 | Adaptive weight optimizer (EWMA + Sharpe-based), batch backtest runner | +16 |
| Sprint 6 | 022 | FastAPI REST API (22 endpoints, 8 route modules, Pydantic v2) | +10 |
| Sprint 7 | 023-026 | React frontend (7 pages, 36 components), thesis tracking, SummaryAgent | +28 |
| Sprint 8 | 027 | Close position lifecycle, realized P&L, signal auto-resolution, position history | +12 |
| Sprint 9 | 028-032 | Dashboard home page, analyze-to-add flow, thesis editing, alert management, position detail page | +11 |
| Sprint 10 | 033-037 | SentimentAgent (Claude API), WebNewsProvider, aggregator integration, catalyst scanner, news feed UI | +30 |
| Sprint 11 | 038-041 | Concentration check, correlation analysis, position sizing, portfolio impact preview UI | +18 |
| Sprint 12 | 042-045 | Email alerts (SMTP), Telegram bot, CSV/JSON export (5 endpoints), Settings page | +28 |
| Sprint 13 | 046-049 | Watchlist, performance analytics, tech debt fixes, multi-portfolio support | +49 |
| Sprint 14 | 050-053 | Regime detection engine, L2 weight switching, batch watchlist, dashboard enhancements | +52 |
| Sprint 15 | UI primitives (design system: Button, Input, Card, Skeleton, Toast), SWR cache | +0 (infra) |
| Sprint 16 | Design system 100% adoption, toast wiring, Trade Journal page, ToastContainer mount | +0 (UX) |
| Sprint 17 | Risk Dashboard (Sharpe/Sortino/VaR/drawdown/correlations), code splitting, ConfirmModal | +0 (risk/perf) |
| Sprint 18 | ErrorAlert retry pattern (8 pages), Journal DataTable, Signals filtering, auto-refresh | +0 (UX) |
| Sprint 19 | Dashboard auto-refresh, SPY benchmark comparison (API+chart), monthly returns toggle | +1 (benchmark) |
| Sprint 20 | Thesis editing (ThesisEditForm), RegimeBadge, watchlist inline editing, vitest + testing-library (62 FE tests), risk+regime API tests | +77 (15 BE + 62 FE) |
| Sprint 21 | 113 new FE tests (useApi, client, colors, 6 UI + 7 shared components), utility consolidation (pnlColor/holdColor/formatRelativeTime), mobile padding | +113 FE |
| Sprint 22 | Alert acknowledge/delete actions, dashboard position links, dead code cleanup, ARIA accessibility, 16 BE API tests (export/watchlist/thesis/summary) | +19 (16 BE + 3 FE) |
| Sprint 23 | Keyboard a11y (focus-visible, Escape, skip-to-content), design consistency (Button/Skeleton/onRetry), lazy-load PriceHistoryChart (86% chunk reduction), 12 page integration tests | +14 FE |
| Sprint 24 | 14/14 pages tested, all 53 API endpoints tested, all shared/UI components tested. Profile/signal/daemon API tests (18 BE), 8 page tests + 5 component tests (80 FE) | +98 (18 BE + 80 FE) |
| Sprint 25 | Final 3 page tests (Analyze, PositionDetail, Risk), all 4 hooks tested, AnalyzePage UX (quick tickers, copy button, signal bar), RiskPage UX (risk banner, badge, formatting) | +33 FE |
| Sprint 26 | Sector allocation horizontal stacked bar, thesis drift summary panel, cumulative realized P&L chart, position P&L performance bar, trade return distribution histogram, equity curve, profit factor/expectancy/streak metrics | +2 FE |
| Sprint 27 | Watchlist signal filter + inline analysis panel + comparison table, monitoring alert timeline + severity filter + summary chips + batch acknowledge + inline alert table, backtest localStorage history + save/compare/delete runs, signals accuracy trend chart + agent agreement matrix + signal timeline, 4 new backend routes + 2 new store methods + 2 new tracker methods | +2 FE |
| **Total** | **55+ tasks** | **130+ source files, 9 CLIs, 57 API endpoints, 14 UI pages, 10 tables** | **772 passed (465 BE + 307 FE), 1 skipped** |

### Planned

| Sprint | Focus | Priority | Status |
|--------|-------|----------|--------|
| Sprint 9 | **Dashboard + Workflow** -- home dashboard, analyze-to-buy flow, thesis editing, alert management | P0 (usability) | **COMPLETE** |
| Sprint 10 | **SentimentAgent** -- Claude-powered news/catalyst eval + daemon catalyst scanner | P1 (differentiation) | **COMPLETE** |
| Sprint 11 | Portfolio-aware analysis (concentration limits, correlation checks, position sizing) | P2 (optimization) | **COMPLETE** |
| Sprint 12 | **Notifications + Integrations** -- Email/Telegram alerts, CSV/JSON export, Settings page | P3 (expansion) | **COMPLETE** |
| Sprint 13 | **Watchlist + Analytics + Tech Debt + Multi-Portfolio** | P2 (workflow) | **COMPLETE** |
| Sprint 14 | **Advanced Intelligence** -- Regime detection, L2 weight switching, batch analysis, dashboard | P2 (intelligence) | **COMPLETE** |
| Sprint 16 | Design system adoption (100%), toast notifications, Trade Journal page | P0 (UX consistency) | COMPLETE |
| Sprint 17 | Risk Dashboard, code splitting, confirmation modals, portfolio correlations API | P1 (risk + perf) | COMPLETE |
| Sprint 18 | ErrorAlert retry, Journal DataTable, Signals filtering, portfolio auto-refresh | P0 (UX resilience) | COMPLETE |
| Sprint 19 | Dashboard auto-refresh, SPY benchmark comparison, monthly returns toggle | P1 (benchmarking) | COMPLETE |
| Sprint 20 | Thesis editing, regime badge, watchlist inline editing, test infrastructure (vitest) | P0 (UX + quality) | COMPLETE |
| Sprint 21 | Frontend test suite expansion (175 tests), utility consolidation, mobile polish | P0 (quality) | COMPLETE |
| Sprint 22 | Alert actions, dashboard links, dead code cleanup, ARIA accessibility, API test coverage | P0 (polish) | COMPLETE |
| Sprint 23 | Keyboard a11y, design system consistency, lazy-load performance, page integration tests | P0 (a11y + perf) | COMPLETE |
| Sprint 24 | Comprehensive test coverage: 14/14 pages, all API routes, all shared components | P0 (quality) | COMPLETE |
| Sprint 25 | Complete coverage (14/14 pages, 4/4 hooks), AnalyzePage + RiskPage UX improvements | P0 (quality + UX) | COMPLETE |
| Sprint 26 | Advanced analytics charts, sector allocation bar, thesis drift panel, cumulative P&L, position P&L bar | P1 (analytics UX) | COMPLETE |
| Sprint 27 | Watchlist comparison + signal filter, monitoring timeline + batch ack, backtest history, signals accuracy trend + agent agreement | P1 (workflow UX) | COMPLETE |
| Sprint 28+ | OnChainAgent, ValidationAgent, desktop app (Tauri) | P3+ (deferred) | PLANNED |

-----

## 20. Product Roadmap Detail

### Sprint 8: Investment Lifecycle Loop (P0)

**Problem:** Users can open positions but cannot close them properly. "Remove" deletes the position without recording exit price, realized P&L, or outcome. This breaks the thesis accountability feedback loop -- the product's core differentiator.

**Deliverables:**

1. **Close Position API + UI**
   - New `POST /portfolio/positions/{ticker}/close` endpoint
   - Records: exit_price, exit_date, exit_reason (manual | target_hit | stop_loss | signal_reversal)
   - Computes realized P&L and stores in trade_executions
   - Position moves to "closed" state (not deleted)
   - Frontend: "Close Position" modal with exit price + reason

2. **Position Outcome Resolution**
   - Closed positions automatically resolve linked signals (WIN/LOSS based on return)
   - Signal outcome feeds into adaptive weight system
   - Creates the feedback loop: signal -> trade -> outcome -> weight adjustment

3. **Realized P&L Tracking**
   - New `closed_positions` view or status column on active_positions
   - Portfolio page shows: unrealized P&L (open) + realized P&L (closed) + total
   - Historical performance: win rate, avg return, avg hold time

4. **Position History Page**
   - List of all closed positions with entry/exit details
   - Per-position thesis vs reality comparison
   - Filter by time period, asset type, outcome

### Sprint 9: Dashboard + Workflow (P0)

**Problem:** No daily entry point. Root route is Analysis page, not portfolio overview. Analyze-to-buy flow is disconnected across pages.

**Deliverables:**

1. **Dashboard Home Page (new root route `/`)**
   - Portfolio value + daily change
   - Open positions with P&L heat map
   - Recent alerts (top 5, severity-colored)
   - Quick actions: Analyze, Add Position, Run Check
   - Weekly summary card (if SummaryAgent configured)

2. **Analyze -> Add Position Flow**
   - "Add to Portfolio" button on Analysis results
   - Pre-fills ticker, asset_type, current price as entry price
   - Pre-fills thesis from analysis reasoning + signal
   - One-click flow: Analyze -> Review -> Add

3. **Thesis Editing**
   - Edit thesis after position entry (target price, stop loss, hold days, notes)
   - Thesis version history (what changed and when)

4. **Alert Management**
   - Dismiss/acknowledge alerts
   - Filter by severity, ticker, type
   - Alert configuration (custom thresholds per position)

### Sprint 10: SentimentAgent (P1)

**Problem:** All agents are backward-looking (price history, financials, macro data). No forward-looking catalyst detection.

**Deliverables:**

1. **SentimentAgent**
   - Claude API: analyze recent news headlines for a ticker
   - Scoring: catalyst strength, sentiment direction, relevance to thesis
   - Integrates into aggregator as optional 4th agent for stocks

2. **Catalyst Scanner Daemon Job**
   - Activate the existing 4-hour catalyst_scan stub in daemon
   - Scans all portfolio positions for news events
   - Generates CATALYST_ALERT when significant news detected

3. **News Feed in Frontend**
   - Analysis page shows recent catalysts alongside agent signals
   - Portfolio page shows per-position news alerts

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

Features spec'd in v4 that are **still deferred** (not cancelled):

| v4 Section | Feature | Deferred To | Rationale |
|-----------|---------|-------------|-----------|
| 4.4 | Portfolio-Aware Analysis (overlay, constraints) | Sprint 9 | Core analysis works; this is optimization |
| 6.4 | Catalyst Scanner (LLM news eval) | Sprint 8 | Claude API available; SentimentAgent next |
| 6.6 | Alert Dispatcher (email, push) | Sprint 10+ | SQLite-only sufficient for now |
| 8.1 | SentimentAgent | Sprint 8 | Next LLM integration priority |
| 8.1 | OnChainAgent | Phase 3 | Binance geo-restriction, lower priority |
| 9.2 | ValidationAgent | Sprint 8+ | LLM-dependent |
| 10 | L2 Regime Switching | Sprint 9 | L1 done; L2 needs more signal history |
| 10 | L3 Reasoning Self-Optimize | Phase 4+ | Lowest priority, LLM-dependent |

Features spec'd in v4 that have been **delivered**:

| v4 Section | Feature | Delivered In |
|-----------|---------|-------------|
| 10 | L1 Weight Adaptation | Sprint 5 (Task 020-021) -- EWMA + Sharpe-based optimizer |
| 12 | React Frontend | Sprint 7 (Task 023-026) -- 7 pages, 36 components |
| N/A | FastAPI Backend | Sprint 6 (Task 022) -- 22 endpoints, Pydantic v2 |

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
| Backtest comparison charts | Architect | 4-panel comparison, return-vs-risk scatter, equity curves, interactive HTML |
| Backtest validation (6 tickers) | Architect | AAPL/MSFT/TSLA/NVDA/SPY/BTC 2020-2025, EN/CN reports |
| Adaptive weight optimizer | 020 | EWMA accuracy smoothing + Sharpe-based weight computation + threshold grid search |
| Batch backtest runner | 021 | Multi-ticker x multi-agent sweep with shared price cache + error isolation |
| FastAPI REST API | 022 | 22 endpoints, 8 route modules, Pydantic v2, CORS, error handling |
| React frontend | 023-024 | 7 pages, 36 components, Vite + TypeScript + Tailwind + Recharts |
| Thesis tracking | 025 | Expected vs actual ROI dual-track with position-level thesis |
| SummaryAgent | 026 | Claude-powered weekly portfolio review with thesis divergence detection |
| Demo script | Architect | 7-step feature demo (demo.py) with temp DB |

-----

## 18. Backtest Validation Results (2020-2025)

### 18.1 Configuration

- **Agent**: TechnicalAgent only (PIT-safe)
- **Period**: 2020-01-01 to 2025-12-31 (6 years, largely bull market)
- **Config**: Full position (100%), no SL/TP, weekly rebalance
- **Capital**: $100,000

### 18.2 Summary

| Ticker | Signal Return | B&H Return | Signal MaxDD | B&H MaxDD | DD Improvement | Sharpe | Win Rate |
|--------|-------------|-----------|-------------|-----------|----------------|--------|----------|
| AAPL | +123.6% | +263.7% | -33.2% | -33.4% | +0.2pp | 1.50 | 62.5% |
| MSFT | +52.9% | +203.5% | -32.0% | -37.6% | +5.6pp | 0.95 | 28.6% |
| TSLA | +591.6% | +1484.3% | -69.9% | -73.6% | +3.7pp | 1.87 | 33.3% |
| NVDA | +2381.6% | +3026.8% | -57.5% | -66.4% | +8.9pp | 3.36 | 75.0% |
| SPY | +74.3% | +111.5% | -18.7% | -34.1% | +15.4pp | 1.66 | 66.7% |
| BTC | +1043.2% | +1128.2% | -40.7% | -76.6% | +35.9pp | 2.36 | 75.0% |

### 18.3 Key Findings

1. **Drawdown protection works**: All 6 tickers show reduced max drawdown vs buy-and-hold
2. **BTC is best use case**: 92% of B&H return with half the drawdown (Sharpe 2.36)
3. **SPY risk management**: MaxDD from -34.1% to -18.7% (+15.4pp improvement)
4. **Total returns lag B&H in bull market**: Expected -- system holds cash during HOLD periods
5. **Value proposition = risk management**, not return maximization

### 18.4 Bugs Found & Fixed

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| BTC backtest 0 trades | Aggregator weight 0 for TechnicalAgent on crypto | Backtest engine auto-assigns equal weights |
| Annualized return inflated | Equity curve entry count treated as trading days | Use actual calendar dates for year calculation |

### 18.5 Artifacts

- `data/backtest_report.html` -- Interactive HTML with 3 plotly charts
- `data/backtest_results_2020_2025.md` -- English report with trade logs
- `data/backtest_report_cn.md` -- Chinese report with analysis
- `charts/backtest_comparison.py` -- Chart generator module

-----

## 19. Architecture Decisions Log

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
| 16 | Backtest aggregator weight override | Production aggregator gives TechnicalAgent 0 weight for crypto; backtest needs equal-weight fallback | 2026-03-11 |
| 17 | Annualized return from calendar dates | Using equity curve entry count as days is wrong for non-daily rebalance; use actual date span | 2026-03-11 |
| 18 | Backtest value = drawdown protection | System doesn't beat B&H on returns in bull market; value is risk management | 2026-03-11 |
