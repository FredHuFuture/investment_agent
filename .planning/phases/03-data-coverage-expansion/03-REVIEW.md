---
phase: 03-data-coverage-expansion
reviewed: 2026-04-21T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - Makefile
  - agents/fundamental.py
  - agents/sentiment.py
  - api/app.py
  - api/log_format.py
  - api/routes/health.py
  - daemon/scheduler.py
  - data_providers/edgar_provider.py
  - data_providers/finnhub_provider.py
  - data_providers/sector_pe_cache.py
  - pyproject.toml
  - run.ps1
  - scripts/__init__.py
  - scripts/ensure_pid.py
  - scripts/fetch_finbert.py
  - tests/test_data_coverage_01_finnhub.py
  - tests/test_data_coverage_02_finbert.py
  - tests/test_data_coverage_03_edgar.py
  - tests/test_data_coverage_04_health.py
  - tests/test_data_coverage_05_pid_bind.py
findings:
  critical: 0
  warning: 3
  info: 5
  total: 8
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-04-21
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 3 delivers DATA-01 through DATA-05 cleanly across 13 commits. The critical
contract items from the review scope all pass: the FOUND-04 `backtest_mode`
early-return at line 56 of `fundamental.py` is untouched, the dual-guard defense
at line 140 is present, and neither the Finnhub nor EDGAR code paths can execute in
backtest mode. The FinBERT lazy-import design is correct — the subprocess guard test
correctly verifies no eager pull of `transformers`/`torch`. The `AsyncRateLimiter`
is a sliding-window implementation (not fixed-window), so the burst-across-windows
concern from the review scope does not apply. The `os.kill(pid, 0)` Windows handling
covers both `errno.ESRCH` and `winerror=87`. The insider_score math is correct and
clamped.

Three warnings warrant attention before the next feature phase. No critical issues
were found.

---

## Warnings

### WR-01: `uptime_seconds` in `/health` measures oldest active job age, not daemon uptime

**File:** `api/routes/health.py:113-131`
**Issue:** The field is named `uptime_seconds` and documented as "how long the daemon
has been running," but the implementation queries `MIN(started_at) FROM job_run_log
WHERE status = 'running'`. This returns the age of the oldest *currently-running job
row*, not the daemon process's actual start time. If no jobs are in `'running'` state
(normal between job runs), the field returns `None`. A monitoring consumer interpreting
`null` as "daemon not running" will get false alerts during idle periods.
**Fix:** Two options — (a) expose the daemon's true start time by having
`scheduler.py.start()` insert a sentinel row (e.g., status='started') and reading
`MAX(started_at) WHERE status='started'`; or (b) rename the field to
`oldest_running_job_seconds` and document it as job-age rather than process-age, and
accept `null` as "no active jobs." The second option is low-risk and honest about what
the data actually is.

```python
# Option B: rename for clarity in the response dict
daemon_info["oldest_running_job_seconds"] = None   # rename from uptime_seconds
# ... query stays the same, but field name matches semantics
```

### WR-02: `sector_pe_cache._finnhub_provider` singleton leaks across test modules

**File:** `data_providers/sector_pe_cache.py:61-74` and
`tests/test_data_coverage_01_finnhub.py:327-330`
**Issue:** `_finnhub_provider` is a module-level global that is set on the first call
to `_get_finnhub_provider()` when `FINNHUB_API_KEY` is set. Tests in
`test_data_coverage_01_finnhub.py` correctly reset it via
`sector_pe_cache._finnhub_provider = None` before each test. However, if tests from
another module call `get_sector_pe_median()` with `FINNHUB_API_KEY` set (e.g., through
`FundamentalAgent.analyze`) and the test finishes without resetting the singleton, the
live `FinnhubProvider` instance persists into subsequent tests in the same process.
The `test_data_coverage_03_edgar.py` integration tests mock out `sector_pe_cache`
entirely (via `sys.modules`), so they are safe. But if the test execution order changes
or new tests are added that call `FundamentalAgent.analyze` without mocking
`sector_pe_cache`, a stale provider could cause surprising cross-test state.
**Fix:** Add a `_reset_sector_pe_cache()` helper to `sector_pe_cache.py` (or add an
`autouse` fixture in `conftest.py`) that clears both `_cache` and `_finnhub_provider`
before each test module that touches `FundamentalAgent`.

```python
# In conftest.py or as a module-scoped fixture:
@pytest.fixture(autouse=True)
def _reset_sector_pe_cache():
    from data_providers import sector_pe_cache
    sector_pe_cache._cache.clear()
    sector_pe_cache._source_cache.clear()
    sector_pe_cache._finnhub_provider = None
    yield
    sector_pe_cache._cache.clear()
    sector_pe_cache._source_cache.clear()
    sector_pe_cache._finnhub_provider = None
