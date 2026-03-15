# Investment Analysis Agent -- Product & Technical Roadmap

**Last updated:** 2026-03-14
**Current state:** Sprint 15 complete (416 tests, 120+ source files, 50 API endpoints, 12 pages, 6 agents, 20+ UI components)

---

## Executive Summary

The Investment Analysis Agent is a self-hosted, multi-agent portfolio analysis and monitoring system. Core analysis, backtesting, monitoring, and lifecycle tracking are complete. The next phase focuses on **workflow integration** (making the tool a daily driver) and **intelligence expansion** (adding forward-looking analysis).

---

## Completed Sprints

| Sprint | Focus | Key Deliverables | Tests |
|--------|-------|------------------|-------|
| Phase 1 | Foundation | DB, portfolio, 3 agents, pipeline, aggregator, drift, monitoring, signals, CLI | 95 |
| Sprint 3 | Visualization | Plotly charts, interactive HTML, walk-forward signals | +20 |
| Sprint 4 | Automation | Monitoring daemon (daily/weekly), detail mode | +14 |
| Sprint 4.5 | Agent Enhancement | FundamentalAgent upgrade, CryptoAgent 7-factor, sector rotation | +33 |
| Sprint 5 | Learning | EWMA weight adapter, Sharpe optimizer, batch backtesting | +16 |
| Sprint 6 | API | FastAPI REST API (22 endpoints), Pydantic v2 | +10 |
| Sprint 7 | Frontend | React 18 + TypeScript + Tailwind (7 pages, 36 components), SummaryAgent | +28 |
| Sprint 8 | Lifecycle | Close position, realized P&L, signal auto-resolution, position history | +12 |
| **Sprint 9** | **Dashboard + Workflow** | **Dashboard home, analyze-to-add flow, thesis editing, alert management, position detail page** | **+11** |
| **Sprint 10** | **SentimentAgent + Catalyst Scanner** | **SentimentAgent (Claude API), WebNewsProvider (Google RSS), aggregator integration, catalyst scanner daemon, news feed UI** | **+30** |
| **Sprint 11** | **Portfolio-Aware Analysis** | **Concentration check, correlation analysis, position sizing, portfolio impact preview UI** | **+18** |
| **Sprint 12** | **Notifications + Integrations** | **Email alerts (SMTP), Telegram bot, CSV/JSON export (5 endpoints), Settings page** | **+28** |
| **Sprint 13** | **Watchlist + Analytics + Multi-Portfolio** | **Watchlist CRUD, performance analytics, portfolio profiles, tech debt fixes** | **+49** |
| **Sprint 14** | **Advanced Intelligence** | **Regime detection (5 types), L2 weight switching, batch watchlist, dashboard charts** | **+52** |
| **Sprint 15** | **UI/UX Overhaul** | **Design system (8 components), responsive sidebar, enhanced DataTable, command palette, breadcrumbs** | **+0 (frontend)** |

**Total: 416 tests, 0 failures**

---

## Active Roadmap

### Sprint 9: Dashboard + Workflow (P0 -- Usability) -- COMPLETE

**Goal:** Make the tool a daily driver with a proper home page and streamlined workflows.

| Task | Description | Scope | Status |
|------|-------------|-------|--------|
| 9.1 Dashboard Home Page | New `/` route: portfolio value + daily P&L, position heat map, recent alerts, quick actions, weekly summary | Frontend | DONE |
| 9.2 Analyze -> Add Flow | "Add to Portfolio" button on analysis results, pre-fills ticker/price/thesis from analysis | Frontend + API | DONE |
| 9.3 Thesis Editing | Edit thesis fields after position entry (target, stop loss, hold days, notes) | Backend + Frontend | DONE |
| 9.4 Alert Management | Acknowledge/dismiss alerts, filter by severity/ticker, bulk actions | Backend + Frontend | DONE |
| 9.5 Position Detail Page | Dedicated page per position: thesis vs reality, price chart, linked signals, alert history | Frontend | DONE |

**Delivered:**
- `PUT /portfolio/positions/{ticker}/thesis` endpoint
- `PATCH /alerts/{id}/acknowledge` + `DELETE /alerts/{id}` endpoints
- Dashboard page component with metric aggregation
- Route restructure: `/` -> Dashboard, `/portfolio` -> Portfolio
- Analyze -> Add flow with query param pre-fill
- +8 new tests (3 thesis, 5 alert management)

---

### Sprint 10: SentimentAgent + Catalyst Scanner (P1 -- Differentiation)

**Goal:** Add forward-looking intelligence. All current agents analyze historical data; SentimentAgent evaluates current news and catalysts.

