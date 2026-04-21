# Research Summary: Investment Agent -- Competitive Benchmarking

**Project:** Investment Agent
**Domain:** Thesis-aware portfolio monitoring + multi-agent signal generation
**Researched:** 2026-04-21
**Confidence:** MEDIUM (GitHub READMEs and documentation verified; OSS feature absences based on documentation review)

---

## 1. Differentiator Confirmed

The combination of (a) structured thesis capture at entry, (b) continuous per-position drift detection via a six-agent pipeline, and (c) regime-aware signal aggregation with adaptive weights is unique in the OSS landscape. No surveyed competitor across 30+ projects including Ghostfolio (15k stars), TradeNote, Portfolio Performance, TradingAgents, and ai-hedge-fund closes the loop between why a position was opened and whether the current signal still supports that reason.

Specific moat elements no competitor replicates:
- Structured thesis fields (target price, stop loss, time horizon, thesis text) linked to per-position monitoring, not free-text notes
- Daily daemon comparing current agent signal vs. the original thesis parameters (engine/drift_analyzer.py)
- Multi-channel alert delivery (Email + Telegram) -- Ghostfolio, the closest OSS portfolio tracker, delivers in-app notifications only
- Regime-aware signal aggregation with bidirectional threshold optimization (engine/weight_adapter.py)

This moat is worth protecting explicitly. The roadmap should extend the thesis/drift/journal surface before reaching for net-new data integrations.

---

## 2. Must-Borrow Stack

All free-tier compatible and fitting the existing Python/FastAPI/SQLite/React stack.

| # | Capability | Source | Integration Surface | Effort | Priority | Category |
|---|-----------|--------|---------------------|--------|----------|----------|
| 1 | Dynamic block-size via arch.optimal_block_length() | arch lib 6.x https://github.com/bashtage/arch | engine/monte_carlo.py -- replace hardcoded block_size=5 | XS | P0 | signal quality |
| 2 | Agent weight renormalization when agents disabled | Internal fix | engine/aggregator.py lines 150-180 | XS | P0 | signal quality |
| 3 | backtest_mode flag suppressing restated yfinance fundamentals | Internal fix (look-ahead bias) | agents/fundamental.py + backtesting/engine.py | XS | P0 | signal quality |
| 4 | yfinance batch download (yfinance.download with list + group_by=ticker) | FinRL, freqtrade pattern | data_providers/yfinance_provider.py | S | P0 | data |
| 5 | Local Parquet cache layer for OHLCV | freqtrade, lumibot pattern | New data_providers/cache.py (TTL-backed) | S | P0 | data |
| 6 | SQLite WAL indexes + 90-day signal pruning | qlib, freqtrade pattern | db/database.py + daemon/jobs.py | S | P0 | arch/deploy |
| 7 | job_run_log table + atomic daemon transactions | freqtrade, nautilus_trader pattern | db/database.py + daemon/jobs.py + daemon/scheduler.py | S | P0 | arch/deploy |
| 8 | CVaR / Expected Shortfall via quantstats | QuantStats https://github.com/ranaroussi/quantstats | engine/analytics.py -- add compute_risk_metrics() | S | P0 | signal quality |
| 9 | Brier score for agent confidence calibration | Academic consensus / qlib IC pattern | tracking/tracker.py -- extend accuracy tracking | S | P1 | signal quality |
| 10 | Rolling IC/ICIR per agent | qlib https://github.com/microsoft/qlib | tracking/tracker.py + engine/weight_adapter.py | M | P1 | signal quality |
| 11 | Transaction costs in backtester | qlib, freqtrade | backtesting/ -- add cost_per_trade parameter | S | P1 | signal quality |
| 12 | Walk-forward backtesting scaffold | freqtrade, vectorbt https://github.com/polakowo/vectorbt | New backtesting/walk_forward.py | M | P1 | signal quality |
| 13 | Finnhub provider (live sector P/E, insider, ESG, transcripts) | Finnhub free 60 req/min https://finnhub.io/docs/api/ | New data_providers/finnhub_provider.py; agents/fundamental.py | M | P1 | data |
| 14 | FinBERT local sentiment fallback | ProsusAI/finbert Apache 2.0 https://huggingface.co/ProsusAI/finbert | agents/sentiment.py -- check ANTHROPIC_API_KEY; fallback | M | P1 | data |
| 15 | TTWROR + IRR per-position and aggregate | Portfolio Performance / FinanceToolkit pattern | engine/analytics.py + api/routes/analytics.py + PerformancePage.tsx | M | P1 | portfolio/UI |
| 16 | Benchmark comparison overlay (SPY default) | Ghostfolio / Wealthfolio pattern | engine/analytics.py + PerformancePage.tsx | M | P1 | portfolio/UI |
| 17 | Named rules inventory panel + enable/disable toggles | Ghostfolio X-ray https://github.com/ghostfolio/ghostfolio | api/routes/monitoring.py + MonitoringPage.tsx | M | P1 | portfolio/UI |
| 18 | Target-weight rebalancing visualization | Portfolio Performance / Ghostfolio | db/database.py (add target_weight col); PortfolioPage.tsx | S | P1 | portfolio/UI |
| 19 | Calendar heatmap for daily P&L | TradeNote https://github.com/Eleven-Trading/TradeNote | PerformancePage.tsx -- new chart component | S | P1 | portfolio/UI |
| 20 | SEC EDGAR insider transactions via edgartools | edgartools Apache 2.0 https://github.com/dgunning/edgartools | New data_providers/edgar_provider.py; agents/fundamental.py | M | P2 | data |
| 21 | Portfolio-level VaR with covariance matrix | qlib / QuantStats | engine/analytics.py -- pairwise correlation across held positions | M | P2 | signal quality |
| 22 | Bull/Bear LLM synthesis step (opt-in) | TradingAgents, MarketSenseAI arxiv 2502.00415 | engine/pipeline.py -- opt-in post-gather; ENABLE_LLM_SYNTHESIS env flag | M | P2 | signal quality |
| 23 | Structured logs (JSON) + GET /health daemon status endpoint | freqtrade, nautilus_trader pattern | api/app.py + new api/routes/health.py | S | P2 | arch/deploy |
| 24 | Daemon PID file + localhost-only default binding | freqtrade pattern | daemon/scheduler.py + api/app.py + startup scripts | XS | P2 | arch/deploy |
| 25 | PositionStatus FSM Enum with transition guard | freqtrade persistence pattern | portfolio/models.py + portfolio/manager.py | S | P2 | arch/deploy |

