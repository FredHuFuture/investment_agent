# Investment Agent -- Session Context Document

> **Last Updated**: 2026-03-16 | **Sprint**: 38 | **Version**: v5

Use this document to start a new Claude session with full project context. Copy it into the conversation or reference it as a file.

---

## 1. Who I Am

- Developer-investor managing $200K-500K portfolio (US stocks + BTC/Crypto)
- Bilingual: Chinese and English interchangeably
- You act as **CTO / CPO / Architect** -- make strategic product decisions, write task specs, manage roadmap, directly implement
- I dispatch dev work to sub-agents using task specs you write
- Casual, human tone -- no "AI味" (AI-sounding copy)
- Drill-down reasoning on metrics -- not just signals, but the "why" behind them

---

## 2. Standing Instructions (Must Follow)

| Rule | Detail |
|------|--------|
| **Auto commit** | After each dev task: run quality gates, stage, commit. Don't ask. |
| **No Co-Authored-By** | Commits must NOT include `Co-Authored-By: Claude` -- I am sole author |
| **Sprint summaries** | After each sprint, provide business-angle summary (what was built in user terms, product improvement, next steps) |
| **Architecture doc** | Keep `docs/architecture_v5.md` updated after each task that changes the system |
| **README sync** | Keep `README.md` test counts, endpoint counts, component counts current |
| **Parallel agents** | 4 agents per sprint with strict file ownership to avoid merge conflicts |
| **Shared file pre-edit** | Before dispatching agents, pre-edit shared files: `types.ts`, `endpoints.ts`, `app.py`, `Sidebar.tsx` |
| **Quality gates** | Before every commit: `tsc --noEmit`, `pytest`, `vitest run`, `vite build` |

---

## 3. Product Overview

**Tagline**: "The investment journal that fights back -- tracks your thesis, monitors positions, tells you when reality diverges from your plan."

**Core Value Prop**: Risk management, not alpha generation. Backtested on 6 tickers (2020-2025): signal timing reduces max drawdown by 15-36pp while capturing majority of upside.

| Dimension | Decision |
|-----------|----------|
| Assets | US stocks + BTC/Crypto |
| Capital scale | $200K-500K |
| Positioning | Continuous monitoring + analysis advice, manual trading |
| Data sources | yfinance + CCXT + FRED (free) |
| Learning | L1 EWMA weight adaptation (done) -> L2 regime switching (done) -> L3 reasoning (deferred) |
| Cost | $0 core, ~$5-10/mo if Claude API enabled |

**Competitive Edge vs ai-hedge-fund / TradingAgents / PortfolioPilot / OpenBB**: Self-hosted, persistent portfolio, thesis tracking, drift analysis, continuous monitoring, zero cost.

---

## 4. Architecture

```
React 18 + TypeScript + Tailwind CSS (15 pages, 65+ components)
    | port 3000 -> 8000 (CORS)
FastAPI + Pydantic v2 (~100 endpoints, 21 route modules)
    |
CLI Layer + Analysis Pipeline + Portfolio Manager + Monitoring Daemon
    |
6 Agents: Technical(17) | Fundamental(20) | Macro(11) | Crypto(7-factor) | Sentiment(LLM) | Summary(LLM)
+ RegimeDetector(5 regimes) | SignalAggregator | DriftAnalyzer | WeightAdapter
    |
Data: SQLite WAL (13 tables) | YFinance | FRED | CCXT | Google News RSS
Notifications: SMTP Email | Telegram Bot
Export: CSV | JSON | PDF
```

**Tech Stack**: Python 3.11+ · FastAPI · aiosqlite · React 18 · TypeScript · Tailwind · Recharts · Vite · Vitest · Plotly · APScheduler

---

## 5. Current State (Sprint 38 Complete)

### Key Metrics

