---
phase: 03-data-coverage-expansion
plan: "04"
subsystem: observability
tags:
  - health-endpoint
  - structured-logging
  - pid-file
  - localhost-bind
  - DATA-04
  - DATA-05
dependency_graph:
  requires:
    - 01-02-SUMMARY.md  # FOUND-07 job_run_log schema (read-only)
  provides:
    - GET /health with job_run_log aggregation (daemon state, DB health)
    - api/log_format.py JsonFormatter (stdlib, no new deps)
    - data/daemon.pid lifecycle management
  affects:
    - daemon/scheduler.py (JSON logs, PID file on start/stop)
    - api/app.py (version 0.2.0, /health router, root JSON logger)
tech_stack:
  added: []
  patterns:
    - stdlib logging Formatter subclass for structured JSON logs
    - os.kill(pid, 0) cross-platform stale-PID detection
    - atexit + graceful stop for PID file cleanup
key_files:
  created:
    - api/routes/health.py
    - api/log_format.py
    - scripts/ensure_pid.py
    - tests/test_data_coverage_04_health.py
    - tests/test_data_coverage_05_pid_bind.py
  modified:
    - api/app.py
    - daemon/scheduler.py
    - run.ps1
    - Makefile
decisions:
  - "JsonFormatter placed in api/log_format.py (shared) so both API and daemon import from one location — avoids duplication"
  - "uptime_seconds = (now - MIN running started_at) accepted as approximation; true monotonic uptime would require shared state file written by daemon at start"
  - "install_json_logging() clears root-logger handlers; uvicorn.access and uvicorn.error are named loggers with propagate=False after uvicorn configures them, so they are unaffected"
  - "/health always returns HTTP 200; status='degraded' distinguishes api-up-db-down from api-down so external monitors work correctly"
  - "check_pid_file / ensure_pid_file / remove_pid_file are importable functions in scripts/ensure_pid.py so both daemon/scheduler.py and tests can import them directly"
  - "PID reconciliation in start() happens before _setup_logging() so any RuntimeError is visible before log setup completes"
metrics:
  duration_seconds: 1107
  completed_date: "2026-04-22"
  tasks_completed: 3
  files_created: 5
  files_modified: 4
---

# Phase 03 Plan 04: Operator Observability (DATA-04 + DATA-05) Summary

**One-liner:** Stdlib JSON logging + `GET /health` from `job_run_log` + `data/daemon.pid` lifecycle + 127.0.0.1 uvicorn bind (29 tests, 0 new deps).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | /health endpoint + JSON log formatter | ab47161 | api/routes/health.py, api/log_format.py, api/app.py, tests/test_data_coverage_04_health.py |
| 2 | Daemon logging -> JsonFormatter | dc58633 | daemon/scheduler.py |
| 3 | PID file + localhost bind | 5ba2f01 | scripts/ensure_pid.py, daemon/scheduler.py, run.ps1, Makefile, tests/test_data_coverage_05_pid_bind.py |

## Test Results

```
tests/test_data_coverage_04_health.py   17 passed
tests/test_data_coverage_05_pid_bind.py 12 passed
tests/test_014_daemon.py                10 passed  (pre-existing, unbroken)
Total new tests:                        29
```

All 39 tests (29 new + 10 pre-existing daemon) pass with `pytest tests/test_data_coverage_04_health.py tests/test_data_coverage_05_pid_bind.py tests/test_014_daemon.py -q`.

## Artifacts

### GET /health Response Example

```json
{
  "data": {
    "status": "ok",
    "api_version": "0.2.0",
    "daemon": {
      "last_run": "2026-04-21T03:00:00.123456+00:00",
      "last_run_job": "run_weekly_revaluation",
      "uptime_seconds": null,
      "jobs_last_24h": {
        "succeeded": 12,
        "failed": 0,
        "aborted": 1
      },
      "stale_running": 0,
      "pid_file_present": true,
      "pid": 12345
    },
    "db": {
      "wal_mode": true,
      "signal_history_rows": 47
    }
  },
  "warnings": []
}
```

`status` is `"ok"` when DB is reachable; `"degraded"` when DB query fails (always HTTP 200).

### JSON Log Format Example

Single-line JSON per record, written to stderr (API) and RotatingFileHandler (daemon):

