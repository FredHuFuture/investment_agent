# Architecture

**Analysis Date:** 2026-04-21

## Pattern Overview

**Overall:** Layered event-driven pipeline with async data flow from external providers through agent-based analysis to API endpoints and frontend UI.

**Key Characteristics:**
- Asynchronous Python backend (FastAPI) with parallel agent execution
- Multi-layered abstraction: data providers → agents → aggregator → API routes → frontend
- Scheduled background jobs (APScheduler) for monitoring and revaluation
- SQLite database with connection pooling
- React/TypeScript frontend with lazy-loaded pages and API client layer
- Separation between analysis engine (core logic) and API layer (HTTP exposure)

## Layers

**Data Provider Layer:**
- Purpose: Abstract data source access with pluggable implementations
- Location: `data_providers/`
- Contains: Base interface, provider implementations (YFinance, FRED, CCXT, News), caching, rate limiting
- Depends on: External APIs (Yahoo Finance, FRED, CCXT, web scrapers)
- Used by: Agents, API routes for ticker info

**Agent Layer:**
- Purpose: Domain-specific analysis implementations for different asset classes
- Location: `agents/`
- Contains: BaseAgent abstract class, specialized agents (Technical, Fundamental, Macro, Crypto, Sentiment)
- Depends on: DataProvider layer for price/financial data, agent models
- Used by: Pipeline for parallel analysis execution

**Engine Layer (Core Analysis):**
- Purpose: Orchestrate data flow, aggregate signals, apply regime detection, compute analytics
- Location: `engine/`
- Contains: AnalysisPipeline, SignalAggregator, Regime detection, Analytics, Risk (Monte Carlo), Weight adaptation
- Depends on: Agent layer, DataProvider layer, Portfolio models
- Used by: API routes, Daemon jobs

**Portfolio Layer:**
- Purpose: Manage positions, portfolios, performance tracking, thesis drift
- Location: `portfolio/`, `tracking/`, `monitoring/`
- Contains: PortfolioManager (CRUD operations), SignalTracker (historical tracking), PortfolioMonitor (alerts)
- Depends on: Database, Engine layer for analytics
- Used by: API routes, Daemon jobs

**Database Layer:**
- Purpose: Persistent storage with async SQLite connection pooling
- Location: `db/`
- Contains: Connection pool, schema initialization, migrations
- Depends on: aiosqlite
- Used by: Portfolio layer, API routes, Engine components

**API Layer:**
- Purpose: REST endpoints exposing analysis, portfolio, monitoring, and daemon capabilities
- Location: `api/`
- Contains: FastAPI app factory, route handlers, request/response models, middleware
- Depends on: Engine layer, Portfolio layer, Database layer
- Used by: Frontend, external clients

**Frontend Layer:**
- Purpose: React-based UI for dashboard, analysis, portfolio management
- Location: `frontend/src/`
- Contains: Pages, components, API client layer, hooks, contexts
- Depends on: API endpoints
- Used by: End users

**Daemon Layer:**
- Purpose: Long-running background scheduler for periodic jobs
- Location: `daemon/`
- Contains: APScheduler-based scheduler, job definitions, configuration
- Depends on: Engine layer, Portfolio layer
- Used by: System maintenance tasks

## Data Flow

**Analysis Request Flow:**

1. Frontend submits ticker and asset type via `/analyze/{ticker}` endpoint
2. API route handler (e.g., `api/routes/analyze.py`) resolves asset type
3. API initializes `AnalysisPipeline` from `engine/pipeline.py`
4. Pipeline:
   - Selects appropriate `DataProvider` based on asset_type via factory
   - Initializes agents (Technical, Fundamental, Macro, Crypto, Sentiment) with provider
   - Constructs `AgentInput` with ticker, asset_type, optional portfolio context
   - Runs agents in parallel via `asyncio.gather()`
   - Each agent calls `DataProvider.get_price_history()` and domain-specific data
5. Pipeline aggregates agent outputs via `SignalAggregator`:
   - Computes weighted signal: (∑ agent_signal × weight) / ∑ weights
   - Applies dynamic thresholds (buy_threshold, sell_threshold)
   - Optionally applies regime-based weight switching from MacroAgent
6. Pipeline applies portfolio overlay (if portfolio provided) and sector modifier
7. API returns `AggregatedSignal` as JSON via `APIResponse` envelope
8. Frontend renders signal, confidence, reasoning, agent details

**Portfolio Management Flow:**

1. Frontend sends `AddPositionRequest` to `/portfolio/positions`
2. API creates position in database via `PortfolioManager`
3. PortfolioManager stores in `active_positions` table with thesis fields
4. Daemon jobs periodically:
   - Run daily analysis on all portfolio tickers
   - Store signals in `signals` table for tracking
   - Update `thesis_drift` for hypothesis tracking
   - Compute performance metrics in `portfolio_performance`
5. API serves position data and performance from database
6. Frontend displays holdings, P&L, drift alerts

**Monitoring/Daemon Flow:**

1. `MonitoringDaemon` (daemon/scheduler.py) runs APScheduler
2. Configured cron jobs trigger:
   - `run_daily_check()` - analyzes watchlist/portfolio at configured time
   - `run_weekly_revaluation()` - updates regime and recomputes weights
   - `run_catalyst_scan()` - scans news for catalysts (stub)