| Metric | Value |
|--------|-------|
| Tests | **889** (517 BE + 372 FE) |
| API Endpoints | **~100** (across 21 route modules) |
| Frontend Pages | **15** |
| UI Components | **65+** |
| Analysis Agents | **6** |
| Database Tables | **13** |
| Source Files | **140+** |

### Pages (15)

| Page | Route | Key Features |
|------|-------|-------------|
| Dashboard | `/` | 5 metric cards, earnings calendar, top movers, signals, risk summary, thesis drift, regime timeline, activity feed, 60s auto-refresh |
| Analysis | `/analyze` | Single + Compare mode, 6 quick tickers, signal gauge, weight adjuster, add-to-portfolio |
| Portfolio | `/portfolio` | Goal tracker, allocation chart, sector drill-down, CSV import, multi-profile, thesis management |
| Position Detail | `/portfolio/:ticker` | Price chart, P&L timeline, dividends, position notes, trade annotations, thesis edit |
| Watchlist | `/watchlist` | Bulk add, signal filter, compare mode (5 tickers), alert config, analyze all |
| Performance | `/performance` | Benchmark comparison, drawdown, rolling Sharpe, monthly heatmap, attribution, sector P&L, snapshot comparison |
| Risk | `/risk` | Health score, VaR/CVaR, correlation matrix, stress test, Monte Carlo, risk badge |
| Journal | `/journal` | Trading insights, return distribution, lesson tag analytics, trade annotations |
| Backtest | `/backtest` | Single + batch, preset manager, history + comparison, equity curve, 14 metrics |
| Signals | `/signals` | 7 tabs: history, accuracy, calibration, agent perf, trend, agreement, timeline |
| Monitoring | `/monitoring` | Alert rules engine, severity filter, batch acknowledge, alert analytics |
| Weights | `/weights` | Agent + factor weight donut charts |
| Daemon | `/daemon` | 5 job cards, run once, run history |
| Analysis History | `/analysis-history` | Historical analyses, ticker/signal filter, expandable details |
| Settings | `/settings` | Theme, notifications, cache, export hub (7 exports), risk params, system info |

### Backend Route Modules (21)

| Module | Endpoints | Focus |
|--------|-----------|-------|
| portfolio.py | 19 | Position CRUD, thesis, bulk import, cash, goals, earnings |
| analytics.py | 17 | Value history, performance, P&L, sector performance |
| alerts.py | 12 | Alert CRUD, rules engine, filtering |
| watchlist.py | 11 | Watchlist CRUD, alerts, comparison |
| export.py | 7 | CSV/JSON export |
| analyze.py | 6 | Analysis, catalysts, correlation |
| journal.py | 6 | Annotations, notes, insights |
| signals.py | 6 | History, accuracy, agreement |
| profiles.py | 6 | Multi-portfolio |
| risk.py | 3 | Stress test, Monte Carlo, health score |
| backtest.py | 2 | Single + batch |
| daemon.py | 2 | Status + run-once |
| regime.py | 2 | Current + history |
| + 8 more | ~9 | Summary, notifications, system, weights, etc. |

### Database Schema (13 Tables)

`active_positions` · `portfolio_meta` · `positions_thesis` · `trade_executions` · `portfolio_snapshots` · `monitoring_alerts` · `signal_history` · `daemon_runs` · `price_history_cache` · `watchlist` · `portfolios` · `regime_history` · `trade_annotations`

+ Sprint 36-38 added: `portfolio_goals` · `position_notes` · `alert_rules` (created inline via aiosqlite)

---

## 6. Analysis Engine

### 6 Agents

| Agent | Type | Assets | Key Metrics |
|-------|------|--------|-------------|
| **Technical** | Rule-based | All | SMA 20/50/200, RSI, MACD, Bollinger, ADX, ATR, volume (17 metrics) |
| **Fundamental** | Rule-based | Stocks | P/E, PEG, ROE, revenue growth, D/E, FCF yield, dividends (20 metrics) |
| **Macro** | Rule-based | All | VIX, yield curve, fed funds, M2, CLI, unemployment (11 metrics) |
| **Crypto** | Rule-based | BTC/ETH | 7-factor: momentum, volatility, trend, volume, macro, network, cycle |
| **Sentiment** | LLM | All | News via Claude API (optional, needs ANTHROPIC_API_KEY) |
| **Summary** | LLM | All | Weekly portfolio review via Claude (optional) |

