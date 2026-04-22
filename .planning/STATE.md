---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 04-01-PLAN.md (TTWROR + IRR + benchmark allowlist + daily P&L heatmap)
last_updated: "2026-04-22T06:43:54.548Z"
last_activity: 2026-04-22
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 14
  completed_plans: 11
  percent: 79
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-21)

**Core value:** Drawdown protection via thesis-aware, regime-aware multi-agent signals — catching when a held position no longer matches the reason it was bought.
**Current focus:** Phase 4 — Portfolio UI + Analytics Uplift

## Current Position

Phase: 4 (Portfolio UI + Analytics Uplift) — EXECUTING
Plan: 2 of 4
Status: Ready to execute
Last activity: 2026-04-22

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 10
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | - | - |
| 2 | 3 | - | - |
| 3 | 4 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01 P01 | 502 | 3 tasks | 6 files |
| Phase 01 P02 | 1620 | 3 tasks | 5 files |
| Phase 01 P03 | 1135 | 3 tasks | 8 files |
| Phase 02 P01 | 1320 | 3 tasks | 5 files |
| Phase 02-signal-quality-upgrade P02 | 2400 | 3 tasks | 9 files |
| Phase 02-signal-quality-upgrade P03 | 2400 | 3 tasks | 8 files |
| Phase 03-data-coverage-expansion P01 | 395 | 2 tasks | 4 files |
| Phase 03-data-coverage-expansion P02 | 420 | 2 tasks | 5 files |
| Phase 03-data-coverage-expansion P04 | 1107 | 3 tasks | 9 files |
| Phase 03-data-coverage-expansion P03-03 | 376 | 2 tasks | 4 files |
| Phase 04 P01 | 2475 | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: 4-phase coarse structure validated against SUMMARY.md dependency chain. No deviation from research recommendation.
- Roadmap: Phase 2 and Phase 4 flagged for `/gsd-research-phase` before planning (walk-forward window sizing; chart library decision).
- Roadmap: DATA-04 and DATA-05 (structured logs, PID file, localhost binding) placed in Phase 3 rather than Phase 1 — they are observability/hardening features but depend on the Phase 1 `job_run_log` table being in place first (DATA-04 reads from it).
- [Phase 01]: _yfinance_lock preserved for Ticker.info paths; batch download bypasses lock safely via yf.download list+threads=True
- [Phase 01]: ParquetOHLCVCache is synchronous (not async) — file I/O for OHLCV is fast and keeps the API simple
- [Phase 01]: parquet_cache=None default ensures CachedProvider is 100% backward-compatible with all existing callers
- [Phase 01]: Two-connection log-vs-transaction pattern: log_conn for job_run_log INSERT/UPDATE committed independently; main job on separate conn with BEGIN/COMMIT/ROLLBACK so a job ROLLBACK cannot erase the audit row (SC-3 compliance)
- [Phase 01]: daemon_runs table preserved for backwards compat; job_run_log is additive audit with 'running'/'aborted' states that daemon_runs cannot express
- [Phase 01]: Phase 3 DATA-04 followup: job_run_log error_message writes raw str(exc) — scrubbing deferred to DATA-04 structured logs plan
- [Phase 01]: arch imported locally inside _auto_select_block_size (not at module top) — defensive against future arch absence without breaking Monte Carlo imports
- [Phase 01]: data_completeness=0.0 in backtest_mode HOLD return ensures aggregator weight renormalization fully excludes FundamentalAgent contribution
- [Phase 01]: backtest_mode=True threaded into Backtester.run() as the single source of truth — agents cannot accidentally use restated data in historical loops
- [Phase 02]: Headless-safe quantstats import: pre-stub quantstats.plots/reports/._plotting in sys.modules before package init to prevent matplotlib/seaborn leak on API/daemon startup
- [Phase 02]: Positive-loss sign convention: negate QuantStats negative floats * 100 to match existing var_95/cvar_95 consumers
- [Phase 02]: Tier 1 portfolio_var = var_95 identity: both historical-sim VaR at 95% on portfolio return series — cross-position correlations naturally embedded in realized returns
- [Phase 02-signal-quality-upgrade]: Dual-constructor Backtester: isinstance(BacktestConfig) gate detects config vs provider, enabling Backtester(provider).run(cfg) pattern for walk_forward and signal_corpus
- [Phase 02-signal-quality-upgrade]: purge_days defaults: generate_walk_forward_windows=1 (Sharpe-only); run_walk_forward=5 (IC-feeding 5-day forward return horizon for SIG-03 per 02-RESEARCH.md Q4)
- [Phase 02-signal-quality-upgrade]: rebuild_signal_corpus not cron-registered: corpus rebuild expensive (~1 min/ticker); on-demand only via direct import or future CLI/API endpoint
- [Phase 02-signal-quality-upgrade]: asyncio_mode=auto: seeding helpers are async def coroutines awaited directly — no asyncio.run() wrappers in tests
- [Phase 02-signal-quality-upgrade]: IC test tolerance ±0.08 for N=100: SE of Pearson r is 1/sqrt(N)=0.10 at N=100; ±0.05 is too tight
- [Phase 02-signal-quality-upgrade]: Weight sum tolerance 1e-3 for 4dp-rounded weights: round(v/total,4) accumulates rounding error
- [Phase 03-data-coverage-expansion]: Peer-basket sector P/E derivation (5 proxy tickers/sector) for Finnhub — free tier has no sector-aggregate endpoint; median of N=5 resists single poisoned value
- [Phase 03-data-coverage-expansion]: Sibling get_sector_pe_source() pattern keeps get_sector_pe_median() return type float|None backward-compatible while exposing source provenance for reasoning strings
- [Phase 03-data-coverage-expansion]: Priority-1 Finnhub inside sector_pe_cache.py (not fundamental.py) — single integration point; yfinance ETF + static table remain as fallback tiers
- [Phase 03-data-coverage-expansion]: [llm-local] added to [all] extra — give-me-everything intent includes local LLM; ~400 MB size noted in pyproject.toml comment
- [Phase 03-data-coverage-expansion]: HOLD confidence fixed at 40.0 when below FinBERT threshold — matches plan spec and existing codebase HOLD@40 convention for insufficient data
- [Phase 03-data-coverage-expansion]: _FINBERT_IMPORT_ATTEMPTED is process-level global (not instance) — import check happens once per process; pipeline cached on instance for resource lifecycle
- [Phase 03-data-coverage-expansion]: JsonFormatter in api/log_format.py shared by API and daemon -- single import location, no new deps
- [Phase 03-data-coverage-expansion]: C:/Program Files/Git/health always returns HTTP 200 with status=degraded on DB failure so external monitors distinguish api-up-db-down from api-down
- [Phase 03-data-coverage-expansion]: uptime_seconds = MIN(running started_at) proxy accepted; true monotonic uptime requires shared state file (deferred)
- [Phase 03-data-coverage-expansion]: edgartools added to core [project.dependencies] — pure-Python Apache 2.0, insider data is v1 differentiator not opt-in
- [Phase 03-data-coverage-expansion]: Insider tilt applied AFTER value/quality/growth weighted average — orthogonal lever prevents insider data from distorting valuation ratios
- [Phase 03-data-coverage-expansion]: _MIN_TRANSACTIONS_FOR_REASONING=3 defined locally in fundamental.py to avoid import-time dependency on edgar_provider
- [Phase 04]: TTWROR returns decimal from compute_ttwror(); get_ttwror_irr() multiplies by 100 for percentage display
- [Phase 04]: Aggregate IRR uses closed-form single-window; multi-cashflow aggregate IRR deferred to UI-v2
- [Phase 04]: VALID_BENCHMARKS type-annotated as frozenset[str]; daily P&L uses last-of-day semantics

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 2 planning requires checking `signal_history` table row count and date range before designing walk-forward window sizes (qlib default: 252-day train + 63-day validation; may need adjustment if history is < 2 years).
- Finnhub free-tier commercial-use terms should be reviewed before shipping DATA-01 in Phase 3.
- FinBERT first-run download (~400 MB) needs a UX decision (progress indicator or prefetch step) before DATA-02 ships.
- Chart library decision (TradingView Lightweight Charts vs. Recharts) must be resolved before Phase 4 planning.

## Session Continuity

Last session: 2026-04-22T06:43:54.545Z
Stopped at: Completed 04-01-PLAN.md (TTWROR + IRR + benchmark allowlist + daily P&L heatmap)
Resume file: None
