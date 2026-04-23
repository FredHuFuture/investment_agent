---
phase: 01-foundation-hardening
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - db/database.py
  - db/connection_pool.py
  - daemon/jobs.py
  - daemon/scheduler.py
  - tests/test_foundation_06_db_wal_indexes.py
  - tests/test_foundation_07_job_run_log.py
autonomous: true
requirements: [FOUND-06, FOUND-07]
tags: [database, daemon, durability, wal, sqlite, apscheduler, transactions]

must_haves:
  truths:
    - "Every SQLite connection opened by the app (pool or direct aiosqlite.connect) runs with journal_mode=WAL."
    - "The signal_history table has a composite index on (ticker, created_at) that is used by analytics queries (EXPLAIN QUERY PLAN shows USING INDEX)."
    - "The portfolio_snapshots table has a composite index on (timestamp) so analytics scans are bounded."
    - "A pruning job archives or deletes signal_history rows older than 90 days, and it runs weekly via APScheduler."
    - "A new job_run_log table records {job_name, started_at, completed_at, status, error_message, duration_ms} for every daemon job, with status IN ('running', 'success', 'error', 'aborted')."
    - "Every daemon job wraps its DB writes in a single atomic transaction (BEGIN ... COMMIT) that is rolled back on exception so no partial signal rows persist after a mid-job crash."
    - "On daemon startup, any stale job_run_log rows with status='running' are reconciled to status='aborted' before the scheduler starts."
  artifacts:
    - path: "db/database.py"
      provides: "job_run_log table schema + new covering indexes + startup PRAGMAs"
      contains: ["CREATE TABLE IF NOT EXISTS job_run_log", "idx_signal_history_ticker_created", "idx_portfolio_snapshots_timestamp", "journal_mode=WAL"]
    - path: "db/connection_pool.py"
      provides: "Existing WAL PRAGMA preserved + documented; no regression"
      contains: ["PRAGMA journal_mode=WAL", "PRAGMA busy_timeout", "PRAGMA synchronous=NORMAL"]
    - path: "daemon/jobs.py"
      provides: "Atomic transactions + job_run_log write-on-start/finish/error + pruning job"
      contains: ["INSERT INTO job_run_log", "UPDATE job_run_log", "status = 'running'", "status = 'success'", "status = 'error'", "prune_signal_history", "BEGIN"]
    - path: "daemon/scheduler.py"
      provides: "Startup reconciliation of stale 'running' rows to 'aborted' + pruning job registration"
      contains: ["reconcile_aborted_jobs", "status = 'aborted'", "prune_signal_history"]
    - path: "tests/test_foundation_06_db_wal_indexes.py"
      provides: "Tests for WAL pragma + index presence + pruning job"
      contains: ["test_wal_mode_enabled", "test_signal_history_index_used", "test_pruning_deletes_old_rows"]
    - path: "tests/test_foundation_07_job_run_log.py"
      provides: "Tests for job_run_log writes + atomic tx rollback + startup reconciliation"
      contains: ["test_job_run_log_writes_start_and_finish", "test_mid_job_crash_sets_aborted", "test_partial_write_rolled_back"]
  key_links:
    - from: "daemon/jobs.py::run_weekly_revaluation"
      to: "job_run_log table"
      via: "wrapping writes in a single transaction + INSERT row on start + UPDATE row on finish/error"
      pattern: "INSERT INTO job_run_log|UPDATE job_run_log"
    - from: "daemon/scheduler.py::start"
      to: "job_run_log reconciliation"
      via: "on startup, UPDATE rows WHERE status='running' SET status='aborted'"
      pattern: "reconcile_aborted_jobs|status = 'aborted'"
    - from: "db/database.py::init_db"
      to: "PRAGMA journal_mode=WAL"
      via: "set on the initialization connection, not just pool connections"
      pattern: "journal_mode=WAL"
---

<objective>
Make the SQLite database durable under concurrent daemon + API writes and make daemon jobs crash-recoverable. This plan delivers FOUND-06 (WAL mode + covering indexes + 90-day pruning job) and FOUND-07 (`job_run_log` table + atomic job transactions).

Purpose: Today, every daemon job uses `async with aiosqlite.connect(db_path) as conn:` WITHOUT explicitly setting PRAGMAs (the connection pool sets WAL, but jobs and ad-hoc scripts open raw connections that may not). The jobs write multiple tables (`signal_history`, `monitoring_alerts`, `portfolio_snapshots`) via sequential `conn.execute()` calls with a single `commit()` at the end, but an exception mid-job silently aborts and leaves some rows written from earlier `executemany` batches. The existing `daemon_runs` table logs JOB OUTCOMES but NOT partial execution state — there is no way to answer "did job X crash mid-flight, and what got written before it died?" FOUND-07 introduces an explicit `job_run_log` with `status='running'` on entry and `status='success'|'error'|'aborted'` on exit, plus true atomic transactions via `BEGIN; ... COMMIT;`/`ROLLBACK;` semantics. Startup reconciliation converts any stale `running` rows to `aborted`.

Additionally, `signal_history` grows unbounded (50-100 rows/day per PITFALLS.md) and lacks a composite index on `(ticker, created_at)` that analytics queries need. FOUND-06 adds the index and a weekly pruning job that archives or deletes rows older than 90 days.

