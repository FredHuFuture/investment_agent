---
phase: 05-corpus-population-live-data-closeout
plan: 01
subsystem: api
tags: [calibration, background-task, sqlite, fastapi, corpus, live-01, pydantic]

# Dependency graph
requires:
  - phase: 02-signal-quality-upgrade
    provides: "rebuild_signal_corpus daemon job (FOUND-07 two-connection + BLOCKER-3 DELETE rollback)"
  - phase: 01-foundation-hardening
    provides: "FOUND-06 WAL mode + CREATE TABLE IF NOT EXISTS idempotent pattern"
provides:
  - "POST /analytics/calibration/rebuild-corpus — async batch corpus rebuild endpoint"
  - "GET /analytics/calibration/rebuild-corpus/{job_id} — per-ticker progress polling"
  - "corpus_rebuild_jobs SQLite table with per-ticker progress JSON"
  - "RebuildCorpusRequest / RebuildCorpusResponse / RebuildCorpusProgressResponse Pydantic models"
  - "13-test suite covering DDL, models, endpoints, FOUND-07 delegation, failure isolation"
affects:
  - 05-02 (CLOSE-01..06 UAT closeout — may reference these endpoints)
  - 06-calibration-page (CalibrationPage.tsx will POST to rebuild-corpus and poll progress)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "BackgroundTasks (FastAPI built-in) for async fire-and-forget without asyncio.create_task"
    - "Short-lived aiosqlite connections per _update_progress call (WR-02 pattern)"
    - "Per-ticker single-element delegation: rebuild_signal_corpus(tickers=[(t, at)]) preserves FOUND-07"
    - "500-char error truncation before DB write (T-05-01-04 defense-in-depth)"

key-files:
  created:
    - tests/test_live_01_corpus_rebuild.py
    - .planning/phases/05-corpus-population-live-data-closeout/05-01-SUMMARY.md
  modified:
    - db/database.py
    - api/models.py
    - api/routes/calibration.py

key-decisions:
  - "BackgroundTasks (not asyncio.create_task) chosen: TestClient executes BTs synchronously, enabling deterministic test assertions without sleep/polling"
  - "Per-ticker single-element list to rebuild_signal_corpus preserves FOUND-07 atomicity: one DELETE rollback scope per ticker"
  - "corpus_rebuild_jobs separate from job_run_log: needs TEXT job_id (UUID), per-ticker JSON progress, and 'partial' status distinct from 'error'/'success'"
  - "Short-lived connections in _update_progress: avoids holding write lock across entire batch (WR-02 pattern)"
  - "Error truncation at 500 chars: defense-in-depth for Phase 3 accepted risk of API keys in exception text"

patterns-established:
  - "LIVE-01 endpoint shape: POST returns job_id immediately; GET polls corpus_rebuild_jobs"
  - "Batch job status taxonomy: running -> success | partial (some failed) | error (all failed)"
  - "Null tickers -> enumerate PortfolioManager.get_all_positions() filtering status='open'"

requirements-completed: [LIVE-01]

# Metrics
duration: 25min
completed: 2026-04-23
---

# Phase 5 Plan 01: Corpus Rebuild Endpoints Summary

**HTTP API surface for async per-ticker backtest corpus rebuild: POST /calibration/rebuild-corpus returns job_id within 500ms; GET polls per-ticker progress from corpus_rebuild_jobs table; delegates per-ticker work to existing rebuild_signal_corpus preserving FOUND-07 atomicity**

## Performance

- **Duration:** 25 min
- **Started:** 2026-04-23T05:54:19Z
- **Completed:** 2026-04-23T06:19:08Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 4

## Accomplishments

- `corpus_rebuild_jobs` table (10 columns, 2 indexes) added to `db/database.py init_db` via idempotent `CREATE TABLE IF NOT EXISTS` per FOUND-06 pattern
- Three Pydantic v2 models in `api/models.py`: `RebuildCorpusRequest` (with ticker length validation + uppercase normalization), `RebuildCorpusResponse`, `RebuildCorpusProgressResponse`
- `POST /analytics/calibration/rebuild-corpus` and `GET /analytics/calibration/rebuild-corpus/{job_id}` implemented in `api/routes/calibration.py` without modifying existing `get_calibration` function
- `_run_batch_rebuild` background task with per-ticker failure isolation, progress persistence, and 500-char error truncation
- 13 tests passing (6 DDL/model + 7 endpoint); 43 prior regression tests pass with zero failures

## Task Commits

1. **Task 1: Add corpus_rebuild_jobs table + Pydantic models** - `769fc17` (feat)
2. **Task 2: Implement POST/GET endpoints + background task runner** - `466c194` (feat)

**Plan metadata:** (final commit recorded below after state updates)

_Note: Both tasks TDD — tests written first (RED), then implementation (GREEN)._

## Files Created/Modified

