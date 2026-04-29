---
phase: 08-pit-fundamentals-reliability-plots
plan: 01
subsystem: database

tags:
  - schema
  - migration
  - tripwire
  - pyproject
  - wave-0
  - fundamentals_provider
  - found-04
  - simfin-prep

# Dependency graph
requires:
  - phase: 05-corpus-population-live-data-closeout
    provides: corpus_rebuild_jobs table (Phase 5 LIVE-01) — extended here with fundamentals_provider column for first-enable detection
  - phase: 07-digest-analytics-completeness
    provides: drift_log table (Phase 7 AN-02) — extended here with fundamentals_provider column for provider-aware drift signals
provides:
  - fundamentals_provider TEXT NOT NULL DEFAULT 'yfinance' column on signal_history, backtest_signal_history, drift_log, corpus_rebuild_jobs (4 corpus tables)
  - 4 composite indexes (idx_signal_history_ticker_created_provider, idx_bsh_ticker_signal_date_provider, idx_drift_log_agent_asset_provider_evaluated, idx_crj_provider_status)
  - _migrate_fundamentals_provider helper (idempotent, mirrors _ensure_column pattern)
  - test_fundamental_agent_backtest_mode_default_unchanged (Pitfall 1 tripwire — FOUND-04 contract pinned)
  - test_simfin_provider_no_silent_yfinance_fallback (Pitfall 9 tripwire — scaffolded, auto-arms when 08-02 lands SimfinProvider)
  - test_db_fundamentals_provider_migration (3 tests covering idempotency + backfill + corpus_rebuild_jobs prereq)
  - scikit-learn / numpy / scipy promoted to direct deps in pyproject.toml
affects:
  - 08-02-pit-fundamentals (will inject fundamentals_provider='simfin' into signal_history rows + first-enable rebuild detection)
  - 08-03-reliability-plots-backend (will use sklearn calibration_curve + scipy norm.ppf)
  - 08-04-reliability-plots-frontend (consumer of reliability JSON shapes)

# Tech tracking
tech-stack:
  added:
    - "scikit-learn>=1.4,<2.0 (promoted from transitive — calibration_curve binning contract)"
    - "numpy>=1.26,<3.0 (promoted from transitive — Wilson CI vectorization)"
    - "scipy>=1.10,<2.0 (promoted from transitive — Murphy decomposition + future Phase 10 wilcoxon)"
  patterns:
    - "Idempotent _migrate_* helper pattern: wrap _ensure_column loop + CREATE INDEX IF NOT EXISTS for additive schema evolution"
    - "Tripwire scaffolding via importlib.util.find_spec + @pytest.mark.skipif: tests for code that doesn't exist yet AUTO-ARM the moment the missing module lands"
    - "Defensive ordering: schema migration ships in Wave 0 BEFORE the feature that introduces the new provider — prevents data corruption windows"

key-files:
  created:
    - "tests/test_fundamental_agent_backtest_mode_default_unchanged.py — FOUND-04 tripwire (Pitfall 1)"
    - "tests/test_simfin_provider_no_silent_yfinance_fallback.py — Pitfall 9 tripwire scaffold"
    - "tests/test_db_fundamentals_provider_migration.py — 3 migration verification tests"
    - ".planning/phases/08-pit-fundamentals-reliability-plots/deferred-items.md — pre-existing test-isolation flake documentation"
  modified:
    - "db/database.py — added _migrate_fundamentals_provider + wired into init_db before commit"
    - "pyproject.toml — bumped 0.4.0 -> 0.5.0; added scikit-learn / numpy / scipy direct deps"

key-decisions:
  - "Migration helper inserted between _migrate_ticker_unique_to_partial and _seed_default_alert_rules (alphabetical with other _migrate_* helpers)"
  - "_migrate_fundamentals_provider invoked at end of init_db() — AFTER all CREATE TABLE statements but BEFORE conn.commit() so the schema lands in one transaction"
  - "4th composite index (idx_crj_provider_status) on corpus_rebuild_jobs — supports 08-02 Task 4 first-enable detection query (SELECT COUNT(*) WHERE fundamentals_provider='simfin' AND status IN ('success','partial'))"
  - "Test-isolation errors in test_an02_drift_api.py confirmed pre-existing on baseline (verified by stashing changes + running suite) — documented in deferred-items.md, NOT a regression from this plan"
  - "Project version bumped 0.4.0 -> 0.5.0 marking v1.2 milestone start"

patterns-established:
  - "Wave 0 defensive-ordering hinge: schema + tripwire tests ship in same PR BEFORE the feature that uses them. 08-02 SimfinProvider is now only allowed to USE the schema column, not INTRODUCE it."
  - "Tripwire skipif via importlib.util.find_spec: scaffolds a regression test for a module that hasn't been created yet; auto-runs when the module lands without any test-file edit"
  - "Migration test triple: idempotency + backfill semantics + downstream-prereq column existence — ensures migration is safe to re-run AND that the column is present where future plans expect it"

requirements-completed:
  - DATA-v2-04

# Metrics
duration: 91min
completed: 2026-04-29
---

