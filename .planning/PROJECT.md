# Investment Agent

## What This Is

An "investment journal that fights back" — a personal investing system that tracks the thesis behind every position, monitors six specialized analysis agents (Technical, Fundamental, Macro, Crypto, Sentiment, Summary) continuously, and alerts the user when reality diverges from the original plan. Local-first Python/FastAPI backend + React/TypeScript dashboard. Solo-operator scope. v1.0 "Competitive Parity" shipped 2026-04-22 — benchmark-grade analytics (TTWROR/IRR, CVaR, portfolio VaR, benchmark overlay, calendar heatmap), calibrated signal quality (Brier, IC/IC-IR, walk-forward backtesting, transaction costs), expanded free-tier data coverage (Finnhub + FinBERT + SEC EDGAR), operator observability (`GET /health` + structured JSON logs), and daemon hardening (`job_run_log` + PID file + localhost bind).

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
- ✓ QuantStats historical-simulation CVaR (95% + 99%) + portfolio-level VaR in `engine/analytics.py` (matplotlib-safe via sys.modules stub) — Phase 2 (SIG-01, SIG-06)
- ✓ Brier score (one-vs-rest binary, HOLD excluded, N≥20) + rolling IC (time-series Pearson on `raw_score`, 5-day forward, N≥30) + IC-IR (60-obs rolling) in `tracking/tracker.py` — Phase 2 (SIG-02, SIG-03)
- ✓ Negative-IC agents lose weight via `max(0, IC-IR/2.0)` scaling in `engine/weight_adapter.py` — Phase 2 (SIG-03)
- ✓ `GET /api/v1/analytics/calibration` endpoint with stable `ic_5d` key + `ic_horizon` sibling + `preliminary_calibration` + `survivorship_bias_warning` flags — Phase 2 (SIG-03)
- ✓ Backtester transaction costs (10 bps equities / 25 bps crypto, applied at entry AND exit) with `total_costs_paid` / `n_trades` / `cost_drag_pct` in `BacktestResult.metrics` — Phase 2 (SIG-04)
- ✓ Walk-forward backtesting scaffold (30-day train / 10-day OOS, `purge_days=1` Sharpe-only / `purge_days=5` IC-feeding) in `backtesting/walk_forward.py` — Phase 2 (SIG-05)
- ✓ `backtest_signal_history` corpus table + `populate_signal_corpus` + `rebuild_signal_corpus` daemon job (dynamic date derivation + DELETE rollback on error, honors FOUND-07) — Phase 2 (SIG-05)
- ✓ Finnhub data provider with peer-basket sector P/E (5 proxy tickers, median, sanity filter) under 60/min rate limit — Phase 3 (DATA-01)
- ✓ FinBERT local sentiment fallback (Apache 2.0, `[llm-local]` optional extra, lazy-import safe) when `ANTHROPIC_API_KEY` absent — Phase 3 (DATA-02)
- ✓ SEC EDGAR Form 4 insider-transaction signal (90-day lookback, 3-transaction minimum, ±0.10 composite tilt) in `FundamentalAgent` — Phase 3 (DATA-03)
- ✓ `GET /health` endpoint reading `job_run_log` (24h counts, stale detection, uptime via PID mtime, WAL mode check) + stdlib JSON logging — Phase 3 (DATA-04)
- ✓ Daemon PID file + cross-platform stale detection via `os.kill(pid, 0)` + `atexit` cleanup + API/uvicorn pinned to `--host 127.0.0.1` — Phase 3 (DATA-05)
- ✓ TTWROR + IRR (closed-form + scipy.brentq for multi-cashflow) in `engine/analytics.py` + `GET /analytics/returns` — Phase 4 (UI-01)
- ✓ SPY benchmark overlay with SSRF-safe allowlist (`frozenset{"SPY","QQQ","TLT","GLD","BTC-USD"}`) enforced at API layer — Phase 4 (UI-02)
- ✓ `AlertRulesPanel` with "Built-in" badge + daemon wiring (`monitoring/monitor._load_enabled_rules` reads `alert_rules WHERE enabled=1`) — toggling a rule off stops it firing in the next daemon run — Phase 4 (UI-03)
- ✓ `target_weight` column + `PATCH /portfolio/positions/{ticker}/target-weight` + `TargetWeightBar` frontend component — Phase 4 (UI-04)
- ✓ Daily P&L calendar heatmap (custom SVG + Tailwind, keyboard-accessible, 52-week grid) in `DailyPnlHeatmap.tsx` — Phase 4 (UI-05)
- ✓ `PositionStatus(Enum)` + `VALID_TRANSITIONS` dict + `validate_status_transition` FSM guard reading actual row status (not hardcoded) in `portfolio/manager.py::close_position` — Phase 4 (UI-06)
- ✓ Opt-in Bull/Bear LLM synthesis (`ENABLE_LLM_SYNTHESIS` flag, default off) in `engine/llm_synthesis.py` with FOUND-04 backtest_mode short-circuit as FIRST check, PII-safe prompt (no $ amounts, no thesis_text, confidence bucketed to 10%), (ticker, asset_type, date)-keyed cache — Phase 4 (UI-07)

