# Roadmap: Investment Agent — Competitive Parity Milestone

## Overview

This milestone hardens an already-working brownfield system against the liabilities exposed by competitive benchmarking (30+ OSS projects surveyed), then layers in calibrated signal quality, expanded free-tier data coverage, and a UI/analytics uplift that closes the gap with Ghostfolio and Portfolio Performance. The dependency chain is strict: infrastructure correctness first, then metrics that depend on that infrastructure, then data providers that require the Parquet cache, then UI analytics that rely on transaction-cost math.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases: Inserted via `/gsd-insert-phase` if urgent work surfaces mid-milestone

- [x] **Phase 1: Foundation Hardening** - Fix the hardest-failing codebase liabilities before any new capability is layered on top
 (completed 2026-04-21)
- [ ] **Phase 2: Signal Quality Upgrade** - Deepen the thesis/drift moat with calibrated, measurable signal quality and rigorous backtesting
- [ ] **Phase 3: Data Coverage Expansion** - Add free-tier providers and operator-observability so new data flows through a trusted pipeline
- [ ] **Phase 4: Portfolio UI + Analytics Uplift** - Close the UI gap vs. Ghostfolio and Portfolio Performance with accurate performance math and legible dashboards

## Phase Details

### Phase 1: Foundation Hardening
**Goal**: The system's core infrastructure is correct and trustworthy — downloads are fast, backtests are unbiased, the daemon is crash-recoverable, and the database is durable.
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06, FOUND-07
**Success Criteria** (what must be TRUE):
  1. Backtesting 100 tickers no longer serializes on the yfinance lock — wall-clock time for a 100-ticker backtest download drops by at least 50% vs. the baseline, verifiable by timing before and after.
  2. Running a backtest with `backtest_mode=True` causes `FundamentalAgent` to return HOLD with a warning rather than silently injecting restated financials — verifiable by the test suite and a manual log-grep.
  3. Killing the daemon mid-job and restarting produces a `job_run_log` entry with `status='aborted'` for the interrupted job and no orphaned partial signal rows — verifiable by the crash-simulation test.
  4. Disabling any single agent (e.g., removing `ANTHROPIC_API_KEY`) causes the aggregator to renormalize remaining weights to sum to 1.0 and produces correctly-scaled confidence — verifiable via the parametrized unit test.
  5. The analytics page loads in under 1 second against a database containing 50,000 signal history rows, with no `database is locked` errors during a 24-hour soak — verifiable by timing query and reviewing logs.
**Plans**: 3 plans
  - [ ] 01-PLAN-data-provider-caching.md — FOUND-01 (yfinance batch) + FOUND-02 (Parquet OHLCV cache)
  - [ ] 02-PLAN-db-daemon-durability.md — FOUND-06 (WAL + indexes + 90-day prune) + FOUND-07 (job_run_log + atomic tx)
  - [ ] 03-PLAN-signal-math-corrections.md — FOUND-03 (arch block-length) + FOUND-04 (backtest_mode) + FOUND-05 (agent renormalization test)

### Phase 2: Signal Quality Upgrade
**Goal**: Every agent's predictive contribution is measurable, the backtester prices in transaction reality, and tail risk is visible at the portfolio level.
**Depends on**: Phase 1
**Requirements**: SIG-01, SIG-02, SIG-03, SIG-04, SIG-05, SIG-06
**Success Criteria** (what must be TRUE):
  1. `GET /api/v1/analytics/risk` returns a `cvar_95` field (CVaR/Expected Shortfall via QuantStats) and a `portfolio_var` field computed from the position covariance matrix — both verifiable by calling the endpoint and inspecting the JSON response.
  2. `GET /api/v1/analytics/calibration` returns per-agent Brier score and rolling Information Coefficient (IC) — agents with negative IC show reduced weight in the next weight-adapter cycle, verifiable by comparing `WeightsPage` before and after a Brier/IC refresh.
  3. Running a backtest with a non-zero `cost_per_trade` produces a P&L that is strictly lower than the same run with `cost_per_trade=0` — verifiable by running both and diffing the `total_return` field.
  4. The walk-forward backtest scaffold produces per-window out-of-sample Sharpe ratios consumable by `BacktestPage.tsx`, rather than a single in-sample result — verifiable by inspecting the `BacktestResult` JSON for a `walk_forward_windows` array.
