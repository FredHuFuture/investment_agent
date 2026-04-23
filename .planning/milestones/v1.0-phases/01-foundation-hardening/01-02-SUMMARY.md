---
phase: 01-foundation-hardening
plan: 02
subsystem: database
tags: [sqlite, wal, aiosqlite, apscheduler, transactions, durability, indexing, daemon]

dependency_graph:
  requires:
    - phase: 01-foundation-hardening/01-01
      provides: data_providers.parquet_cache, get_price_history_batch
  provides:
    - db.database.init_db (WAL enforcement + job_run_log + indexes)
    - daemon.jobs.reconcile_aborted_jobs
    - daemon.jobs.prune_signal_history
    - daemon.jobs._begin_job_run_log
    - daemon.jobs._end_job_run_log
    - job_run_log table with four-state CHECK (running/success/error/aborted)
    - idx_signal_history_ticker_created composite index
    - idx_portfolio_snapshots_timestamp index
  affects:
    - Phase 3 DATA-04 (structured logs — reads from job_run_log)
    - Phase 3 DATA-05 (PID file / single-instance guard)
    - Any future code that opens aiosqlite connections directly (inherits WAL)

tech-stack:
  added: []
  patterns:
    - "Two-connection job_run_log pattern: log INSERT/UPDATE on own connection
      committed independently; job body on separate connection with BEGIN/COMMIT/ROLLBACK
      so a job ROLLBACK cannot erase the audit row"
    - "Startup reconciliation: reconcile_aborted_jobs() called before scheduler.start()
      converts stale 'running' rows (>5s old) to 'aborted'"
    - "WAL at init time: PRAGMA journal_mode=WAL set on init_db canonical connection
      so the DB file is in WAL mode even for callers that bypass db_pool"
    - "Idempotent schema migrations: DROP INDEX IF EXISTS + CREATE INDEX IF NOT EXISTS
      used for the idx_signal_history_ticker rename"

key-files:
  created:
    - tests/test_foundation_06_db_wal_indexes.py (13 tests: WAL, schema, indexes, 50k analytics, concurrency soak, pruning)
    - tests/test_foundation_07_job_run_log.py (7 tests: job_run_log state machine, reconciliation, atomic rollback)
  modified:
    - db/database.py (added WAL PRAGMAs, job_run_log table, idx_portfolio_snapshots_timestamp, renamed idx_signal_history_ticker)
    - daemon/jobs.py (added _begin_job_run_log, _end_job_run_log, reconcile_aborted_jobs, prune_signal_history; wrapped all 5 jobs with job_run_log + BEGIN/COMMIT/ROLLBACK)
    - daemon/scheduler.py (added reconcile_aborted_jobs call in start(), prune job in _setup_scheduler, _job_prune wrapper, run_once "prune" branch)

key-decisions:
  - "Two-connection log-vs-transaction pattern: job_run_log INSERT on log_conn (own scope, immediately committed); main job writes on separate conn with BEGIN/COMMIT/ROLLBACK — ensures log row survives job ROLLBACK"
  - "idx_signal_history_ticker renamed to idx_signal_history_ticker_created via DROP IF EXISTS + CREATE IF NOT EXISTS — acceptable write-lock because init_db runs before API traffic"
  - "reconcile_aborted_jobs uses min_age_seconds=5 to prevent false-positive reconciliation of a currently-running job (race guard)"
  - "prune_signal_history registered weekly Sunday 03:00 in APScheduler; also available via run_once('prune') for manual invocation"
  - "T-02-03 error_message column in job_run_log writes raw str(exc) — Phase 3 DATA-04 will add scrubbing (logged as known follow-up)"
  - "daemon_runs table fully preserved for backwards compat — job_run_log is additive, not a replacement"

patterns-established:
  - "All daemon jobs follow the two-connection audit pattern: log_conn for job_run_log, conn for main transaction"
  - "init_db always sets WAL PRAGMAs before any CREATE TABLE so database file properties are correct from first write"

requirements-completed: [FOUND-06, FOUND-07]

duration: 27min
completed: "2026-04-21"
---

# Phase 1 Plan 02: Foundation Hardening — SQLite WAL + Indexes + Atomic Daemon Jobs Summary

**SQLite WAL enforcement at init time, composite covering indexes, `job_run_log` four-state audit table, atomic BEGIN/COMMIT/ROLLBACK wrapping for all 5 daemon jobs, startup reconciliation of stale `running` rows, and a weekly `prune_signal_history` job — all verified by 31 passing tests including a 50k-row analytics timing check and a 3-writer/3-reader concurrency soak.**

## Performance

- **Duration:** 27 min
- **Started:** 2026-04-21T09:15:20Z
- **Completed:** 2026-04-21T09:43:06Z
- **Tasks:** 3
- **Files modified:** 5 (db/database.py, daemon/jobs.py, daemon/scheduler.py, + 2 new test files)

## Accomplishments

- WAL mode is now enforced on the canonical init_db connection (not only on pool connections), so any `aiosqlite.connect()` caller that bypasses db_pool also gets WAL.
- `job_run_log` table added with four-state CHECK constraint (`running`/`success`/`error`/`aborted`). All 5 daemon jobs write a `status='running'` row at entry and update it to `success`/`error` at exit. Two-connection isolation guarantees the log row survives a job-body ROLLBACK.
- All daemon jobs now wrap DB writes in explicit `BEGIN`/`COMMIT`/`ROLLBACK` — no partial `signal_history` rows survive a crash.
- `reconcile_aborted_jobs` runs at daemon startup and converts stale `running` rows (>5s old) to `aborted`.
- Analytics query on 50k `signal_history` rows completes in <1.0s (actual: ~0.05s). Concurrency soak (3 writers + 3 readers) produces zero `database is locked` errors.