# Phase 8 Plan 01: Wave 0 Defensive Foundation Summary

**fundamentals_provider TEXT NOT NULL DEFAULT 'yfinance' column landed on 4 corpus tables (signal_history, backtest_signal_history, drift_log, corpus_rebuild_jobs) with 4 composite indexes; FOUND-04 contract pinned via tripwire test; sklearn/numpy/scipy promoted to direct deps**

## Performance

- **Duration:** ~91 min (most spent on full-suite pytest runs to confirm no regression)
- **Started:** 2026-04-29T02:53:47Z
- **Completed:** 2026-04-29T04:24:54Z
- **Tasks:** 3
- **Files modified:** 5 (2 source, 3 new test files; plus deferred-items.md)
- **Test count:** 929 baseline → 934 after Plan 08-01 (+5 new: 1 FOUND-04 + 1 SimFin scaffold + 3 migration)

## Accomplishments

- **DATA-v2-04 schema migration shipped** — 4 ALTER TABLE additions + 4 composite indexes, all idempotent. The corpus_rebuild_jobs column is the critical 4th table that 08-02 Task 4's first-enable detection query needs.
- **FOUND-04 contract is now PINNED** — `test_fundamental_agent_backtest_mode_default_unchanged` will fail loudly if any future change accidentally lifts the backtest_mode short-circuit. This is the Pitfall 1 mitigation.
- **Pitfall 9 tripwire scaffolded** — silent-yfinance-fallback test exists with skipif guard; the moment 08-02 ships `data_providers/simfin_provider.py`, the test auto-arms with no further setup.
- **Wave 0 defensive ordering achieved** — 08-02 SimfinProvider PR is now only allowed to USE the fundamentals_provider column, not INTRODUCE it. No more deferred-schema decision time during feature implementation.

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 tripwire tests (FOUND-04 + Pitfall 9 scaffolds)** — `6020886` (test)
2. **Task 2: Schema migration — fundamentals_provider on 4 corpus tables + composite indexes** — `b3038d6` (feat)
3. **Task 3: Promote sklearn/numpy/scipy to direct deps + version bump** — `40e65ef` (chore)

## Files Created/Modified

- `tests/test_fundamental_agent_backtest_mode_default_unchanged.py` (NEW) — Pitfall 1 tripwire pinning the FOUND-04 short-circuit; uses AsyncMock to assert provider methods are NOT called
- `tests/test_simfin_provider_no_silent_yfinance_fallback.py` (NEW) — Pitfall 9 tripwire scaffolded with `@pytest.mark.skipif(not SIMFIN_AVAILABLE, ...)`; auto-arms when 08-02 lands SimfinProvider
- `tests/test_db_fundamentals_provider_migration.py` (NEW) — 3 tests: `test_fundamentals_provider_migration_idempotent`, `test_existing_rows_backfill_to_yfinance`, `test_corpus_rebuild_jobs_has_fundamentals_provider_column`
- `db/database.py` (MODIFIED) — added `_migrate_fundamentals_provider` (idempotent helper looping over 4 tables + 4 CREATE INDEX IF NOT EXISTS); wired into `init_db()` before final commit
- `pyproject.toml` (MODIFIED) — version bumped 0.4.0 -> 0.5.0; added `scikit-learn>=1.4,<2.0`, `numpy>=1.26,<3.0`, `scipy>=1.10,<2.0` to `[project] dependencies`
- `.planning/phases/08-pit-fundamentals-reliability-plots/deferred-items.md` (NEW) — documents pre-existing test-isolation flakes in `test_an02_drift_api.py` (verified pre-existing on baseline)

## Decisions Made

- **Migration helper placement:** Added `_migrate_fundamentals_provider` between `_migrate_ticker_unique_to_partial` and `_seed_default_alert_rules` (alphabetical-ish with other `_migrate_*` helpers).
- **Migration invocation point:** Called `await _migrate_fundamentals_provider(conn)` at the end of `init_db()` AFTER all `CREATE TABLE IF NOT EXISTS` statements but BEFORE `conn.commit()`. This ensures the schema lands in a single transaction and that the helper sees the canonical-shape tables (not pre-migration ones).
- **4th composite index for corpus_rebuild_jobs:** `idx_crj_provider_status (fundamentals_provider, status, completed_at DESC)` — supports 08-02 Task 4's first-enable detection query (`WHERE fundamentals_provider='simfin' AND status IN ('success','partial') ORDER BY completed_at DESC`). Without this index the lookup degrades to a table scan; with it, it's an index-only seek.
- **Test-isolation flakes deferred, not fixed:** The 9 errors in `test_an02_drift_api.py` (RuntimeError: There is no current event loop) appear in both baseline and post-migration full-suite runs. Confirmed pre-existing by stashing all 08-01 changes and re-running. Out of scope per the SCOPE BOUNDARY rule; documented in `deferred-items.md`.
- **Version bump:** 0.4.0 -> 0.5.0 marks v1.2 milestone start. Patch-level was insufficient for a milestone boundary; minor-level signals new direct deps to anyone tracking pyproject.

## Deviations from Plan