### Signal Aggregation

1. `effective_weight = agent_weight * (confidence / 100)`
2. `weighted_sum = SUM(signal_value * effective_weight)` where BUY=+1, HOLD=0, SELL=-1
3. `raw_score = weighted_sum / total_effective_weight`
4. BUY if raw_score >= +0.30, SELL if <= -0.30, else HOLD
5. Consensus < 50% agreement -> confidence * 0.8 penalty

**Default Weights**: Stock: Technical 0.30, Fundamental 0.45, Macro 0.25 | Crypto: CryptoAgent 1.0

### Regime Detection (5 Types)

BULL · BEAR · SIDEWAYS · HIGH_VOL · RISK_OFF -- drives L2 adaptive weight switching

---

## 7. Sprint History (Complete)

| Sprint | Focus | Key Deliverables |
|--------|-------|-----------------|
| Phase 1 | Foundation | DB, portfolio, 3 agents, pipeline, aggregator, drift, monitoring, signals, CLI (95 tests) |
| 3 | Visualization | Plotly charts, walk-forward backtesting |
| 4 | Automation | Monitoring daemon, detail mode |
| 4.5 | Agents | CryptoAgent 7-factor, FundamentalAgent upgrade, sector rotation |
| 5 | Learning | EWMA weight adapter, Sharpe optimizer, batch backtest |
| 6 | API | FastAPI REST (22 endpoints, Pydantic v2) |
| 7 | Frontend | React 18 + TypeScript + Tailwind (7 pages), SummaryAgent |
| 8 | Lifecycle | Close position, realized P&L, signal auto-resolution |
| 9 | Dashboard | Dashboard home, analyze-to-add flow, thesis editing, alert management |
| 10 | Sentiment | SentimentAgent (Claude API), WebNewsProvider, catalyst scanner |
| 11 | Portfolio-aware | Concentration check, correlation, position sizing, impact preview |
| 12 | Notifications | Email (SMTP), Telegram, CSV/JSON export (5 endpoints), Settings page |
| 13 | Watchlist | Watchlist CRUD, performance analytics, multi-portfolio, tech debt |
| 14 | Intelligence | Regime detection, L2 weight switching, batch watchlist analysis |
| 15 | UI/UX | Design system (Button/Input/Card/Skeleton/Toast), responsive sidebar, command palette |
| 16 | Adoption | 100% design system adoption (19 files), Trade Journal page |
| 17 | Risk | Risk Dashboard (Sharpe/VaR/drawdown/correlations), code splitting |
| 18 | Resilience | ErrorAlert retry, Journal DataTable, Signals filtering, auto-refresh |
| 19 | Benchmarking | Dashboard auto-refresh, SPY benchmark comparison, monthly returns toggle |
| 20 | Quality | Thesis editing, RegimeBadge, vitest + testing-library (62 FE tests) |
| 21 | Testing | 113 new FE tests, utility consolidation, mobile polish |
| 22 | Polish | Alert actions, ARIA accessibility, 16 BE API tests, dead code cleanup |
| 23 | A11y | Keyboard a11y, lazy-load (86% chunk reduction), page integration tests |
| 24 | Coverage | 14/14 pages tested, all API routes tested, all components tested |
| 25 | Completion | Final 3 page tests, all 4 hooks tested, AnalyzePage + RiskPage UX |
| 26 | Analytics | Sector allocation bar, thesis drift, cumulative P&L, position P&L, return distribution |
| 27 | Workflow | Watchlist comparison, monitoring timeline + batch ack, backtest history, signals trend |
| 28 | UX | Settings hub (theme/cache), dashboard cards, portfolio search + sector drill-down, compare mode |
| 29 | Journal | Trade annotations + lesson tags, stress test, drawdown/sharpe/heatmap charts, export |
| 30 | Profiles | Multi-portfolio UI, regime timeline, watchlist alerts, lesson-tag analytics |
| 31 | Infrastructure | Regime daemon, watchlist alert scan, expanded backtest metrics, daemon UI |
| 32 | History | P&L timeline chart, daemon run history, alert analytics, analysis history page |
| 33 | Risk | Backtest presets, Monte Carlo, settings risk params, daily return + risk widget |
| 34 | Observability | Notification config UI, position timeline, correlation heatmap, activity feed |
| 35 | Import | Bulk CSV import, watchlist targets banner, performance attribution, backtest comparison |
| 36 | Tracking | Dividend tracker, signal strength gauge, snapshot comparison, watchlist bulk add |
| 37 | Planning | Earnings calendar, portfolio goal tracker, position quick notes, sector performance |
| 38 | Config | Export hub (7 exports), alert rules engine, portfolio health score, journal insights |