| Task | Description | Scope |
|------|-------------|-------|
| 10.1 SentimentAgent | Claude API: analyze news headlines, score catalyst strength/sentiment/relevance | New agent | DONE |
| 10.2 News Data Source | Google News RSS + DuckDuckGo fallback for recent headlines | Data provider | DONE |
| 10.3 Aggregator Integration | Add SentimentAgent as optional 4th agent for stocks (weight 0.15) | Engine | DONE |
| 10.4 Catalyst Scanner | Real daemon: scan portfolio positions for news, create CATALYST alerts | Daemon | DONE |
| 10.5 News Feed UI | CatalystPanel on analysis page and position detail page | Frontend | DONE |

**Technical work:**
- New `agents/sentiment.py` with Claude API integration
- New `data_providers/news_provider.py` (Brave Search or Google News)
- Update `SignalAggregator.DEFAULT_WEIGHTS` for stocks to include SentimentAgent
- Activate `run_catalyst_scan()` in daemon/jobs.py (currently stub)
- New `CATALYST_ALERT` alert type

---

### Sprint 11: Portfolio-Aware Analysis (P2 -- Optimization)

**Goal:** Make analysis context-aware. Currently agents analyze tickers in isolation; they should consider existing portfolio composition.

| Task | Description | Scope |
|------|-------------|-------|
| 11.1 Concentration Check | Warn if new position would exceed 40% sector concentration | Engine | DONE |
| 11.2 Correlation Analysis | Warn if new position rho > 0.8 with existing holdings | Engine | DONE |
| 11.3 Position Sizing | Suggest position size based on portfolio constraints and risk | Engine + API | DONE |
| 11.4 Impact Preview | Show before/after exposure impact in analysis report | Frontend | DONE |

**Technical work:**
- Pass `Portfolio` object to `AgentInput` (currently `None`)
- Add portfolio overlay to `AggregatedSignal` output
- Extend analysis report with portfolio impact section

---

### Sprint 12: Notifications + Integrations (P3 -- Expansion) -- COMPLETE

| Task | Description | Status |
|------|-------------|--------|
| 12.1 Email Alerts | SMTP email dispatcher with HTML templates, test endpoint | DONE |
| 12.2 Telegram Bot | Telegram Bot API dispatcher with HTML formatting, test endpoint | DONE |
| 12.3 Export System | CSV/JSON export (portfolio, trades, signals, alerts, full report) -- 5 streaming endpoints | DONE |
| 12.4 Settings Page | Notification test UI, export download links, configuration guide | DONE |

**Delivered:**
- `notifications/email_dispatcher.py` -- SMTP with dark-theme HTML templates, async via thread executor
- `notifications/telegram_dispatcher.py` -- Telegram Bot API with severity emojis, aiohttp
- `export/portfolio_report.py` -- 5 async export methods (CSV + JSON)
- `api/routes/export.py` -- 5 GET endpoints with StreamingResponse
- `POST /alerts/test-email` + `POST /alerts/test-telegram` test endpoints
- Daemon integration: auto-dispatch alerts to email + Telegram after daily checks
- Settings page with notification testing and export downloads
- +28 tests (8 email, 9 telegram, 8 export, 3 frontend type-check)

---

### Sprint 13: Watchlist + Performance Analytics + Tech Debt + Multi-Portfolio -- COMPLETE

| Task | Description | Status |
|------|-------------|--------|
| 13.1 Watchlist | DB table, CRUD API (5 endpoints), WatchlistPage with add/analyze/remove, sidebar nav | DONE |
| 13.2 Performance Analytics | Portfolio value history, win/loss stats, monthly returns, top performers, PerformancePage | DONE |
| 13.3 Tech Debt | SHORT position drift sign inversion fix, stock split thesis price adjustment | DONE |
| 13.4 Multi-Portfolio | Portfolio profiles (CRUD + default switching), DB migration, 6 API endpoints | DONE |

**Delivered:**
- `watchlist/manager.py` -- WatchlistManager with CRUD + analysis integration
- `engine/analytics.py` -- PortfolioAnalytics (value history, performance summary, monthly returns, top performers)
- `portfolio/profiles.py` -- PortfolioProfileManager for multiple portfolio profiles
- `api/routes/watchlist.py` -- 5 watchlist endpoints
- `api/routes/analytics.py` -- 4 analytics endpoints
- `api/routes/profiles.py` -- 6 portfolio profile endpoints
- WatchlistPage + PerformancePage (2 new frontend pages)
- SHORT drift inversion fix in monitoring/checker.py
- Stock split thesis price adjustment in portfolio/manager.py
- +49 tests (12 watchlist, 10 analytics, 6 tech debt, 10 multi-portfolio, 11 frontend)

---

### Sprint 14: Advanced Intelligence -- COMPLETE

| Task | Description | Status |
|------|-------------|--------|
| 14.1 Regime Detection Engine | Multi-signal regime detector (bull/bear/sideways/high-vol/risk-off) with macro + price analysis | DONE |
| 14.2 L2 Adaptive Weight Switching | Regime-aware weight adjustments, re-normalization, pipeline integration | DONE |
| 14.3 Batch Watchlist Analysis | Analyze-all endpoint, batch results, dashboard watchlist widget | DONE |
| 14.4 Dashboard Enhancements | Portfolio value mini-chart, watchlist highlights on dashboard | DONE |