None — plan executed exactly as written.

The only sub-decision left to discretion (per the plan's flexibility) was where to insert the new migration helper in `db/database.py` and how to handle the pre-existing test-isolation flakes; both were resolved as documented in "Decisions Made" above.

## Issues Encountered

- **Pre-existing test-isolation errors in `test_an02_drift_api.py`** — when running the full pytest suite, all 9 tests in this file error with `RuntimeError: There is no current event loop in thread 'MainThread'` at fixture setup (line 22: `asyncio.get_event_loop().run_until_complete(...)`). The tests pass 9/9 when run in isolation. **Verified pre-existing** by stashing my Plan 08-01 changes and re-running — same 9 errors. Documented in `deferred-items.md`. Per SCOPE BOUNDARY this is out of scope for 08-01 and tracked for a focused test-hygiene plan.

## User Setup Required

None - no external service configuration required for Plan 08-01. (08-02 will require `SIMFIN_API_KEY` at first SimFin enable; that user-setup will be generated by 08-02.)

## Next Phase Readiness

**08-02 (SimfinProvider) is now safe to land.** Specifically:

- **Schema is ready:** `signal_history`, `backtest_signal_history`, `drift_log`, AND `corpus_rebuild_jobs` all have `fundamentals_provider` column. 08-02's INSERT statements can now write `'simfin'` without any schema work; 08-02 Task 4's first-enable detection query (`WHERE fundamentals_provider='simfin' AND status IN ('success','partial')`) will execute cleanly.
- **Indexes are ready:** `idx_signal_history_ticker_created_provider`, `idx_bsh_ticker_signal_date_provider`, `idx_drift_log_agent_asset_provider_evaluated`, AND `idx_crj_provider_status` all exist — IC, drift, and first-enable queries can filter by provider on day 1 without sequential scans.
- **FOUND-04 tripwire is GREEN:** any 08-02 change to `agents/fundamental.py` that accidentally regresses the backtest_mode short-circuit will fail this test loudly.
- **Pitfall 9 tripwire is armed-on-arrival:** 08-02 just needs to create `data_providers/simfin_provider.py` and the SKIP turns into a RUN. If SimfinProvider silently falls back to yfinance, the test will fail at the next pytest run.
- **Dependencies are explicit:** sklearn / numpy / scipy are direct deps with version pins matching the contracts 08-03 will use (`calibration_curve(strategy='quantile')`, `norm.ppf(0.975)`).

**Phase 8 Wave 0 closed.** Ready for Wave 1 (08-02 SimfinProvider + agent routing + first-enable rebuild) and Wave 2 (08-03 reliability backend, 08-04 reliability frontend).

## Verification Evidence

```
$ pytest tests/test_fundamental_agent_backtest_mode_default_unchanged.py tests/test_simfin_provider_no_silent_yfinance_fallback.py -v
tests/test_fundamental_agent_backtest_mode_default_unchanged.py::test_fundamental_agent_backtest_mode_default_unchanged PASSED
tests/test_simfin_provider_no_silent_yfinance_fallback.py::test_no_silent_yfinance_fallback SKIPPED
1 passed, 1 skipped

$ pytest tests/test_db_fundamentals_provider_migration.py -v
tests/test_db_fundamentals_provider_migration.py::test_fundamentals_provider_migration_idempotent PASSED
tests/test_db_fundamentals_provider_migration.py::test_existing_rows_backfill_to_yfinance PASSED
tests/test_db_fundamentals_provider_migration.py::test_corpus_rebuild_jobs_has_fundamentals_provider_column PASSED
3 passed

$ pip show scikit-learn numpy scipy | grep -E "^(Name|Version):"
Name: scikit-learn   Version: 1.6.1     # satisfies >=1.4,<2.0
Name: numpy          Version: 2.2.6     # satisfies >=1.26,<3.0
Name: scipy          Version: 1.15.3    # satisfies >=1.10,<2.0

$ python -c "import sklearn, numpy, scipy; print(sklearn.__version__, numpy.__version__, scipy.__version__)"
1.6.1 2.2.6 1.15.3

$ pytest --collect-only -q | tail -1
934 tests collected   # 929 baseline + 5 new from Plan 08-01
```

## Self-Check: PASSED

- All 7 artifact files verified to exist on disk
- All 3 task commits verified to exist in git log (`6020886`, `b3038d6`, `40e65ef`)
- All required schema strings verified in `db/database.py` (16 matches: `_migrate_fundamentals_provider`, 4 index names, `TEXT NOT NULL DEFAULT 'yfinance'`, `corpus_rebuild_jobs`)
- All 3 dep promotions verified in `pyproject.toml` (`scikit-learn>=1.4`, `numpy>=1.26`, `scipy>=1.10`)
- All 5 new tests pass (3 migration + 1 FOUND-04 tripwire + 1 SimFin scaffold SKIP)
- 9 errors in `test_an02_drift_api.py` confirmed pre-existing on baseline (not regression)

---
*Phase: 08-pit-fundamentals-reliability-plots*
*Plan: 01*
*Completed: 2026-04-29*