---

## 8. Development Patterns

### Sprint Execution Model (4 Parallel Agents)

```
1. Pre-edit shared files (types.ts, endpoints.ts, app.py, Sidebar.tsx)
2. Dispatch 4 agents with strict file ownership:
   - Agent X.1: Feature A (owns specific files)
   - Agent X.2: Feature B (owns specific files)
   - Agent X.3: Feature C (owns specific files)
   - Agent X.4: Feature D (owns specific files)
3. Quality gates: tsc --noEmit && pytest && vitest run && vite build
4. Commit
5. Update README.md + architecture_v5.md
6. Commit docs
7. Business summary -> next sprint
```

### Code Conventions

| Area | Pattern |
|------|---------|
| Backend DB | `from api.deps import get_db_path` then `async with aiosqlite.connect(db_path) as conn` |
| Frontend data | `useApi` SWR hook with cache TTL |
| Frontend tests | `vitest` + `@testing-library/react` + `jsdom`; recharts mocked |
| Test timing | `waitFor` on dynamic/async text, NOT static headers (prevents race conditions in full suite) |
| API format | `{ data: {...}, warnings: [...] }` success, `{ error: { code, message } }` failure |
| Components | Tailwind utility classes, Card/Button/Input from design system |
| Routes | FastAPI routers, Pydantic v2 models, aiosqlite async |
| State | localStorage cache + memory cache, per-page TTLs (15s-120s) |

### File Structure

```
investment_agent/
  agents/          -- 6 analysis agents
  engine/          -- pipeline, aggregator, regime, drift, weight optimizer, analytics
  portfolio/       -- position mgmt, thesis, multi-portfolio
  monitoring/      -- real-time alerts
  tracking/        -- signal accuracy + calibration
  backtesting/     -- walk-forward + batch
  watchlist/       -- ticker watchlist + batch analysis
  notifications/   -- Email SMTP + Telegram
  export/          -- CSV/JSON report
  api/             -- FastAPI app + 21 route modules
    routes/        -- alert_analytics, alerts, analysis_history, analytics, analyze,
                      backtest, daemon, daemon_history, export, journal, notifications,
                      portfolio, profiles, regime, risk, signals, summary, system,
                      watchlist, weights
  frontend/        -- React 18 + TypeScript + Tailwind
    src/
      pages/       -- 15 page components
      components/  -- 16 directories (ui, shared, dashboard, analysis, portfolio,
                      position, performance, risk, backtest, signals, monitoring,
                      watchlist, journal, settings, daemon, summary, layout)
      api/         -- types.ts, endpoints.ts, client.ts
      lib/         -- useApi hook, colors, formatters
  daemon/          -- APScheduler monitoring
  data_providers/  -- YFinance, FRED, CCXT, Google News
  charts/          -- Plotly interactive generators
  cli/             -- CLI entry points
  db/              -- SQLite WAL, 13 tables
  tests/           -- 51 backend test files
  docs/            -- architecture_v5.md, ROADMAP.md, USER_MANUAL.md, etc.
```

