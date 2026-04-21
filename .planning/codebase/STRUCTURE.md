# Codebase Structure

**Analysis Date:** 2026-04-21

## Directory Layout

```
investment_agent/
├── agents/                    # Agent-based analysis implementations
│   ├── base.py               # BaseAgent abstract class
│   ├── technical.py          # Technical analysis agent (moving averages, RSI, MACD)
│   ├── fundamental.py        # Fundamental analysis agent (P/E, growth, valuation)
│   ├── macro.py              # Macroeconomic agent (interest rates, VIX, economic indicators)
│   ├── crypto.py             # Crypto-specific 7-factor model
│   ├── sentiment.py          # News sentiment analysis via Anthropic Claude
│   ├── summary_agent.py      # Portfolio summary generation
│   ├── models.py             # AgentInput, AgentOutput, Signal, Regime dataclasses
│   └── utils.py              # Agent helper functions
├── api/                       # FastAPI REST API
│   ├── app.py                # FastAPI app factory, middleware, exception handlers
│   ├── models.py             # Pydantic v2 request/response models
│   ├── deps.py               # Dependency injection (get_db_path, map_ticker, etc.)
│   └── routes/               # Endpoint implementations
│       ├── analyze.py        # POST /analyze/{ticker}, GET /analyze/{ticker}/catalysts
│       ├── portfolio.py      # Portfolio CRUD: add/update/close positions
│       ├── alerts.py         # Alert management and retrieval
│       ├── monitoring.py     # Alert condition tracking
│       ├── daemon.py         # Daemon status and job control
│       ├── backtest.py       # Backtesting request/status
│       ├── signals.py        # Signal history and tracking
│       ├── watchlist.py      # Watchlist management
│       ├── journal.py        # Trade journal entry management
│       ├── risk.py           # Risk metrics, Monte Carlo simulation
│       ├── regime.py         # Regime detection and regime-based analysis
│       ├── weights.py        # Agent weight configuration
│       ├── analytics.py      # Portfolio analytics and performance
│       ├── export.py         # Export portfolio reports
│       └── [others...]       # Additional routes
├── backtesting/               # Historical backtesting engine
│   ├── engine.py             # Backtester class for running simulations
│   ├── models.py             # BacktestConfig, results dataclasses
│   ├── batch_runner.py       # Multi-ticker/agent combo backtesting
│   ├── metrics.py            # Performance metrics (Sharpe, sortino, max drawdown)
│   └── data_slicer.py        # Time-slice data for point-in-time backtests
├── charts/                    # Visualization and charting
│   ├── analysis_charts.py    # Charts for agent signals and analysis
│   ├── portfolio_charts.py   # Portfolio performance and holdings charts
│   ├── backtest_comparison.py # Comparative backtest result charts
│   └── tracking_charts.py    # Signal accuracy tracking charts
├── cli/                       # Command-line interfaces
│   ├── analyze_cli.py        # CLI for analyzing tickers
│   ├── portfolio_cli.py      # CLI for portfolio management
│   ├── backtest_cli.py       # CLI for backtesting
│   ├── daemon_cli.py         # CLI for daemon control
│   ├── monitor_cli.py        # CLI for monitoring alerts
│   ├── signal_cli.py         # CLI for signal tracking
│   ├── charts_cli.py         # CLI for generating charts
│   └── report.py             # Report formatting utilities
├── config/                    # Configuration management
│   └── [config files]        # Environment-specific configs (if present)
├── daemon/                    # Background monitoring daemon
│   ├── scheduler.py          # MonitoringDaemon + APScheduler setup
│   ├── jobs.py               # Job implementations (daily check, weekly revaluation, catalysts)
│   ├── config.py             # DaemonConfig dataclass
│   ├── watchlist_job.py      # Watchlist scanning job
│   └── signal_comparator.py  # Signal comparison utilities
├── data/                      # Data directory
│   └── investment_agent.db   # SQLite database file (created on first run)
├── data_providers/            # Pluggable data source layer
│   ├── base.py               # DataProvider abstract interface
│   ├── yfinance_provider.py  # Yahoo Finance provider
│   ├── fred_provider.py      # FRED economic data provider
│   ├── ccxt_provider.py      # CCXT crypto exchange data
│   ├── news_provider.py      # Base news provider interface
│   ├── web_news_provider.py  # Web scraper-based news provider
│   ├── factory.py            # Provider factory for asset type selection
│   ├── cached_provider.py    # LRU cache wrapper around providers
│   ├── cache.py              # Cache implementation with TTL
│   ├── rate_limiter.py       # Sliding window rate limiter
│   └── sector_pe_cache.py    # Persistent sector P/E cache
├── db/                        # Database layer
│   ├── database.py           # Schema initialization, migrations, async init_db()
│   └── connection_pool.py    # Async SQLite connection pooling
├── docs/                      # Documentation
│   └── [markdown docs]       # Feature docs, API docs, etc.
├── engine/                    # Core analysis engine
│   ├── pipeline.py           # AnalysisPipeline: end-to-end orchestration
│   ├── aggregator.py         # SignalAggregator: weighted signal combination
│   ├── accuracy_tracker.py   # Agent accuracy metrics and learning
│   ├── analytics.py          # Portfolio analytics, Sharpe ratio, drawdowns
│   ├── regime.py             # Regime detection (bull/bear/sideways)
│   ├── regime_history.py     # Regime change tracking
│   ├── dynamic_threshold.py  # Threshold computation from market conditions
│   ├── correlation.py        # Cross-asset correlation analysis
│   ├── drift_analyzer.py     # Thesis drift analysis
│   ├── sector.py             # Sector modifier application
│   ├── weight_adapter.py     # Adaptive weight learning from signals
│   ├── portfolio_overlay.py  # Portfolio-context signal adjustment
│   ├── monte_carlo.py        # Monte Carlo risk simulation
│   ├── stress_test.py        # Stress testing scenarios
│   └── journal_analytics.py  # Trade journal analytics
├── export/                    # Export functionality
│   └── portfolio_report.py   # Export portfolio to PDF/HTML report
├── frontend/                  # React TypeScript frontend (Vite + Tailwind)
│   ├── src/
│   │   ├── main.tsx          # React entry point
│   │   ├── App.tsx           # Root component, Routes, ErrorBoundary
│   │   ├── index.css         # Tailwind styles
│   │   ├── api/              # API client layer
│   │   │   ├── client.ts     # Axios instance, base configuration
│   │   │   └── hooks.ts      # Custom hooks for API calls (useAnalyze, usePortfolio, etc.)
│   │   ├── components/       # Reusable React components
│   │   │   ├── layout/       # Page layout (AppShell, Sidebar, Header)
│   │   │   ├── dashboard/    # Dashboard widgets and cards
│   │   │   ├── analysis/     # Analysis-related components
│   │   │   ├── portfolio/    # Portfolio display components
│   │   │   ├── position/     # Position detail components
│   │   │   ├── monitoring/   # Alert and monitoring components
│   │   │   ├── journal/      # Trade journal components
│   │   │   ├── backtest/     # Backtesting result components
│   │   │   ├── risk/         # Risk analysis components
│   │   │   ├── watchlist/    # Watchlist components
│   │   │   ├── signals/      # Signal display components
│   │   │   ├── performance/  # Performance analytics components
│   │   │   ├── settings/     # Settings components
│   │   │   ├── daemon/       # Daemon control components
│   │   │   ├── shared/       # Shared utilities (Badge, Tooltip, etc.)
│   │   │   └── ui/           # Base UI components (Button, Input, Modal, etc.)
│   │   ├── pages/            # Route-based pages (lazy-loaded)
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── AnalyzePage.tsx
│   │   │   ├── PortfolioPage.tsx
│   │   │   ├── PositionDetailPage.tsx
│   │   │   ├── PerformancePage.tsx
│   │   │   ├── RiskPage.tsx
│   │   │   ├── WatchlistPage.tsx
│   │   │   ├── JournalPage.tsx
│   │   │   ├── BacktestPage.tsx
│   │   │   ├── SignalsPage.tsx
│   │   │   ├── MonitoringPage.tsx
│   │   │   ├── WeightsPage.tsx
│   │   │   ├── DaemonPage.tsx
│   │   │   ├── SettingsPage.tsx
│   │   │   └── AnalysisHistoryPage.tsx
│   │   ├── contexts/         # React context providers
│   │   │   └── ToastContext.tsx
│   │   ├── hooks/            # Custom React hooks
│   │   │   ├── useHotkeys.ts  # Keyboard shortcut management
│   │   │   ├── usePortfolio.ts
│   │   │   └── [others...]
│   │   ├── lib/              # Utility libraries
│   │   │   ├── api.ts        # API client wrapper
│   │   │   ├── format.ts     # Formatting utilities (currency, percentage, date)
│   │   │   └── [others...]
│   │   └── test/             # Test utilities
│   ├── public/               # Static assets
│   ├── index.html            # HTML template
│   ├── vite.config.ts        # Vite build config
│   ├── tsconfig.json         # TypeScript config
│   ├── tailwind.config.ts    # Tailwind CSS config
│   ├── postcss.config.js     # PostCSS config
│   ├── package.json          # Node dependencies (React, Tailwind, etc.)
│   └── dist/                 # Build output (generated)
├── landing/                   # Marketing landing page (separate Vite app)
│   ├── src/
│   │   ├── components/       # Landing page components
│   │   └── sections/         # Page sections (hero, features, etc.)
│   └── [vite config files]
├── monitoring/                # Portfolio monitoring and alerts
│   ├── monitor.py            # PortfolioMonitor class for alert detection
│   ├── checker.py            # Alert condition checker functions
│   ├── store.py              # Alert storage and retrieval
│   └── models.py             # Alert dataclasses
├── notifications/             # Notification system
│   └── [notification handlers]
├── portfolio/                 # Portfolio management
│   ├── manager.py            # PortfolioManager: CRUD, performance, thesis tracking
│   ├── models.py             # Portfolio, Position, Thesis dataclasses
│   └── profiles.py           # Portfolio profiles and presets
├── project/                   # Project planning/tracking
│   └── [project docs]
├── tasks/                     # Task definitions (if using task runner)
│   └── [task files]
├── tests/                     # Python unit tests
│   ├── test_agents.py        # Agent unit tests
│   ├── test_pipeline.py      # Pipeline integration tests
│   ├── test_portfolio.py     # Portfolio manager tests
│   └── [others...]
├── tracking/                  # Signal tracking and accuracy measurement
│   ├── tracker.py            # SignalTracker for accuracy computation
│   └── store.py              # Historical signal storage
├── watchlist/                 # Watchlist management
│   └── [watchlist handlers]
├── demo.py                    # Feature demonstration script
├── seed.py                    # Database seed script for sample data
├── run.ps1                    # PowerShell startup script (Windows)
├── Makefile                   # Make targets for common tasks
├── pyproject.toml            # Python package config, dependencies
├── .env.example              # Example environment variables
├── .gitignore                # Git ignore rules
├── CONTRIBUTING.md           # Contribution guidelines
├── LICENSE                   # License file
└── README.md                 # Project README
```

