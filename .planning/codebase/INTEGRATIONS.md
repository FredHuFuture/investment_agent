# External Integrations

**Analysis Date:** 2026-04-21

## APIs & External Services

**Financial Data:**
- Yahoo Finance (yfinance) - Stock and crypto price history, OHLCV data, fundamental data
  - SDK/Client: `yfinance` 0.2+
  - Rate limit: 2 calls/second (configurable via `YFINANCE_RATE_LIMIT` env var)
  - Location: `data_providers/yfinance_provider.py` - Thread-locked downloads due to yfinance's non-thread-safe MultiIndex handling
  - Async rate limiter in `data_providers/rate_limiter.py`

- FRED API (Federal Reserve Economic Data) - Macroeconomic indicators
  - SDK/Client: `fredapi` 0.5+
  - Auth: `FRED_API_KEY` environment variable
  - Rate limit: 5 requests/second (configurable via `FRED_RATE_LIMIT`, FRED allows 120 req/min)
  - Location: `data_providers/fred_provider.py`
  - Optional: If not set, FredProvider falls back to mock data mode with warning

- CCXT (Cryptocurrency Exchange Trading Library) - Crypto exchange data and trading
  - SDK/Client: `ccxt` 4.0+ (async support)
  - Supported exchanges: Binance (default), and 150+ others via ccxt
  - Location: `data_providers/ccxt_provider.py`
  - Features: OHLCV data, ticker data, funding rates for crypto
  - Installation tier: Optional `[exchange]` in pyproject.toml

**News & Sentiment:**
- Web news provider (built-in) - Headlines and news sources
  - Location: `data_providers/web_news_provider.py`
  - Used by: Sentiment analysis agent via `agents/sentiment.py`

- Anthropic Claude API - LLM for sentiment analysis and portfolio summaries
  - SDK/Client: `anthropic` 0.42+ (AsyncAnthropic for async/await)
  - Auth: `ANTHROPIC_API_KEY` environment variable
  - Model: `claude-sonnet-4-20250514`
  - Use cases:
    - Sentiment analysis on news headlines (`api/routes/analyze.py` lines 55-96)
    - Weekly portfolio summary generation (`agents/summary_agent.py`)
    - Conditional: Only runs if ANTHROPIC_API_KEY is set
  - Installation tier: Optional `[llm]` in pyproject.toml
  - Response tracking: Counts input/output tokens and USD cost in `SummaryResponse` model

## Data Storage

**Databases:**
- SQLite (local file)
  - Path: `data/investment_agent.db`
  - Client: `aiosqlite` 0.19+ for async access
  - Connection pooling: `db/connection_pool.py` implements AsyncConnectionPool with queue-based pooling
  - Migrations: Idempotent schema evolution in `db/database.py`
    - Portfolio management table with default portfolio support
    - Partial unique index on ticker for open positions only (allows reopening closed positions)
  - Tables: `portfolios`, `active_positions`, `portfolio_meta`, `alerts`, `analysis_history`, etc.

**File Storage:**
- Local filesystem only - No cloud storage integration
  - Database file: `data/investment_agent.db`
  - Logs: `logs/investment_daemon.log` (rotating, 5MB max per file, 3 backups)
  - Charts: Generated as HTML files in export/

**Caching:**
- In-memory caching for data providers
  - Location: `data_providers/cache.py` and `data_providers/cached_provider.py`
  - Sector PE cache: `data_providers/sector_pe_cache.py`
  - No external caching service (Redis/Memcached)

## Authentication & Identity

**Auth Provider:**
- Custom - No third-party identity provider
- No authentication layer on FastAPI endpoints currently (open API)
- CORS policy: Allows requests from `http://localhost:3000` only
  - Location: `api/app.py` lines 42-48

## Monitoring & Observability

**Error Tracking:**
- None detected - No Sentry, DataDog, or similar service integrated

**Logs:**
- File-based logging via Python's `logging` module
  - Location: `daemon/scheduler.py` lines 33-60 - RotatingFileHandler setup
  - File: `logs/investment_daemon.log`
  - Format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
  - Rotation: 5 MB per file, 3 backup files
  - Level: Configurable via `DaemonConfig.log_level` (default: INFO)
  - Loggers: `investment_daemon` (main), agent loggers, provider loggers

**Metrics:**
- None detected - No Prometheus, StatsD, or metrics service

## CI/CD & Deployment

**Hosting:**
- Self-hosted only - No cloud platform detected (no AWS SDK, Azure SDK, GCP SDK imports)
- Run via:
  - Makefile targets (make run-backend, make run-frontend)
  - PowerShell script `run.ps1` (Windows)
  - Manual: uvicorn + npm commands

**CI Pipeline:**
- None detected in codebase - No GitHub Actions, GitLab CI, or other CI config files

**Deployment:**
- Development: `uvicorn api.app:app --port 8000 --reload` (with auto-reload)
- Production ready: Standard ASGI deployment via uvicorn

## Environment Configuration

**Required env vars:**
- `FRED_API_KEY` (optional) - FRED macro data provider authentication
- `ANTHROPIC_API_KEY` (optional) - Claude API for sentiment/summaries
- `TELEGRAM_BOT_TOKEN` (optional) - Telegram alert notifications
- `TELEGRAM_CHAT_ID` (optional) - Telegram destination chat
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` (optional) - Email alert configuration
- `ALERT_FROM_EMAIL`, `ALERT_TO_EMAILS` (optional) - Email alert sender/recipients
- `SMTP_USE_TLS` (optional) - TLS for SMTP (default: true)
- `YFINANCE_RATE_LIMIT` (optional) - Rate limit for yfinance (default: 2 calls/sec)
- `FRED_RATE_LIMIT` (optional) - Rate limit for FRED (default: 5 calls/sec)

**Secrets location:**
- `.env` file (local, not committed)
- Example: `.env.example` shows template

## Webhooks & Callbacks

**Incoming:**
- None detected - No webhook endpoints for external services

**Outgoing:**
- Telegram Bot API - Async POST requests via `aiohttp` to send alerts
  - Location: `notifications/telegram_dispatcher.py`
  - Endpoint: `https://api.telegram.org/bot{token}/sendMessage`
  - Trigger: Alert dispatch on portfolio events (drawdown, signal reversal, target hit, stop-loss)

- SMTP - Email alert dispatch
  - Location: `notifications/email_dispatcher.py`
  - Protocol: SMTP (configurable TLS)
  - Trigger: Alert dispatch on portfolio events (CRITICAL/HIGH severity only per design)
  - Threading: SMTP send runs in thread executor to avoid blocking async event loop

## Real-Time Monitoring

**Background Daemon:**
- APScheduler - Long-running scheduled tasks
  - Location: `daemon/scheduler.py`, `daemon/jobs.py`
  - Jobs:
    - Daily check (Mon-Fri, configurable hour, default 5 PM ET)
    - Weekly revaluation (configurable day/hour, default Saturday 10 AM ET)
    - Regime detection
    - Catalyst scan (stub, disabled)
  - Trigger: Manual via API endpoint `/daemon/run-once` or scheduled execution

## Market Data Flow

**Real-time updates:**
- Pull-based (not push) - Data fetched on-demand for analysis
- Providers: yfinance (stocks), FRED (macro), CCXT (crypto)
- Rate limiting: Async rate limiters on all providers to respect API quotas

---

*Integration audit: 2026-04-21*
