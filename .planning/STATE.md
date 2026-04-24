---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Competitive Parity
status: verifying
stopped_at: Completed 06-03-PLAN.md (CLOSE-04, CLOSE-05, CLOSE-06 UAT closeout — Phase 6 complete)
last_updated: "2026-04-24T07:24:31.346Z"
last_activity: 2026-04-24
progress:
  total_phases: 2
  completed_phases: 2
  total_plans: 5
  completed_plans: 5
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-22)

**Core value:** Drawdown protection via thesis-aware, regime-aware multi-agent signals — catching when a held position no longer matches the reason it was bought.
**Current focus:** Phase 6 — Calibration & Weights UI

## Current Position

Phase: 6
Plan: Not started
Status: Phase complete — ready for verification
Last activity: 2026-04-24

Progress: [░░░░░░░░░░] 0%

## v1.0 Archive Summary

v1.0 Competitive Parity shipped 2026-04-22. 4 phases, 14 plans, 25/25 requirements shipped.
Full record: `.planning/milestones/v1.0-ROADMAP.md`, `.planning/milestones/v1.0-REQUIREMENTS.md`

## Performance Metrics

**v1.1 Velocity:** (updated after each plan completion)

**v1.0 Reference (14 plans total):**

| Phase | Plans | Avg Duration |
|-------|-------|-------------|
| 1 - Foundation Hardening | 3 | ~1086s |
| 2 - Signal Quality Upgrade | 3 | ~2040s |
| 3 - Data Coverage Expansion | 4 | ~575s |
| 4 - Portfolio UI + Analytics Uplift | 4 | ~1301s |
| Phase 05-corpus-population-live-data-closeout P01 | 1489 | 2 tasks | 4 files |
| Phase 05-corpus-population-live-data-closeout P02 | 7 | 3 tasks | 7 files |
| Phase 06-calibration-weights-ui P06-01 | 600 | 3 tasks | 6 files |
| Phase 06-calibration-weights-ui P06-02 | 1446 | 3 tasks | 19 files |
| Phase 06-calibration-weights-ui P06-03 | 420 | 3 tasks | 10 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.

Key decisions carrying forward into v1.1:

