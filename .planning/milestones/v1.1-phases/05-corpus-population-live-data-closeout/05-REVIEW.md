---
phase: 05-corpus-population-live-data-closeout
reviewed: 2026-04-22T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - api/models.py
  - api/routes/calibration.py
  - db/database.py
  - scripts/verify_close_01_finbert.py
  - scripts/verify_close_02_finnhub.py
  - scripts/verify_close_03_daemon_pid.py
  - tests/test_close_01_finbert_live.py
  - tests/test_close_02_finnhub_live.py
  - tests/test_close_03_daemon_pid_live.py
  - tests/test_live_01_corpus_rebuild.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-04-22T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 5 lands the LIVE-01 batch corpus rebuild (POST + GET endpoints with a new
`corpus_rebuild_jobs` table) and closes out three human UAT items (CLOSE-01 FinBERT,
CLOSE-02 Finnhub, CLOSE-03 daemon PID). Overall the code is well-structured. The
FOUND-07 single-element list contract is preserved correctly, UUID job_id is generated
via `uuid.uuid4().hex`, and the FinBERT lazy-import contract (no top-level `import
transformers`) is maintained. No secrets are committed.

Two warnings require attention: (1) `_run_batch_rebuild` has no outer-level exception
guard, so a systemic failure before the per-ticker loop begins (e.g., `ImportError`
importing `rebuild_signal_corpus`) will leave the job row stuck in `'running'` forever;
(2) `error_message` on `corpus_rebuild_jobs` is never written by the current code,
making the column defined but dead in the schema.

Three informational items are noted: a missing test for zero-position 400 path, a minor
gotcha in the `verify_close_03_daemon_pid.py` operator script where `pid_content ==
str(daemon_proc.pid)` can produce a false-negative on Windows, and a dead schema column.

---

## Warnings

### WR-01: No outer exception guard in `_run_batch_rebuild` — job stuck `'running'` on systemic failure

**File:** `api/routes/calibration.py:265`

**Issue:** `_run_batch_rebuild` wraps each *per-ticker* call in a `try/except Exception`
(line 296-317), but there is no outer `try/except` around the function body itself.
If anything raises before the loop begins — most concretely the deferred import at
line 283 (`from daemon.jobs import rebuild_signal_corpus`) raising `ImportError` or
`ModuleNotFoundError` — the function exits without updating the job row. The row
inserted at `status='running'` by the POST handler (line 191-206) will stay `'running'`
indefinitely. Any subsequent `GET /{job_id}` will return `status='running'` with
`tickers_completed=0`, giving the operator no signal that something went wrong and no
mechanism to detect the stuck job short of a database inspection.

The inner `try` on the final status UPDATE (line 331-347) only protects the DB write
itself — it does not help here because the function never reaches that point.

**Fix:**

```python
async def _run_batch_rebuild(
    db_path: str,
    job_id: str,
    tickers_with_type: list[tuple[str, str]],
) -> None:
    """..."""
    try:
        from daemon.jobs import rebuild_signal_corpus
    except Exception as import_exc:
        _route_logger.error(
            "rebuild_corpus_batch: failed to import rebuild_signal_corpus for job_id=%s: %s",
            job_id,
            import_exc,
        )
        # Mark job as error so GET polling surfaces the failure
        try:
            async with aiosqlite.connect(db_path) as conn:
                await conn.execute(
                    """
                    UPDATE corpus_rebuild_jobs
                    SET status = 'error', completed_at = ?, error_message = ?
                    WHERE job_id = ?
                    """,
                    (
                        datetime.now(timezone.utc).isoformat(),
                        str(import_exc)[:500],
                        job_id,
                    ),
                )
                await conn.commit()
        except Exception:
            pass
        return

    # ... existing loop ...
```

Alternatively, wrap the entire function body in a single outer `try/except Exception`
that catches any unhandled raise and writes `status='error'` + `error_message` before
returning, then re-raises nothing. This is the more thorough mitigation.

---

### WR-02: `error_message` column on `corpus_rebuild_jobs` is never written

**File:** `api/routes/calibration.py:331-347` / `db/database.py:649-669`

