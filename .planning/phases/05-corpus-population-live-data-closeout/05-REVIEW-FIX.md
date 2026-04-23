---
phase: 05-corpus-population-live-data-closeout
fixed_at: 2026-04-22T00:00:00Z
review_path: .planning/phases/05-corpus-population-live-data-closeout/05-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 5: Code Review Fix Report

**Fixed at:** 2026-04-22T00:00:00Z
**Source review:** .planning/phases/05-corpus-population-live-data-closeout/05-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2 (WR-01, WR-02 — fix_scope: critical_warning)
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01 + WR-02: Outer exception guard + `error_message` population in `_run_batch_rebuild`

**Files modified:** `api/routes/calibration.py`, `tests/test_live_01_corpus_rebuild.py`
**Commit:** 707e740
**Applied fix:**

`api/routes/calibration.py` — `_run_batch_rebuild` rewritten with two layers of protection:

1. **Outer `try/except Exception` (WR-01):** The entire function body is now wrapped in an outer guard. Any systemic exception that fires before or outside the per-ticker loop (including `ImportError` on the deferred `from daemon.jobs import rebuild_signal_corpus`) is caught, logged, and written to `corpus_rebuild_jobs` as `status='error'` with `error_message=str(exc)[:500]`. The job row can no longer be stuck at `status='running'` indefinitely.

2. **`error_message` population on completion (WR-02):** The final-status `UPDATE` now includes `error_message = ?` in all paths:
   - `status='success'`: `error_message = NULL` (no errors).
   - `status='error'` (all tickers failed): `error_message` is a `;`-delimited summary of `ticker: <error>` pairs, truncated to 500 chars.
   - `status='partial'` (some tickers failed): `error_message` contains a count + ticker list, e.g. `"1 ticker(s) failed (see ticker_progress for per-ticker errors): BADINPUT"`, truncated to 500 chars.

3. **Inner import guard preserved:** The `from daemon.jobs import rebuild_signal_corpus` import is still deferred inside a nested `try/except` that logs the error before re-raising to the outer guard, giving a specific log message for the import-failure case.

Two new tests added to `tests/test_live_01_corpus_rebuild.py`:

- **`test_batch_rebuild_outer_exception_marks_error`**: Replaces `daemon.jobs` in `sys.modules` with a `_BrokenModule` whose `__getattr__` raises `ImportError`, simulating a systemic import failure. Asserts the job transitions to `status='error'` with a non-null, non-empty `error_message` — not stuck at `running`.

- **`test_batch_rebuild_partial_writes_error_message`**: Uses a stub that fails for ticker `BADINPUT` and succeeds for `GOOD1`. Asserts `status='partial'` and that `error_message` is non-null, non-empty, and contains the string `"BADINPUT"`.

All 27 tests in scope passed (27 passed, 2 deprecation warnings, 0 failures):
```
tests/test_live_01_corpus_rebuild.py      (13 tests — 11 pre-existing + 2 new)
tests/test_signal_quality_05b_signal_corpus.py
tests/test_foundation_07_job_run_log.py
```

## Skipped Issues (Info — out of scope)

### IN-01: No test coverage for zero-open-positions 400 path

**File:** `tests/test_live_01_corpus_rebuild.py`
**Reason:** fix_scope=critical_warning — Info findings excluded from this iteration.
**Original issue:** No test for the HTTP 400 path when `tickers=null` and portfolio has no open positions.

### IN-02: `verify_close_03_daemon_pid.py` PID-match assertion is flawed on Windows

**File:** `scripts/verify_close_03_daemon_pid.py:80`
**Reason:** fix_scope=critical_warning — Info findings excluded from this iteration. Cosmetic operator-script issue only; automated tests are correct.
**Original issue:** `pid_content == str(daemon_proc.pid)` can produce false-negative on Windows when the daemon spawns a sub-process.

### IN-03: `idx_crj_job_id` index is redundant given the UNIQUE constraint

**File:** `db/database.py:670-675`
**Reason:** fix_scope=critical_warning — Info findings excluded from this iteration. No functional or performance impact at current scale.
**Original issue:** Explicit `CREATE INDEX idx_crj_job_id` duplicates the implicit index created by the `UNIQUE` constraint on `job_id`.

---

_Fixed: 2026-04-22T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