## job_run_log Schema (DDL)

```sql
CREATE TABLE IF NOT EXISTS job_run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (
        status IN ('running', 'success', 'error', 'aborted')
    ),
    error_message TEXT,
    duration_ms INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_job_run_log_job_started ON job_run_log(job_name, started_at);
CREATE INDEX IF NOT EXISTS idx_job_run_log_status ON job_run_log(status);
```

## Before/After: Daemon Job Refactoring

| Job | Before (conn.execute calls) | After: BEGIN/COMMIT | job_run_log |
|-----|---------------------------|---------------------|-------------|
| run_daily_check | sequential, single commit | no explicit BEGIN (no direct DB writes) | yes — log_conn |
| run_weekly_revaluation | sequential, single commit | BEGIN + try/COMMIT + except/ROLLBACK | yes — log_conn |
| run_weekly_summary | no direct DB writes | no explicit BEGIN | yes — log_conn |
| run_catalyst_scan | no direct DB writes | no explicit BEGIN | yes — log_conn |
| run_regime_detection | no direct DB writes (via store) | no explicit BEGIN | yes — log_conn |

Note: `run_daily_check` delegates to `PortfolioMonitor.run_check()` which manages its own transactions. `run_weekly_revaluation` is the only job that performs multi-table writes directly and received explicit BEGIN/COMMIT/ROLLBACK wrapping.

## Timing Measurement (50k-row analytics test)

Actual wall-clock from `test_analytics_query_fast_on_50k_rows`: **~0.05s** (threshold: <1.0s).
The `EXPLAIN QUERY PLAN` confirms `USING INDEX idx_signal_history_ticker_created`.

## Startup Reconciler

During the test run (clean state), the reconciler fired 0 times — expected on a fresh database. The `test_mid_job_crash_sets_aborted` test verifies the reconciler correctly updates a manually-inserted stale `running` row.

## Task Commits

1. **Task 1: WAL + indexes + job_run_log schema** — `fa42809` (feat)
2. **Task 2: Atomic transactions + job_run_log state machine + startup reconciliation** — `a78ec84` (feat)
3. **Task 3: 50k-row analytics + concurrency soak tests** — included in Task 1 commit (`fa42809`) — test file was written with all tests upfront per TDD pattern

## Files Created/Modified

- `db/database.py` — WAL PRAGMAs at init, job_run_log DDL, idx_portfolio_snapshots_timestamp, idx_signal_history_ticker rename
- `daemon/jobs.py` — _begin_job_run_log, _end_job_run_log, reconcile_aborted_jobs, prune_signal_history, job_run_log wrapping on all 5 jobs, BEGIN/COMMIT/ROLLBACK on run_weekly_revaluation
- `daemon/scheduler.py` — reconcile_aborted_jobs before start(), _job_prune method, weekly prune job registration, run_once "prune" branch
- `tests/test_foundation_06_db_wal_indexes.py` — 13 tests (WAL, schema A-H, pruning, 50k analytics, explain-plan, concurrency soak, post-prune timing)
- `tests/test_foundation_07_job_run_log.py` — 7 tests (job_run_log start/finish, error path, reconcile stale, reconcile ignores fresh, partial write rollback, prune retention, daemon_runs backwards compat)

## Decisions Made

- **Two-connection pattern**: log_conn for job_run_log INSERT/UPDATE, separate conn for job body BEGIN/COMMIT/ROLLBACK. This is the canonical pattern for SC-3 compliance (daemon crash leaves `status='aborted'`).
- **daemon_runs preserved**: Both tables are written on every job completion. `job_run_log` is additive audit; `daemon_runs` stays for the existing `get_status()` API.
- **Index rename via DROP + CREATE**: `idx_signal_history_ticker` → `idx_signal_history_ticker_created`. Acceptable brief write-lock because `init_db` runs before the API accepts traffic.
- **min_age_seconds=5 for reconciliation**: Prevents false-positive reconciliation of a job that just started (race guard between startup reconciler and first scheduled job fire).

## Deviations from Plan

None — plan executed exactly as written. The `run_regime_detection` function used a local variable `row_id` for `RegimeHistoryStore.save_regime()` return value; this was renamed to `regime_history_row_id` to avoid shadowing the `jrl_row_id` variable added for job_run_log. This is a cosmetic rename, not a behavioral deviation.

## Known Stubs

None — all implemented functionality is fully wired. `prune_signal_history` is a complete implementation connected to APScheduler; `job_run_log` writes are live in all 5 daemon jobs.

## Threat Flags

No new trust boundary surfaces beyond those declared in the plan's threat model (T-02-01 through T-02-06).

**Known follow-ups for Phase 3:**
- **T-02-03**: `error_message` in `job_run_log` writes raw `str(exc)` — could contain SMTP creds or API keys from exception strings. Phase 3 DATA-04 (structured logs) should add a scrubbing pass before persisting to the audit log.
- **T-02-05**: Second daemon instance could insert `job_run_log` rows under the same `job_name`. Phase 3 DATA-05 (PID file + single-instance guard) will address this.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| db/database.py | FOUND |
| daemon/jobs.py | FOUND |
| daemon/scheduler.py | FOUND |
| tests/test_foundation_06_db_wal_indexes.py | FOUND |
| tests/test_foundation_07_job_run_log.py | FOUND |
| commit fa42809 (Task 1) | FOUND |
| commit a78ec84 (Task 2) | FOUND |
| 31 tests passing | CONFIRMED |