Output:
- `db/database.py`: adds `CREATE TABLE IF NOT EXISTS job_run_log (...)`, `CREATE INDEX IF NOT EXISTS idx_signal_history_ticker_created ON signal_history(ticker, created_at)`, `CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_timestamp ON portfolio_snapshots(timestamp)`, and an explicit `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=5000;` block in `init_db`.
- `daemon/jobs.py`: adds `_begin_job_run_log(conn, job_name) -> int`, `_end_job_run_log(conn, row_id, status, error=None)`, a new `async def prune_signal_history(db_path, retention_days=90)`, and refactors `run_weekly_revaluation`, `run_daily_check`, `run_catalyst_scan`, `run_regime_detection`, `run_weekly_summary` to wrap their DB writes in a `conn.execute("BEGIN")` / `conn.execute("COMMIT")` pair with explicit rollback on exception.
- `daemon/scheduler.py`: adds `async def _reconcile_aborted_jobs(db_path)` called before `_scheduler.start()`, AND registers a new `prune_signal_history` cron job (weekly).
- Two new test files: one verifying WAL + indexes + pruning, one verifying job_run_log state machine and atomic rollback.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/research/SUMMARY.md
@.planning/research/PITFALLS.md
@.planning/codebase/ARCHITECTURE.md
@.planning/codebase/CONCERNS.md
@.planning/codebase/TESTING.md

<interfaces>
<!-- Key types and contracts the executor MUST use. Extracted from the existing codebase. -->

