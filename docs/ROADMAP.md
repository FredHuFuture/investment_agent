# Investment Analysis Agent -- Product & Technical Roadmap

**Last updated:** 2026-03-14
**Current state:** Sprint 11 complete (287 tests, 81 source files, 31 API endpoints, 9 pages, 6 agents)

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

**Total: 287 tests, 0 failures**

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

### Sprint 12: Notifications + Integrations (P3 -- Expansion)

| Task | Description |
|------|-------------|
| 12.1 Email Alerts | SendGrid/SES integration for CRITICAL alerts |
| 12.2 Telegram Bot | Alert forwarding to Telegram channel |
| 12.3 Export System | PDF/Excel portfolio reports, trade journal export |
| 12.4 Multi-Portfolio | Support multiple portfolio profiles (e.g., retirement vs trading) |

---

### Sprint 13+: Advanced (Deferred)

| Feature | Priority | Rationale |
|---------|----------|-----------|
| L2 Regime Switching | P2 | Auto-adjust weights based on detected macro regime |
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
| SHORT position drift sign inversion | Wrong drift for shorts | Sprint 11 |
| Stock split invalidates thesis prices | Target/stop loss break after split | Sprint 11 |
| pandas_ta Pandas 3.x deprecation warning | Console noise | Wait for upstream fix |
| ~~active_positions.ticker UNIQUE constraint~~ | ~~Can't re-open same ticker after close~~ | **FIXED in Sprint 9** (partial unique index) |

---

## Key Metrics to Track

| Metric | Current (Sprint 11) | Sprint 12 Target | Sprint 13 Target |
|--------|---------------------|------------------|------------------|
| Test count | 287 | 310+ | 340+ |
| API endpoints | 31 | 35+ | 38+ |
| Frontend pages | 9 | 10+ | 11+ |
| Agents | 6 | 6 | 7+ |
| Signal accuracy (resolved) | TBD | Baseline established | > 55% win rate |
| Daily active use | Dashboard available | Daily dashboard check | Automated alerts |

---

## Architecture Principles

1. **Rule-based first, LLM second** -- Prove signal quality before spending API tokens
2. **Self-hosted, zero recurring cost** -- Core functionality works without any API keys
3. **Graceful degradation** -- Missing API keys or data sources never crash the system
4. **Deterministic and testable** -- Weighted aggregation, not LLM consensus
5. **Risk management > return maximization** -- System's value is drawdown protection
6. **CLI-first, API-second, UI-third** -- Every feature works from the command line
