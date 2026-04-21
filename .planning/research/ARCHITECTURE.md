# Competitive Product/UX Analysis: Portfolio/Thesis Tracking + UI Dimension

**Domain:** OSS investment agents, portfolio trackers, trading dashboards, AI-finance tools
**Researched:** 2026-04-21
**Analysis Type:** Comparative product/UX (not system architecture)
**Overall Confidence:** MEDIUM — all OSS project features verified against GitHub repos and official docs; UX claims cited; confidence noted per section.

---

## Projects Surveyed

| # | Project | GitHub | Stars (approx) | Primary Domain | Relevance |
|---|---------|--------|----------------|----------------|-----------|
| 1 | **Ghostfolio** | [ghostfolio/ghostfolio](https://github.com/ghostfolio/ghostfolio) | 15k+ | Wealth management | HIGH — closest OSS portfolio tracker with rules engine |
| 2 | **Wealthfolio** | [afadil/wealthfolio](https://github.com/afadil/wealthfolio) | 3k+ | Private portfolio tracking | HIGH — desktop-first, SQLite, similar deployment story |
| 3 | **Portfolio Performance** | [portfolio-performance/portfolio](https://github.com/portfolio-performance/portfolio) | 3.8k | Performance calculation | HIGH — deep analytics, Java desktop app |
| 4 | **rotki** | [rotki/rotki](https://github.com/rotki/rotki) | 3k+ | Crypto+equity tracking, tax | MEDIUM — privacy-first, strong tax/accounting |
| 5 | **TradeNote** | [Eleven-Trading/TradeNote](https://github.com/Eleven-Trading/TradeNote) | 2k+ | Day-trading journal | HIGH — closest OSS analog to our journal concept |
| 6 | **InvestBrain** | [investbrainapp/investbrain](https://github.com/investbrainapp/investbrain) | ~500 | Multi-brokerage tracker + AI | MEDIUM — Laravel, AI chat grounded in positions |
| 7 | **OpenBB** | [OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB) | 35k+ | Financial data platform | MEDIUM — data infra + workspace UI, Open Portfolio suite |
| 8 | **TradingAgents** | [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | 5k+ | Multi-agent LLM trading framework | MEDIUM — agent architecture parallel, no portfolio UI |
| 9 | **FinRobot** | [AI4Finance-Foundation/FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | 3k+ | AI equity research reports | LOW — report generation, not tracking/monitoring |
| 10 | **Riskfolio-Lib** | [dcajasn/Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) | 4k+ | Portfolio optimization | MEDIUM — math library, no UI, pluggable |
| 11 | **Quant Lab Alpha** | [husainm97/quant-lab-alpha](https://github.com/husainm97/quant-lab-alpha) | ~100 | Factor analytics + Monte Carlo | MEDIUM — FF5 risk decomposition, Tkinter UI |
| 12 | **FinanceToolkit** | [JerBouma/FinanceToolkit](https://github.com/JerBouma/FinanceToolkit) | 4k+ | 150+ financial ratios, portfolio module | MEDIUM — Python library, no standalone UI |
| 13 | **Maybe Finance** | [maybe-finance/maybe](https://github.com/maybe-finance/maybe) | 40k+ | Personal finance (archived Jul 2025) | LOW — archived; patterns only |
| 14 | **Beancount/Fava** | [beancount/fava](https://github.com/beancount/fava) | 3k+ | Plain-text double-entry accounting | LOW for trading; HIGH for export/journal patterns |
| 15 | **TradingView Lightweight Charts** | [tradingview/lightweight-charts](https://github.com/tradingview/lightweight-charts) | 10k+ | Chart library | HIGH for UI — embeddable, MIT licensed |
| 16 | **Pinnacle** | [F4pl0/pinnacle](https://github.com/F4pl0/pinnacle) | ~100 | OSS portfolio analysis | LOW — microservices demo, limited features |

---

## Section 1: Thesis / Journal / Commit-at-Entry Patterns

**This is our central differentiator. The question: does any OSS competitor track WHY a position was opened, not just what?**

### What Competitors Do

**TradeNote** ([tradenote.co](https://tradenote.co)) is the closest OSS analog to a trade journal. It allows:
- Adding a per-trade note, pattern tag, mistake tag, and satisfaction rating (thumbs up/down)
- Uploading annotated screenshots of the entry setup
- A daily diary for "trader psychology" tracking
- A "yearly playbook" document
- Filtering by patterns and mistakes after the fact
- Source: [TradeNote README](https://github.com/Eleven-Trading/TradeNote/blob/main/README.md)

**Verdict:** TradeNote captures the "what I was thinking" for day-traders via notes + tags, but it is designed for day-trading (stock/futures/forex import from brokers) rather than thesis-driven, long-term investing. It has no concept of a hypothesis that should be validated over time — there is no drift detection, no signal comparison, no "did this thesis play out?" loop.

**Portfolio Performance** (Java desktop) allows:
- A note field per security (security-level, not trade-level)
- Individual buy/sell transactions can have a comment field
- Events (notes tied to specific dates on a security) for splits, dividends, ad-hoc notes
- Source: [PP Trades docs](https://help.portfolio-performance.info/en/reference/view/reports/performance/trades/)

**Verdict:** Notes exist but are cosmetic — there is no structured hypothesis capture (target price, stop loss, time horizon, thesis statement), no monitoring hook, and no drift comparison. Per the forum: "you cannot have a separate note for each trade" in the standard trades view — a known user frustration.

**Ghostfolio**: Supports custom tags on holdings (added 2024-2025). Has a note/comment field on activities (buy/sell transactions). No structured thesis fields; notes are free-text, not machine-readable.
- Source: [Ghostfolio changelog](https://ghostfol.io/en/about/changelog)

**Wealthfolio**: No documented journal or thesis tracking. The "beautiful and boring" design philosophy prioritizes clean performance views over annotation.

**InvestBrain**: Captures position data across brokerages but does not document structured thesis capture. The AI chat assistant can discuss holdings but the data model does not include hypothesis fields.

**OpenBB**: The Open Portfolio suite ingests transactions and produces performance attribution, but does not have a thesis layer — it operates on what happened, not why a position was opened.

**Beancount/Fava**: Supports narration fields (free-text per transaction), tags, and links between transactions. The plain-text format means thesis metadata could be embedded in narration. No UI for structured hypothesis tracking or monitoring.

### What We Do Today

We have the most comprehensive OSS implementation of thesis-at-entry tracking found in this survey:
- Structured `thesis` fields on `active_positions`: target price, stop loss, time horizon, thesis statement text
- `engine/drift_analyzer.py`: compares current signal vs. original thesis parameters
- `monitoring/monitor.py` + `monitoring/checker.py`: PortfolioMonitor fires alerts when thesis drift detected
- `monitoring/` tables: `thesis_drift` tracked per job run
- `JournalPage.tsx` + `journal/` components: UI surface for journal insights
- `engine/journal_analytics.py`: analytics derived from journal data
- Source: `.planning/codebase/ARCHITECTURE.md` (Portfolio Layer), `STRUCTURE.md`

### Who Wins

**We win here.** No OSS competitor combines: (a) structured thesis capture at entry, (b) continuous machine monitoring of drift, (c) signal comparison vs. original thesis, and (d) a dashboard surface showing thesis validity over time. TradeNote comes closest on the journaling UX side; Portfolio Performance comes closest on the trades-view analytics side. Neither closes the loop.

### What to Borrow

| From | Borrow | Integration Point |
|------|--------|-------------------|
| TradeNote | Per-trade annotated screenshot upload | `PositionDetailPage.tsx` — add media attachment to thesis capture form |
| TradeNote | Pattern/mistake tag taxonomy + post-trade review filter | `JournalPage.tsx` — structured tag taxonomy (entry_reason, exit_reason, mistake_type) |
| TradeNote | Annual "playbook" document (free-text long-form review) | New `JournalPage` section or dedicated `PlaybookPage.tsx` |
| Portfolio Performance | Trade-level IRR and holding-period display per position | `PositionDetailPage.tsx` — add IRR field alongside P&L |

### UX Anti-Patterns to Avoid

- **Ghostfolio's free-text-only notes**: Machine-unreadable, can't trigger monitoring or analytics. Keep thesis fields structured (target_price, stop_loss, horizon, thesis_text) — do not collapse to a single textarea.
- **Portfolio Performance's security-level notes**: Notes attached to the instrument, not the trade. Breaks when same ticker is reopened. Our per-position model (with position_id FK) is correct.

### Roadmap Priority: HIGH (preserve and extend — this is our moat)

---

## Section 2: Drift Detection and Alerting

**How do competitors signal when reality diverges from the plan?**

### What Competitors Do

**Ghostfolio X-ray** is the closest commercial-OSS analog to thesis drift:
- Static portfolio analysis rules (e.g., "emergency fund too low," "regional cluster risk," "currency concentration")
- Customizable rule thresholds (experimental, added ~2024)
- Rules fire when a portfolio metric breaches a static threshold
- No per-position thesis awareness — rules operate on portfolio-level allocations
- Source: [Ghostfolio GitHub issues #3247, #4477](https://github.com/ghostfolio/ghostfolio/issues/3247)

**Wealthfolio**: No drift detection found. Goal tracking shows progress toward savings targets but no investment thesis monitoring.

**Portfolio Performance**: Rebalancing viewer shows deviation from target allocation (not thesis). When actual allocation drifts beyond the user-defined target weight, the viewer highlights it. This is allocation drift, not thesis drift.

**OpenBB**: Workspace offers real-time dashboard monitoring; Open Portfolio tracks ex-post metrics (VaR, tracking error). No thesis-level alerting — no concept of "this position should be sold if X condition diverges from the original plan."

**rotki**: No documented drift detection. Privacy-first tracker with P&L and tax focus.

**TradingAgents**: The Risk Management agent evaluates portfolio risk continuously, but it generates signals for new trades — it does not compare current conditions to a stored entry thesis.

**Commercial comparators (non-OSS)**: Addepar Trading (drift monitoring widget), Guardfolio (allocation drift alerts), Investipal (policy misalignment detection) — these exist in wealth management SaaS but are not open source.

### What We Do Today

- `engine/drift_analyzer.py`: Compares current agent signal vs. original thesis parameters (target price, stop loss, time horizon)
- `monitoring/checker.py`: Alert condition checker — fires when thesis drift detected
- `monitoring/monitor.py` (PortfolioMonitor): Orchestrates monitoring per position
- `daemon/jobs.py` (run_daily_check): Scheduled drift computation
- `alerts` table + `api/routes/alerts.py`: Alert storage, retrieval, and UI surface
- `MonitoringPage.tsx`: Frontend view of active alerts
- Delivery: Email (`notifications/email_dispatcher.py`) + Telegram (`notifications/telegram_dispatcher.py`)
- Source: `.planning/codebase/ARCHITECTURE.md` (Portfolio Layer), `STRUCTURE.md`

### Who Wins

**We win on thesis-aware drift.** Ghostfolio's X-ray rules are the only comparable OSS feature, but they operate on portfolio-level allocation rules (static thresholds), not per-position thesis validation. Our drift detection is signal-aware and per-position — meaningfully deeper.

**Ghostfolio wins on rule discoverability**: Their X-ray rules are named, listed, and selectable in a UI. Our alert rule system exists but the rules are code-defined and not browsable/editable by the user in a rules-builder UI.

### What to Borrow

| From | Borrow | Integration Point |
|------|--------|-------------------|
| Ghostfolio X-ray | Named, browsable rules list with enable/disable toggles | `MonitoringPage.tsx` — rules inventory panel above active alerts list |
| Ghostfolio X-ray | Threshold customization per rule in UI (not just config file) | `api/routes/monitoring.py` — expose rule threshold as editable field |
| Portfolio Performance | Allocation drift visualization (actual vs. target weight bar chart) | `PortfolioPage.tsx` — add target-weight column + deviation indicator |

### UX Anti-Patterns to Avoid

- **Silent alert swallowing** (our own risk per `CONCERNS.md`): Daemon jobs catch all exceptions; alerts may be generated but not delivered. Implement alert delivery status tracking (sent/failed/acknowledged).
- **Ghostfolio's non-delivery**: No email/webhook alerts as of 2025; monitoring is purely in-app. Our multi-channel delivery (email, Telegram) is a genuine advantage — preserve it.

### Roadmap Priority: HIGH (rules-builder UI to expose existing logic)

---

## Section 3: Portfolio-Level Analytics

**Health score, factor exposures, risk decomposition, sector/region allocation, performance attribution, benchmarking.**

### What Competitors Do

**Ghostfolio**:
- Portfolio summary: total value, invested amount, performance (TWR and IRR variants)
- Allocation breakdown by asset class, sector, currency, country/region (proportion charts)
- Benchmark comparison (vs. S&P 500, custom benchmark)
- Return on Average Investment (ROAI) across multiple timeframes (Today, WTD, MTD, YTD, 1Y, 5Y, Max)
- No portfolio health score; X-ray rules serve as health indicators
- Source: [Ghostfolio DeepWiki](https://deepwiki.com/ghostfolio/ghostfolio/4-portfolio-management), [Ghostfolio GitHub](https://github.com/ghostfolio/ghostfolio)

**Wealthfolio**:
- Portfolio composition, performance analytics, benchmark comparison (vs. S&P 500 or any ETF)
- Account-side-by-side comparison
- Goal tracking with progress visualization
- Net worth tracking (v3.0+: properties, vehicles, precious metals)
- No factor exposure, no risk decomposition
- Source: [Wealthfolio website](https://wealthfolio.app/), [GitHub](https://github.com/afadil/wealthfolio)

**Portfolio Performance** (Java desktop):
- True Time-Weighted Return (TTWROR) and IRR per position and portfolio
- Benchmark comparison via reference portfolio
- Asset classification hierarchy (user-defined taxonomy for sector, region, etc.)
- Rebalancing viewer: actual vs. target allocation bar/pie charts
- No health score concept; no factor model
- Source: [PP Manual](https://help.portfolio-performance.info/en/)

**OpenBB Open Portfolio**:
- Brinson performance attribution (asset allocation effect + security selection effect)
- Ex-post risk analytics: standard deviation, VaR (95%/99%), tracking error
- Daily holdings snapshots with P&L, market value, weight, P/E enrichment
- Carino linking for compounded attribution
- No health score, but most rigorous attribution of any OSS tool found
- Source: [OpenBB blog](https://openbb.co/blog/open-portfolio-a-suite-for-asset-managers-on-openbb/)

**Quant Lab Alpha**:
- Fama-French Five-Factor risk decomposition (FF5)
- Rolling factor exposure with configurable 3y/5y/10y windows
- CVaR/VaR at 95% confidence, historical drawdown
- Correlation heatmaps, efficient frontier visualization
- Ledoit-Wolf covariance shrinkage
- No dashboard; Tkinter GUI is rudimentary
- Source: [GitHub](https://github.com/husainm97/quant-lab-alpha)

**Riskfolio-Lib** (Python library, no UI):
- 20 convex risk measures for optimization
- Kelly criterion, risk parity, HRP, HERC, NCO
- Black-Litterman with Bayesian update
- Factor attribution and risk contribution per factor
- Source: [GitHub](https://github.com/dcajasn/Riskfolio-Lib)

**FinanceToolkit**:
- 150+ financial ratios computed transparently
- Portfolio module: invested amount, current value, return, benchmark return, alpha, beta per position
- Source: [GitHub](https://github.com/JerBouma/FinanceToolkit)

### What We Do Today

- `engine/analytics.py`: Sharpe ratio, drawdown, performance metrics
- `engine/monte_carlo.py`: Monte Carlo risk simulation (block bootstrap, 10k iterations)
- `engine/stress_test.py`: Stress testing scenarios
- `engine/correlation.py`: Cross-asset correlation analysis
- `engine/sector.py`: Sector modifier application
- `engine/regime.py`: Regime detection (bull/bear/sideways)
- Portfolio health score: EXISTS (`PortfolioPage.tsx` + relevant backend)
- `PerformancePage.tsx`: Performance analytics display
- `RiskPage.tsx`: Risk metrics display
- `api/routes/analytics.py`: Portfolio analytics endpoints
- Source: `.planning/codebase/STRUCTURE.md`

**What we lack relative to competitors:**
- Brinson-style performance attribution (what we got from alpha vs. allocation vs. selection?)
- Factor exposure (Fama-French beta decomposition)
- Benchmark comparison (TWR vs. SPY or user-defined benchmark)
- True Time-Weighted Return calculation (our current analytics focus on P&L, not TTWROR)
- Geographic/region allocation visualization (we have sector, not country-level)

### What to Borrow

| From | Borrow | Priority | Integration Point |
|------|--------|----------|-------------------|
| Ghostfolio | Multi-timeframe return breakdown (Today/WTD/MTD/YTD/1Y/5Y) | HIGH | `PerformancePage.tsx` — time-range selector with cached metrics |
| Portfolio Performance | TTWROR and IRR per-position and aggregate | HIGH | `engine/analytics.py` — add TTWROR implementation; expose via `api/routes/analytics.py` |
| Ghostfolio | Allocation breakdown by currency, country, asset class (proportion charts) | MEDIUM | `PortfolioPage.tsx` — add pie/donut breakdown widgets |
| OpenBB Open Portfolio | Brinson attribution (allocation effect + selection effect vs. benchmark) | MEDIUM | New `api/routes/attribution.py` + `PerformancePage.tsx` section |
| Quant Lab Alpha | Factor exposure (at minimum: market beta, possibly FF3) | LOW | `engine/analytics.py` extension — compute rolling beta vs. benchmark |
| Riskfolio-Lib | Import as library for position-sizing recommendations | LOW | New `api/routes/sizing.py` — wrap Riskfolio optimization |

### UX Anti-Patterns to Avoid

- **Quant Lab Alpha's Tkinter UI**: Factor analytics buried in a desktop GUI nobody installs. Expose analytics in the web dashboard with clear labeling.
- **Portfolio Performance's flat table view for allocation**: Long tables of percentages are hard to scan. Ghostfolio's proportion charts (donut, treemap) are more legible at a glance.
- **Metric overload without hierarchy**: Don't put Sharpe, Sortino, VaR, CVaR, beta, alpha, TTWROR, IRR all at the same visual weight. Ghostfolio correctly leads with simple P&L then expands to advanced metrics.

### Roadmap Priority: HIGH for TTWROR + benchmark; MEDIUM for attribution; LOW for factor models

---

## Section 4: Alert Rules Engines

**Rule DSL, declarative vs. imperative, delivery channels.**

### What Competitors Do

**Ghostfolio X-ray rules** (closest OSS analog):
- Named rules (e.g., "Emergency fund coverage," "Currency cluster risk," "Regional cluster risk")
- Rules have configurable thresholds (experimental feature, 2024)
- Enable/disable per rule in UI
- Rules are hardcoded in application logic (NestJS service), not user-definable DSL
- Delivery: in-app notifications only; no email or webhook as of 2025
- Source: [Ghostfolio issues #3247](https://github.com/ghostfolio/ghostfolio/issues/3247), [#4477](https://github.com/ghostfolio/ghostfolio/issues/4477)

**Portfolio Performance**: No alert rules engine. The rebalancing viewer highlights deviation but does not alert.

**Wealthfolio**: No alert rules engine found. Goal tracking shows visual progress.

**rotki**: No documented alert rules engine.

**TradeNote**: No alert rules — it is a retrospective journal, not a monitoring system.

**OpenBB**: AI copilot can analyze conditions on request but is not a rules engine. No persistent alerting loop.

**Commercial context**: Addepar, Guardfolio, and Investipal all have threshold-based drift monitoring, but none are open source.

### What We Do Today

We have the most complete OSS alert rules engine found in this survey:
- `monitoring/checker.py`: Alert condition checker with multiple rule types
- `monitoring/monitor.py`: PortfolioMonitor orchestrates rules evaluation
- `api/routes/alerts.py`: Alert management API
- `api/routes/monitoring.py`: Alert condition tracking
- `MonitoringPage.tsx`: Alert rules display and management
- Alert delivery: Email (SMTP) + Telegram bot
- Rule conditions include: thesis drift, price targets, stop loss violations
- Daemon scheduling: rules run daily via APScheduler
- Source: `.planning/codebase/ARCHITECTURE.md`, `STRUCTURE.md`

**What we lack relative to best practices:**
- User-definable rule builder UI (rules are currently code-defined in Python, not editable in UI)
- Named/listed rules inventory visible to the user (Ghostfolio's X-ray style)
- Rule enable/disable toggles in UI
- Alert acknowledgment / dismiss workflow (are alerts marked as read/actioned?)
- Webhook delivery (no webhook outbound from our system)
- Alert history / archive

### What to Borrow

| From | Borrow | Priority | Integration Point |
|------|--------|----------|-------------------|
| Ghostfolio | Named rules inventory panel with enable/disable toggles | HIGH | `MonitoringPage.tsx` — add rules list above alert feed |
| Ghostfolio | Threshold customization via UI (not config file) | HIGH | `api/routes/monitoring.py` + new alert rule settings form |
| Generic pattern | Alert acknowledge/dismiss + alert history archive | MEDIUM | `api/routes/alerts.py` — add status field; `MonitoringPage.tsx` — mark-as-read UX |
| Generic pattern | Webhook delivery channel (Slack, Discord, generic HTTP) | LOW | `notifications/` — add webhook dispatcher alongside email/Telegram |

### UX Anti-Patterns to Avoid

- **Ghostfolio's in-app-only delivery**: Our email + Telegram delivery is a real advantage. Don't remove channels to simplify.
- **Alert flood without prioritization**: If every agent signal change generates an alert, users mute everything. Add severity levels (Critical/Warning/Info) and aggregation (don't fire the same rule twice in 24h unless condition worsens).
- **Rules as code only**: If threshold changes require a code deploy, adoption is zero. Rules must be editable from the UI.

### Roadmap Priority: HIGH (rules-builder UI); MEDIUM (webhook + alert history)

---

## Section 5: Dashboard UX Patterns

**Layout, visualizations — what charts, what data density, what hierarchies.**

### What Competitors Do

**Ghostfolio** (Angular + Angular Material + Bootstrap utilities):
- Mobile-first PWA layout; sidebar navigation
- Homepage: net worth number + sparkline + performance band (Today/WTD/MTD/YTD)
- Portfolio view: holdings table + proportion chart breakdown by asset class, sector, currency
- Activity list: chronological buy/sell/dividend log
- X-ray page: rule cards with status indicators
- Chart types: line charts (performance over time), proportion/donut charts (allocation), bar charts (rebalancing deviation)
- Data density: LOW-MEDIUM — clean, minimal, prioritizes legibility over information density
- Source: [Ghostfolio GitHub](https://github.com/ghostfolio/ghostfolio), [XDA Developers review](https://www.xda-developers.com/this-self-hosted-app-changed-the-way-track-investments/)

**Wealthfolio** (Tauri + React 19 + Vite):
- Desktop-first (Tauri native window) with PWA option
- "Beautiful and boring" design philosophy — deliberately understated
- Performance dashboard: cumulative return line chart, account comparison table
- Holdings breakdown: sector/country pie charts, allocation table
- Goal progress: visual target bars
- Chart types: line charts (performance), pie/donut (allocation), bar charts (goals)
- Data density: LOW — intentionally minimal
- Source: [Wealthfolio website](https://wealthfolio.app/), [GitHub](https://github.com/afadil/wealthfolio), [HN thread](https://news.ycombinator.com/item?id=46006016)

**Portfolio Performance** (Java SWT desktop):
- Multi-pane dashboard with configurable widgets
- Dashboard widgets include: securities reaching price levels, rebalancing status bars, performance charts
- Chart types: line charts (portfolio value over time), bar/pie charts (allocation vs. target), waterfall charts (contribution breakdown), candlestick (security price history)
- High data density — tables everywhere, desktop paradigm
- Source: [PP Manual](https://help.portfolio-performance.info/en/)

**TradeNote** (VueJS SPA):
- Dashboard view: daily P&L, trade calendar, progress tracking
- Daily view: trade list with pattern/mistake/note per trade
- Calendar view: month-level P&L heatmap (calendar cells colored by daily profit/loss)
- Screenshot gallery: annotated entry screenshots
- Chart types: P&L bar charts, calendar heatmap, running balance line
- Data density: MEDIUM — oriented toward pattern recognition
- Source: [TradeNote GitHub](https://github.com/Eleven-Trading/TradeNote)

**OpenBB Workspace** (proprietary web UI):
- Widget-based customizable dashboard canvas
- Drag-drop widget placement
- Chart types: tables, bar, pie, area charts as configurable widget types
- Data density: HIGH — designed for professional analysts
- Source: [OpenBB Workspace docs](https://docs.openbb.co/workspace)

### What We Do Today

15-page React/TS dashboard with "Modern Craft" editorial design system:
- `DashboardPage.tsx`: Overview cards + status
- `PortfolioPage.tsx`: Holdings table, portfolio health score
- `PositionDetailPage.tsx`: Per-position analytics, thesis display
- `PerformancePage.tsx`: Performance metrics and charts
- `RiskPage.tsx`: Risk analysis display
- `JournalPage.tsx`: Journal insights
- `MonitoringPage.tsx`: Alert display
- `BacktestPage.tsx`: Backtest results
- `SignalsPage.tsx`: Signal history
- `WatchlistPage.tsx`: Watchlist management
- `AnalysisHistoryPage.tsx`: Historical analysis
- `WeightsPage.tsx`: Agent weight configuration
- Chart library: Not specified in docs (likely Recharts or similar given React/TS stack)
- Source: `.planning/codebase/STRUCTURE.md` (frontend/src/pages/)

**What we likely lack** (inferred — no visual screenshots available to this researcher):
- Calendar heatmap for P&L history (TradeNote pattern — highly legible for trend spotting)
- Proportion/donut charts for allocation breakdown (Ghostfolio pattern)
- Multi-timeframe return selector (TWD/MTD/YTD/1Y toggle on dashboard summary card)
- Spark lines on holdings table (mini-chart per row showing price trend)

### What to Borrow

| From | Pattern | Priority | Integration Point |
|------|---------|----------|-------------------|
| TradeNote | Calendar heatmap (daily P&L colored cells) | HIGH | `PerformancePage.tsx` or `DashboardPage.tsx` — add calendar widget using Recharts or a heatmap component |
| Ghostfolio | Time-range toggle on summary metrics (Today/WTD/MTD/YTD/1Y/5Y) | HIGH | `DashboardPage.tsx` — performance band with toggle selector |
| Ghostfolio | Proportion charts (donut) for sector/currency/asset class allocation | MEDIUM | `PortfolioPage.tsx` — add allocation donut alongside holdings table |
| Portfolio Performance | Rebalancing deviation bars (actual vs. target weight side-by-side) | MEDIUM | `PortfolioPage.tsx` — add target weight column with deviation indicator |
| Wealthfolio | Benchmark overlay on cumulative return chart | MEDIUM | `PerformancePage.tsx` — add benchmark line (SPY or configurable) |
| TradeNote | Annotated screenshot attachment per position | LOW | `PositionDetailPage.tsx` — add media upload to thesis form |

### Chart Type Inventory (what competitors use and why)

| Chart Type | Used By | When to Use |
|------------|---------|-------------|
| Line chart (cumulative return) | All | Portfolio performance over time — mandatory |
| Proportion/donut chart | Ghostfolio, Wealthfolio | Allocation breakdown — better than pie for small slices |
| Bar chart (deviation) | Portfolio Performance, Ghostfolio | Rebalancing: actual vs. target weight — highlights imbalances |
| Calendar heatmap | TradeNote | Daily P&L pattern recognition — shows volatility clusters |
| Candlestick/OHLC | Portfolio Performance, TV Lightweight | Price history for individual securities |
| Waterfall/attribution | OpenBB | Return decomposition (allocation effect, selection effect) |
| Spark lines | Wealthfolio (implied) | Holdings table — micro price trend per row |
| Correlation heatmap | Quant Lab Alpha | Cross-asset correlation — useful in RiskPage |
| Scatter (efficient frontier) | Quant Lab Alpha | Risk/return tradeoff — niche but valuable |

### UX Anti-Patterns to Avoid

- **Portfolio Performance's table density**: Java desktop paradigm (20-column tables, nested pane layouts) is hostile in a web context. Our "Modern Craft" direction is correct — maintain editorial hierarchy.
- **OpenBB's drag-drop dashboard**: Powerful for analysts but overwhelms individual investors. Widget configurability is a complexity sink — defer it.
- **Ghostfolio's mobile-first at cost of data density**: Their homepage is too sparse for a power user who wants all signals visible. Our 15-page structure gives appropriate depth — don't collapse it into a single overview screen.
- **Heatmaps without tooltip**: Calendar heatmaps are useless without hover-tooltip showing exact date/value. Always pair heatmap cells with interactive tooltip.

### Recommended Chart Library: TradingView Lightweight Charts + Recharts

**TradingView Lightweight Charts** ([GitHub](https://github.com/tradingview/lightweight-charts), MIT, 10k stars):
- Best-in-class candlestick, area, line charts for financial time series
- 45KB bundle, performant on large datasets, HTML5 canvas
- Vanilla JS/TS — requires React wrapper (community wrappers exist)
- Use for: price history, signal overlays, backtest result charts
- Confidence: HIGH (verified current, widely used in OSS finance tools)

**Recharts** (current chart library pattern for React finance dashboards):
- Declarative JSX API, ~1.8M weekly downloads, TypeScript support
- Use for: allocation donuts, bar charts, performance lines, calendar heatmap (via custom cell)
- Confidence: HIGH

### Roadmap Priority: HIGH for calendar heatmap + time-range selector; MEDIUM for allocation donuts + benchmark overlay

---

## Section 6: Export and Reporting

**PDF, CSV, Markdown, tax reports.**

### What Competitors Do

**Portfolio Performance**: All data stored as XML; export to CSV and JSON available. PDF generation not documented; community uses third-party print-to-PDF.

**Ghostfolio**: JSON export of accounts, activities, custom asset profiles, market data. CSV import/export for activities. No PDF report generation.

**Wealthfolio**: CSV import from brokerages. Export capabilities not prominently documented.

**rotki**: The strongest export story of any OSS tool — specifically designed for tax reporting. Generates profit/loss reports across any time period using customizable accounting settings (FIFO, LIFO, etc.). CSV and report exports.
- Source: [rotki GitHub](https://github.com/rotki/rotki)

**Beancount/Fava**: Plain-text ledger format is the export. Fava provides CSV export, balance sheet, income statement, and portfolio summary exports. Tax-period filtering built in.

**TradeNote**: Basic export implied; not a reporting-first tool.

**FinanceToolkit**: Python library outputs DataFrames; export is caller's responsibility.

### What We Do Today

- `export/portfolio_report.py`: PDF/HTML report generation
- `api/routes/export.py`: Export endpoints
- Export Hub: EXISTS in frontend (mentioned in PROJECT.md as "export hub")
- Source: `.planning/codebase/STRUCTURE.md`

**What we lack relative to competitors:**
- Tax-lot accounting (FIFO/LIFO cost basis tracking for capital gains) — rotki excels here
- Markdown export for journal/thesis records (Beancount pattern — text-first)
- Broker CSV import for auto-populating trades (Ghostfolio, Portfolio Performance, Wealthfolio all have this)
- Scheduled report delivery (e.g., weekly email digest of portfolio state)

### What to Borrow

| From | Borrow | Priority | Integration Point |
|------|--------|----------|-------------------|
| rotki | Tax-lot (FIFO/LIFO) capital gains report | MEDIUM | `export/` — new tax report generator; `api/routes/export.py` |
| Ghostfolio/Portfolio Performance | CSV import of broker transactions | MEDIUM | `api/routes/portfolio.py` — bulk import endpoint (skeleton exists per `manager.py`) |
| Beancount | Markdown export of journal/thesis history | LOW | `export/` — journal_to_markdown exporter |
| Generic | Scheduled weekly digest email | LOW | `daemon/jobs.py` — add weekly_digest job |

### Roadmap Priority: MEDIUM (tax-lot + CSV import); LOW (Markdown + digest)

---

## Section 7: Rebalancing and Position-Sizing Guidance

**Kelly, risk parity, mean-variance, target-weight deviation alerts.**

### What Competitors Do

**Portfolio Performance**:
- Rebalancing viewer: user defines target weights per asset class; viewer shows actual vs. target
- Rebalancing solutions when securities span multiple classifications
- No position-sizing formula (no Kelly, no risk parity math) — purely visual
- Source: [PP Manual](https://help.portfolio-performance.info/en/)

**Ghostfolio**: Portfolio X-ray includes an experimental rebalancing suggestion. Shows which assets are over/underweight relative to target. No mathematical optimization.

**Riskfolio-Lib** (Python library):
- Full implementation: Kelly criterion, mean-variance (Markowitz, Ledoit-Wolf), risk parity (equal risk contribution), HRP, HERC, Black-Litterman
- No UI — library only
- Requires a frontend to expose recommendations
- Source: [GitHub](https://github.com/dcajasn/Riskfolio-Lib)

**Quant Lab Alpha**: Efficient frontier display with Ledoit-Wolf shrinkage; Markowitz optimization for allocation suggestions.

**Wealthfolio**: Goal-based planning with allocation management. No mathematical optimization documented.

**FinanceToolkit**: Portfolio module shows alpha, beta, performance but no sizing guidance.

### What We Do Today

- `backtesting/metrics.py`: Sharpe, Sortino, max drawdown — analytical metrics that inform sizing but no explicit sizing output
- `engine/monte_carlo.py`: Block bootstrap Monte Carlo — risk simulation, not sizing
- `engine/weight_adapter.py`: Adaptive agent weights (meta-level, not position sizing)
- No Kelly criterion implementation found
- No risk parity implementation found
- No target-weight rebalancing visualization found
- Source: `.planning/codebase/STRUCTURE.md`

**We are behind competitors here.** Portfolio Performance and Ghostfolio both have visual rebalancing (target vs. actual weight display). We have no equivalent.

### What to Borrow

| From | Borrow | Priority | Integration Point |
|------|--------|----------|-------------------|
| Portfolio Performance / Ghostfolio | Target-weight vs. actual-weight visualization per position | HIGH | `PortfolioPage.tsx` — add target_weight field to positions; deviation displayed in table |
| Riskfolio-Lib | Import as Python dependency for Kelly/risk parity calculations | MEDIUM | New `engine/sizing.py` wrapping Riskfolio; `api/routes/sizing.py` endpoint |
| Quant Lab Alpha | Efficient frontier chart for current portfolio | LOW | `RiskPage.tsx` — add scatter plot showing portfolio point on risk/return frontier |

### UX Anti-Patterns to Avoid

- **Recommending rebalancing without friction**: Automated "rebalance now" suggestions lead to over-trading. Show deviation and recommendation, but require user confirmation (we don't execute orders anyway, but the UX framing matters).
- **Kelly as default**: Full Kelly is known to be too aggressive (2x leverage implied). If adding Kelly, present as fractional Kelly (1/4 or 1/2) and label it clearly.

### Roadmap Priority: HIGH for target-weight visualization; MEDIUM for Riskfolio integration; LOW for efficient frontier UI

---

## Section 8: Mobile / Responsive Story

**Even though we deprioritized mobile, this section documents where competitors land.**

### What Competitors Do

**Ghostfolio**: PWA, mobile-first design. Described as "mobile-first" with responsive layout. Works on phone browsers.
- Source: [GitHub](https://github.com/ghostfolio/ghostfolio)

**Wealthfolio**: Tauri desktop app with PWA option. iOS app released in v2.0+ (2025). Docker self-hosted option.
- Source: [HN thread](https://news.ycombinator.com/item?id=46006016), [Wealthfolio website](https://wealthfolio.app/)

**Portfolio Performance**: Java desktop application. No mobile story whatsoever.

**rotki**: Desktop app (Electron). No mobile story.

**TradeNote**: Responsive website (VueJS). Works on mobile for viewing; data entry primarily desktop.

**Beancount/Fava**: Web UI, responsive. Plain-text files not ideal for mobile.

### What We Do Today

Web-first (Vite + React + Tailwind). No PWA manifest, no mobile-specific layout work. Explicitly out of scope for this milestone per `PROJECT.md`.

### What to Borrow (Future Milestones Only)

- Ghostfolio's PWA manifest + service worker pattern for installable web app — low effort, high perceived quality
- Wealthfolio v3.0's "stale-valuation warnings" on mobile dashboard — useful pattern when values are > N hours old

### Roadmap Priority: LOW (out of scope this milestone; PWA manifest is future quick-win)

---

## Consolidated Comparison: Our Project vs. Competitors

| Dimension | Our Project | Best OSS Competitor | Gap? |
|-----------|-------------|---------------------|------|
| **Thesis capture at entry** | Structured fields (target, stop, horizon, thesis text) | TradeNote (notes + tags, no structure) | WE WIN — unique in OSS |
| **Continuous thesis drift monitoring** | Daily daemon + PortfolioMonitor | Ghostfolio X-ray (allocation rules, not thesis) | WE WIN — unique in OSS |
| **Agent-based signal generation** | 6 parallel agents, regime-aware | TradingAgents (multi-agent LLM), FinRobot (research reports) | WE WIN on integration with portfolio tracking |
| **Alert delivery channels** | Email + Telegram | Ghostfolio (in-app only) | WE WIN |
| **Rules discoverability in UI** | Partial (MonitoringPage exists) | Ghostfolio (named rules list, toggles) | COMPETITOR WINS — borrow X-ray panel |
| **TTWROR / IRR analytics** | Not found | Portfolio Performance, FinanceToolkit | COMPETITOR WINS — must add |
| **Benchmark comparison** | Not found | Ghostfolio, Wealthfolio, Portfolio Performance | COMPETITOR WINS — must add |
| **Performance attribution (Brinson)** | Not found | OpenBB Open Portfolio | COMPETITOR WINS — medium priority |
| **Factor exposure (FF3/FF5)** | Not found | Quant Lab Alpha, Riskfolio-Lib | COMPETITOR WINS — low priority |
| **Rebalancing (target-weight UI)** | Not found | Portfolio Performance, Ghostfolio | COMPETITOR WINS — must add |
| **Position-sizing (Kelly / risk parity)** | Monte Carlo only | Riskfolio-Lib (library) | COMPETITOR WINS — medium priority |
| **Export (PDF/HTML)** | export/portfolio_report.py | rotki (tax-focused), Ghostfolio (JSON/CSV) | PARTIAL — add tax-lot CSV |
| **Tax-lot accounting** | Not found | rotki | COMPETITOR WINS — medium priority |
| **Calendar heatmap (P&L)** | Not found | TradeNote | COMPETITOR WINS — borrow pattern |
| **Allocation donut charts** | Not confirmed | Ghostfolio, Wealthfolio | LIKELY GAP — add to PortfolioPage |
| **Mobile / PWA** | Not implemented | Ghostfolio, Wealthfolio | Out of scope this milestone |
| **Trade journal annotations** | JournalPage + journal_analytics | TradeNote (richer: screenshots, psychology diary) | PARTIAL — borrow screenshot attachment |
| **Backtesting** | Full backtester + Monte Carlo + regime | Riskfolio-Lib (math), Quant Lab Alpha (math) | WE WIN on integration |

---

## Priority Summary for Roadmap

### Must-Borrow (address within next milestone)

1. **TTWROR + IRR per-position and aggregate** (Portfolio Performance / FinanceToolkit pattern): Our analytics page is missing the industry-standard performance metric. Every competitor has it. Add to `engine/analytics.py` and expose in `PerformancePage.tsx`.

2. **Benchmark comparison overlay** (Ghostfolio / Wealthfolio pattern): Allow user to configure a benchmark ticker (SPY default); overlay on cumulative return chart. This is the most-requested missing feature type in self-hosted portfolio tools. Add to `PerformancePage.tsx`.

3. **Target-weight rebalancing visualization** (Portfolio Performance / Ghostfolio pattern): Add a `target_weight` field per position; display actual vs. target deviation in `PortfolioPage.tsx`. No math required yet — visual only.

4. **Named rules inventory panel** (Ghostfolio X-ray pattern): Make our existing alert rules visible and toggleable in `MonitoringPage.tsx`. Currently rules live in Python code; expose them via `api/routes/monitoring.py` as named configurable items.

5. **Calendar heatmap for daily P&L** (TradeNote pattern): Add to `PerformancePage.tsx` or `DashboardPage.tsx`. Highly legible for spotting drawdown clusters. Use Recharts custom cell or a heatmap lib (react-calendar-heatmap).

### Should-Borrow (medium priority)

6. **Riskfolio-Lib for position sizing** (Kelly fractional / risk parity): Import as Python dependency; wrap in `engine/sizing.py`; expose via `api/routes/sizing.py`. Present recommendations, not automated rebalancing.

7. **Broker CSV import** (Ghostfolio / Portfolio Performance pattern): Skeleton exists in `portfolio/manager.py` bulk_import. Complete the import UI in frontend — critical for user onboarding.

8. **Tax-lot capital gains report** (rotki pattern): Add FIFO/LIFO cost basis tracking to `export/` for tax season utility.

9. **Alert threshold UI editing** (Ghostfolio X-ray pattern): Rules today require Python code changes. Add threshold fields to the monitoring settings UI.

10. **Allocation donut charts** (Ghostfolio pattern): Add proportion charts (sector, currency, asset class) to `PortfolioPage.tsx`. Recharts PieChart component — low implementation cost.

### Not-Worth-Borrowing (this milestone)

- **Factor exposure (FF5)**: Quant Lab Alpha shows the math works but Tkinter UI shows the demand is niche. Defer until benchmark comparison is proven useful.
- **Brinson attribution**: OpenBB Open Portfolio is impressive, but it requires reliable TTWROR as a prerequisite. Build sequentially.
- **Drag-drop widget dashboard**: OpenBB Workspace pattern — high complexity sink, wrong for solo operator focus.
- **Mobile / PWA**: Explicitly out of scope per `PROJECT.md`.
- **Psychology diary / annual playbook**: TradeNote's full journaling workflow. Our `JournalPage.tsx` already covers the core; the playbook extension is low-leverage.

---

## Integration Points Summary

| Feature | Files to Modify or Create |
|---------|--------------------------|
| TTWROR + IRR | `engine/analytics.py`, `api/routes/analytics.py`, `PerformancePage.tsx` |
| Benchmark comparison | `engine/analytics.py`, `api/routes/analytics.py`, `PerformancePage.tsx`, position/portfolio settings |
| Target-weight visualization | `db/database.py` (add target_weight column), `portfolio/manager.py`, `api/routes/portfolio.py`, `PortfolioPage.tsx` |
| Rules inventory panel | `api/routes/monitoring.py` (expose named rules), `MonitoringPage.tsx` |
| Calendar heatmap | `PerformancePage.tsx` or `DashboardPage.tsx`, new chart component |
| Riskfolio-Lib integration | `pyproject.toml` (add riskfolio-lib), new `engine/sizing.py`, new `api/routes/sizing.py` |
| Broker CSV import UI | `frontend/src/pages/` (import wizard), `api/routes/portfolio.py` |
| Allocation donut charts | `PortfolioPage.tsx`, no backend changes needed |
| Alert threshold editing | `api/routes/monitoring.py`, `MonitoringPage.tsx` settings panel |

---

## Sources

- Ghostfolio GitHub: https://github.com/ghostfolio/ghostfolio
- Ghostfolio DeepWiki portfolio management: https://deepwiki.com/ghostfolio/ghostfolio/4-portfolio-management
- Ghostfolio X-ray issues: https://github.com/ghostfolio/ghostfolio/issues/3247, https://github.com/ghostfolio/ghostfolio/issues/4477
- Wealthfolio GitHub: https://github.com/afadil/wealthfolio
- Wealthfolio website: https://wealthfolio.app/
- Wealthfolio HN thread (v2.0 launch): https://news.ycombinator.com/item?id=46006016
- Portfolio Performance GitHub: https://github.com/portfolio-performance/portfolio
- Portfolio Performance manual (trades view): https://help.portfolio-performance.info/en/reference/view/reports/performance/trades/
- Portfolio Performance manual: https://help.portfolio-performance.info/en/
- TradeNote GitHub: https://github.com/Eleven-Trading/TradeNote
- InvestBrain GitHub: https://github.com/investbrainapp/investbrain
- OpenBB GitHub: https://github.com/OpenBB-finance/OpenBB
- OpenBB Open Portfolio blog: https://openbb.co/blog/open-portfolio-a-suite-for-asset-managers-on-openbb/
- TradingAgents GitHub: https://github.com/TauricResearch/TradingAgents
- FinRobot GitHub: https://github.com/AI4Finance-Foundation/FinRobot
- Riskfolio-Lib GitHub: https://github.com/dcajasn/Riskfolio-Lib
- Quant Lab Alpha GitHub: https://github.com/husainm97/quant-lab-alpha
- FinanceToolkit GitHub: https://github.com/JerBouma/FinanceToolkit
- rotki GitHub: https://github.com/rotki/rotki
- Beancount/Fava GitHub: https://github.com/beancount/fava
- TradingView Lightweight Charts GitHub: https://github.com/tradingview/lightweight-charts
- Pinnacle GitHub: https://github.com/F4pl0/pinnacle
- Beancount.io features: https://beancount.io/docs/Tips/ui-features
- OpenBB Workspace docs: https://docs.openbb.co/workspace

---

*Analysis date: 2026-04-21*
*Confidence: MEDIUM — GitHub READMEs and documentation verified; actual running UX not screen-tested against live instances. Feature absences are based on documentation review; some features may exist but are undocumented.*