---

## 3. Nice-to-Borrow

| Capability | Source | Why Defer | Integration Surface | Effort |
|-----------|--------|-----------|---------------------|--------|
| MarketAux news + pre-computed sentiment | MarketAux https://www.marketaux.com/documentation (100 req/day free) | Supplements existing scraper; not a blocker | data_providers/web_news_provider.py augmentation | S |
| Calibration plot / reliability diagram | Academic pattern | Needs Brier score data first (months of history) | engine/analytics.py + frontend chart | M |
| Adaptive RSI thresholds (regime-conditioned) | vectorbt / freqtrade hyperopt | Needs observability metrics to validate improvement | agents/technical.py + agents/macro.py | M |
| Allocation donut charts (sector/currency) | Ghostfolio pattern | Pure frontend; no backend changes needed | PortfolioPage.tsx -- Recharts PieChart | S |
| Broker CSV import UI | Ghostfolio / Portfolio Performance | Skeleton exists in portfolio/manager.py; UI not complete | Frontend import wizard + api/routes/portfolio.py | M |
| Alert threshold editing in UI | Ghostfolio X-ray | Rules today require code changes to modify thresholds | api/routes/monitoring.py settings panel | M |
| SimFin point-in-time fundamentals | SimFin CC license https://simfin.readthedocs.io/ | 12-month delay; useful only for historical backtests | New data_providers/simfin_provider.py | M |
| Jesse dual Monte Carlo (trade-order shuffle) | jesse https://github.com/jesse-ai/jesse | Block bootstrap already covers scenario diversity | engine/monte_carlo.py | S |
| QuantStats tearsheet integration | QuantStats | Nice visual; depends on analytics extension above | engine/analytics.py + report endpoint | S |
| CoinGecko GeckoTerminal DEX on-chain data | CoinGecko demo 30 req/min https://www.coingecko.com/en/api/ | Low urgency vs. equity gaps | agents/crypto.py augmentation | M |
| Riskfolio-Lib position sizing (Kelly / risk parity) | Riskfolio-Lib https://github.com/dcajasn/Riskfolio-Lib | No UI surface yet; prerequisite is target-weight visualization | New engine/sizing.py + api/routes/sizing.py | L |
| pandas-ta-classic migration | https://github.com/xgboosted/pandas-ta-classic | Still works; defer until Pandas 4.x forces the issue | agents/technical.py import swap | S |
| Docker / docker-compose.yml | freqtrade, jesse pattern | Increases setup friction but not blocking solo development | Root Dockerfile + docker-compose.yml | M |
| OpenTelemetry + Prometheus metrics | opentelemetry-python-contrib | Structured logs + health endpoint sufficient for Phase 1 | api/app.py auto-instrumentation | M |