```json
{"timestamp": "2026-04-22T03:00:01.234567+00:00", "level": "INFO", "logger": "investment_daemon", "message": "Investment monitoring daemon starting..."}
{"timestamp": "2026-04-22T03:05:02.345678+00:00", "level": "INFO", "logger": "investment_daemon", "message": "Scheduler started. Daily check: Mon-Fri 17:00:00 US/Eastern. Weekly revaluation: sat 10:00:00 US/Eastern."}
{"timestamp": "2026-04-22T03:05:03.456789+00:00", "level": "WARNING", "logger": "investment_daemon", "message": "Reconciled 1 stale 'running' job(s) to 'aborted'"}
{"timestamp": "2026-04-22T03:10:04.567890+00:00", "level": "ERROR", "logger": "investment_daemon", "message": "Job failed", "exc_info": "Traceback (most recent call last):\n  ...\nValueError: bad data"}
```

Extras are flattened to top level:
```json
{"timestamp": "...", "level": "INFO", "logger": "...", "message": "job done", "job_name": "daily_check", "duration_ms": 1234}
```

### PID File Behavior

```
daemon/scheduler.py start() flow:
  1. check_pid_file(data/daemon.pid)
     -> "missing"  : proceed
     -> "stale"    : remove_pid_file(), proceed
     -> "ok"       : raise RuntimeError("Daemon already running (pid=X)")
  2. ensure_pid_file(data/daemon.pid)  -- writes str(os.getpid())
  3. atexit.register(remove_pid_file, ...)  -- crash-safe cleanup
  4. ... normal start body ...

stop() flow:
  1. scheduler.shutdown()
  2. shutdown_event.set()
  3. remove_pid_file(data/daemon.pid)  -- graceful cleanup
```

Stale PID detection uses `os.kill(pid, 0)`:
- POSIX: raises `ProcessLookupError` (errno ESRCH) when process is gone
- Windows: raises `OSError` with `winerror=87` (ERROR_INVALID_PARAMETER) when PID is gone
- Both: raises `PermissionError` when process exists but is owned by another user (treated as alive)

### Localhost Bind Verification

```
run.ps1:    2 occurrences of "--host 127.0.0.1" (Backend mode + parallel Start-Job)
Makefile:   run-backend target uses "--host 127.0.0.1"
Comment in run.ps1 and api/app.py docstring document the LAN override procedure.
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] signal_history seed INSERT missing required NOT NULL columns**
- **Found during:** Task 1 test GREEN phase
- **Issue:** `_seed_signal_history` omitted `raw_score`, `consensus_score`, `agent_signals_json` (all NOT NULL) — caused `sqlite3.IntegrityError`
- **Fix:** Added all required columns to seed INSERT in test helper
- **Files modified:** tests/test_data_coverage_04_health.py
- **Commit:** ab47161 (included in same commit)

**2. [Rule 1 - Bug] pyproject.toml read used default encoding on Windows**
- **Found during:** Task 1 test GREEN phase (Windows GBK codec error)
- **Issue:** `Path("pyproject.toml").read_text()` uses system locale encoding (GBK on Windows) — fails on UTF-8 file with smart quotes
- **Fix:** Added `encoding="utf-8"` explicit argument
- **Files modified:** tests/test_data_coverage_04_health.py
- **Commit:** ab47161 (included in same commit)

## Open Follow-ups

- **T-03-04-01 (Auth for /health):** Endpoint is currently unauthenticated — acceptable for solo operator per threat model. API key middleware or JWT planned for Phase 4+.
- **uptime_seconds precision:** Current implementation uses `MIN(started_at)` of running rows as a proxy for daemon uptime. True uptime would require a daemon-written state file (e.g., `data/daemon-start.json`) outside job_run_log. Acceptable simplification for solo-operator use case.
- **PID file race window:** `check_pid_file` + `ensure_pid_file` are not atomic (TOCTOU). Documented in threat model T-03-04-08 as acceptable for solo-operator + rare launch scenario. `ensure_pid.py --remove-stale` resolves false-positive "already running" states.

## Known Stubs

None. All /health fields are wired to live data sources (job_run_log, signal_history COUNT, PRAGMA journal_mode, filesystem PID file).

## Threat Flags

No new network endpoints, auth paths, or schema changes beyond those documented in the plan's threat model (T-03-04-01 through T-03-04-08 all addressed).

## Self-Check: PASSED

| Item | Result |
|------|--------|
| api/routes/health.py | FOUND |
| api/log_format.py | FOUND |
| scripts/ensure_pid.py | FOUND |
| tests/test_data_coverage_04_health.py | FOUND |
| tests/test_data_coverage_05_pid_bind.py | FOUND |
| commit ab47161 | FOUND |
| commit dc58633 | FOUND |
| commit 5ba2f01 | FOUND |