```

### WR-03: `stale_running` threshold in `/health` (300s) disagrees with `reconcile_aborted_jobs` default threshold (5s)

**File:** `api/routes/health.py:39` vs `daemon/jobs.py:896`
**Issue:** The `/health` endpoint flags a job as stale-running after 300 seconds
(`STALE_RUNNING_SECONDS = 300`). The reconciliation job in `daemon.start()` uses
`min_age_seconds=5` (the default) — it will mark jobs aborted after just 5 seconds of
idle. This means during the window between daemon restart (5s reconciliation) and the
health endpoint's view (300s stale threshold), there is an asymmetry: health could report
`stale_running > 0` for jobs that the daemon already reconciled in a previous run but
the DB still shows `status='running'` because the process crashed before writing
`status='error'`. In practice the reconciliation call in `start()` would clean up before
the scheduler runs new jobs, so this is not a crash path. The concern is monitoring
coherence: the health check's 300s threshold matches the `run_once` path's 300s
threshold (line 272 of scheduler.py) but not the `start()` path's 5s threshold.
**Fix:** Document the intentional mismatch in `health.py` comments, or align both
thresholds. If jobs legitimately take more than 5s, the default `min_age_seconds=5` in
`reconcile_aborted_jobs` is too aggressive for the `start()` path and should also be 300s.

```python
# daemon/scheduler.py line 204 — align with health.py STALE_RUNNING_SECONDS:
aborted_count = await reconcile_aborted_jobs(self._config.db_path, min_age_seconds=300)
```

---

## Info

### IN-01: `_get_finnhub_provider()` singleton never closed — httpx client accumulates unclosed connections

**File:** `data_providers/sector_pe_cache.py:64-74`
**Issue:** `_finnhub_provider` holds a `FinnhubProvider` instance whose `httpx.AsyncClient`
is never closed. For a long-running process (daemon or API server) this is a low-severity
resource leak — httpx uses connection pooling internally so connections do eventually time
out, but the explicit `aclose()` on `FinnhubProvider` is never called. There is no
lifecycle hook to close the cached provider on server shutdown.
**Fix:** Either call `await _finnhub_provider.aclose()` in a lifespan shutdown hook, or
rely on process termination (acceptable for solo-operator scope). At minimum document
the known leak:

```python
# sector_pe_cache.py — add docstring note:
# NOTE: The cached provider's httpx client is not explicitly closed.
# Connections will be released on process exit (acceptable for solo-operator scope).
# For long-running daemon use, wire aclose() into the shutdown lifecycle.
```

### IN-02: `_source_cache` not invalidated when TTL cache expires — can return stale source label

**File:** `data_providers/sector_pe_cache.py:103-138`
**Issue:** When a cached entry expires and the `get_sector_pe_median()` function fetches
fresh data from a different source (e.g., Finnhub was down on the previous fill, so
`_source_cache[key] = "static"`, but now Finnhub is available so `_source_cache[key]`
gets overwritten to `"finnhub"`), the behavior is correct. However if the *new* fetch
also fails (falls through to static), `_source_cache[key]` stays as the old source string
until a successful non-static fetch overwrites it. The static fallback at line 135-137
unconditionally sets `_source_cache[key] = "static"`, so this case is actually handled.
This is informational — the logic is correct but the code path is subtle.
**Fix:** No code change needed. Add an inline comment at line 135 clarifying that the
static branch also updates `_source_cache`:

```python
# Priority 3: Static fallback
static_pe = STATIC_SECTOR_PE.get(key)
if static_pe is not None:
    _source_cache[key] = "static"  # always update source on static fill