---

## 4. Anti-Features / Confirmed Out of Scope

| Anti-Feature | Why Skip | What We Do Instead |
|-------------|----------|--------------------|
| LLM investor persona agents (Buffett, Munger style) | Not calibrated; deterministic agents are more testable and reproducible | Extend six-agent structure with IC/Brier signal quality metrics |
| RL for weight optimization (FinRL pattern) | Requires simulator + years of labeled signal data; cost >> benefit for 6-agent system | IC/ICIR-based weight adaptation (qlib pattern) |
| LangGraph orchestration without full LLM agents | Adds dependency overhead; asyncio.gather() is simpler for deterministic agents | Keep asyncio pipeline; add opt-in LLM synthesis step only |
| Glassnode on-chain integration | No free tier; Professional plan + API add-on required | CoinGecko GeckoTerminal for DEX on-chain (free demo tier) |
| Kaiko / Bloomberg / WRDS paid data | Institutional-only; incompatible with free-only constraint | Finnhub + FMP + EDGAR free tiers |
| Automated order execution / broker hooks | Out of scope per PROJECT.md; multiplies regulatory/liability surface | Remain signal + thesis tool only |
| Unusual Whales options / dark pool flow | All providers paid (50+/mo); execution-focused | Out of scope for thesis-tracking tool |
| IEX Cloud | Shut down August 2024 | Migrate any references to Tiingo or Finnhub |
| pytrends Google Trends scraping | Archived April 2025; TOS prohibits automated scraping | Wikipedia pageviews API as future nice-to-have |
| Real-time tick data / level 2 order book | nautilus_trader and freqtrade do this better; requires low-latency infra | Out of scope for daily thesis-review cadence |
| Multi-tenant SaaS / account system | Out of scope this milestone per PROJECT.md | Solo-operator first |
| Drag-drop widget dashboard (OpenBB Workspace pattern) | High complexity sink; wrong for solo operator | 15-page structure provides depth without configurability overhead |
| Brinson performance attribution | Requires reliable TTWROR as prerequisite; do not build out of order | Add TTWROR first; defer attribution |
| Factor exposure (FF5) | Niche demand demonstrated by Quant Lab Alpha Tkinter UI; defer | Not in this milestone |
| Full TradeNote psychology diary / annual playbook | JournalPage.tsx covers the core; low leverage for next milestone | Partial borrow only: structured tag taxonomy + screenshot attachment |

---

## 5. Phase Suggestions

Four coarse phases. Each phase is shippable independently. Order respects the dependency chain:
yfinance batch fix -> faster backtests -> walk-forward validation -> IC-based weight upgrades.

### Phase 1: Foundation Hardening

**Rationale:** Fix the codebase liabilities identified by competitor gap analysis before layering
new capabilities on top. The yfinance serial-lock, hardcoded MC block size, look-ahead bias in
the backtester, and missing daemon crash recovery are all prerequisites for trust in the
signal-quality metrics introduced in Phase 2.

**Ships:**
- Row 4: yfinance batch download (P0 data)
- Row 5: Parquet OHLCV cache layer (P0 data)
- Row 1: arch.optimal_block_length() replacing hardcoded block_size=5 (P0 signal quality)
- Row 3: backtest_mode flag for look-ahead bias (P0 signal quality)
- Row 2: agent weight renormalization guard (P0 signal quality)
- Row 6: SQLite WAL indexes + 90-day signal pruning (P0 arch)
- Row 7: job_run_log table + atomic daemon transactions (P0 arch)

**Pitfalls addressed:** #1 yfinance global lock, #2 APScheduler crash recovery, #3 SQLite WAL
contention, #4 look-ahead bias, #8 weight normalization

**Research flag:** Standard patterns. No phase research needed.

---

