# Technology Stack

**Analysis Date:** 2026-04-21

## Languages

**Primary:**
- Python 3.11+ - Backend services, analysis engines, APIs, backtesting
- TypeScript 5.6.3 - Frontend React application and type-safe API client

**Secondary:**
- JavaScript (Node.js ecosystem) - Frontend tooling and runtime

## Runtime

**Environment:**
- Python 3.11+ (as specified in `pyproject.toml`)
- Node.js (implied by npm usage in `frontend/package.json`)

**Package Manager:**
- pip (Python) - Lockfile: `pyproject.toml` with pre-release support (`--pre` flag)
- npm (Node.js) - Lockfile: `frontend/package-lock.json`

## Frameworks

**Core Backend:**
- FastAPI 0.115+ - REST API framework with async support
  - Location: `api/app.py` - Application factory creating API with CORS, exception handlers, 14 routers
  - Used for: Portfolio management, analysis, backtesting, daemon control, alerts, export

**Core Frontend:**
- React 18.3.1 - UI framework
- React Router DOM 6.28.0 - Client-side routing
- Vite 6.0.5 - Build tool and dev server (port 3000)

**Async Runtime:**
- uvicorn[standard] 0.30+ - ASGI server for FastAPI (port 8000)
- APScheduler 3.10 (< 4.0) - Background job scheduling for daemon

**Testing:**
- pytest 8.0+ - Python test runner
- pytest-asyncio 0.23+ - Async test support
- vitest 2.1.8 - Frontend test runner (configured for jsdom, globals mode)
- @testing-library/react 16.1.0 - React component testing

**Build/Dev Tools:**
- TypeScript 5.6.3 - Type checking and compilation
- Tailwind CSS 3.4.17 - Utility-first CSS framework
- PostCSS 8.4.49 - CSS transformations with autoprefixer
- @vitejs/plugin-react 4.3.4 - JSX support in Vite
- jsdom 25.0.1 - DOM implementation for tests

## Key Dependencies

**Critical - Data & Analytics:**
- yfinance 0.2+ - Stock market data provider (primary source for price history)
- pandas 2.0+ - Data manipulation and analysis
- pandas-ta 0.4.25b0 - Technical analysis indicators
- fredapi 0.5+ - FRED API client for macroeconomic data
- ccxt 4.0+ - Unified crypto exchange API (optional, Exchange tier)
- httpx 0.27+ - Async HTTP client (likely for news/data fetching)
- plotly 5.0+ - Interactive charting and visualization

**Critical - Database:**
- aiosqlite 0.19+ - Async SQLite wrapper (primary database)

**Critical - LLM/AI:**
- anthropic 0.42+ - Claude API client for sentiment analysis and summaries (optional, LLM tier)

**Critical - Async/Async Web:**
- aiohttp - Used by data providers (e.g., `telegram_dispatcher.py` line 9: `import aiohttp`)

**Critical - Configuration:**
- python-dotenv 1.0+ - Environment variable loading from `.env` files

**Development:**
- Pydantic v2 - Data validation (used in `api/models.py` for request/response models)

## Configuration

**Environment:**
- Loaded via `python-dotenv` - reads `.env` file on startup
- Example: `.env.example` shows FRED_API_KEY and optional ANTHROPIC_API_KEY
- Frontend proxies `/api` requests to backend via Vite config (line 14-16 in `frontend/vite.config.ts`)

**Frontend Build:**
- `frontend/tsconfig.json` - TypeScript ES2020 target, JSX support, strict mode
- `frontend/tailwind.config.ts` - Custom color system (accent, gray, up, down, caution) with CSS variables
- `frontend/vite.config.ts` - Dev server on port 3000, test environment jsdom with globals

**Backend Configuration:**
- `pyproject.toml` - Build system (hatchling), package metadata, dependencies by tier
- `pyproject.toml` markers: `network` marker for integration tests
- Tier structure: `[llm]`, `[exchange]`, `[dev]`, `[all]` for conditional installs

**Database:**
- SQLite (local file at `data/investment_agent.db` per `db/database.py`)
- Schema migrations inline in `db/database.py` (idempotent portfolio and ticker unique constraint migrations)

## Platform Requirements

**Development:**
- Python 3.11+ interpreter
- Node.js with npm for frontend
- Makefile support (macOS/Linux) or PowerShell `run.ps1` (Windows)

**Production:**
- Python 3.11+ runtime
- SQLite database file system access
- Network access for yfinance, FRED API, optional Anthropic API
- SMTP server access (optional, for email alerts)
- Telegram Bot API access (optional, for Telegram alerts)

**Storage:**
- Local filesystem: `data/investment_agent.db` (SQLite)
- Log files: `logs/investment_daemon.log` (rotating file handler, 5MB max)

---

*Stack analysis: 2026-04-21*