### Active — v1.1 Live Validation

<!-- Current milestone: transition from "ships clean code" to "actually used weekly for 5-10 US equity positions" with signal noise surfaced and actionable. -->

**LIVE** — Live data & calibration
- [x] **LIVE-01**: `POST /analytics/calibration/rebuild-corpus` endpoint + `corpus_rebuild_jobs` table + `_run_batch_rebuild` background task (per-ticker FOUND-07 delegation, outer exception guard, error_message on all non-success paths) — Phase 5
- [ ] **LIVE-02**: `CalibrationPage.tsx` — per-agent Brier, rolling IC, IC-IR + 90-day sparkline; becomes home of weekly review
- [ ] **LIVE-03**: Agent weight management UI (apply IC-IR weights button + per-agent manual override)
- [ ] **LIVE-04**: Weekly digest (scheduled Sundays 18:00, Markdown render, email opt-in)

**CLOSE** — v1.0 human-UAT closeout
- [x] **CLOSE-01**: FinBERT live test on real headlines — `tests/test_close_01_finbert_live.py` with `importlib.util.find_spec` lazy guard + operator script; `03-HUMAN-UAT.md` flipped to `resolved` — Phase 5
- [x] **CLOSE-02**: Live Finnhub API round-trip — `tests/test_close_02_finnhub_live.py` with `FINNHUB_API_KEY` skipif guard + sector_pe_cache singleton reset + operator script — Phase 5
- [x] **CLOSE-03**: Daemon PID + `netstat 127.0.0.1` verification — `tests/test_close_03_daemon_pid_live.py` subprocess test (natural exit for atexit on Windows/POSIX) + operator script — Phase 5
- [ ] **CLOSE-04**: Target-weight browser flow
- [ ] **CLOSE-05**: Rules panel toggle → daemon log exclusion
- [ ] **CLOSE-06**: DailyPnlHeatmap tooltip

**AN** — Analytics completeness
- [ ] **AN-01**: Dividend-aware IRR
- [ ] **AN-02**: Signal drift detector (alert + auto weight scale when IC-IR drops)

## Current Milestone: v1.1 Live Validation

**Goal:** Transition from "ships clean code" to "actually used weekly for 5-10 US equity positions" — with signal noise surfaced, triaged, and actionable.

