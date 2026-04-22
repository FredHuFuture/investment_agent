# Requirements: Investment Agent

**Defined:** 2026-04-21
**Core Value:** Drawdown protection via thesis-aware, regime-aware multi-agent signals — catching when a held position no longer matches the reason it was bought.

> These requirements derive from competitive benchmarking research across 30+ OSS projects. See `.planning/research/SUMMARY.md` for the gap analysis that produced them.

## v1 Requirements

Requirements for this milestone (competitive parity + moat hardening). Each maps to one roadmap phase.

### Foundation (FOUND) — Phase 1: Foundation Hardening

- [x] **FOUND-01**: Replace `_yfinance_lock` serial download with `yfinance.download([list], group_by="ticker")` batch mode to eliminate the 2-call/sec global bottleneck — `data_providers/yfinance_provider.py`
- [x] **FOUND-02**: Add local Parquet OHLCV cache layer with TTL and explicit invalidation — `data_providers/cache.py` (new), integrated into providers
- [x] **FOUND-03**: Replace hardcoded Monte Carlo `block_size=5` with `arch.bootstrap.optimal_block_length()` (Patton-Politis-White) — `engine/monte_carlo.py`
- [x] **FOUND-04**: Add `backtest_mode=True` flag that suppresses restated-fundamentals calls so `FundamentalAgent` cannot silently introduce look-ahead bias — `agents/fundamental.py` + `backtesting/engine.py`
- [x] **FOUND-05**: Agent-weight renormalization guard — when an agent is disabled or returns nothing, remaining weights re-sum to 1.0 — `engine/aggregator.py`
- [x] **FOUND-06**: SQLite WAL mode + covering indexes on hot query paths + 90-day `signal_history` pruning job — `db/database.py` + `daemon/jobs.py`
- [x] **FOUND-07**: `job_run_log` table + atomic transaction boundaries around daemon job writes (no silent partial commits) — `db/database.py` + `daemon/jobs.py` + `daemon/scheduler.py`

### Signal Quality (SIG) — Phase 2: Signal Quality Upgrade

- [x] **SIG-01**: Portfolio-level CVaR / Expected Shortfall via QuantStats — `engine/analytics.py.compute_risk_metrics()`
- [x] **SIG-02**: Brier score for per-agent confidence calibration, stored alongside hit-rate tracking — `tracking/tracker.py`
- [x] **SIG-03**: Rolling Information Coefficient (IC) and IC-IR per agent, consumable by the weight adapter — `tracking/tracker.py` + `engine/weight_adapter.py`
- [x] **SIG-04**: Transaction costs in the backtester (`cost_per_trade` parameter, realistic default; applied in P&L) — `backtesting/engine.py`
- [x] **SIG-05**: Walk-forward backtesting scaffold (training window → out-of-sample validation, rolling) — `backtesting/walk_forward.py` (new)
- [x] **SIG-06**: Portfolio-level VaR using position covariance matrix (not just per-ticker MC) — `engine/analytics.py`

### Data Coverage (DATA) — Phase 3: Data Coverage Expansion

- [x] **DATA-01**: Finnhub provider (live sector P/E, insider, ESG, transcripts) under the existing DataProvider interface with rate-limit + cache — `data_providers/finnhub_provider.py` (new) + `agents/fundamental.py` integration
- [x] **DATA-02**: FinBERT local sentiment fallback when `ANTHROPIC_API_KEY` absent or for cost-sensitive flows, using HuggingFace pipeline — `agents/sentiment.py`
- [x] **DATA-03**: SEC EDGAR insider transactions (Form 4) via `edgartools`, feeding a new signal in `FundamentalAgent` — `data_providers/edgar_provider.py` (new) + `agents/fundamental.py`
- [x] **DATA-04**: Structured JSON logs for API and daemon + `GET /health` endpoint reporting daemon status and job run counts — `api/app.py` + `api/routes/health.py` (new)
- [x] **DATA-05**: Daemon PID file + localhost-only default binding for API/daemon — `daemon/scheduler.py` + `api/app.py` + `run.ps1` / `Makefile`

### Portfolio UI & Analytics (UI) — Phase 4: Portfolio UI + Analytics Uplift

- [x] **UI-01**: True Time-Weighted Return (TTWROR) + IRR per-position and aggregate — `engine/analytics.py` + `api/routes/analytics.py` + `PerformancePage.tsx`
- [x] **UI-02**: Benchmark comparison overlay (SPY default, user-selectable) on performance chart — `engine/analytics.py` + `PerformancePage.tsx`
- [x] **UI-03**: Named rules inventory panel with enable/disable toggles on `MonitoringPage.tsx` (surface the alert rules engine already in code as a legible UI) — `api/routes/monitoring.py` + `MonitoringPage.tsx`
- [x] **UI-04**: Target-weight rebalancing visualization (actual vs. target deviation bars) — `db/database.py` adds `target_weight` column + `PortfolioPage.tsx`
- [x] **UI-05**: Calendar heatmap for daily P&L (TradeNote-style) on `PerformancePage.tsx` — new chart component
- [x] **UI-06**: `PositionStatus` FSM Enum with transition guard (open → closed → reopened rules enforced) — `portfolio/models.py` + `portfolio/manager.py`
- [x] **UI-07**: Opt-in Bull/Bear LLM synthesis step (behind `ENABLE_LLM_SYNTHESIS` flag, falls back to weighted average when off) — `engine/pipeline.py`

