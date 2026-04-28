---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Trustworthy Signals
status: planning
stopped_at: Roadmap complete — Phases 8-10 defined; ready for /gsd-plan-phase 8
last_updated: "2026-04-27T00:00:00.000Z"
last_activity: 2026-04-27
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-27 for v1.2 milestone)

**Core value:** Drawdown protection via thesis-aware, regime-aware multi-agent signals — catching when a held position no longer matches the reason it was bought.
**Current focus:** v1.2 Trustworthy Signals — Phase 8 planning (research → plan → execute pending)

## Current Position

Phase: 8 — Not started (planning)
Plan: —
Status: Ready for `/gsd-plan-phase 8`
Last activity: 2026-04-27 — Roadmap created (Phases 8-10 / 10 reqs / 100% coverage)

Progress: [░░░░░░░░░░] 0%

## v1.0 Archive Summary

v1.0 Competitive Parity shipped 2026-04-22. 4 phases, 14 plans, 25/25 requirements shipped.
Full record: `.planning/milestones/v1.0-ROADMAP.md`, `.planning/milestones/v1.0-REQUIREMENTS.md`

## v1.1 Archive Summary

v1.1 Live Validation shipped 2026-04-25. 3 phases, 8 plans, 12/12 requirements shipped.
Full record: `.planning/milestones/v1.1-ROADMAP.md`, `.planning/milestones/v1.1-REQUIREMENTS.md`

## Performance Metrics

**v1.2 Velocity:** (updated after each plan completion)

**v1.1 Reference (8 plans total):**

| Phase | Plans | Avg Duration |
|-------|-------|-------------|
| 5 - Corpus Population + Live Data Closeout | 2 | ~498s |
| 6 - Calibration & Weights UI            | 3 | ~822s |
| 7 - Digest + Analytics Completeness     | 3 | ~859s |

**v1.0 Reference (14 plans total):**

| Phase | Plans | Avg Duration |
|-------|-------|-------------|
| 1 - Foundation Hardening                  | 3 | ~1086s |
| 2 - Signal Quality Upgrade                | 3 | ~2040s |
| 3 - Data Coverage Expansion               | 4 | ~575s |
| 4 - Portfolio UI + Analytics Uplift       | 4 | ~1301s |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.

Key decisions carrying forward into v1.2:

- [v1.2 scope] Tight (~3 phases / 10 reqs) combining Signal Quality v2 (reliability plots) + Data Coverage v2 (SimFin + CoinGecko) + v1.1 carry-forward drift-threshold validation
- [v1.2 phase ordering] Phase 8 → 9 → 10 mandatory due to corpus contamination risk (Cross-1/2/3/4 pitfalls) — Phase 8 bundles SimFin + Reliability Plots so the `fundamentals_provider` schema migration ships in one PR; Phase 9's `asyncio.wait_for(10s)` primitive lands before Phase 10 validates against the rebuilt corpus
- [v1.2 honesty] v1.2 ships *capability to validate*, NOT *validated thresholds* — corpus is ~13 weeks at ship vs 60-week floor; Phase 10 success criterion = panel landing with "needs N more weeks" text, not flipped `validated` flag
- [v1.2 anti-feature] Auto-tuning drift thresholds on every weekly run is explicitly out-of-scope (DRIFT-v2-05 deferred) — threshold thrashing defeats the validation purpose
- [v1.2 anti-feature] Switching the *entire* fundamental pipeline to SimFin is out-of-scope — single-provider failure surface; SimFin free tier ~5y history; layered routing via opt-in `use_pit_fundamentals` field on `AgentInput` instead

Key decisions carrying forward from v1.1:

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
- [Phase 07]: DividendCache uses 24h TTL Parquet (data/cache/dividends/) — consistent with FOUND-02 ParquetOHLCVCache pattern; survives restarts
- [Phase 07]: Pipeline wiring: load_weights_from_db in analyze_ticker else-branch only; adaptive-weights legacy path left intact for backward compat
- [Phase 07]: Never-zero-all guard checks total_new <= 0 across all asset_type agents after scaling, not just the target agent
- [Phase 07]: PII clamp uses _clamp_pii() stripping dollar-amounts + thesis-marker keywords from alert message fields — monitoring_alerts.message can contain thesis text from portfolio notes
- [Phase 07]: send_markdown_email uses html.escape() + pre-wrap (not full Markdown-to-HTML conversion) — sufficient since digest body is machine-generated, no user-supplied text
- [Phase 07]: DriftBadge: preliminary_threshold takes precedence over triggered (amber before red); 7-day RECENT_DRIFT_WINDOW_MS enforced client-side; driftByAgent keyed by agent_name after assetType filter in CalibrationPage

### Pending Todos

- `/gsd-plan-phase 8` — decompose Phase 8 (PIT Fundamentals + Reliability Plots) into plans; expect SimFin provider + simfin_cache, `fundamentals_provider` schema migration, FOUND-04 tripwire test, reliability bin computation, Murphy decomposition, ReliabilityPlot.tsx + MurphyDecompositionCard.tsx, restated-vs-as-filed delta badge
- Phase 8 research (highly recommended per SUMMARY.md) — open questions: SimFin filing-date filtering for amended 10-Q/A, Murphy decomposition exact-bin vs PAV, `use_pit_fundamentals` opt-in scope (per-analyze vs per-portfolio vs global)
- Phase 9 research — CryptoAgent factor weights: how to z-score `commit_count_4_weeks` against asset-specific baselines (BTC vs ETH vs altcoins have different commit rhythms)
- Phase 10 research — multi-comparison correction (Bonferroni vs FDR) for 16-point grid Wilcoxon tests; resolve before Phase 10 implementation

### Blockers/Concerns

- v1.2 ships *capability to validate*, NOT *validated thresholds* — operator-facing communication needed at Phase 10 closeout so a future contributor doesn't see "preliminary" still flying and conclude v1.2 failed (must be documented as Key Decision in PROJECT.md at v1.2 completion)
- Phase 8 must include `fundamentals_provider` schema migration in the SAME PR as SimFin provider (Pitfall 4 — provider mixing in `signal_history`/`backtest_signal_history`/`drift_log` is silent IC contamination)
- Phase 9 must include `asyncio.wait_for(timeout=10s)` per-agent timeout primitive (Pitfall 3 — CoinGecko 5-15/min rate limit blocks `asyncio.gather` for 60s); reusable defensive primitive for any future rate-limited provider
- Phase 10 prerequisite check: assert `corpus_rebuild_jobs.completed_at >= max(SimFin/CoinGecko enable timestamp)` — without this, Phase 10 validates against a half-rebuilt corpus and produces garbage (Cross-4)
- SimFin free-tier exact daily cap not published — Phase 8 research must verify with real rebuild against operator's portfolio; ship `AsyncRateLimiter(2/sec, 60s sliding window)` conservatively
- CoinGecko `community_data` Twitter follower discontinuation (2024) — Reddit + Telegram are the only social signals on Demo tier; Phase 9 must confirm Reddit + Telegram coverage for BTC/ETH on operator's actual portfolio

## Session Continuity

Last session: 2026-04-27T00:00:00.000Z
Stopped at: Roadmap created — Phases 8-10 defined / 10 reqs / 100% coverage; STATE updated to planning
Resume: Run `/gsd-plan-phase 8` to begin Phase 8 (PIT Fundamentals + Reliability Plots)