- [v1.1 scope] Weekly cadence + 5-10 US equities only; signal noise is top rough edge; calibration visibility is north star
- [v1.1 scope] 6 v1.0 human-UAT items promoted to CLOSE-01..06 as first-class requirements — folded into Phase 5 (infra UATs) and Phase 6 (browser UATs) rather than a standalone UAT phase
- [v1.1 scope] Phase 7 AN-02 drift detector thresholds (>20% IC-IR drop / IC-IR<0.5 for 2 weeks) are reasonable priors but not back-tested — flag for research if planner cannot validate from existing corpus data
- [v1.1 arch] WeightsPage UI reuses Phase 4 Recharts + custom-SVG stack — no new chart library research needed
- [v1.1 arch] `agent_weights` table is the persistence target for both LIVE-03 (weights UI apply) and AN-02 (drift detector auto-scale) — both paths go through the existing WeightAdapter
- [v1.1 arch] `engine/digest.py` is a new module; weekly digest endpoint reuses existing email/Telegram notification channels from `notifications/`
- [v1.0 Phase 01]: backtest_mode=True threaded into Backtester.run() as single source of truth — FundamentalAgent excluded from corpus (FOUND-04 contract)
- [v1.0 Phase 02]: asyncio_mode=auto — async helpers awaited directly, no asyncio.run() wrappers in tests
- [v1.0 Phase 02]: IC test tolerance ±0.08 for N=100 (SE of Pearson r is ~0.10 at N=100)
- [v1.0 Phase 02]: Weight sum tolerance 1e-3 for 4dp-rounded weights
- [v1.0 Phase 02]: preliminary_calibration=true + survivorship_bias_warning=true are permanent flags until live history accumulates
- [v1.0 Phase 03]: Peer-basket sector P/E for Finnhub (5 proxy tickers/sector, median) — free tier has no sector-aggregate endpoint
- [v1.0 Phase 03]: FinBERT lazy-import, [llm-local] optional extra; HOLD@40 convention for below-threshold confidence
- [v1.0 Phase 04]: window.prompt used for target-weight inline edit — proper modal deferred to UI-v2-03
- [v1.0 Phase 04]: Built-in alert rules sorted first; delete hidden for metric==="hardcoded" rules
- [v1.0 Phase 04]: backtest_mode short-circuit is FIRST check in run_llm_synthesis — prevents ~$2.78/ticker API cost on 3yr backtests
- [Phase 05-corpus-population-live-data-closeout]: BackgroundTasks (not asyncio.create_task) for corpus rebuild: TestClient executes synchronously enabling deterministic test assertions; production runs async after response
- [Phase 05-corpus-population-live-data-closeout]: corpus_rebuild_jobs separate from job_run_log: needs UUID TEXT job_id, per-ticker JSON progress, and 'partial' status distinct from error/success
- [Phase 05-corpus-population-live-data-closeout]: Per-ticker single-element delegation: rebuild_signal_corpus(tickers=[(t, at)]) preserves FOUND-07 atomicity — one DELETE rollback scope per ticker
- [Phase 05-corpus-population-live-data-closeout]: importlib.util.find_spec at module top for lazy-import contract: CLOSE-01 never loads transformers at test collection time
- [Phase 05-corpus-population-live-data-closeout]: Meta-tests introspect fn.pytestmark to lock in skipif guards: refactor-proof CI safety
- [Phase 05-corpus-population-live-data-closeout]: subprocess natural exit (sleep+exit) not terminate() for atexit PID cleanup: Windows SIGTERM does not trigger atexit
- [Phase 05-corpus-population-live-data-closeout]: sector_pe_cache._finnhub_provider = None reset in CLOSE-02: closes Phase 3 singleton isolation follow-up
- [Phase 06-calibration-weights-ui]: agent_weights table is the persistence target for LIVE-03 weights UI (source='default'|'ic_ir'|'manual'); seeds from DEFAULT_WEIGHTS on empty; pipeline wiring to load_weights_from_db deferred to Phase 7 AN-02
- [Phase 06-calibration-weights-ui]: GET /weights LIVE-03 shape supersedes legacy {buy_threshold,sell_threshold,weights} contract; frontend WeightsPage donut breaks until 06-02 ships
- [Phase 06-calibration-weights-ui]: Unified CalibrationPage combines LIVE-02 (calibration table) + LIVE-03 (weights editor) — weekly review workflow consults both surfaces together; /weights redirects via Navigate
- [Phase 06-calibration-weights-ui]: data-testid cal-weights-editor on wrapper div (not Card) because Card component does not forward arbitrary DOM props
- [Phase 06-calibration-weights-ui]: invalidateCache() in beforeEach for snapshot test isolation: useApi in-memory cache persists between Vitest tests — must clear cache key before each test that sets up different mock data
- [Phase 06-calibration-weights-ui]: Frontend UAT closure pattern: Vitest toMatchSnapshot() + operator script + UAT doc flip (mirrors Phase 5 pytest-skipif + operator script + doc flip for backend UATs)

### Pending Todos

- Run `/gsd-plan-phase 5` to generate the Phase 5 execution plan

### Blockers/Concerns

- Phase 7 AN-02: drift detector threshold calibration ("IC-IR drop >20%" baseline definition) is a research question — determine whether existing backtest corpus provides enough signal variation to validate thresholds before committing to implementation constants.

## Session Continuity

Last session: 2026-04-24T06:49:55.312Z
Stopped at: Completed 06-03-PLAN.md (CLOSE-04, CLOSE-05, CLOSE-06 UAT closeout — Phase 6 complete)
Resume: Run `/gsd-plan-phase 5`