return static_pe
```

### IN-03: `ensure_pid_file` TOCTOU race window not acknowledged in code comments

**File:** `scripts/ensure_pid.py:70-88`
**Issue:** `ensure_pid_file` calls `check_pid_file` then `path.write_text` — there is a
race window between the check and the write where another process could also pass the check
and both write their PIDs. The plan acknowledges this risk. The code comment at line 80 does
not mention the race. For a solo-operator local-first app this is acceptable, but a future
multi-instance deployment could hit this.
**Fix:** Add a brief comment acknowledging the TOCTOU window:

```python
def ensure_pid_file(path: Path = DEFAULT_PID_PATH) -> int:
    # TOCTOU note: check_pid_file + write_text is not atomic.  For a solo-operator
    # local daemon this is acceptable — two concurrent daemon starts are unlikely.
    path.parent.mkdir(parents=True, exist_ok=True)
    ...
```

### IN-04: `install_json_logging()` called before uvicorn starts — comment about `propagate=False` is slightly misleading

**File:** `api/log_format.py:94-95`
**Issue:** The comment reads "Clearing root-logger handlers does NOT affect
`uvicorn.access` and `uvicorn.error` loggers because they are named loggers with
`propagate=False` after uvicorn configures them." The key word is "after" — at the
time `install_json_logging()` runs (module import, before uvicorn starts), uvicorn
has not yet configured its loggers. The root-logger handler replacement is still safe
because uvicorn *replaces* its own handlers when it starts, but the comment implies
the uvicorn loggers are already isolated at the time of the call, which is only true
retrospectively. This does not affect behavior.
**Fix:** Update comment to be temporally precise:

```python
# Uvicorn configures its own named loggers (uvicorn.access, uvicorn.error) with
# propagate=False when it starts, so this root-logger change does not affect
# uvicorn's access/error logs after uvicorn initialises.  Safe to call before
# uvicorn starts.
```

### IN-05: `_FINBERT_IMPORT_ATTEMPTED` is not reset between independent test runs when transformers is genuinely installed

**File:** `tests/test_data_coverage_02_finbert.py:145-148`
**Issue:** The `_reset_finbert_globals` helper correctly uses `monkeypatch.setattr`,
which reverts after each test. However, T8 (pipeline caching test) verifies that
`pipeline()` is called once across two `analyze()` calls. If `transformers` is genuinely
installed in the test environment (e.g., a CI machine with `.[all]`), T2 will succeed
via real FinBERT, but the `fake_transformers` injection pattern will still be used
because the test inserts the fake module via `sys.modules`. The fake module is injected
before the `_FINBERT_IMPORT_ATTEMPTED=False` guard runs. Since `_try_load_finbert`
checks `_FINBERT_IMPORT_ATTEMPTED` first and returns early, a fresh agent created after
`_reset_finbert_globals` will try to import from `sys.modules["transformers"]` (the fake).
This works correctly. However the subprocess test `test_import_does_not_pull_transformers`
will fail if `transformers` is installed and something in the dependency chain imports it
at module load time of a transitive dependency. This is a correctness concern for
`.[all]` CI environments, but does not affect the `.[dev]`-only environment assumed by
the test suite.
**Fix:** Document in the test file that these tests assume `transformers` is not installed
in the active environment, or add `@pytest.mark.skipif(importlib.util.find_spec('transformers') is not None, reason="real transformers installed")` on the subprocess test.

---

## Scrutiny Item Disposition

The following items from the review brief were specifically checked:

| # | Item | Finding |
|---|------|---------|
| 1 | FOUND-04 backtest_mode preservation | PASS. Early-return at `fundamental.py:56` intact. Double-guard `if not backtest_mode:` at line 140. Both guards confirmed in test I4 (finnhub) and T16 (edgar). |
| 2 | FinBERT lazy import | PASS. No top-level `transformers`/`torch` import. Subprocess test at `test_data_coverage_02_finbert.py:155` verifies this in a clean subprocess. |
| 3 | Finnhub rate-limit type | PASS. `AsyncRateLimiter` is a sliding-window implementation (deque + `now - oldest >= period`). No fixed-window burst vulnerability. |
| 4 | EDGAR User-Agent compliance | PASS. `"Investment Agent solo-operator@localhost"` follows the `Name email@example.com` pattern SEC accepts for low-volume non-commercial operators. |
| 5 | `asyncio.to_thread` rate-limit scope | PASS by design. The limiter gates call *rate* (how many slots per period), not concurrent connection count. `to_thread` occupies the thread pool, not the rate-limiter slot. The slot is released after `acquire()` records the call. This is standard rate-limiter behavior. |
| 6 | `/health` SQL edge cases | PASS. `GROUP BY status` on empty table returns zero rows, handled by the per-row `async for` loop. `stale_running` uses `started_at` (correct). `jobs_last_24h` uses `started_at >= day_ago` (correct — activity in last 24h). |
| 7 | JSON formatter root-logger clearing | PASS (with IN-04 caveat on comment accuracy). uvicorn loggers set `propagate=False` after startup so behavior is safe. Daemon's RotatingFileHandler is NOT routed through `install_json_logging` — daemon calls `_setup_logging()` which adds its own JSON handlers directly to the named `"investment_daemon"` logger, not the root logger. |
| 8 | PID race + atexit | PASS with IN-03 info note. SIGTERM is handled via `loop.add_signal_handler` on POSIX. `atexit` handles SIGKILL (process exit). Windows does not receive SIGTERM, but the daemon process exit path goes through atexit. |
| 9 | `os.kill(pid, 0)` on Windows | PASS. `ensure_pid.py:42` checks `winerror=87` (ERROR_INVALID_PARAMETER) for dead PIDs on Windows, in addition to `errno.ESRCH` which covers POSIX. |
| 10 | `_build_reasoning` backward compat | PASS. Both `sector_pe_source` and `insider_info` are keyword args with defaults (`"static"` and `None`). All 4 combinations produce valid reasoning strings. |
| 11 | `insider_score` application and clamping | PASS. `composite + insider_score * 100.0` adds ±10 points (0.10 × 100). `_clamp` bounds to `[-100, 100]`. No overflow possible. |
| 12 | API key in logs | PASS. `finnhub_provider.py` explicitly never logs the token (security note T-03-01-01). httpx `default_params` are not logged by httpx at INFO level. No `extra={"api_key": ...}` calls found. |
| 13 | EDGAR user-agent leak in logs | PASS. No log statement passes `_user_agent` as an extra field. `edgar.set_identity()` call is in `__init__`, not in any log statement. |

---

## Clean Files

The following files were reviewed and found to contain no issues:

- `Makefile` — correct `--host 127.0.0.1` on the `run-backend` target.
- `run.ps1` — correct `--host 127.0.0.1` on both the `-Backend` block and the background job block (2 occurrences, matching the test assertion).
- `pyproject.toml` — `[llm-local]` group correctly gates `transformers`/`torch`. `edgartools>=3.0` in core deps (not optional). No `structlog` or `python-json-logger`.
- `scripts/__init__.py` — empty init file, appropriate.
- `scripts/fetch_finbert.py` — correct guard for missing `transformers`, clean download logic.
- `data_providers/finnhub_provider.py` — `aclose()` present, token in `default_params` only, 429 handled gracefully, `get_price_history` correctly raises `NotImplementedError`.
- `agents/sentiment.py` — 3-branch fallback logic correct, `_filter_recent` handles timezone-naive timestamps safely, `parse_sentiment_response` validates all fields with fallbacks.
- `data_providers/edgar_provider.py` — `asyncio.to_thread` wrapping correct, per-filing exception handling continues rather than aborts, share count conversion handles floats.
- `api/app.py` — `install_json_logging()` called before uvicorn starts (acceptable), lifespan pattern correct, all routers registered.
- `tests/test_data_coverage_01_finnhub.py` — cache cleared before each integration test, backtest_mode regression test (I4) confirms `get_sector_pe_median` not called.
- `tests/test_data_coverage_02_finbert.py` — `_reset_finbert_globals` applied consistently, subprocess guard test correctly verifies lazy import.
- `tests/test_data_coverage_03_edgar.py` — `sys.modules` injection pattern correct, FOUND-04 regression test confirms `edgar_called=False`.
- `tests/test_data_coverage_04_health.py` — fixtures use `tmp_path` correctly, all schema fields tested, degraded-on-DB-error path covered.
- `tests/test_data_coverage_05_pid_bind.py` — stale PID (9999999) is a reasonable dead-PID proxy, CLI test verifies exit code.

---

_Reviewed: 2026-04-21_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