## Directory Purposes

**agents/:**
- Purpose: Pluggable domain-specific analysis agents
- Contains: Agent implementations for technical, fundamental, macro, crypto, sentiment analysis
- Key files: `base.py` (interface), `models.py` (signal/regime enums)

**api/:**
- Purpose: REST API layer exposing backend analysis and portfolio management
- Contains: FastAPI app, route handlers, request/response models, dependency injection
- Key files: `app.py` (app factory), `routes/` (endpoint implementations)

**backtesting/:**
- Purpose: Historical simulation and performance backtesting
- Contains: Backtester engine, metrics computation, data slicing for point-in-time accuracy
- Key files: `engine.py` (main backtester), `metrics.py` (performance metrics)

**charts/:**
- Purpose: Visualization generation for analysis and portfolio results
- Contains: Matplotlib/Plotly chart generation functions
- Key files: `analysis_charts.py`, `portfolio_charts.py`, `backtest_comparison.py`

**cli/:**
- Purpose: Command-line interfaces for all major features
- Contains: Argument parsers, command implementations, report formatters
- Key files: `report.py` (common formatting), individual CLI modules

**daemon/:**
- Purpose: Long-running background monitoring and periodic job execution
- Contains: APScheduler-based scheduler, job definitions, configuration
- Key files: `scheduler.py` (main daemon), `jobs.py` (scheduled tasks)