**Target features:**
- Live corpus + calibration (Brier/IC/IC-IR produce real numbers for the user's actual portfolio)
- CalibrationPage + WeightsPage UIs so the user SEES which agents are noisy this week
- Weekly digest as the canonical weekly-review artifact
- Close 6 v1.0 human-UAT items so "partial" UATs flip to "resolved"
- Dividend-aware IRR for dividend-paying equities
- Signal drift detection with auto weight scaling

### Human-UAT closeout (promoted into v1.1 scope as CLOSE-01..06)

The 6 deferred v1.0 items are now REQ-IDs `CLOSE-01` through `CLOSE-06` in the v1.1 Active list above — see `.planning/REQUIREMENTS.md` for full detail. Source records at `.planning/milestones/v1.0-phases/03-data-coverage-expansion/03-HUMAN-UAT.md` and `.planning/milestones/v1.0-phases/04-portfolio-ui-analytics-uplift/04-HUMAN-UAT.md`.

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
| Phase 2 ROADMAP SC-1 wording amended from "position covariance matrix" to "cross-position correlation awareness (historical simulation on portfolio returns)" | Tier 1 historical simulation IS correlation-aware (portfolio returns capture cross-position correlations naturally); Tier 2 covariance-matrix decomposition requires longer signal history than current 10-row `signal_history` supports — deferred to v2 | ✓ Good — Phase 2 verified passing (4/4 criteria, 70 regressions, 0 gaps) |
| Phase 2 calibration uses backtester-generated corpus (`backtest_signal_history`) not live `signal_history` | Live `signal_history` has only 10 rows (single day); walk-forward + Brier + IC need 30+ observations per agent; backtester generates years of synthetic signals against cached prices | ✓ Good — corpus table + `populate_signal_corpus` shipped; Phase 3 will populate AAPL 2022-2025 corpus manually |
| Phase 2 walk-forward windows: 30/10/5 (IC-feeding) vs 30/10/1 (Sharpe-only); labeled `preliminary_calibration: true` | Standard qlib windows (252/63) require 500+ days of signal history; current corpus supports shorter windows; flag plumbed to API so Phase 4 UI can surface caveat | — Revisit to 252/63 once live signal_history accumulates 2+ years |
| Phase 3 Finnhub uses peer-basket sector P/E (5 hardcoded proxy tickers per sector, median) | Finnhub free tier doesn't expose sector aggregate endpoints; peer basket is pragmatic and cheap (5 calls per sector, cached 24h) | ✓ Good — Phase 3 verified passing (5/5 criteria, 3 items deferred to human-UAT) |
| Phase 3 FinBERT gated behind `[llm-local]` optional extra (`transformers>=4.30`, `torch>=2.0`) | Default install stays ~50 MB; FinBERT + PyTorch is ~400 MB and most users won't need the local fallback | ✓ Good — lazy-import verified: `import agents.sentiment` does NOT pull transformers |
| Phase 3 `edgartools` added to CORE dependencies (not optional) | Pure-Python Apache 2.0, small footprint, required by DATA-03 insider signal which is not optional | ✓ Good — tests use `sys.modules` monkeypatch so CI doesn't need SEC network calls |
| Phase 3 `/health` uptime derived from PID file mtime (not job_run_log) | WR-01 review finding: oldest-running job is `null` during idle periods, misleading to monitors; PID mtime is a reliable daemon-alive signal | ✓ Good — WR-01 fixed in review-fix pass |
| Phase 3 `daemon.start()` calls `reconcile_aborted_jobs(min_age_seconds=300)` explicitly | WR-03 review: 5s default would false-positive-abort jobs legitimately running 1-5 min; 300s aligns with `/health` stale threshold and normal job budget | ✓ Good — WR-03 fixed |
| Phase 4 reuses both existing chart libs (Recharts for analytics, LightweightCharts for candlestick) — NO migration | Both were already in `package.json`; migrating would cost ~600 lines of test churn for zero user-visible benefit; custom SVG+Tailwind for heatmap (no third chart lib) | ✓ Good — Phase 4 verified 5/5 criteria, 400 frontend tests passing, 0 regressions |
| Phase 4 UI-07 LLM synthesis: FOUND-04 backtest_mode short-circuit is the FIRST check — before `ENABLE_LLM_SYNTHESIS`, before API key lookup, before client init | Research warned missing this would cost ~$2.78/ticker on a 3-year daily backtest (~750 Anthropic calls/ticker). The FIRST-check ordering is a regression-test assertion: `mock_client.messages.create.call_count == 0` | ✓ Good — `test_synthesis_skipped_in_backtest_mode` passing |
| Phase 4 UI-07 LLM prompt PII clamp: ticker + signal label + regime + confidence bucketed to 10% only; NO dollar amounts, NO thesis_text, NO portfolio_id | Prompt-injection via thesis text + PII exposure via dollar amounts are the two highest-risk LLM attack surfaces for a personal investing tool; bucketing confidence is sufficient signal without exposing precise figures | ✓ Good — `test_prompt_excludes_pii` passing |
| Phase 4 WR-01 fix: `ap.target_weight` added to `load_portfolio` + `get_all_positions` SELECT queries | Review found PATCH succeeded but GET never returned the value — frontend could never display a set target. Real functional bug, not a style nit | ✓ Good — regression test added that PATCHes then GETs and asserts equality |
| v1.1 Live Validation: narrow scope to 5-10 US equities + weekly cadence + signal-noise-as-top-risk | User explicitly chose weekly review + research workflow; "signals too noisy" as the top rough edge. This scope prioritizes calibration visibility (CalibrationPage) and action-surfacing (WeightsPage + drift detector) over deploy/UX/crypto breadth — which move to v1.2, v1.3, v1.4 respectively | — Pending v1.1 execution |
| v1.1 promotes 6 v1.0 human-UAT items to REQ-IDs CLOSE-01..06 | Carrying "partial" UATs across milestones is tech debt; making closure a first-class requirement ensures the 6 external-integration validations actually get done before v1.2 builds on assumed-good foundations | — Pending v1.1 execution |
| v1.1 skips phase research | All features extend existing v1.0 systems (calibration endpoint + Brier/IC math + notification channels + backtest corpus builder); standard patterns apply; no new technical domain | — Pending v1.1 execution |

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
*Last updated: 2026-04-23 after v1.1 Phase 5 (Corpus Population + Live Data Closeout) completion — LIVE-01, CLOSE-01..03 shipped; live corpus population queued as human-UAT*