### Phase 2: Signal Quality Upgrade

**Rationale:** Extend the thesis/drift moat with calibrated, measurable signal quality. IC/ICIR
and Brier score give per-agent accountability, walk-forward backtesting removes the
single-window bias, and CVaR/VaR surfaces the tail risk competitors ignore. This phase
deepens the core moat before expanding the data surface.

**Ships:**
- Row 8: CVaR / Expected Shortfall via QuantStats (P0 signal quality)
- Row 9: Brier score for agent confidence calibration (P1 signal quality)
- Row 10: Rolling IC/ICIR per agent (P1 signal quality)
- Row 11: Transaction costs in backtester (P1 signal quality)
- Row 12: Walk-forward backtesting scaffold (P1 signal quality)
- Row 21: Portfolio-level VaR with covariance matrix (P2 signal quality)

**Pitfalls addressed:** #9 survivorship bias (walk-forward), #12 static RSI/VIX thresholds
(IC data enables adaptive thresholds in Nice-to-Borrow), #8 weight normalization follow-through

**Research flag:** Walk-forward window sizing and IC significance threshold need validation
against actual signal history length. Consider /gsd-research-phase before implementation.

---

### Phase 3: Data Coverage Expansion

**Rationale:** Expand the free-tier data surface with Finnhub (live sector P/E, transcripts,
insider flow), FinBERT (local sentiment, no API key), and SEC EDGAR (insider transactions).
These close the three largest data gaps vs. competitors while staying free-only. Comes
after Phase 1 because the Parquet cache and rate-limit architecture must be in place
before adding more providers.

**Ships:**
- Row 13: Finnhub provider (P1 data)
- Row 14: FinBERT local sentiment fallback (P1 data)
- Row 20: SEC EDGAR insider transactions via edgartools (P2 data)
- Row 23: Structured JSON logs + GET /health endpoint (P2 arch)
- Row 24: Daemon PID file + localhost-only binding (P2 arch)

**Pitfalls addressed:** #6 observability blind spot (health endpoint), #10 pandas_ta future
warnings mitigated via TA-Lib comparison data

**Research flag:** FinBERT download size (~400 MB) needs first-run UX decision; Finnhub
free-tier commercial use terms should be reviewed before shipping.

---

### Phase 4: Portfolio UI + Analytics Uplift

**Rationale:** Close the UI gap vs. Ghostfolio and Portfolio Performance. TTWROR, benchmark
overlay, and target-weight visualization are table-stakes for a credible portfolio tracker.
Calendar heatmap and named rules panel are differentiator extensions. Comes last because
accurate P&L math requires transaction cost data from Phase 2.

**Ships:**
- Row 15: TTWROR + IRR per-position and aggregate (P1 portfolio/UI)
- Row 16: Benchmark comparison overlay -- SPY default (P1 portfolio/UI)
- Row 17: Named rules inventory panel + enable/disable toggles (P1 portfolio/UI)
- Row 18: Target-weight rebalancing visualization (P1 portfolio/UI)
- Row 19: Calendar heatmap for daily P&L (P1 portfolio/UI)
- Row 25: PositionStatus FSM Enum with transition guard (P2 arch)
- Row 22: Bull/Bear LLM synthesis step opt-in (P2 signal quality) -- if chart lib and
  LLM provider questions are resolved

**Pitfalls addressed:** #5 position lifecycle fragmentation (FSM), #3 SQLite write contention
from high-frequency UI queries (index work extends Phase 1 coverage)

**Research flag:** TradingView Lightweight Charts vs. Recharts for financial time-series is
an open question. Recommend /gsd-research-phase before starting PerformancePage.tsx work.

---

## 6. Open Questions

These are unresolved decisions that will surface during phase planning:

1. **Chart library for financial time-series:** TradingView Lightweight Charts (MIT, 10k stars,
   candlestick-native) vs. extending Recharts (already in the project). Decision affects
   PerformancePage.tsx architecture. Recommend resolving before Phase 4 kickoff.

2. **LLM provider for Bull/Bear synthesis (Row 22):** Claude API vs. local Ollama vs. skip.
   TradingAgents uses GPT-4o/DeepSeek; cost and latency differ 10x. This is opt-in, but the
   provider decision shapes the env-flag design. Resolve during Phase 4 scoping.

