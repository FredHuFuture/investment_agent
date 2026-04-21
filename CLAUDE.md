<!-- GSD:project-start source:PROJECT.md -->
## Project

**Investment Agent**

An "investment journal that fights back" — a personal investing system that tracks the thesis behind every position, monitors six specialized analysis agents (Technical, Fundamental, Macro, Crypto, Sentiment, Summary) continuously, and alerts the user when reality diverges from the original plan. Built as a local-first Python/FastAPI backend with a React/TypeScript dashboard; solo-operator focus today, with intent to benchmark against the broader OSS investment-agent landscape.

**Core Value:** **Drawdown protection via thesis-aware, regime-aware multi-agent signals** — if one thing must work, it is catching when a held position no longer matches the reason it was bought.

### Constraints

- **Tech stack**: Python 3.11+ backend / React+TS frontend / SQLite — new features must fit this stack unless a strong case is made.
- **Deployment**: Local-first (single-user) for this milestone — don't design anything that assumes multi-tenant.
- **Safety**: No order execution / broker APIs this milestone (Out of Scope).
- **Test discipline**: 889-test bar is the floor; features ship with tests.
- **Data costs**: Free/community data providers only (YFinance, FRED, CCXT, scrapers) — no paid market-data subscriptions assumed.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11+ - Backend services, analysis engines, APIs, backtesting
- TypeScript 5.6.3 - Frontend React application and type-safe API client
- JavaScript (Node.js ecosystem) - Frontend tooling and runtime
## Runtime
- Python 3.11+ (as specified in `pyproject.toml`)
- Node.js (implied by npm usage in `frontend/package.json`)
- pip (Python) - Lockfile: `pyproject.toml` with pre-release support (`--pre` flag)
- npm (Node.js) - Lockfile: `frontend/package-lock.json`
## Frameworks
- FastAPI 0.115+ - REST API framework with async support
- React 18.3.1 - UI framework
- React Router DOM 6.28.0 - Client-side routing
- Vite 6.0.5 - Build tool and dev server (port 3000)
- uvicorn[standard] 0.30+ - ASGI server for FastAPI (port 8000)
- APScheduler 3.10 (< 4.0) - Background job scheduling for daemon
- pytest 8.0+ - Python test runner
- pytest-asyncio 0.23+ - Async test support
- vitest 2.1.8 - Frontend test runner (configured for jsdom, globals mode)
- @testing-library/react 16.1.0 - React component testing
- TypeScript 5.6.3 - Type checking and compilation
- Tailwind CSS 3.4.17 - Utility-first CSS framework
- PostCSS 8.4.49 - CSS transformations with autoprefixer
- @vitejs/plugin-react 4.3.4 - JSX support in Vite
- jsdom 25.0.1 - DOM implementation for tests
## Key Dependencies
- yfinance 0.2+ - Stock market data provider (primary source for price history)
- pandas 2.0+ - Data manipulation and analysis
- pandas-ta 0.4.25b0 - Technical analysis indicators
- fredapi 0.5+ - FRED API client for macroeconomic data
- ccxt 4.0+ - Unified crypto exchange API (optional, Exchange tier)
- httpx 0.27+ - Async HTTP client (likely for news/data fetching)
- plotly 5.0+ - Interactive charting and visualization
- aiosqlite 0.19+ - Async SQLite wrapper (primary database)
- anthropic 0.42+ - Claude API client for sentiment analysis and summaries (optional, LLM tier)
- aiohttp - Used by data providers (e.g., `telegram_dispatcher.py` line 9: `import aiohttp`)
- python-dotenv 1.0+ - Environment variable loading from `.env` files
- Pydantic v2 - Data validation (used in `api/models.py` for request/response models)
## Configuration
- Loaded via `python-dotenv` - reads `.env` file on startup
- Example: `.env.example` shows FRED_API_KEY and optional ANTHROPIC_API_KEY
- Frontend proxies `/api` requests to backend via Vite config (line 14-16 in `frontend/vite.config.ts`)
- `frontend/tsconfig.json` - TypeScript ES2020 target, JSX support, strict mode
- `frontend/tailwind.config.ts` - Custom color system (accent, gray, up, down, caution) with CSS variables
- `frontend/vite.config.ts` - Dev server on port 3000, test environment jsdom with globals
- `pyproject.toml` - Build system (hatchling), package metadata, dependencies by tier
- `pyproject.toml` markers: `network` marker for integration tests
- Tier structure: `[llm]`, `[exchange]`, `[dev]`, `[all]` for conditional installs
- SQLite (local file at `data/investment_agent.db` per `db/database.py`)
- Schema migrations inline in `db/database.py` (idempotent portfolio and ticker unique constraint migrations)
## Platform Requirements
- Python 3.11+ interpreter
- Node.js with npm for frontend
- Makefile support (macOS/Linux) or PowerShell `run.ps1` (Windows)
- Python 3.11+ runtime
- SQLite database file system access
- Network access for yfinance, FRED API, optional Anthropic API
- SMTP server access (optional, for email alerts)
- Telegram Bot API access (optional, for Telegram alerts)
- Local filesystem: `data/investment_agent.db` (SQLite)
- Log files: `logs/investment_daemon.log` (rotating file handler, 5MB max)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- React components: PascalCase (e.g., `ErrorAlert.tsx`, `Button.tsx`, `DataTable.tsx`)
- Utility modules: camelCase (e.g., `useApi.ts`, `formatters.ts`, `cache.ts`)
- Test files: mirror source with `.test.ts` or `.test.tsx` suffix
- Python modules: snake_case (e.g., `technical.py`, `base.py`, `models.py`)
- React components: Named PascalCase exports
- Utilities: Named camelCase exports (e.g., `formatCurrency`, `formatPct`, `apiGet`, `apiPost`)
- Async functions: camelCase with async/await pattern
- Private functions: Leading underscore for internal/helper functions (e.g., `_safe_last`, `_to_float`, `_validate_asset_type`)
- Python private methods: Single underscore prefix (e.g., `_validate_asset_type`, `_clamp_confidence`)
- camelCase for JavaScript/TypeScript locals and parameters
- UPPER_CASE for constants
- Numeric subscripts with underscores for separators (e.g., `1_000_000`, `30_000`)
- State variables: descriptive camelCase (e.g., `lastUpdated`, `stale`, `cacheKey`)
- Interfaces: PascalCase with Props suffix for component props (e.g., `ButtonProps`, `ErrorAlertProps`, `UseApiOptions`)
- Enums: PascalCase (e.g., `Signal`, `Regime`)
- Generic type parameters: Single letter or PascalCase (e.g., `<T>`, `<TestRow>`)
## Code Style
- TypeScript/React: Inferred from tsconfig (ES2020 target, strict mode)
- Indentation: 2 spaces (based on package.json and file structure)
- Line length: Inferred pragmatic from codebase, no hard limit detected
- No explicit `.eslintrc` found at project root or `frontend/` level
- TypeScript strict mode enforced: `"strict": true` in `tsconfig.json`
- Unused variable detection: `"noUnusedLocals": true`, `"noUnusedParameters": true`
- Strict array indexing: `"noUncheckedIndexedAccess": true`
- No fallthrough cases: `"noFallthroughCasesInSwitch": true`
- `from __future__ import annotations` at top of all modules for PEP 563 compatibility
- Type hints required for function parameters and returns
- Uses stdlib `logging` module for logging
- Async/await pattern throughout (not callback-based)
## Import Organization
- `@/*` maps to `src/` in `frontend/`
- No path aliases in Python code (uses relative imports from package root)
## Error Handling
- Custom `ApiError` class extends Error with status, code, detail fields (see `src/api/client.ts`)
- Error responses follow envelope pattern with `error` field containing `code`, `message`, `detail`
- Graceful degradation: cache stale data on error, display error message to user
- Validation before render (e.g., `result.current.error` checked in state)
- Explicit exception handling: `try/except` blocks with specific exception types
- Use `raise ValueError()`, `raise NotImplementedError()` with descriptive messages
- Warnings accumulated in list and returned with output (e.g., `output.warnings`)
- Data validation in `__post_init__` (dataclass validation, e.g., `confidence` must be 0-100)
- Graceful fallbacks: catch exceptions, log, continue (e.g., weekly data unavailable in TechnicalAgent)
## Logging
- Python: stdlib `logging` module
- TypeScript: No global logging library; uses browser console (inferred from codebase)
- Python agents log via `self._logger = logging.getLogger(f"investment_agent.{self.name}")`
- Use `logger.info()`, `logger.warning()` for key events
- Log before processing: "Analyzing %s" when analyzing a ticker
- Frontend: Error states and user feedback via state (not console logging)
## Comments
- JSDoc/TSDoc for public APIs and complex utility functions
- Inline comments for non-obvious algorithmic decisions
- Block comments for complex logic sections (e.g., cache stale-while-revalidate explanation)
- Used on public functions with parameters and return types documented
- Example from `useApi.ts`:
- Interface properties documented with inline comments explaining purpose
## Function Design
- Keep functions focused and small (most utilities 10-50 lines)
- Complex agents (technical, fundamental) may span 100+ lines but decompose logic into sections
- Prefer destructuring for multiple parameters or options
- Use options objects for function overloads (e.g., `UseApiOptions` with `cacheKey` and `ttlMs`)
- Type all parameters explicitly
- Explicit return type annotations on all functions
- Return wrapped envelopes (API responses): `{ data: T, warnings: string[] }`
- Python dataclasses for complex returns (e.g., `AgentOutput`)
- Nullable returns use `T | null` or `Optional[T]`
## Module Design
- Named exports preferred over default exports
- React components often use `export default` for single-component files
- Utility modules use named exports (e.g., `export function apiGet<T>(...)`)
- `__init__.py` in Python packages (e.g., `agents/__init__.py`)
- No explicit barrel exports detected in frontend (but could be added)
- Components in `frontend/src/components/` organized by domain (`shared/`, `ui/`, `pages/`)
- Utilities in `frontend/src/lib/` and `frontend/src/hooks/`
- Tests in `__tests__/` subdirectories at same level as source
- Python packages at root: `agents/`, `api/`, `db/`, `portfolio/`, etc.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Asynchronous Python backend (FastAPI) with parallel agent execution
- Multi-layered abstraction: data providers → agents → aggregator → API routes → frontend
- Scheduled background jobs (APScheduler) for monitoring and revaluation
- SQLite database with connection pooling
- React/TypeScript frontend with lazy-loaded pages and API client layer
- Separation between analysis engine (core logic) and API layer (HTTP exposure)
## Layers
- Purpose: Abstract data source access with pluggable implementations
- Location: `data_providers/`
- Contains: Base interface, provider implementations (YFinance, FRED, CCXT, News), caching, rate limiting
- Depends on: External APIs (Yahoo Finance, FRED, CCXT, web scrapers)
- Used by: Agents, API routes for ticker info
- Purpose: Domain-specific analysis implementations for different asset classes
- Location: `agents/`
- Contains: BaseAgent abstract class, specialized agents (Technical, Fundamental, Macro, Crypto, Sentiment)
- Depends on: DataProvider layer for price/financial data, agent models
- Used by: Pipeline for parallel analysis execution
- Purpose: Orchestrate data flow, aggregate signals, apply regime detection, compute analytics
- Location: `engine/`
- Contains: AnalysisPipeline, SignalAggregator, Regime detection, Analytics, Risk (Monte Carlo), Weight adaptation
- Depends on: Agent layer, DataProvider layer, Portfolio models
- Used by: API routes, Daemon jobs
- Purpose: Manage positions, portfolios, performance tracking, thesis drift
- Location: `portfolio/`, `tracking/`, `monitoring/`
- Contains: PortfolioManager (CRUD operations), SignalTracker (historical tracking), PortfolioMonitor (alerts)
- Depends on: Database, Engine layer for analytics
- Used by: API routes, Daemon jobs
- Purpose: Persistent storage with async SQLite connection pooling
- Location: `db/`
- Contains: Connection pool, schema initialization, migrations
- Depends on: aiosqlite
- Used by: Portfolio layer, API routes, Engine components
- Purpose: REST endpoints exposing analysis, portfolio, monitoring, and daemon capabilities
- Location: `api/`
- Contains: FastAPI app factory, route handlers, request/response models, middleware
- Depends on: Engine layer, Portfolio layer, Database layer
- Used by: Frontend, external clients
- Purpose: React-based UI for dashboard, analysis, portfolio management
- Location: `frontend/src/`
- Contains: Pages, components, API client layer, hooks, contexts
- Depends on: API endpoints
- Used by: End users
- Purpose: Long-running background scheduler for periodic jobs
- Location: `daemon/`
- Contains: APScheduler-based scheduler, job definitions, configuration
- Depends on: Engine layer, Portfolio layer
- Used by: System maintenance tasks
## Data Flow
- Database: SQLite with schema in `db/database.py` (portfolios, positions, signals, alerts, etc.)
- Session: API routes maintain request-level context via dependency injection
- Frontend: React Context for user auth, Toast notifications; component state for UI
- Cache: Data providers use in-memory LRU cache (`data_providers/cache.py`) with TTL
## Key Abstractions
- Purpose: Unified access to market data across multiple sources
- Examples: `data_providers/yfinance_provider.py`, `data_providers/fred_provider.py`, `data_providers/ccxt_provider.py`
- Pattern: Abstract base class with async methods for price history, current price, financials, key stats. Implementations fetch from different APIs. Cached provider wraps to avoid redundant calls.
- Purpose: Common interface for all analysis agents
- Examples: `agents/technical.py`, `agents/fundamental.py`, `agents/macro.py`, `agents/crypto.py`
- Pattern: Subclasses implement `async analyze(agent_input) → agent_output`. Each agent has a name, supported asset types, and returns AgentOutput with signal, confidence, reasoning.
- Purpose: Encapsulate final investment signal with full context
- Location: `engine/aggregator.py`
- Pattern: Contains ticker, asset_type, final_signal (BUY/HOLD/SELL), confidence, regime, list of raw agent outputs, reasoning, metrics, warnings. Used as return type for pipeline and serialized to JSON.
- Purpose: Weighted aggregation of agent signals with threshold-based buy/sell decisions
- Location: `engine/aggregator.py`
- Pattern: Stateless aggregator class. Takes agent outputs and optional adaptive weights. Computes weighted average signal value, applies dynamic thresholds, optional regime-based weight switching.
- Purpose: CRUD operations for positions, portfolios, and thesis tracking
- Location: `portfolio/manager.py`
- Pattern: Async class wrapping database operations. Methods for add_position, close_position, update_thesis, get_portfolio_stats, bulk_import. Maintains referential integrity with portfolios table.
- Purpose: Historical tracking of analysis signals for accuracy measurement and backtesting
- Location: `tracking/tracker.py`, `tracking/store.py`
- Pattern: Tracker computes accuracy metrics by comparing historical signals to actual price moves. Store persists signals and historical data to database.
## Entry Points
- Location: `api/app.py`
- Triggers: `uvicorn api.app:app` or FastAPI startup
- Responsibilities: Create FastAPI app, initialize database, register routes, configure CORS, attach exception handlers, start on configured port (default 8000)
- Location: `daemon/scheduler.py` → `MonitoringDaemon` class
- Triggers: `python -m daemon.scheduler` or scheduled via system task
- Responsibilities: Initialize APScheduler, register cron jobs, run async event loop, execute periodic analysis and monitoring tasks
- Location: `frontend/src/main.tsx`
- Triggers: Browser loads `index.html`, Vite development server or production build
- Responsibilities: Mount React app, initialize BrowserRouter, provide ToastContext and ToastProvider, render AppShell with Routes
- Location: `demo.py`
- Triggers: `python demo.py`
- Responsibilities: Create temporary database, demonstrate all major features (portfolio, analysis, backtesting, daemon, monitoring, tracking) without touching production data
## Error Handling
- Pipeline warnings: If optional agent fails (e.g., MacroAgent without FRED key, SentimentAgent without API key), it logs warning and continues with available agents. Warnings list is collected and returned in response.
- Provider failures: Try/except in pipeline when fetching ticker info. If provider fails, warning is logged but analysis continues.
- Validation errors: Request bodies validated by Pydantic; invalid data returns 400 with ErrorResponse envelope.
- Generic exceptions: Caught by FastAPI exception handlers; return 500 with ErrorResponse envelope.
- Database errors: Connection pool handles retries; if unrecoverable, error propagates with context.
- Async exceptions: asyncio.gather() with `return_exceptions=True` captures exceptions from parallel tasks; pipeline filters and logs individually.
## Cross-Cutting Concerns
- Framework: Python logging module with named loggers per module (e.g., `investment_agent.pipeline`, `investment_daemon`)
- Configuration: File + console handlers for daemon; console-only for API/frontend
- Levels: DEBUG for detailed tracing, INFO for key events, WARNING for recoverable issues, ERROR for failures
- Pydantic v2 for request/response models: `api/models.py`, `agents/models.py`, `portfolio/models.py`
- Custom validators in route handlers for cross-field validation (e.g., exit_price > 0)
- Data provider methods raise NotImplementedError for unsupported operations
- Currently: None (endpoints unauthenticated)
- Future: JWT tokens via dependency injection in `api/deps.py`
- Data providers: LRU cache with TTL for price history and financials
- Sector PE cache: Persistent cache for sector P/E ratios to avoid repeated fetches
- Rate limiting: Decorator pattern with sliding window bucket algorithm
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