**Delivered:**
- `engine/regime.py` -- RegimeDetector with 5 regime types, multi-signal scoring, weight adjustments
- `api/routes/regime.py` -- GET /regime/current endpoint
- L2 weight switching in aggregator + pipeline integration
- POST /watchlist/analyze-all batch endpoint
- Dashboard: portfolio value sparkline, watchlist highlights widget
- +52 tests (24 regime, 10 L2 weights, 7 batch watchlist, 11 dashboard)

---

### Sprint 15: UI/UX Design & Usability Overhaul -- COMPLETE

| Task | Description | Status |
|------|-------------|--------|
| 15.1 Design System + Toast | Button, Input, Card, Skeleton, ErrorBoundary, Toast notification components | DONE |
| 15.2 Responsive Layout | Mobile sidebar (hamburger + overlay drawer), responsive charts, useMobile hook | DONE |
| 15.3 Table Enhancement | DataTable with pagination, search/filter, sort indicators, mobile column hiding | DONE |
| 15.4 Navigation + Interaction | Command palette (Ctrl+K), Breadcrumb, usePageTitle, useHotkeys, favicon | DONE |

**Delivered:**
- 8 new UI components in `components/ui/` (Button, Input, Card, Skeleton, ErrorBoundary, Toast, CommandPalette, index barrel)
- ToastProvider + useToast context (success/error/info/warning with auto-dismiss)
- Mobile-responsive sidebar with hamburger menu, backdrop overlay, auto-close on navigation
- Enhanced DataTable: pagination (10/25/50 rows), debounced search, tri-state sort, mobile column hiding
- Pagination + TableSearch shared components
- Command palette (Ctrl+K / Cmd+K) with fuzzy search across 11 pages + 3 actions
- Breadcrumb navigation on PositionDetailPage
- usePageTitle hook on all 12 pages (dynamic document.title)
- useHotkeys hook for keyboard shortcuts
- useMobile hook for responsive breakpoint detection
- SVG favicon (trending-up chart icon)
- Toast animation CSS keyframes
- Fix: SQLite autoindex migration (table rebuild for UNIQUE constraint removal)
- PowerShell `run.ps1` launcher for Windows
- README updated (416 tests, 50 endpoints, 6 agents, Windows/Mac/Linux start instructions)

---

### Sprint 16+: Advanced (Deferred)

| Feature | Priority | Rationale |
|---------|----------|-----------|
| OnChainAgent | P3 | BTC-specific on-chain metrics (MVRV, SOPR, exchange flows) |
| ValidationAgent | P3 | LLM cross-checks agent logic consistency |
| Desktop App (Tauri) | P3 | Native wrapper for offline use |
| FMP Data Upgrade | P3 | Point-in-time fundamentals ($20-50/mo) |
| L3 Reasoning Self-Optimize | P4 | LLM analyzes its own signal quality and adjusts |

---

## Technical Debt Backlog

| Item | Impact | Target Sprint |
|------|--------|---------------|
| ~~Portfolio exposure uses cost_basis not market_value~~ | ~~Inaccurate exposure %~~ | **FIXED in Sprint 9** |
| Expected/Actual data across 3 tables | Complex queries | Sprint 11 (consolidate to trade_records) |
| ~~SHORT position drift sign inversion~~ | ~~Wrong drift for shorts~~ | **FIXED in Sprint 13** |
| ~~Stock split invalidates thesis prices~~ | ~~Target/stop loss break after split~~ | **FIXED in Sprint 13** |
| pandas_ta Pandas 3.x deprecation warning | Console noise | Wait for upstream fix |
| ~~active_positions.ticker UNIQUE constraint~~ | ~~Can't re-open same ticker after close~~ | **FIXED in Sprint 9** (partial unique index) |

---

## Key Metrics to Track

| Metric | Current (Sprint 15) | Sprint 16 Target | Sprint 17 Target |
|--------|---------------------|------------------|------------------|
| Test count | 416 | 440+ | 470+ |
| API endpoints | 50 | 54+ | 58+ |
| Frontend pages | 12 | 13+ | 14+ |
| UI components | 20+ | 25+ | 30+ |
| Agents | 6 | 7+ | 8+ |
| Signal accuracy (resolved) | TBD | Baseline established | > 55% win rate |
| Daily active use | Full UI polish | On-chain + validation | Fully autonomous |

---

## Architecture Principles

1. **Rule-based first, LLM second** -- Prove signal quality before spending API tokens
2. **Self-hosted, zero recurring cost** -- Core functionality works without any API keys
3. **Graceful degradation** -- Missing API keys or data sources never crash the system
4. **Deterministic and testable** -- Weighted aggregation, not LLM consensus
5. **Risk management > return maximization** -- System's value is drawdown protection
6. **CLI-first, API-second, UI-third** -- Every feature works from the command line
