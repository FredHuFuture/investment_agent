# Investment Agent

## What This Is

An "investment journal that fights back" — a personal investing system that tracks the thesis behind every position, monitors six specialized analysis agents (Technical, Fundamental, Macro, Crypto, Sentiment, Summary) continuously, and alerts the user when reality diverges from the original plan. Built as a local-first Python/FastAPI backend with a React/TypeScript dashboard; solo-operator focus today, with intent to benchmark against the broader OSS investment-agent landscape.

## Core Value

**Drawdown protection via thesis-aware, regime-aware multi-agent signals** — if one thing must work, it is catching when a held position no longer matches the reason it was bought.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Inferred from existing codebase (commits through 25f2bbc, 889 passing tests, 15 frontend pages). -->

- ✓ Multi-agent analysis pipeline (Technical / Fundamental / Macro / Crypto / Sentiment / Summary) — existing
- ✓ Regime-aware signal aggregator with adaptive weights — existing (`engine/signal_aggregator.py`, `engine/weight_adapter.py`)
- ✓ Thesis capture at entry + drift monitoring + alerting — existing (`monitoring/`, `notifications/`)
- ✓ Multi-asset data providers (YFinance / FRED / CCXT / news scrapers) with cache + rate-limit + pool — existing (`data_providers/`)
- ✓ Backtesting with regime context and block-bootstrap Monte Carlo — existing (`backtesting/`, `engine/monte_carlo.py`)
- ✓ FastAPI REST surface with APScheduler daemon for continuous revaluation — existing (`api/`, `daemon/`)
- ✓ SQLite + aiosqlite connection pooling — existing (`db/`)
- ✓ 15-page React/TS dashboard ("Modern Craft" design system), export hub, alert rules engine, portfolio health score, journal insights — existing (Sprint 38 work, `frontend/`)
- ✓ 889 passing tests across backend + frontend — existing
- ✓ yfinance batch download + Parquet OHLCV cache (Windows-safe atomic writes + stampede-resistant) — Phase 1 (FOUND-01, FOUND-02)
- ✓ Auto-selected Monte Carlo block size via `arch.optimal_block_length()` — Phase 1 (FOUND-03)
- ✓ `backtest_mode` flag on `AgentInput` prevents look-ahead bias via restated fundamentals — Phase 1 (FOUND-04)
- ✓ Agent-weight renormalization proven by 12-case parametrized test across stock/btc/eth — Phase 1 (FOUND-05)
- ✓ SQLite WAL mode + covering indexes + 90-day signal_history pruning — Phase 1 (FOUND-06)
- ✓ `job_run_log` four-state machine + atomic daemon transactions + startup reconciliation — Phase 1 (FOUND-07)

### Active

<!-- Next milestone work: Phase 2 Signal Quality Upgrade. -->

- [ ] Phase 2: Signal Quality Upgrade (SIG-01..06) — CVaR / Brier / IC-ICIR / transaction costs / walk-forward / portfolio VaR
- [ ] Phase 3: Data Coverage Expansion (DATA-01..05) — Finnhub / FinBERT / SEC EDGAR / structured logs + health endpoint / daemon PID + localhost bind
- [ ] Phase 4: Portfolio UI + Analytics Uplift (UI-01..07) — TTWROR+IRR / benchmark overlay / named rules panel / target-weight viz / calendar heatmap / PositionStatus FSM / opt-in Bull-Bear synthesis

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Automated order execution / broker integration — this is a thesis + signal tool, not an execution venue; crossing that line multiplies regulatory, safety, and liability surface.
- Multi-tenant SaaS / account system — stays solo-operator for this milestone; revisit only after competitive analysis confirms demand.
- Mobile app — dashboard is web-first for this milestone.
- Replacing the six-agent structure — we may add agents but the Technical/Fundamental/Macro/Crypto/Sentiment/Summary skeleton stays.

## Context

**Technical environment:**
- Python 3.11+ backend (FastAPI, APScheduler, aiosqlite, pandas, pandas_ta, yfinance, CCXT, FRED, custom news scrapers)
- React + TypeScript + Vite frontend, 15 pages, "Modern Craft" editorial design system
- SQLite with connection pooling; local-first deployment
- Windows + macOS/Linux dev (PowerShell + Makefile parity)
- 889 passing tests (pytest backend + Vitest frontend)

**Prior work and recent state (last ~5 commits):**
- 25f2bbc — frontend redesign (Modern Craft design system)
- 5cbd1c9 — 9 prediction accuracy improvements across 3 priority tiers
- 159cd93 — code quality, caching, rate limiting, connection pool, logging
- aaeb90b — critical prediction model review, 15 issues fixed across 9 files (RSI trend-context, sector P/E, VIX normalization, block-bootstrap MC, bidirectional weight optimization, crypto weight redistribution)

**Known tech debt (from `.planning/codebase/CONCERNS.md`):**
- Position lifecycle fragmented across `active_positions` / `trade_records` / `signal_history` — complex joins
- `pandas_ta` emits Pandas 3.x FutureWarnings — waiting on upstream
- yfinance thread-safety lock serializes all equity downloads (2 calls/s cap)
- Residual risks from aaeb90b fixes: hardcoded RSI thresholds, static sector P/E medians, fixed MC block size, static VIX SMA window

**User framing:**
Brownfield project with substantial momentum; the user wants to ground the next milestone in a competitive scan of similar OSS projects rather than guessing what to build next.

## Constraints

- **Tech stack**: Python 3.11+ backend / React+TS frontend / SQLite — new features must fit this stack unless a strong case is made.
- **Deployment**: Local-first (single-user) for this milestone — don't design anything that assumes multi-tenant.
- **Safety**: No order execution / broker APIs this milestone (Out of Scope).
- **Test discipline**: 889-test bar is the floor; features ship with tests.
- **Data costs**: Free/community data providers only (YFinance, FRED, CCXT, scrapers) — no paid market-data subscriptions assumed.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Run a full OSS competitive scan before committing roadmap phases | User wants borrowable ideas + integrations identified, not guessed at | ✓ Good — surfaced 25 borrowable items across 30+ projects |
| Stay solo-operator, no SaaS or mobile this milestone | Focus on product depth over distribution surface | — Pending |
| Keep six-agent skeleton; add but don't replace | The skeleton is working and validated | — Pending |
| Ship Phase 1 infrastructure-first (yfinance batch, WAL, atomic daemon, arch, backtest_mode) before Phase 2 signal-quality work | Research flagged yfinance lock + look-ahead bias + hardcoded MC block size as hardest-failing liabilities that Phase 2 metrics would trust without fixing first | ✓ Good — Phase 1 verified passing (5/5 criteria, 143 tests, 0 regressions) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-21 after Phase 1 (Foundation Hardening) completion*