3. Jobs call `AnalysisPipeline` and store results in database
4. `PortfolioMonitor` checks for alert conditions (thesis drift, price targets)
5. Alerts stored in `alerts` table; frontend polls or receives via API

**State Management:**
- Database: SQLite with schema in `db/database.py` (portfolios, positions, signals, alerts, etc.)
- Session: API routes maintain request-level context via dependency injection
- Frontend: React Context for user auth, Toast notifications; component state for UI
- Cache: Data providers use in-memory LRU cache (`data_providers/cache.py`) with TTL

## Key Abstractions

**DataProvider Interface:**
- Purpose: Unified access to market data across multiple sources
- Examples: `data_providers/yfinance_provider.py`, `data_providers/fred_provider.py`, `data_providers/ccxt_provider.py`
- Pattern: Abstract base class with async methods for price history, current price, financials, key stats. Implementations fetch from different APIs. Cached provider wraps to avoid redundant calls.

**BaseAgent Abstract Class:**
- Purpose: Common interface for all analysis agents
- Examples: `agents/technical.py`, `agents/fundamental.py`, `agents/macro.py`, `agents/crypto.py`
- Pattern: Subclasses implement `async analyze(agent_input) → agent_output`. Each agent has a name, supported asset types, and returns AgentOutput with signal, confidence, reasoning.

**AggregatedSignal Dataclass:**
- Purpose: Encapsulate final investment signal with full context
- Location: `engine/aggregator.py`
- Pattern: Contains ticker, asset_type, final_signal (BUY/HOLD/SELL), confidence, regime, list of raw agent outputs, reasoning, metrics, warnings. Used as return type for pipeline and serialized to JSON.

**SignalAggregator:**
- Purpose: Weighted aggregation of agent signals with threshold-based buy/sell decisions
- Location: `engine/aggregator.py`
- Pattern: Stateless aggregator class. Takes agent outputs and optional adaptive weights. Computes weighted average signal value, applies dynamic thresholds, optional regime-based weight switching.

**PortfolioManager:**
- Purpose: CRUD operations for positions, portfolios, and thesis tracking
- Location: `portfolio/manager.py`
- Pattern: Async class wrapping database operations. Methods for add_position, close_position, update_thesis, get_portfolio_stats, bulk_import. Maintains referential integrity with portfolios table.

**SignalTracker & Store:**
- Purpose: Historical tracking of analysis signals for accuracy measurement and backtesting
- Location: `tracking/tracker.py`, `tracking/store.py`
- Pattern: Tracker computes accuracy metrics by comparing historical signals to actual price moves. Store persists signals and historical data to database.

## Entry Points

**API Server:**
- Location: `api/app.py`
- Triggers: `uvicorn api.app:app` or FastAPI startup
- Responsibilities: Create FastAPI app, initialize database, register routes, configure CORS, attach exception handlers, start on configured port (default 8000)

**Daemon Process:**
- Location: `daemon/scheduler.py` → `MonitoringDaemon` class
- Triggers: `python -m daemon.scheduler` or scheduled via system task
- Responsibilities: Initialize APScheduler, register cron jobs, run async event loop, execute periodic analysis and monitoring tasks

**Frontend Entry:**
- Location: `frontend/src/main.tsx`
- Triggers: Browser loads `index.html`, Vite development server or production build
- Responsibilities: Mount React app, initialize BrowserRouter, provide ToastContext and ToastProvider, render AppShell with Routes

**Demo/Test Script:**
- Location: `demo.py`
- Triggers: `python demo.py`
- Responsibilities: Create temporary database, demonstrate all major features (portfolio, analysis, backtesting, daemon, monitoring, tracking) without touching production data

## Error Handling

**Strategy:** Graceful degradation with warning collection and exception envelopes

**Patterns:**
- Pipeline warnings: If optional agent fails (e.g., MacroAgent without FRED key, SentimentAgent without API key), it logs warning and continues with available agents. Warnings list is collected and returned in response.
- Provider failures: Try/except in pipeline when fetching ticker info. If provider fails, warning is logged but analysis continues.
- Validation errors: Request bodies validated by Pydantic; invalid data returns 400 with ErrorResponse envelope.
- Generic exceptions: Caught by FastAPI exception handlers; return 500 with ErrorResponse envelope.
- Database errors: Connection pool handles retries; if unrecoverable, error propagates with context.
- Async exceptions: asyncio.gather() with `return_exceptions=True` captures exceptions from parallel tasks; pipeline filters and logs individually.

## Cross-Cutting Concerns

**Logging:** 
- Framework: Python logging module with named loggers per module (e.g., `investment_agent.pipeline`, `investment_daemon`)
- Configuration: File + console handlers for daemon; console-only for API/frontend
- Levels: DEBUG for detailed tracing, INFO for key events, WARNING for recoverable issues, ERROR for failures

**Validation:**
- Pydantic v2 for request/response models: `api/models.py`, `agents/models.py`, `portfolio/models.py`
- Custom validators in route handlers for cross-field validation (e.g., exit_price > 0)
- Data provider methods raise NotImplementedError for unsupported operations

**Authentication:**
- Currently: None (endpoints unauthenticated)
- Future: JWT tokens via dependency injection in `api/deps.py`

**Caching:**
- Data providers: LRU cache with TTL for price history and financials
- Sector PE cache: Persistent cache for sector P/E ratios to avoid repeated fetches
- Rate limiting: Decorator pattern with sliding window bucket algorithm

---

*Architecture analysis: 2026-04-21*