**Plans**: 3 plans
  - [ ] 02-01-PLAN.md — SIG-01 (QuantStats CVaR) + SIG-06 (portfolio VaR historical simulation)
  - [ ] 02-02-PLAN.md — SIG-04 (transaction costs) + SIG-05 (walk-forward scaffold + backtest_signal_history)
  - [ ] 02-03-PLAN.md — SIG-02 (Brier) + SIG-03 (IC/IC-IR + weight-adapter feedback; depends on 02-02)
**Research completed**: .planning/phases/02-signal-quality-upgrade/02-RESEARCH.md (2026-04-21) — 30/10/1 walk-forward windows validated against 959 cached AAPL bars; signal_history depth confirmed insufficient for live calibration.

### Phase 3: Data Coverage Expansion
**Goal**: Three new free-tier data sources feed the existing pipeline through the Phase 1 cache infrastructure, and the operator has structured observability into daemon health.
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05
**Success Criteria** (what must be TRUE):
  1. `FundamentalAgent` returns live sector P/E from Finnhub (not the static `SECTOR_PE_MEDIANS` table) when `FINNHUB_API_KEY` is set — verifiable by checking the agent reasoning field for "Finnhub sector P/E" vs. "static median".
  2. With `ANTHROPIC_API_KEY` absent, `SentimentAgent` falls back to FinBERT local inference and still returns a non-HOLD signal for news-rich tickers — verifiable by unsetting the key and running a full analysis.
  3. `FundamentalAgent` includes a Form 4 insider-transaction signal sourced from SEC EDGAR via `edgartools` — verifiable by inspecting `agent_output.reasoning` for an insider-transaction component on a ticker with recent Form 4 filings.
  4. `GET /health` returns daemon last-run timestamps and per-job success/error counts drawn from `job_run_log` — verifiable by calling the endpoint and confirming the JSON schema matches the documented contract.
  5. The daemon process writes a PID file on startup and the API/daemon default bind address is `127.0.0.1`, not `0.0.0.0` — verifiable by inspecting the PID file after launch and confirming `netstat` shows localhost-only binding.
**Plans**: TBD

### Phase 4: Portfolio UI + Analytics Uplift
**Goal**: The dashboard matches table-stakes analytics from Ghostfolio and Portfolio Performance, with accurate return math, a legible daily P&L calendar, and the alert rules engine made visible and toggleable.
**Depends on**: Phase 2
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07
**Success Criteria** (what must be TRUE):
  1. `PerformancePage.tsx` displays True Time-Weighted Return (TTWROR) and IRR per position and for the aggregate portfolio, with a user-selectable SPY benchmark overlay line on the cumulative return chart — verifiable by opening the page with at least two closed positions spanning different periods.
  2. `MonitoringPage.tsx` shows a named rules inventory panel with per-rule enable/disable toggles backed by `GET /api/v1/monitoring/rules` — toggling a rule off prevents that rule from firing in the next daemon run, verifiable by disabling the thesis-drift rule and confirming no thesis-drift alerts in the next job log.
  3. `PortfolioPage.tsx` shows an actual-vs-target deviation bar for each position when a `target_weight` has been set — verifiable by setting a target weight and confirming the bar renders with the correct delta direction and magnitude.
  4. `PerformancePage.tsx` includes a calendar heatmap showing daily P&L colored by positive/negative/neutral, with an interactive tooltip showing exact date and P&L — verifiable by hovering a cell and reading the tooltip value.
  5. `PositionStatus` FSM (`portfolio/models.py`) raises a `ValueError` on invalid transitions (e.g., `closed → monitored`) and the `ENABLE_LLM_SYNTHESIS` flag gates the Bull/Bear synthesis step without breaking the pipeline when the flag is off — both verifiable by the test suite.
**Plans**: TBD
**UI hint**: yes
**Research flag**: TradingView Lightweight Charts vs. Recharts decision for financial time-series (benchmark overlay, calendar heatmap) should be resolved before planning. Run `/gsd-research-phase` before planning Phase 4.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation Hardening | 3/3 | Complete    | 2026-04-21 |
| 2. Signal Quality Upgrade | 0/TBD | Not started | - |
| 3. Data Coverage Expansion | 0/TBD | Not started | - |
| 4. Portfolio UI + Analytics Uplift | 0/TBD | Not started | - |