- `db/database.py` — added `corpus_rebuild_jobs` DDL + `idx_crj_job_id` + `idx_crj_status` inside `init_db`
- `api/models.py` — added `RebuildCorpusRequest`, `RebuildCorpusResponse`, `RebuildCorpusProgressResponse`; added `field_validator` import
- `api/routes/calibration.py` — added `POST /calibration/rebuild-corpus`, `GET /calibration/rebuild-corpus/{job_id}`, `_run_batch_rebuild`, `_update_progress`; added `json`, `logging`, `uuid`, `datetime`, `aiosqlite`, `BackgroundTasks`, `HTTPException` imports
- `tests/test_live_01_corpus_rebuild.py` — 13 new tests (created)

## Decisions Made

- **BackgroundTasks over asyncio.create_task**: FastAPI's `BackgroundTasks` executes synchronously in `TestClient` context, allowing tests to assert final DB state without sleep/polling. For production uvicorn, it runs asynchronously after response. No downside for solo-operator scope.
- **Per-ticker single-element delegation**: `rebuild_signal_corpus(tickers=[(ticker, asset_type)])` — calling with a single-element list means each ticker gets its own `run_id`, its own DELETE rollback scope, and its own job_run_log row. This is the FOUND-07 contract; breaking it would silently corrupt corpus on partial failure.
- **Separate `corpus_rebuild_jobs` table**: `job_run_log` uses integer `id` + `name`-keyed rows and has no per-sub-unit progress JSON. The new table adds: UUID `job_id` (HTTP-safe), `ticker_progress_json`, and `partial` status. Separate concerns.
- **`_update_progress` short-lived connections**: Matches WR-02 pattern from `daemon/jobs.py::prune_signal_history`. Avoids holding a WAL write lock across an entire batch (which could take minutes for 10-ticker portfolios).

## Deviations from Plan

None — plan executed exactly as written. The implementation matches the action blocks in both `<task>` elements verbatim. The only minor adaptation: `get_all_positions()` already filters by `status='open'` in the SELECT (confirmed from manager.py), but `_run_batch_rebuild` also filters `p.status == "open"` at the Python level for defense-in-depth (negligible cost, extra safety).

## Contract Honor-Check

| Contract | Status | Evidence |
|----------|--------|----------|
| FOUND-07 two-connection pattern | Honored | `_run_batch_rebuild` calls `rebuild_signal_corpus(tickers=[(t, at)])` — single-element list; each ticker is its own atomic unit with its own DELETE rollback scope |
| FOUND-07 BLOCKER-3 DELETE rollback | Honored | Each per-ticker call runs its own `run_id`-scoped DELETE rollback inside `rebuild_signal_corpus`; batch-level partial failure does NOT undo completed tickers (by design — `partial` status exposes this) |
| FOUND-04 backtest_mode | Honored | `rebuild_signal_corpus` already sets `backtest_mode=True`; this plan does not construct `AgentInput` directly |
| FOUND-06 WAL mode + idempotent DDL | Honored | `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`; no new PRAGMA concerns |
| Phase 3 DATA-05 localhost bind | Honored | New endpoints mounted under existing router at prefix `/analytics` — same `127.0.0.1` bind |
| T-05-01-04 error truncation | Honored | `str(exc)[:500]` in `_run_batch_rebuild` before writing to `ticker_progress_json` |

## Issues Encountered

None — both tasks implemented cleanly on first pass. Tests passed on the first GREEN run.

## Known Stubs

None — `ticker_progress_json` is populated with real per-ticker results from `rebuild_signal_corpus`. The `rows_inserted` field reflects the actual corpus rows written. No placeholder data flows to UI rendering.

## Threat Flags

None beyond what is documented in the plan's `<threat_model>`. The new endpoints introduce no surface not already analyzed there.

## User Setup Required

None — no external service configuration required. The endpoints use the existing SQLite DB and existing `daemon.jobs.rebuild_signal_corpus` function.

## Next Phase Readiness

- LIVE-01 backend surface complete: Phase 6 `CalibrationPage.tsx` can POST to `/analytics/calibration/rebuild-corpus` and poll `/analytics/calibration/rebuild-corpus/{job_id}` for progress
- `corpus_rebuild_jobs` table ready for Phase 6 progress UI
- Plan 05-02 (CLOSE-01..06 human-UAT closeout) can proceed independently — no dependency on this plan's output

---

## Self-Check

**Files exist:**

| File | Status |
|------|--------|
| `db/database.py` (CREATE TABLE IF NOT EXISTS corpus_rebuild_jobs) | FOUND |
| `api/models.py` (RebuildCorpusRequest) | FOUND |
| `api/routes/calibration.py` (rebuild-corpus endpoints) | FOUND |
| `tests/test_live_01_corpus_rebuild.py` (13 tests) | FOUND |

**Commits exist:**

| Hash | Message |
|------|---------|
| 769fc17 | feat(05-01): add corpus_rebuild_jobs DDL + Pydantic models (Task 1) |
| 466c194 | feat(05-01): implement rebuild-corpus endpoints + background task runner (Task 2) |

**Test counts:**

- 6 Task 1 tests (DDL + models): PASSED
- 7 Task 2 tests (endpoints + background): PASSED
- 43 regression tests (corpus + API + daemon + job_run_log): PASSED

## Self-Check: PASSED

---
*Phase: 05-corpus-population-live-data-closeout*
*Completed: 2026-04-23*
