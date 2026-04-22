---
phase: 03-data-coverage-expansion
fixed_at: 2026-04-22T04:00:00Z
review_path: .planning/phases/03-data-coverage-expansion/03-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 3: Code Review Fix Report

**Fixed at:** 2026-04-22T04:00:00Z
**Source review:** `.planning/phases/03-data-coverage-expansion/03-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (WR-01, WR-02, WR-03; Info findings skipped per task instructions)
- Fixed: 3
- Skipped: 0

---

## Fixed Issues

### WR-01: `uptime_seconds` in `/health` measures oldest active job age, not daemon uptime

**Files modified:** `api/routes/health.py`, `tests/test_data_coverage_04_health.py`
**Commit:** `8394b8a`
**Applied fix:** Replaced the `MIN(started_at) FROM job_run_log WHERE status='running'` query
with PID file mtime approach. `uptime_seconds` is now computed as
`int((now - os.path.getmtime(PID_FILE_PATH)).total_seconds())` when the PID file exists,
and `null` when absent. This correctly returns a positive integer during idle periods
(no active job_run_log rows) — distinguishing "daemon running but idle" from "daemon not
running". The `import os` was added to the module. Module docstring extended with
`uptime_seconds semantics (WR-01)` section. Also fixed the pre-existing cross-module event
loop issue in `test_data_coverage_04_health.py` where `asyncio.get_event_loop().run_until_complete()`
raised `RuntimeError` after pytest-asyncio closed the default loop; replaced with
`asyncio.run()`. Three new tests added in `TestHealthUptimeFromPidMtime`:
- `test_uptime_seconds_positive_when_pid_file_present_and_job_log_empty` — key regression
  guard: confirms uptime is non-null even with empty job_run_log
- `test_uptime_seconds_null_when_pid_file_absent` — confirms null when no PID file
- `test_uptime_seconds_reflects_pid_file_age` — confirms value is within expected range

### WR-02: `sector_pe_cache._finnhub_provider` singleton leaks across test modules

**Files modified:** `tests/conftest.py` (new file), `tests/test_data_coverage_04_health.py`
**Commit:** `333d9a4`
**Applied fix:** Created `tests/conftest.py` with an `autouse=True` sync generator fixture
`_reset_sector_pe_cache` that clears `sector_pe_cache._cache`, `sector_pe_cache._source_cache`,
and sets `sector_pe_cache._finnhub_provider = None` both before and after every test in the
suite. This prevents a live `FinnhubProvider` instance (and its `httpx.AsyncClient`) from
leaking into subsequent tests when `FINNHUB_API_KEY` is set. The `test_data_coverage_04_health.py`
`_run()` helper was also updated (as part of the cross-module isolation fix needed for WR-02's
test run) to use `asyncio.run()` instead of the deprecated `asyncio.get_event_loop().run_until_complete()`.

### WR-03: `stale_running` threshold in `/health` (300s) disagrees with `reconcile_aborted_jobs` default (5s)

**Files modified:** `daemon/scheduler.py`, `tests/test_014_daemon.py`
**Commit:** `33bcc3f`
**Applied fix:** Changed the `reconcile_aborted_jobs` call in `MonitoringDaemon.start()` at
`daemon/scheduler.py:209` from using the 5s default to explicitly passing `min_age_seconds=300`,
aligning with both the `/health` `STALE_RUNNING_SECONDS=300` constant and the existing `run_once()`
call site (which already passed `min_age_seconds=300`). The 5s default in `reconcile_aborted_jobs`
signature is preserved for callers that want a tighter sweep. Added a new async test
`test_daemon_start_reconcile_uses_300s_threshold` to `test_014_daemon.py` that patches all I/O,
intercepts the `reconcile_aborted_jobs` call, and asserts `min_age_seconds == 300`.

---

## Skipped Issues

None — all 3 in-scope findings were fixed.

---

_Fixed: 2026-04-22T04:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