**Issue:** The `corpus_rebuild_jobs` DDL declares an `error_message TEXT` column
(database.py line 665), and `RebuildCorpusProgressResponse` exposes it as an optional
field (models.py line 215). However, no `UPDATE` statement in `calibration.py` ever
sets `error_message`. The final-status UPDATE at line 333-340 only sets `status`,
`completed_at`, and `ticker_progress_json`. The `_update_progress` helper also never
touches it. Per-ticker error text is stored inside `ticker_progress_json["ticker"]["error"]`
— which is correct for individual failures — but the top-level `error_message` field
intended for systemic failures (referenced in WR-01 above) is dead code.

This means:
- `GET /{job_id}` always returns `error_message: null` regardless of what happened.
- If the WR-01 fix is implemented, the `error_message` column becomes live; until then
  it is always null.

**Fix:** Either (a) implement WR-01 which activates the column for systemic failures, or
(b) if the column is intentionally reserved for future use, add a comment to the DDL and
the response model noting it is not yet populated. At minimum, the dead column should not
be silently misleading — a GET response showing `error_message: null` on a `status:
'error'` job is confusing.

---

## Info

### IN-01: No test coverage for zero-open-positions 400 path

**File:** `tests/test_live_01_corpus_rebuild.py`

**Issue:** `rebuild_corpus_endpoint` raises HTTP 400 when `tickers_with_type` is empty
(calibration.py lines 179-185). This fires when `tickers=null` and the portfolio has no
open positions. There is a test for `null` tickers with seeded positions
(`test_rebuild_corpus_null_tickers_enumerates_portfolio`) but no test for the empty-
portfolio 400 case. The `test_rebuild_corpus_background_task_does_not_leak_on_exception`
test name suggests coverage of exception handling but exercises per-ticker failures, not
the empty-portfolio guard. The 400 path is code that can fail in production.

**Fix:** Add a test:

```python
def test_rebuild_corpus_null_tickers_empty_portfolio_returns_400(tmp_path: Path) -> None:
    """POST with tickers=null on an empty portfolio returns 400."""
    from api.app import create_app
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "test.db")
    asyncio.run(init_db(db_path))
    app = create_app(db_path=db_path)

    with TestClient(app) as client:
        resp = client.post(
            "/analytics/calibration/rebuild-corpus",
            json={"tickers": None},
        )
    assert resp.status_code == 400
```

---

### IN-02: `verify_close_03_daemon_pid.py` PID-match assertion is flawed on Windows

**File:** `scripts/verify_close_03_daemon_pid.py:80`

**Issue:** Line 80 prints:
```
pid_file_matches_proc: {pid_content == str(daemon_proc.pid)}
```
On Windows, `subprocess.Popen` spawns a child process, but `daemon.scheduler` internally
calls `ensure_pid_file()` which writes `os.getpid()` — the PID of the daemon process
*itself*, not the PID of the `subprocess.Popen` wrapper. On POSIX these are the same
process. On Windows, if the daemon spawns any sub-subprocess at startup (e.g., a worker
thread using spawn multiprocessing), or if `sys.executable ... -m daemon.scheduler`
results in an intermediate launcher, the PID written to the file will differ from
`daemon_proc.pid`. The printout will show `False` and confuse the operator.

The automated test in `test_close_03_daemon_pid_live.py` avoids this issue by using
`_subprocess_launcher_script` (a direct inline script that calls `ensure_pid_file`
itself), so the test is correct. This is an operator script quality issue only —
it cannot be mistaken for a passing assertion.

**Fix:** Either document the limitation explicitly in the script's output or replace the
comparison with a `psutil`-based check that verifies the PID is in the subprocess tree,
or change the printout to:

```python
print(f"  pid_file_matches_proc: {pid_content == str(daemon_proc.pid)} "
      f"(may be False on Windows if daemon spawns sub-process)")
```

---

### IN-03: `idx_crj_job_id` index is redundant given the UNIQUE constraint

**File:** `db/database.py:670-675`

**Issue:** The `corpus_rebuild_jobs.job_id` column carries `UNIQUE` (line 658), which
SQLite automatically backs with an index. The explicit `CREATE INDEX idx_crj_job_id ON
corpus_rebuild_jobs(job_id)` at line 671 creates a second, redundant index on the same
column. SQLite will maintain both indexes on every INSERT/UPDATE, doubling write overhead
for this column (negligible in practice but architecturally incorrect). The UNIQUE
constraint's implicit index already covers all query patterns for `WHERE job_id = ?`.