**data/:**
- Purpose: Runtime data storage directory
- Contains: SQLite database file (created on first run)
- Key files: `investment_agent.db` (database)

**data_providers/:**
- Purpose: Abstraction layer for market data access
- Contains: Provider implementations (Yahoo Finance, FRED, CCXT, news), caching, rate limiting
- Key files: `base.py` (interface), `factory.py` (provider selection)

**db/:**
- Purpose: Database initialization, schema management, connection pooling
- Contains: Async SQLite utilities, migrations, connection pool
- Key files: `database.py` (schema + init), `connection_pool.py` (pooling)

**engine/:**
- Purpose: Core analysis orchestration and signal aggregation
- Contains: Pipeline, aggregator, regime detection, analytics, risk models
- Key files: `pipeline.py` (main orchestrator), `aggregator.py` (signal combination)

**export/:**
- Purpose: Report generation and export
- Contains: PDF/HTML report generators
- Key files: `portfolio_report.py` (portfolio export)

**frontend/:**
- Purpose: React web application for user interaction
- Contains: Pages, components, API client, styling, state management
- Key files: `src/main.tsx` (entry), `src/App.tsx` (routing), `src/pages/` (lazy-loaded pages)

**landing/:**
- Purpose: Marketing/informational landing page
- Contains: Separate Vite React app for landing
- Key files: `src/components/`, `src/sections/`

**monitoring/:**
- Purpose: Portfolio alert generation and tracking
- Contains: Alert detection, storage, retrieval
- Key files: `monitor.py` (alert generator), `store.py` (persistence)

**portfolio/:**
- Purpose: Portfolio and position management
- Contains: PortfolioManager CRUD, performance analytics, thesis tracking
- Key files: `manager.py` (main manager class), `models.py` (data structures)