## v2 Requirements

Deferred — good ideas, but not needed for this milestone. Tracked so they aren't re-discovered.

### Signal Quality

- **SIG-v2-01**: Calibration plot / reliability diagram (needs months of Brier history first)
- **SIG-v2-02**: Adaptive RSI thresholds, regime-conditioned (needs IC data to validate)
- **SIG-v2-03**: Jesse-style trade-order-shuffle Monte Carlo (block bootstrap already covers scenario diversity)

### Data Coverage

- **DATA-v2-01**: MarketAux news with pre-computed sentiment (supplements existing scraper)
- **DATA-v2-02**: SimFin point-in-time fundamentals (12-month delay; historical only)
- **DATA-v2-03**: CoinGecko GeckoTerminal DEX on-chain data (low urgency vs. equity gaps)

### Portfolio UI & Analytics

- **UI-v2-01**: Allocation donut charts (sector / currency) on `PortfolioPage.tsx`
- **UI-v2-02**: Broker CSV import wizard UI (skeleton exists in `portfolio/manager.py`)
- **UI-v2-03**: Alert-threshold editing in UI (today requires code changes)
- **UI-v2-04**: Riskfolio-Lib position-sizing (Kelly / risk parity / Black-Litterman) — prerequisite is UI-04 target-weight viz
- **UI-v2-05**: QuantStats HTML tearsheet endpoint

### Arch / Deploy

- **DEPLOY-v2-01**: Docker + `docker-compose.yml` for reproducible local setup
- **DEPLOY-v2-02**: OpenTelemetry + Prometheus auto-instrumentation (structured logs + health endpoint sufficient for v1)
- **DEPLOY-v2-03**: `pandas-ta-classic` migration (defer until Pandas 4.x forces the issue)

## Out of Scope

Explicit exclusions. Each has a reason so the decision isn't re-litigated.

| Feature | Reason |
|---------|--------|
| Automated order execution / broker hooks | Out of scope per PROJECT.md — signal+thesis tool only; crossing into execution multiplies regulatory/liability surface |
| Multi-tenant SaaS / account system | Solo-operator this milestone; revisit only if competitive analysis reveals demand |
| Mobile app | Web-first dashboard is enough for this milestone |
| Replacing the six-agent skeleton | Skeleton works and is validated; may add agents but not replace |
| LLM investor-persona agents (Buffett/Munger) | Not calibrated; deterministic agents are more testable |
| RL-based weight optimization (FinRL pattern) | Requires simulator + years of labeled data; cost >> benefit for 6 agents — IC/ICIR path is simpler and more defensible |
| LangGraph orchestration | Adds dependency overhead; `asyncio.gather()` is simpler for deterministic agents — opt-in LLM synthesis (UI-07) is the only LLM touchpoint |
| Glassnode on-chain data | No free tier (Professional+ plan required) — violates free-only constraint |
| Kaiko / Bloomberg / WRDS institutional data | Same free-only constraint |
| Unusual Whales options / dark-pool flow | All providers paid; execution-focused; wrong fit for thesis-tracking tool |
| IEX Cloud | Shut down August 2024 — migrate any references to Tiingo or Finnhub |
| pytrends / Google Trends scraping | Archived April 2025; TOS prohibits automated scraping |
| Real-time tick / level-2 order book | nautilus_trader / freqtrade do this better; requires low-latency infra we don't need for daily-cadence thesis review |
| Drag-drop widget dashboard (OpenBB Workspace pattern) | High complexity sink; wrong fit for solo operator — the 15-page structure already gives depth |
| Brinson performance attribution | Requires TTWROR (UI-01) as prerequisite and delivers niche value — revisit after v1 |
| Fama-French 5-factor exposure | Niche demand; defer |
| Full TradeNote-style psychology diary / annual playbook | `JournalPage.tsx` covers the core already; low leverage here |

## Traceability

Which phases cover which requirements. Filled by the roadmapper.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Complete |
| FOUND-02 | Phase 1 | Complete |
| FOUND-03 | Phase 1 | Complete |
| FOUND-04 | Phase 1 | Complete |
| FOUND-05 | Phase 1 | Complete |
| FOUND-06 | Phase 1 | Complete |
| FOUND-07 | Phase 1 | Complete |
| SIG-01 | Phase 2 | Complete |
| SIG-02 | Phase 2 | Complete |
| SIG-03 | Phase 2 | Complete |
| SIG-04 | Phase 2 | Complete |
| SIG-05 | Phase 2 | Complete |
| SIG-06 | Phase 2 | Complete |
| DATA-01 | Phase 3 | Complete |
| DATA-02 | Phase 3 | Complete |
| DATA-03 | Phase 3 | Complete |
| DATA-04 | Phase 3 | Complete |
| DATA-05 | Phase 3 | Complete |
| UI-01 | Phase 4 | Complete |
| UI-02 | Phase 4 | Complete |
| UI-03 | Phase 4 | Complete |
| UI-04 | Phase 4 | Complete |
| UI-05 | Phase 4 | Complete |
| UI-06 | Phase 4 | Complete |
| UI-07 | Phase 4 | Complete |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-21*
*Last updated: 2026-04-21 after competitive benchmarking research synthesis; traceability confirmed by roadmapper (25/25 requirements mapped)*