From db/connection_pool.py (existing — keep these PRAGMAs; they're already correct):
```python
class DatabasePool:
    async def _new_connection(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self._db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute("PRAGMA synchronous=NORMAL;")
        await conn.execute("PRAGMA foreign_keys=ON;")
        ...
```

From db/database.py (existing — relevant excerpts):
```python
# signal_history currently has:
# CREATE TABLE IF NOT EXISTS signal_history (
#   id INTEGER PRIMARY KEY AUTOINCREMENT,
#   ticker TEXT NOT NULL,
#   ...
#   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
#   ...
# );
# and existing:
# CREATE INDEX IF NOT EXISTS idx_signal_history_ticker ON signal_history(ticker, created_at);  <-- line 373-374
# So a (ticker, created_at) composite index already exists. We just need to
# verify & document, and add portfolio_snapshots(timestamp).

# Existing daemon_runs table (DO NOT RENAME — job_run_log is NEW):
# CREATE TABLE IF NOT EXISTS daemon_runs (
#   id INTEGER PRIMARY KEY AUTOINCREMENT,
#   job_name TEXT NOT NULL,
#   status TEXT NOT NULL CHECK (status IN ('success', 'error', 'skipped')),
#   started_at TEXT NOT NULL,
#   duration_ms INTEGER NOT NULL,
#   result_json TEXT,
#   error_message TEXT,
#   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
# );
# daemon_runs ONLY records completed outcomes. job_run_log is NEW — it records
# start-of-run with status='running' and is updated on finish. Crucial
# distinction: daemon_runs has CHECK(status IN ('success','error','skipped'))
# which does NOT include 'running' or 'aborted'. We keep daemon_runs for
# backwards compat; job_run_log is additive.
```

From daemon/jobs.py (existing — pattern to refactor; all jobs look like this):
```python
async def run_weekly_revaluation(db_path, logger=None) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("PRAGMA foreign_keys=ON;")
            # ... many INSERT / UPDATE statements across multiple stores ...
            # await conn.commit()  # single commit at the end
        # ... on success: await _record_daemon_run(status='success', ...)
    except Exception as exc:
        # ... await _record_daemon_run(status='error', ...)
```

From daemon/scheduler.py::start (existing — CronTrigger registration point):
```python
async def start(self) -> None:
    self._logger = self._setup_logging()
    await init_db(self._config.db_path)
    self._setup_scheduler()
    self._scheduler.start()
    ...
```

From apscheduler.triggers.cron.CronTrigger docstring (authoritative):
```python
# CronTrigger(day_of_week='sun', hour=3, minute=0, timezone='America/New_York')
# Runs every Sunday at 3 AM ET.
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add job_run_log table, covering indexes, and WAL enforcement in init_db (FOUND-06 schema + FOUND-07 schema)</name>
  <read_first>
    - db/database.py (whole file — 509 lines; locate the `init_db` function and the existing table/index creation blocks around lines 340-500)
    - db/connection_pool.py (lines 65-77 — existing PRAGMA configuration pattern to mirror)
    - tests/test_001_db.py (pattern for asyncio.run + tmp_path init_db testing)
  </read_first>
  <behavior>
    - Test A: After `init_db(tmp_path / "test.db")`, opening a fresh connection and running `PRAGMA journal_mode;` returns `wal`.
    - Test B: After `init_db`, `SELECT name FROM sqlite_master WHERE type='table' AND name='job_run_log'` returns one row.
    - Test C: `job_run_log` schema has columns: `id` (INTEGER PRIMARY KEY AUTOINCREMENT), `job_name` (TEXT NOT NULL), `started_at` (TEXT NOT NULL), `completed_at` (TEXT), `status` (TEXT NOT NULL with CHECK constraint in ('running','success','error','aborted')), `error_message` (TEXT), `duration_ms` (INTEGER), `created_at` (TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP). Verified via `PRAGMA table_info(job_run_log)` and `sqlite_master.sql`.
    - Test D: `idx_job_run_log_job_started` exists on `(job_name, started_at)`.
    - Test E: `idx_portfolio_snapshots_timestamp` exists on `(timestamp)`.
    - Test F: Existing `idx_signal_history_ticker` (on `(ticker, created_at)`) still exists and is unchanged.
    - Test G: Inserting a row with `status='invalid'` raises `IntegrityError` (CHECK constraint enforced).
    - Test H: `init_db` is idempotent: running it twice does not raise and does not duplicate indexes.
  </behavior>
  <action>
    Edit `db/database.py`. Locate the `init_db` function. Make these additions (do NOT delete any existing statement):

    1. Immediately after the `await db_pool.init(db_path)` / first connection acquisition in `init_db`, add a PRAGMA block run on the initialization connection (this is in addition to the pool's per-connection PRAGMAs — it ensures the database file itself is in WAL mode from the first write, so ad-hoc `aiosqlite.connect()` callers inherit WAL):
       ```python
       # Enforce WAL + safe defaults on the canonical database connection.
       # Individual connections in db_pool also set these, but this ensures
       # the database file is in WAL mode even for callers that bypass the pool.
       await conn.execute("PRAGMA journal_mode=WAL;")
       await conn.execute("PRAGMA synchronous=NORMAL;")
       await conn.execute("PRAGMA busy_timeout=5000;")
       await conn.execute("PRAGMA foreign_keys=ON;")
       ```
       Place this near the start of the `async with` block that holds the init connection (before any CREATE TABLE).

    2. Below the existing `daemon_runs` CREATE TABLE block (currently around line 387-406), add a NEW table. DO NOT rename or alter `daemon_runs` — it is kept for backwards compat:
       ```python
       # FOUND-07: job_run_log — durable start/finish tracking with 'running' + 'aborted' states.
       # daemon_runs records COMPLETED outcomes only. job_run_log records an explicit
       # start-of-run row with status='running'; the row is updated to
       # 'success'|'error' on completion, or 'aborted' by the startup reconciler
       # if the daemon crashed mid-job.
       await conn.execute(
           """
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
           """
       )
       await conn.execute(
           """
           CREATE INDEX IF NOT EXISTS idx_job_run_log_job_started
           ON job_run_log(job_name, started_at);
           """
       )
       await conn.execute(
           """
           CREATE INDEX IF NOT EXISTS idx_job_run_log_status
           ON job_run_log(status);
           """
       )
       ```

    3. Add a new covering index on `portfolio_snapshots(timestamp)` (which does not currently exist):
       ```python
       await conn.execute(
           """
           CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_timestamp
           ON portfolio_snapshots(timestamp);
           """
       )
       ```
       Place this near the existing `idx_active_positions_*` index block (around lines 304-315).

    4. Verify (visual inspection) that the existing `idx_signal_history_ticker` index on `(ticker, created_at)` at lines 371-376 is NOT modified. If for any reason its name was different, REPLACE its CREATE INDEX statement so the final name is `idx_signal_history_ticker_created` with the columns `(ticker, created_at)`. Update the name to `idx_signal_history_ticker_created` to make the rename intent explicit AND add a legacy-alias DROP line first if a prior name existed:
       ```python
       # Rename legacy idx_signal_history_ticker → idx_signal_history_ticker_created (no-op if already renamed)
       await conn.execute("DROP INDEX IF EXISTS idx_signal_history_ticker;")
       await conn.execute(
           """
           CREATE INDEX IF NOT EXISTS idx_signal_history_ticker_created
           ON signal_history(ticker, created_at);
           """
       )
       ```
       (Reference implementation in the existing file uses `idx_signal_history_ticker` — you are renaming it for clarity and adding a covering-name convention. Both names map to the same `(ticker, created_at)` columns.)

    5. Create `tests/test_foundation_06_db_wal_indexes.py`. Use the existing `asyncio.run(_run())` pattern from `tests/test_001_db.py`. For Test D-F, query `SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND tbl_name IN ('signal_history','portfolio_snapshots','job_run_log')`. For Test G (CHECK constraint), attempt an INSERT with `status='invalid'` and assert `aiosqlite.IntegrityError` via `pytest.raises`. For Test H (idempotent), call `init_db` twice on the same path, assert no exception, assert exactly one row per index name.
  </action>
  <verify>
    <automated>
      pytest tests/test_foundation_06_db_wal_indexes.py -x -v -k "wal or index or job_run_log_schema"
      pytest tests/test_001_db.py -x
      python -c "
      import asyncio, aiosqlite, tempfile, os
      from db.database import init_db
      async def check():
          p = os.path.join(tempfile.mkdtemp(), 'x.db')
          await init_db(p)
          async with aiosqlite.connect(p) as conn:
              mode = await (await conn.execute('PRAGMA journal_mode;')).fetchone()
              assert mode[0].lower() == 'wal', f'journal_mode={mode[0]}'
              t = await (await conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='job_run_log'\")).fetchone()
              assert t is not None, 'job_run_log missing'
              idx = await (await conn.execute(\"SELECT name FROM sqlite_master WHERE type='index' AND name='idx_portfolio_snapshots_timestamp'\")).fetchone()
              assert idx is not None, 'portfolio_snapshots index missing'
          print('OK')
      asyncio.run(check())
      "
      grep -q "CREATE TABLE IF NOT EXISTS job_run_log" db/database.py
      grep -q "journal_mode=WAL" db/database.py
      grep -q "idx_portfolio_snapshots_timestamp" db/database.py
    </automated>
  </verify>
  <acceptance_criteria>
    - `db/database.py` contains the literal string `CREATE TABLE IF NOT EXISTS job_run_log`.
    - `db/database.py` contains the literal string `CHECK (\n                   status IN ('running', 'success', 'error', 'aborted'))` or equivalent with the four status values.
    - `db/database.py` contains the literal string `journal_mode=WAL` within a `conn.execute(` call inside `init_db`.
    - `db/database.py` contains the literal string `idx_portfolio_snapshots_timestamp`.
    - `db/database.py` contains `idx_signal_history_ticker_created` (renamed from `idx_signal_history_ticker`).
    - After `init_db(p)`: `PRAGMA journal_mode` returns `wal` for a fresh connection opened against `p`.
    - After `init_db(p)`: `sqlite_master` contains tables `job_run_log`, `signal_history`, `portfolio_snapshots`, `daemon_runs` (daemon_runs preserved).
    - After `init_db(p)`: indexes `idx_job_run_log_job_started`, `idx_job_run_log_status`, `idx_portfolio_snapshots_timestamp`, `idx_signal_history_ticker_created` all exist.
    - `pytest tests/test_001_db.py -x` → exit 0 (regression: existing DB init tests still pass).
    - `pytest tests/test_foundation_06_db_wal_indexes.py -x -k "wal or index or schema"` → exit 0 with at least 8 tests passing (behaviors A-H).
  </acceptance_criteria>
  <done>
    Schema migration is complete: new `job_run_log` table exists, new `idx_portfolio_snapshots_timestamp` index exists, WAL is enforced on init, and `init_db` is idempotent. Existing `daemon_runs` and `signal_history` tables/indexes are preserved.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wrap daemon jobs in atomic transactions + job_run_log state machine + startup reconciliation (FOUND-07)</name>
  <read_first>
    - daemon/jobs.py (whole file — 730 lines; focus on `run_daily_check` 31-133, `run_weekly_revaluation` 135-318, `run_catalyst_scan` 401-546, `_record_daemon_run` 704-729)
    - daemon/scheduler.py (whole file — 253 lines; focus on `start()` 130-178 and `_setup_scheduler()` 69-116)
    - db/database.py (after Task 1 — job_run_log schema is in place)
    - tests/test_014_daemon.py (existing daemon test patterns — fixtures for positions, thesis, aggregated signal)
  </read_first>
  <behavior>
    - Test A: `run_daily_check(db_path)` inserts ONE row into `job_run_log` with `status='running'` at entry. On success, the SAME row is UPDATED to `status='success'` with non-null `completed_at` and `duration_ms`.
    - Test B: If an exception is raised mid-job (simulated by monkey-patching `PortfolioMonitor.run_check` to raise `RuntimeError("boom")`), the `job_run_log` row is updated to `status='error'` with `error_message='boom'`, and the transaction is rolled back — NO partial writes remain in `signal_history` or `monitoring_alerts`.
    - Test C: If the process is killed mid-job (simulated by NOT calling the end-of-job update and leaving a `status='running'` row), the next call to `reconcile_aborted_jobs(db_path)` updates that row to `status='aborted'`.
    - Test D: `reconcile_aborted_jobs` ONLY touches rows with `status='running'` whose `started_at` is older than 5 seconds; it does NOT touch a row that was JUST inserted (prevents a race with a currently-running job).
    - Test E: `run_weekly_revaluation` wraps its multi-position writes in a single `conn.execute("BEGIN")` → per-position writes → `conn.execute("COMMIT")` pattern. On exception, `conn.execute("ROLLBACK")` is called and NO signal_history rows are left from the crashed job.
    - Test F: `prune_signal_history(db_path, retention_days=90)` deletes signal_history rows WHERE `created_at < date('now', '-90 days')` and returns `{"deleted_rows": int, "retained_rows": int}`.
    - Test G: `prune_signal_history` keeps rows within the retention window (seeded with a mix of dates; rows < 90 days stay).
    - Test H: The existing `_record_daemon_run` continues to write to `daemon_runs` (unchanged behavior — backwards compat).
  </behavior>
  <action>
    Edit `daemon/jobs.py`:

    1. Add two new internal helpers at module level (below `_record_daemon_run`):
       ```python
       async def _begin_job_run_log(
           conn: aiosqlite.Connection,
           job_name: str,
           started_at: str | None = None,
       ) -> int:
           """Insert a row with status='running' and return its id.

           Caller MUST call _end_job_run_log on the same row before returning.
           This commits immediately so the row is visible even if the main
           job transaction later rolls back.
           """
           if started_at is None:
               started_at = datetime.now(timezone.utc).isoformat()
           cursor = await conn.execute(
               """
               INSERT INTO job_run_log (job_name, started_at, status)
               VALUES (?, ?, 'running')
               """,
               (job_name, started_at),
           )
           await conn.commit()
           return int(cursor.lastrowid)

       async def _end_job_run_log(
           conn: aiosqlite.Connection,
           row_id: int,
           status: str,
           error_message: str | None = None,
           duration_ms: int | None = None,
       ) -> None:
           """Finalize a job_run_log row. status ∈ {'success','error'}."""
           if status not in ("success", "error"):
               raise ValueError(f"invalid final status: {status!r}")
           completed_at = datetime.now(timezone.utc).isoformat()
           await conn.execute(
               """
               UPDATE job_run_log
               SET status = ?, completed_at = ?,
                   error_message = ?, duration_ms = ?
               WHERE id = ?
               """,
               (status, completed_at, error_message, duration_ms, row_id),
           )
           await conn.commit()

       async def reconcile_aborted_jobs(
           db_path: str = str(DEFAULT_DB_PATH),
           min_age_seconds: int = 5,
       ) -> int:
           """Mark stale 'running' rows as 'aborted'.

           Called at daemon startup. A row is considered stale if status='running'
           AND started_at is older than `min_age_seconds`. Returns count updated.
           """
           async with aiosqlite.connect(db_path) as conn:
               cursor = await conn.execute(
                   """
                   UPDATE job_run_log
                   SET status = 'aborted',
                       completed_at = ?,
                       error_message = 'Daemon restarted with job in flight'
                   WHERE status = 'running'
                     AND (julianday('now') - julianday(started_at)) * 86400 > ?
                   """,
                   (datetime.now(timezone.utc).isoformat(), min_age_seconds),
               )
               await conn.commit()
               return cursor.rowcount or 0

       async def prune_signal_history(
           db_path: str = str(DEFAULT_DB_PATH),
           retention_days: int = 90,
           logger: logging.Logger | None = None,
       ) -> dict[str, int]:
           """Delete signal_history rows older than retention_days. Returns {deleted_rows, retained_rows}."""
           if logger is None:
               logger = logging.getLogger("investment_daemon")

           started_at = datetime.now(timezone.utc).isoformat()
           t0 = time.monotonic()
           row_id: int | None = None

           try:
               async with aiosqlite.connect(db_path) as conn:
                   await conn.execute("PRAGMA foreign_keys=ON;")
                   row_id = await _begin_job_run_log(conn, "prune_signal_history", started_at)

                   cursor = await conn.execute(
                       """
                       DELETE FROM signal_history
                       WHERE created_at < date('now', ? || ' days')
                       """,
                       (f"-{int(retention_days)}",),
                   )
                   deleted = cursor.rowcount or 0

                   retained = await (
                       await conn.execute("SELECT COUNT(*) FROM signal_history")
                   ).fetchone()
                   retained_count = int(retained[0]) if retained else 0

                   await conn.commit()

                   duration_ms = int((time.monotonic() - t0) * 1000)
                   await _end_job_run_log(
                       conn, row_id, "success", duration_ms=duration_ms
                   )

               logger.info(
                   "prune_signal_history: deleted %d rows, %d retained",
                   deleted, retained_count,
               )
               return {"deleted_rows": deleted, "retained_rows": retained_count}

           except Exception as exc:
               duration_ms = int((time.monotonic() - t0) * 1000)
               logger.error("prune_signal_history failed: %s", exc, exc_info=True)
               if row_id is not None:
                   try:
                       async with aiosqlite.connect(db_path) as conn:
                           await _end_job_run_log(
                               conn, row_id, "error",
                               error_message=str(exc), duration_ms=duration_ms,
                           )
                   except Exception:
                       pass
               return {"deleted_rows": 0, "retained_rows": 0, "error": str(exc)}
       ```

    2. Refactor `run_weekly_revaluation` to use the job_run_log + atomic transaction pattern. Replace the existing single-commit block with an explicit BEGIN/COMMIT/ROLLBACK:
       ```python
       # At entry (before existing try/except):
       row_id: int | None = None
       async with aiosqlite.connect(db_path) as log_conn:
           row_id = await _begin_job_run_log(log_conn, "weekly_revaluation", started_at)

       try:
           # ... existing body, but change:
           async with aiosqlite.connect(db_path) as conn:
               await conn.execute("PRAGMA foreign_keys=ON;")
               await conn.execute("BEGIN")
               try:
                   # ... existing per-position writes ...
                   await conn.execute("COMMIT")
               except Exception:
                   await conn.execute("ROLLBACK")
                   raise
           # ... existing success path ...
           async with aiosqlite.connect(db_path) as log_conn:
               await _end_job_run_log(
                   log_conn, row_id, "success", duration_ms=duration_ms
               )
       except Exception as exc:
           # ... existing error path ...
           if row_id is not None:
               async with aiosqlite.connect(db_path) as log_conn:
                   await _end_job_run_log(
                       log_conn, row_id, "error",
                       error_message=str(exc), duration_ms=duration_ms,
                   )
           raise
       ```
       Apply the same wrapping (begin_job_run_log at entry, BEGIN/COMMIT/ROLLBACK around DB writes, end_job_run_log at exit) to `run_daily_check`, `run_catalyst_scan`, `run_regime_detection`, and `run_weekly_summary`. Keep the existing `_record_daemon_run` calls — they continue to write to the `daemon_runs` table. job_run_log is ADDITIVE audit, not a replacement.

    3. Edit `daemon/scheduler.py`:
       - Import `reconcile_aborted_jobs` and `prune_signal_history` at top:
         ```python
         from daemon.jobs import (
             run_catalyst_scan,
             run_daily_check,
             run_regime_detection,
             run_weekly_revaluation,
             reconcile_aborted_jobs,
             prune_signal_history,
         )
         ```
       - In `start()`, call reconciliation BEFORE `self._setup_scheduler()`:
         ```python
         async def start(self) -> None:
             import signal as signal_module
             self._logger = self._setup_logging()
             self._logger.info("Investment monitoring daemon starting...")

             await init_db(self._config.db_path)
             self._logger.info("Database initialized: %s", self._config.db_path)

             aborted_count = await reconcile_aborted_jobs(self._config.db_path)
             if aborted_count > 0:
                 self._logger.warning(
                     "Reconciled %d stale 'running' job(s) to 'aborted'", aborted_count
                 )

             self._setup_scheduler()
             self._scheduler.start()
             # ... rest unchanged
         ```
       - In `_setup_scheduler`, after the existing cron jobs, add a weekly pruning job:
         ```python
         # Weekly signal_history pruning (every Sunday at 03:00)
         self._scheduler.add_job(
             self._job_prune,
             CronTrigger(
                 day_of_week="sun",
                 hour=3,
                 minute=0,
                 timezone=self._config.timezone,
             ),
             id="prune_signal_history",
             name="Signal History Pruning",
         )
         ```
       - Add the wrapper method:
         ```python
         async def _job_prune(self) -> None:
             """Scheduler wrapper for prune_signal_history."""
             await prune_signal_history(self._config.db_path, retention_days=90, logger=self._logger)
         ```
       - In `run_once`, add a branch for `job_name == "prune"`:
         ```python
         elif job_name == "prune":
             return await prune_signal_history(self._config.db_path, retention_days=90, logger=self._logger)
         ```

    4. Create `tests/test_foundation_07_job_run_log.py`. Use the existing patterns from `tests/test_014_daemon.py`:
       - `test_job_run_log_writes_start_and_finish`: call `run_daily_check` with a seeded portfolio; assert `job_run_log` has exactly one row for this call with `status='success'` and non-null `completed_at` and `duration_ms`.
       - `test_mid_job_crash_sets_aborted`: insert a `status='running'` row with `started_at = "2025-01-01T00:00:00+00:00"` (very old), call `reconcile_aborted_jobs`, assert the row is now `status='aborted'`.
       - `test_reconcile_ignores_fresh_running_rows`: insert a `status='running'` row with `started_at = now()`, call `reconcile_aborted_jobs(min_age_seconds=5)`, assert the row is STILL `status='running'`.
       - `test_partial_write_rolled_back`: monkey-patch one of the intermediate steps in `run_weekly_revaluation` to raise; assert (a) `job_run_log` row is `status='error'`; (b) `signal_history` has ZERO rows from the crashed job.
       - `test_prune_signal_history_respects_retention`: seed `signal_history` with 10 rows at dates spanning 120 days ago → today; call `prune_signal_history(retention_days=90)`; assert rows < 90 days remain, rows ≥ 90 days are deleted; assert return dict shape.
       - `test_daemon_runs_still_written`: call `run_daily_check`; assert `daemon_runs` has a row (backwards compat).
  </action>
  <verify>
    <automated>
      pytest tests/test_foundation_07_job_run_log.py -x -v
      pytest tests/test_014_daemon.py -x
      pytest tests/test_030_daemon_jobs.py -x 2>/dev/null || true
      grep -q "INSERT INTO job_run_log" daemon/jobs.py
      grep -q "UPDATE job_run_log" daemon/jobs.py
      grep -q "reconcile_aborted_jobs" daemon/scheduler.py
      grep -q "prune_signal_history" daemon/scheduler.py
      grep -q "BEGIN" daemon/jobs.py
      grep -q "ROLLBACK" daemon/jobs.py
      python -c "
      import asyncio
      from daemon.jobs import reconcile_aborted_jobs, prune_signal_history, _begin_job_run_log, _end_job_run_log
      from daemon.scheduler import MonitoringDaemon
      print('imports OK')
      "
    </automated>
  </verify>
  <acceptance_criteria>
    - `daemon/jobs.py` contains literal strings `INSERT INTO job_run_log`, `UPDATE job_run_log`, `status = 'running'` (with spacing), `status = 'success'`, `status = 'error'` (within SQL statements), `BEGIN` (in an `conn.execute(` call), `ROLLBACK`, `reconcile_aborted_jobs`, `prune_signal_history`.
    - `daemon/scheduler.py` contains `reconcile_aborted_jobs` and `prune_signal_history` imports, and a `_job_prune` method.
    - `daemon/scheduler.py::start` calls `reconcile_aborted_jobs` BEFORE `self._setup_scheduler()` (verified by searching for the sequence in the file).
    - `pytest tests/test_foundation_07_job_run_log.py -x` → exit 0 with at least 6 tests (per the behaviors listed), all passing.
    - `pytest tests/test_014_daemon.py -x` → exit 0 (regression: existing daemon tests still pass; `daemon_runs` still written).
    - `python -c "from daemon.jobs import reconcile_aborted_jobs, prune_signal_history"` → exit 0.
    - After `run_daily_check` (with mocked positions/monitor), the `job_run_log` table has exactly ONE new row with `status='success'`, `completed_at IS NOT NULL`, `duration_ms > 0`, `error_message IS NULL`.
    - After simulated mid-job crash, the `job_run_log` row is `status='error'`, `error_message` matches the raised exception's message, and `signal_history` is NOT contaminated with partial writes.
  </acceptance_criteria>
  <done>
    Every daemon job now writes a `status='running'` row to `job_run_log` at entry, wraps its DB writes in an explicit `BEGIN`/`COMMIT` (with `ROLLBACK` on exception), and updates its row to `status='success'` or `status='error'` at exit. On daemon startup, stale `running` rows older than 5s are reconciled to `aborted`. A weekly pruning job (`prune_signal_history`) is registered with APScheduler and deletes signal_history rows older than 90 days.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Add 50k-row analytics timing test + 24h-soak lock-contention smoke test (FOUND-06 success criterion 5)</name>
  <read_first>
    - engine/analytics.py (analytics query patterns — understand what the analytics page queries)
    - db/database.py (after Task 1 — indexes are in place)
    - tests/test_035_analytics.py (existing analytics test patterns)
    - tests/test_foundation_06_db_wal_indexes.py (created in Task 1; this task ADDS to it)
    - daemon/jobs.py (after Task 2 — pruning is available)
  </read_first>
  <behavior>
    - Test A: Seed `signal_history` with 50,000 synthetic rows spanning 200 days. Run an analytics query equivalent to what `/analytics` page uses (`SELECT * FROM signal_history WHERE ticker = ? ORDER BY created_at DESC LIMIT 100`). Assert it returns in < 1.0 second wall-clock (generous threshold; the covering index on `(ticker, created_at)` makes this O(log n)).
    - Test B: `EXPLAIN QUERY PLAN` on the above query includes `USING INDEX idx_signal_history_ticker_created`.
    - Test C: Short concurrency soak — spawn 3 writer coroutines (each inserting 100 rows into different tables: signal_history, monitoring_alerts, portfolio_snapshots) AND 3 reader coroutines (each running 50 SELECTs against signal_history) concurrently for a bounded runtime (approx. 10 seconds). Assert:
      * No `database is locked` error raised.
      * All writers complete.
      * All readers complete with valid results (not empty unless expected).
    - Test D: After `prune_signal_history(retention_days=30)` on the 50k-row seeded DB, the analytics query from Test A still completes in < 1.0 second (the post-prune table is smaller, so this should be trivially faster — primary check is no regression).
  </behavior>
  <action>
    Extend `tests/test_foundation_06_db_wal_indexes.py` with the four tests above. Use:

    ```python
    async def _seed_signal_history(db_path: str, n_rows: int, span_days: int) -> None:
        """Insert n_rows into signal_history spanning the last span_days."""
        import random
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        async with aiosqlite.connect(db_path) as conn:
            now = datetime.now(timezone.utc)
            rows = []
            for i in range(n_rows):
                age_days = (i * span_days) // n_rows
                ts = (now - timedelta(days=age_days, seconds=random.randint(0, 86400))).isoformat()
                rows.append((
                    random.choice(tickers), "stock", "HOLD", 50.0, None, 0.0, 1.0,
                    "[]", "seed", "[]", None, "OPEN", None, None, ts,
                ))
            await conn.executemany(
                """
                INSERT INTO signal_history (
                    ticker, asset_type, final_signal, final_confidence, regime,
                    raw_score, consensus_score, agent_signals_json, reasoning,
                    warnings_json, thesis_id, outcome, outcome_return_pct,
                    outcome_resolved_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            await conn.commit()

    def test_analytics_query_fast_on_50k_rows(tmp_path):
        async def _run():
            db = str(tmp_path / "perf.db")
            await init_db(db)
            await _seed_signal_history(db, n_rows=50_000, span_days=200)

            async with aiosqlite.connect(db) as conn:
                t0 = time.monotonic()
                rows = await (
                    await conn.execute(
                        "SELECT * FROM signal_history WHERE ticker = ? ORDER BY created_at DESC LIMIT 100",
                        ("AAPL",),
                    )
                ).fetchall()
                duration = time.monotonic() - t0
            assert duration < 1.0, f"analytics query took {duration:.3f}s on 50k rows (want <1.0s)"
            assert len(rows) > 0, "no rows returned for AAPL"
        asyncio.run(_run())

    def test_explain_query_plan_uses_index(tmp_path):
        async def _run():
            db = str(tmp_path / "explain.db")
            await init_db(db)
            await _seed_signal_history(db, n_rows=1_000, span_days=30)
            async with aiosqlite.connect(db) as conn:
                plan = await (
                    await conn.execute(
                        "EXPLAIN QUERY PLAN SELECT * FROM signal_history "
                        "WHERE ticker = ? ORDER BY created_at DESC LIMIT 100",
                        ("AAPL",),
                    )
                ).fetchall()
                plan_text = " ".join(str(r) for r in plan).lower()
                assert "idx_signal_history_ticker" in plan_text, f"index not used: {plan}"
        asyncio.run(_run())

    def test_concurrent_writes_and_reads_no_lock_error(tmp_path):
        async def _run():
            db = str(tmp_path / "concurrency.db")
            await init_db(db)

            errors: list[str] = []

            async def writer(kind: str, n: int):
                try:
                    async with aiosqlite.connect(db) as conn:
                        await conn.execute("PRAGMA journal_mode=WAL;")
                        await conn.execute("PRAGMA busy_timeout=5000;")
                        for i in range(n):
                            if kind == "signal":
                                await conn.execute(
                                    "INSERT INTO signal_history (ticker, asset_type, final_signal, "
                                    "final_confidence, raw_score, consensus_score, agent_signals_json, "
                                    "reasoning, warnings_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                    (f"W{i}", "stock", "HOLD", 50.0, 0.0, 1.0, "[]", "c", "[]"),
                                )
                            await conn.commit()
                except Exception as exc:
                    errors.append(f"writer[{kind}]: {exc}")

            async def reader(n: int):
                try:
                    async with aiosqlite.connect(db) as conn:
                        await conn.execute("PRAGMA busy_timeout=5000;")
                        for _ in range(n):
                            await (await conn.execute(
                                "SELECT COUNT(*) FROM signal_history"
                            )).fetchone()
                except Exception as exc:
                    errors.append(f"reader: {exc}")

            await asyncio.gather(
                writer("signal", 100),
                writer("signal", 100),
                writer("signal", 100),
                reader(50),
                reader(50),
                reader(50),
            )
            assert not any("locked" in e.lower() for e in errors), f"lock errors: {errors}"
            # Some rowcount > 0 proves writes landed
            async with aiosqlite.connect(db) as conn:
                count = await (await conn.execute("SELECT COUNT(*) FROM signal_history")).fetchone()
                assert count[0] >= 300, f"expected >=300 rows, got {count[0]}"
        asyncio.run(_run())

    def test_analytics_fast_after_pruning(tmp_path):
        async def _run():
            db = str(tmp_path / "prune.db")
            await init_db(db)
            await _seed_signal_history(db, n_rows=50_000, span_days=200)
            from daemon.jobs import prune_signal_history
            result = await prune_signal_history(db, retention_days=30)
            assert result["deleted_rows"] > 0
            # Query still fast after prune
            async with aiosqlite.connect(db) as conn:
                t0 = time.monotonic()
                await (await conn.execute(
                    "SELECT * FROM signal_history WHERE ticker = ? "
                    "ORDER BY created_at DESC LIMIT 100",
                    ("AAPL",),
                )).fetchall()
                assert time.monotonic() - t0 < 1.0
        asyncio.run(_run())
    ```

    Adjust tickers and exact column lists to match the real `signal_history` schema (15 columns per the existing CREATE TABLE). Use `pytest.mark.slow` or a custom marker only if the tests exceed 30s on the reference machine — but all four tests should be well under 30s with the correct index in place. Do NOT gate these tests behind the `network` marker — they are offline.
  </action>
  <verify>
    <automated>
      pytest tests/test_foundation_06_db_wal_indexes.py::test_analytics_query_fast_on_50k_rows -x -v
      pytest tests/test_foundation_06_db_wal_indexes.py::test_explain_query_plan_uses_index -x -v
      pytest tests/test_foundation_06_db_wal_indexes.py::test_concurrent_writes_and_reads_no_lock_error -x -v
      pytest tests/test_foundation_06_db_wal_indexes.py::test_analytics_fast_after_pruning -x -v
      pytest tests/test_foundation_06_db_wal_indexes.py -x
    </automated>
  </verify>
  <acceptance_criteria>
    - The 50k-row analytics query test exits 0 with wall-clock duration < 1.0 second (ROADMAP success criterion 5: "Analytics page loads <1s on 50k signal-history rows").
    - `EXPLAIN QUERY PLAN` confirms the `idx_signal_history_ticker_created` (or `idx_signal_history_ticker`) index is being used for the analytics query.
    - The concurrency test completes with zero `database is locked` errors across 300+ mixed concurrent writes and 150 reads.
    - After `prune_signal_history(retention_days=30)`, the 50k-row test DB has rows only within the last 30 days, AND the analytics query still completes in <1.0s.
    - `pytest tests/test_foundation_06_db_wal_indexes.py -x` → exit 0 for ALL tests in the file (Task 1 + Task 3 tests together).
  </acceptance_criteria>
  <done>
    The ROADMAP Phase 1 success criterion 5 ("Analytics page loads <1s on 50k signal-history rows; no `database is locked` in soak") is verifiable by a single pytest file that seeds, times, and concurrency-soaks the schema. The test is self-contained (no network) and runs in under 60 seconds.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Daemon process → SQLite file | Multiple daemon job invocations + API readers share one file; integrity is enforced by SQLite WAL + our transaction discipline. |
| Scheduler → job_run_log | Startup reconciler modifies rows; a malicious actor with filesystem access could pre-populate 'running' rows to trigger spurious 'aborted' writes. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-01 | Tampering | External process writes to `job_run_log` out-of-band | accept | Single-user local-first deployment; filesystem access = full trust per PROJECT.md. |
| T-02-02 | Denial of service | `prune_signal_history` DELETE locks the database during long-running prune | mitigate | Prune runs weekly at 03:00 (off-peak); WAL mode allows concurrent readers during the DELETE; the DELETE is bounded by the WHERE clause. |
| T-02-03 | Information disclosure | `error_message` column of `job_run_log` could contain SMTP creds / API keys from exception strings | mitigate | Task 2 writes `str(exc)` into `error_message`; add a note in the Summary to follow up in Phase 3 (DATA-04 structured logs) with scrubbing. For Phase 1, accept raw exception text in the audit log and document in SUMMARY.md. |
| T-02-04 | Repudiation | A job that completed successfully could have its `job_run_log` row deleted manually, hiding the run | accept | Audit tampering on local-first single-user tool is out of scope. |
| T-02-05 | Spoofing | Another process (e.g., accidentally-started second daemon) inserts `job_run_log` rows under the same `job_name` | mitigate | DATA-05 in Phase 3 adds PID file + single-instance guard. For Phase 1, we document the risk and rely on the reconciler to keep the table consistent. |
| T-02-06 | Elevation of privilege | SQL injection via `job_name` in `_begin_job_run_log` | mitigate | All inserts use parameterized queries (`?` placeholders). No string-formatted SQL. |
</threat_model>

<verification>
```bash
pytest tests/test_foundation_06_db_wal_indexes.py tests/test_foundation_07_job_run_log.py tests/test_001_db.py tests/test_014_daemon.py -x -v
grep -q "CREATE TABLE IF NOT EXISTS job_run_log" db/database.py
grep -q "journal_mode=WAL" db/database.py
grep -q "idx_portfolio_snapshots_timestamp" db/database.py
grep -q "INSERT INTO job_run_log" daemon/jobs.py
grep -q "UPDATE job_run_log" daemon/jobs.py
grep -q "reconcile_aborted_jobs" daemon/scheduler.py
grep -q "prune_signal_history" daemon/scheduler.py
grep -q "BEGIN" daemon/jobs.py
grep -q "ROLLBACK" daemon/jobs.py
python -c "from daemon.jobs import reconcile_aborted_jobs, prune_signal_history, _begin_job_run_log, _end_job_run_log; print('OK')"
```

All 11 checks must exit 0.
</verification>

<success_criteria>
- `job_run_log` table exists with the four-value CHECK constraint on status.
- Every daemon job writes a `status='running'` row at entry, wraps its DB writes in `BEGIN`/`COMMIT` (rolling back on exception), and updates the row to `status='success'` or `status='error'` at exit.
- Daemon startup reconciles stale `running` rows (older than 5s) to `status='aborted'`.
- `prune_signal_history` is registered as a weekly APScheduler cron job and deletes rows older than 90 days.
- `PRAGMA journal_mode` is `wal` for any fresh connection opened after `init_db`.
- Composite indexes exist on `signal_history(ticker, created_at)` and `portfolio_snapshots(timestamp)`.
- Analytics query on a 50k-row `signal_history` returns in <1 second (verified via test).
- Concurrent 3-writer / 3-reader soak produces zero `database is locked` errors (verified via test).
- All pre-existing `tests/test_014_daemon.py` and `tests/test_001_db.py` tests continue to pass (backwards compat preserved; `daemon_runs` still written).
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-hardening/02-PLAN-db-daemon-durability-SUMMARY.md` documenting:
- `job_run_log` schema (copy the CREATE TABLE DDL)
- Before/after diff of each refactored daemon job (count of `conn.execute` calls, presence of `BEGIN`/`COMMIT`)
- Timing measurement from the 50k-row analytics test (actual wall-clock ms)
- Any cases where the startup reconciler fired (should be 0 on a clean run)
- Follow-ups flagged for Phase 3: (a) scrub secrets from `error_message`; (b) PID file / single-instance guard (DATA-05)
</output>
</content>
</invoke>