---

## 9. Startup Commands

```bash
# Location
cd C:\Users\futur\localCodeBase\investment_agent

# Install
pip install --pre -e ".[dev]"
cd frontend && npm install && cd ..

# Run
.\run.ps1              # Both (Windows PowerShell)
# OR manually:
uvicorn api.app:app --port 8000 --reload   # Terminal 1
cd frontend && npm run dev                  # Terminal 2

# Quality gates
npx tsc --noEmit                           # TypeScript check
pytest tests/ -v                           # Backend tests
cd frontend && npx vitest run              # Frontend tests
cd frontend && npx vite build              # Production build
```

---

## 10. Roadmap (What's Next)

### Immediate Options (Sprint 39+)

| Feature | Priority | Notes |
|---------|----------|-------|
| LLM Integration (deeper) | P2 | More Claude-powered features, AI trade coaching |
| OnChainAgent | P3 | BTC-specific: MVRV, SOPR, exchange flows |
| ValidationAgent | P3 | LLM cross-checks agent logic consistency |
| Desktop App (Tauri) | P3 | Native wrapper for offline use |
| FMP Data Upgrade | P3 | Point-in-time fundamentals ($20-50/mo) |
| L3 Reasoning | P4 | LLM analyzes its own signal quality |

### Architecture Principles

1. Rule-based first, LLM second
2. Self-hosted, zero recurring cost
3. Graceful degradation (missing keys never crash)
4. Deterministic and testable
5. Risk management > return maximization
6. CLI-first, API-second, UI-third

---

## 11. Key Git Commits (Recent)

```
ffdca16 docs: update architecture and README for Sprint 38
f8ec33b feat: Sprint 38 -- Export hub, alert rules engine, portfolio health score, journal insights
732a0a3 docs: update architecture and README for Sprint 37
45a426f feat: Sprint 37 -- Earnings calendar, portfolio goal tracker, position quick notes, sector performance
163422a docs: update architecture and README for Sprint 36
1efd899 feat: Sprint 36 -- Dividend tracker, signal strength gauge, snapshot comparison, watchlist bulk add
```

---

## 12. Documents Created

| Document | Location | Purpose |
|----------|----------|---------|
| Architecture (living) | `docs/architecture_v5.md` | Complete system architecture, updated every sprint |
| Roadmap | `docs/ROADMAP.md` | Sprint history + future plans |
| User Manual | `docs/USER_MANUAL.md` | Full user guide (Chinese), all 15 pages documented |
| Developer Guide | `docs/DEVELOPER_INSTRUCTIONS.md` | Agent collaboration workflow |
| This Document | `docs/SESSION_CONTEXT.md` | Session starter for new conversations |

---

## 13. Backtesting Proof Points

| Ticker | Return | vs B&H | Max DD | DD Improvement | Sharpe |
|--------|--------|--------|--------|----------------|--------|
| NVDA | +4,892% | -223pp | -35.2% | **+30.8pp** | 3.36 |
| BTC | +1,043% | -85pp | -40.7% | **+35.9pp** | 2.36 |
| TSLA | +812% | -187pp | -52.1% | **+19.5pp** | 1.87 |
| SPY | +78% | -19pp | -18.7% | **+15.4pp** | 1.66 |
| AAPL | +231% | -107pp | -23.2% | **+16.8pp** | 1.50 |
| MSFT | +118% | -84pp | -31.2% | **+20.5pp** | 0.95 |

**Key insight**: Signal timing consistently reduces max drawdown 15-36pp across all tickers while capturing majority of upside.

---

*This document is the single reference needed to resume development in a new session. When starting a new conversation, say: "Read docs/SESSION_CONTEXT.md and continue development."*