**tests/:**
- Purpose: Python unit and integration tests
- Contains: Test modules for agents, pipeline, portfolio, database
- Key files: Individual test modules (test_*.py)

**tracking/:**
- Purpose: Historical signal tracking and accuracy measurement
- Contains: Signal tracker, historical storage
- Key files: `tracker.py` (accuracy computation), `store.py` (database persistence)

## Key File Locations

**Entry Points:**
- Backend API: `api/app.py` - FastAPI app factory
- Daemon: `daemon/scheduler.py` - MonitoringDaemon class
- Frontend: `frontend/src/main.tsx` - React entry point
- Demo: `demo.py` - Feature demonstration

**Configuration:**
- Python package: `pyproject.toml` - Dependencies, metadata
- Frontend build: `frontend/vite.config.ts` - Vite + TypeScript config
- Environment: `.env.example` - Required environment variables

**Core Logic:**
- Analysis pipeline: `engine/pipeline.py` - Orchestrates data → agents → aggregation
- Signal aggregation: `engine/aggregator.py` - Weighted signal combination
- Portfolio management: `portfolio/manager.py` - CRUD and analytics
- Database schema: `db/database.py` - Schema definition and migrations

**Testing:**
- Python tests: `tests/test_*.py` - Unit/integration tests
- Frontend tests: `frontend/src/**/__tests__/` - Component/hook tests

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `yfinance_provider.py`, `signal_aggregator.py`)
- React components: `PascalCase.tsx` (e.g., `DashboardPage.tsx`, `AnalysisCard.tsx`)
- Type/interface files: `.ts` for utilities, hooks; `.tsx` for components

**Directories:**
- Feature-oriented: `agents/`, `api/`, `portfolio/` (by domain)
- Utility: `data_providers/`, `engine/`, `db/` (shared infrastructure)
- UI: `frontend/src/pages/`, `frontend/src/components/` (by structure)

**Functions & Classes:**
- Python: `snake_case()` for functions, `PascalCase` for classes
- TypeScript: `camelCase()` for functions, `PascalCase` for classes, `UPPER_CASE` for constants

**Database Tables:**
- Snake_case: `active_positions`, `portfolio_performance`, `agent_performance`, `signals`, `alerts`

## Where to Add New Code

**New Analysis Agent:**
- Implementation: Create `agents/new_agent.py` implementing `BaseAgent` with `analyze()` method
- Models: Add signal types to `agents/models.py` if needed
- Pipeline integration: Add instantiation in `engine/pipeline.py` conditional on asset_type
- Tests: Add test module `tests/test_new_agent.py`

**New API Route:**
- Route handler: Create `api/routes/new_feature.py` with FastAPI router
- Models: Add request/response Pydantic models to `api/models.py`
- Integration: Import and `app.include_router()` in `api/app.py`
- Documentation: Add endpoint docstring with example request/response

**New Frontend Page:**
- Page component: Create `frontend/src/pages/NewPage.tsx` implementing page layout
- Sub-components: Add supporting components in `frontend/src/components/new_feature/`
- API client: Add fetch functions to `frontend/src/api/hooks.ts` or create new hooks file
- Routing: Add Route entry in `frontend/src/App.tsx` with lazy loading via `lazy()`
- Navigation: Add menu item to `frontend/src/components/layout/Sidebar.tsx` if needed

**New Portfolio Feature:**
- Database schema: Add table/columns in `db/database.py` migration function
- Manager method: Add CRUD method to `portfolio/manager.py` or create new manager class
- API endpoint: Create route in `api/routes/portfolio.py` exposing manager functionality
- Frontend: Add form/display components and API integration

**Utilities (Shared Helpers):**
- Python helpers: `engine/` (analysis), `data_providers/` (data access), or new module if domain-specific
- TypeScript helpers: `frontend/src/lib/` for general utilities, `frontend/src/hooks/` for React hooks

**Tests:**
- Python tests: Mirror structure in `tests/test_<module>.py`
- Frontend tests: Colocate in `frontend/src/<feature>/__tests__/` next to code

## Special Directories

**frontend/dist/:**
- Purpose: Build output for production frontend
- Generated: Yes (built via `npm run build`)
- Committed: No (in .gitignore)

**data/:**
- Purpose: Runtime data directory (database, logs, exports)
- Generated: Yes (created on first run)
- Committed: No (in .gitignore)

**.planning/:**
- Purpose: GSD planning and documentation
- Contains: Codebase analysis documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Committed: Yes

**.pytest_cache/, .vite/, __pycache__/:**
- Purpose: Build and test caches
- Generated: Yes (created during development)
- Committed: No (in .gitignore)

---

*Structure analysis: 2026-04-21*