3. **Walk-forward window sizing:** qlib uses 252-day training + 63-day validation windows.
   Our signal history depth is unknown -- if < 2 years, windows need adjustment. Check
   signal_history table row count before Phase 2 design.

4. **Finnhub commercial use terms:** Free tier is labeled "Non-commercial use only" in some
   plan descriptions. Verify before shipping the Finnhub provider in Phase 3.

5. **pandas-ta-classic migration timing:** Current pandas_ta emits FutureWarnings on
   Pandas 3.x. pandas-ta-classic is a drop-in fork. Defer migration until Pandas 4.x
   forces the issue (estimated 2026), or pull it into Phase 1 if warnings escalate to errors.

6. **SimFin 12-month delay acceptability:** SimFin point-in-time data has a 12-month embargo
   on the free CC license. Useful only for historical backtest validation, not live signals.
   Confirm use case before adding the provider.

7. **Docker / docker-compose timing:** Containerization adds setup polish but increases
   iteration friction during active development. Defer to end of Phase 3 or after milestone
   is feature-complete.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack (signal quality libs) | MEDIUM-HIGH | arch, quantstats, edgartools are well-documented with active maintainers; FinBERT Apache 2.0 verified |
| Features (competitor gap analysis) | MEDIUM | Based on README and documentation review of 30+ projects; feature absences may not reflect unreleased work |
| Architecture (integration surfaces) | MEDIUM | File paths and function signatures inferred from commit history and existing test suite; no runtime verification |
| Pitfalls (risk catalog) | MEDIUM-HIGH | yfinance lock, look-ahead bias, and APScheduler patterns are well-documented failure modes with community precedent |

**Overall: MEDIUM**

The competitor feature gap analysis is the weakest link -- documentation review cannot rule out
features that exist but are undocumented, or features in active development. The technical
integration surfaces are medium-confidence because they were inferred from commit messages and
file names, not live code inspection of all relevant modules.

---

## Gaps to Address

1. **Chart library decision** -- TradingView vs. Recharts tradeoff needs a focused spike before
   Phase 4 work starts on PerformancePage.tsx.

2. **IC significance threshold** -- what p-value / minimum IC magnitude should trigger weight
   adjustment? Academic literature suggests |IC| > 0.05 but this needs calibration to the
   six-agent system specifically.

3. **Walk-forward history sufficiency** -- signal_history table row count and date range must be
   checked before designing the walk-forward scaffold window sizes.

4. **FinBERT first-run experience** -- 400 MB model download on first sentiment call will
   surprise users. Need a download-progress indicator or a prefetch install step.

---

## Sources

### Primary (direct code/documentation review)
- Ghostfolio: https://github.com/ghostfolio/ghostfolio
- TradingAgents: https://github.com/TauricResearch/TradingAgents
- ai-hedge-fund: https://github.com/virattt/ai-hedge-fund
- OpenBB: https://github.com/OpenBB-finance/OpenBB
- qlib: https://github.com/microsoft/qlib
- freqtrade: https://github.com/freqtrade/freqtrade
- vectorbt: https://github.com/polakowo/vectorbt
- jesse: https://github.com/jesse-ai/jesse
- TradeNote: https://github.com/Eleven-Trading/TradeNote
- nautilus_trader: https://github.com/nautechsystems/nautilus_trader
- QuantStats: https://github.com/ranaroussi/quantstats
- arch: https://github.com/bashtage/arch
- edgartools: https://github.com/dgunning/edgartools
- ProsusAI/finbert: https://huggingface.co/ProsusAI/finbert
- Portfolio Performance: https://github.com/portfolio-performance/portfolio
- Wealthfolio: https://github.com/afadil/wealthfolio
- Riskfolio-Lib: https://github.com/dcajasn/Riskfolio-Lib

### Secondary (API documentation and data provider terms)
- Finnhub API docs: https://finnhub.io/docs/api/
- CoinGecko demo API: https://www.coingecko.com/en/api/
- MarketAux API: https://www.marketaux.com/documentation
- SimFin API: https://simfin.readthedocs.io/

### Tertiary (academic / benchmark references)
- MarketSenseAI: https://arxiv.org/abs/2502.00415
- IC/ICIR methodology: qlib documentation + academic literature on information coefficient
- Block bootstrap optimal block size: Politis & White (2004) via arch library implementation

---

*Last updated: 2026-04-21 -- competitive benchmarking research synthesis*