**Fix:** Remove the explicit `CREATE INDEX IF NOT EXISTS idx_crj_job_id` statement.
`idx_crj_status` (the second explicit index) is non-redundant and correct — keep it.

---

## Test Coverage Notes

- **FOUND-07 preservation:** `test_rebuild_corpus_delegates_per_ticker` correctly asserts
  `len(tickers) == 1` inside the stub. The stub raises `AssertionError` if called with a
  multi-element list, making the test genuinely fail if FOUND-07 is violated.

- **FinBERT lazy-import contract (CLOSE-01):** Confirmed. `test_close_01_finbert_live.py`
  has no top-level `import transformers` or `from transformers`. Module-level code only
  uses `importlib.util.find_spec("transformers")`. `SentimentAgent` and `AgentInput` are
  imported inside function bodies only. The `--collect-only` guard is satisfied.

- **Finnhub skipif guard (CLOSE-02):** All three live tests carry
  `@pytest.mark.skipif(not finnhub_key, ...)`. The meta-test
  `test_finnhub_live_tests_skip_cleanly_when_key_unset` introspects `pytestmark`
  correctly. `spc._finnhub_provider = None` reset is done in test setup (not teardown),
  matching the review criterion.

- **Daemon PID subprocess (CLOSE-03):** Subprocess exits naturally (3-second sleep then
  clean exit). `proc.wait(timeout=10)` is used — not `proc.kill()`. The Windows atexit
  quirk is documented in the module docstring. `os.kill(pid, 0)` is used in
  `ensure_pid.py` for cross-platform liveness checks (no `psutil` dependency required).

- **BackgroundTasks synchrony:** Tests correctly rely on TestClient's synchronous
  BackgroundTasks execution. The `test_rebuild_corpus_progress_endpoint_polls_live_status`
  test comments explicitly acknowledge this. No test incorrectly polls for mid-flight
  `status='running'` in TestClient context.

- **`test_rebuild_corpus_background_task_does_not_leak_on_exception`:** This test
  verifies per-ticker exception isolation correctly — the stub raises `RuntimeError` for
  every ticker, the job ends `status='error'`, and a second POST succeeds. This is
  genuine coverage, not a vacuous pass.

- **No secrets committed:** No `FINNHUB_API_KEY=<actual>`, `ANTHROPIC_API_KEY=<actual>`,
  or `sk-*` secrets found in any reviewed file. Test files use `sk-test` as a fake
  sentinel for env-var presence checks only.

- **Router registration:** `api/routes/calibration.py` router is registered in
  `api/app.py` at line 128 with prefix `/analytics`. The new endpoints at
  `/calibration/rebuild-corpus` mount correctly as
  `POST /analytics/calibration/rebuild-corpus` and
  `GET /analytics/calibration/rebuild-corpus/{job_id}`. No new registration required.

- **UUID job_id and path injection:** `job_id = uuid.uuid4().hex` (line 187) — correct.
  The GET endpoint passes `job_id` directly into a parameterized SQL query
  (`WHERE job_id = ?`, line 244), so SQLite handles sanitization. FastAPI path parameter
  extraction provides no filesystem access, making path traversal via `../` inert.

## Clean Files

The following reviewed files have no issues:

- `api/models.py` — Pydantic models are well-typed; `_validate_ticker_length` validator
  correctly uppercases and length-checks tickers; `RebuildCorpusProgressResponse`
  status literal matches DDL enum values exactly.
- `scripts/verify_close_01_finbert.py` — Correct `__main__` guard; exits 0/2;
  lazy imports inside `main()`.
- `scripts/verify_close_02_finnhub.py` — Correct `__main__` guard; exits 0/2;
  `spc._finnhub_provider = None` reset present.
- `tests/test_close_01_finbert_live.py` — Skipif guard present on all live tests;
  meta-test `test_finbert_live_tests_skip_cleanly_when_unavailable` runs unconditionally
  and verifies marker presence; no top-level live imports.
- `tests/test_close_02_finnhub_live.py` — Skipif + network markers on all live tests;
  meta-test correct; `spc._finnhub_provider = None` reset in test body.
- `tests/test_close_03_daemon_pid_live.py` — Natural-exit subprocess pattern; `clean_pid_file`
  fixture provides test isolation; `test_localhost_bind_assertions_preserved` is a
  regression guard that reads real files.

---

_Reviewed: 2026-04-22T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
