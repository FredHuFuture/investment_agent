---
phase: 01-foundation-hardening
depth: standard
date: 2026-04-21
files_reviewed: 19
files_reviewed_list:
  - agents/fundamental.py
  - agents/models.py
  - backtesting/engine.py
  - daemon/jobs.py
  - daemon/scheduler.py
  - data_providers/cached_provider.py
  - data_providers/parquet_cache.py
  - data_providers/yfinance_provider.py
  - db/database.py
  - engine/aggregator.py
  - engine/monte_carlo.py
  - pyproject.toml
  - tests/test_foundation_01_yfinance_batch.py
  - tests/test_foundation_02_parquet_cache.py
  - tests/test_foundation_03_block_length.py
  - tests/test_foundation_04_backtest_mode.py
  - tests/test_foundation_05_agent_renorm.py
  - tests/test_foundation_06_db_wal_indexes.py
  - tests/test_foundation_07_job_run_log.py
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 01 Code Review

## Summary

Phase 1 Foundation Hardening is architecturally sound. The two-connection daemon pattern for `job_run_log` is correctly implemented, the `backtest_mode` flag cleanly short-circuits `FundamentalAgent`, weight renormalization is provably correct via parametrized tests, and the block bootstrap auto-selection adds real statistical value. Two critical issues require attention: a concrete `os.replace()` data-loss race on Windows when the Parquet target file is open by another reader (`ERROR_SHARING_VIOLATION`), and a thundering-herd cache miss where concurrent async callers for the same ticker all bypass both cache layers and fire redundant upstream yfinance calls. Four warnings cover logic gaps: a `run_once` path that skips startup reconciliation enabling a live job to be re-categorized as aborted, a `prune_signal_history` function that incorrectly reuses the log connection for both the prune transaction and `_end_job_run_log` (defeating the two-connection isolation guarantee), a missing `int` conversion on `block_size` clamp that could raise on degenerate `optimal_block_length` output, and a test (test E in `test_foundation_07`) that does not actually exercise atomic rollback because the code deliberately catches per-position exceptions and continues rather than re-raising.

---

## Critical Issues

### CR-01: Windows `os.replace()` Data-Loss Race on Open Parquet Reader

**Severity:** critical
**File:** `data_providers/parquet_cache.py:78`
**Category:** bug / data-loss

**Finding:**
`write()` uses `os.replace(tmp, path)` described in the comment as "atomic on POSIX & Windows for same FS." On POSIX this is correct — `rename(2)` is atomic even when the target is open by readers. On Windows, however, `MoveFileEx(MOVEFILE_REPLACE_EXISTING)` (which `os.replace` uses) raises `ERROR_SHARING_VIOLATION` (errno 13 / WinError 32) when the destination file is open by another process or thread — specifically `pd.read_parquet(path)` on the same file in a concurrent request. The project runs on Windows 11 (per environment metadata) and runs parallel agent analysis via asyncio + `asyncio.to_thread`. A concurrent `CachedProvider.get_price_history` call that is mid-read on the `.parquet` file will cause `write()` to raise, leaving the `.parquet.tmp` file stranded on disk and raising an unhandled exception that propagates up through `CachedProvider.get_price_history` (the write is inside a bare `try/except` that only logs a warning, so the data loss is silent — the tmp file is leaked).

```python
# parquet_cache.py line 76-78
tmp = path.with_suffix(".parquet.tmp")
df.to_parquet(tmp, engine="pyarrow", compression="snappy")
os.replace(tmp, path)   # ERROR_SHARING_VIOLATION on Windows when reader has path open
```

**Impact:** On Windows (the project's development platform), a stale `.parquet.tmp` file is left on disk each time a concurrent read is in progress during a write. Over time `data/cache/ohlcv/` accumulates orphaned `.parquet.tmp` files. More critically, the cache is not updated and the next call re-fetches from yfinance, defeating the cache's purpose silently.

**Recommendation:**
1. Add `.parquet.tmp` to the cleanup set in `clear_all()` by globbing `"*.parquet.tmp"` in addition to `"*.parquet"`.
2. On Windows, fall back to a write-to-tmp + delete-original + rename-tmp sequence inside a retry loop:

```python
import sys

def write(self, key: tuple[str, str, str], df: pd.DataFrame) -> None:
    if df is None or df.empty:
        raise ValueError("cannot cache empty DataFrame")
    self._cache_dir.mkdir(parents=True, exist_ok=True)
    path = self._path_for(key)
    tmp = path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, engine="pyarrow", compression="snappy")
    if sys.platform == "win32":
        # Windows MoveFileEx raises when target is open; retry up to 3 times
        for attempt in range(3):
            try:
                if path.exists():
                    path.unlink()
                tmp.rename(path)
                break
            except OSError:
                if attempt == 2:
                    logger.warning("ParquetOHLCVCache: replace failed for %s", path)
                    tmp.unlink(missing_ok=True)
    else:
        os.replace(tmp, path)
```

---

### CR-02: Thundering-Herd Cache Miss — Concurrent Async Callers All Hit Upstream

**Severity:** critical
**File:** `data_providers/cached_provider.py:67-89`
**Category:** bug / concurrency

**Finding:**
`CachedProvider.get_price_history` has no request-coalescing mechanism. The read-through sequence is:

1. Check Parquet cache (sync `read()`).
2. If miss: check in-memory `TTLCache.get()`.
3. If miss: call inner provider (yfinance network I/O).
4. Write-through to in-memory cache and Parquet.

Both the Parquet read and the TTLCache lookup are non-blocking checks performed before any write. In an asyncio event loop, multiple coroutines can `await get_price_history("AAPL", "1y", "1d")` concurrently (e.g., several agents in the same `asyncio.gather()` call). On a cold cache, all callers will observe a miss on both the Parquet and the in-memory layers at approximately the same time (before any write has completed), and all will proceed to call `await getattr(self._provider, method)(*args, **kwargs)` — i.e., fire N concurrent yfinance downloads for the same ticker. With `threads=True` and the batch path, this is not protected by `_yfinance_lock`, so multiple download calls for the same ticker key can overlap.

```python
# cached_provider.py lines 67-89 — no coalescing guard
async def get_price_history(self, ticker, period, interval):
    if self._parquet_cache is not None:
        cached = self._parquet_cache.read(key, ttl=self._parquet_ttl)
        if cached is not None and not cached.empty:
            ...
            return cached.copy()
    # ↓ ALL concurrent callers reach here simultaneously on cold cache
    result = await self._cached("get_price_history", ...)
    ...
```

**Impact:** On a cold cache startup or after cache invalidation, N concurrent agent analyses for the same ticker trigger N redundant yfinance network calls. Given the 2 calls/second rate limiter, a 4-agent stock analysis (Technical, Fundamental, Macro, Sentiment) all calling `get_price_history` for the same ticker will saturate the limiter for 2+ seconds before any agent gets a response. This is a latency and rate-limit exhaustion risk, not a data correctness issue, but it can cause agent timeouts on the first analysis after startup.

**Recommendation:**
Use an in-flight request registry (asyncio.Event or dict of asyncio.Task) keyed by cache key to coalesce concurrent misses. A minimal fix using a per-instance `_inflight` dict:

```python
# In CachedProvider.__init__:
self._inflight: dict[tuple, asyncio.Event] = {}

async def get_price_history(self, ticker, period, interval):
    key = (ticker, period, interval)
    if self._parquet_cache is not None:
        cached = self._parquet_cache.read(key, ttl=self._parquet_ttl)
        if cached is not None and not cached.empty:
            await self._cache.set("get_price_history", key, {}, cached.copy())
            return cached.copy()
    # Coalesce concurrent misses
    if key in self._inflight:
        await self._inflight[key].wait()
        # Retry cache after the in-flight request completes
        result = await self._cache.get("get_price_history", key, {})
        if result is not CACHE_MISS:
            return result.copy()
    event = asyncio.Event()
    self._inflight[key] = event
    try:
        result = await self._cached("get_price_history", key, {})
        if self._parquet_cache is not None and result is not None and not result.empty:
            try:
                self._parquet_cache.write(key, result)
            except Exception as exc:
                logger.warning("Parquet write failed for %s: %s", ticker, exc)
        return result.copy()
    finally:
        del self._inflight[key]
        event.set()
```

---

## Warnings

### WR-01: `run_once` Skips Startup Reconciliation — Live Jobs Can Be Falsely Aborted

**Severity:** warning
**File:** `daemon/scheduler.py:223-248`
**Category:** correctness

**Finding:**
`MonitoringDaemon.run_once()` calls `await init_db(...)` but does NOT call `await reconcile_aborted_jobs(...)`. The `start()` path (lines 176-180) correctly runs reconciliation before the scheduler starts, but `run_once()` bypasses it. This means:

1. If the daemon crashed mid-job and left a `status='running'` row in `job_run_log`.
2. An operator calls `run_once("daily")` to manually re-run the check.
3. `run_once` inserts a NEW `status='running'` row for the new job.
4. The stale old row remains in `status='running'` indefinitely with no path to `'aborted'`.

More concretely, the inverse is also problematic: if `start()` is called while a `run_once` job is actually running in another process (sharing the same DB), `reconcile_aborted_jobs(min_age_seconds=5)` will mark the in-flight `run_once` job as `'aborted'` since there is no process-isolation mechanism (no PID stored). For a single-user local deployment this is low probability, but the min_age_seconds=5 guard is very short.

**Recommendation:**
Add `reconcile_aborted_jobs` to `run_once()`, or increase `min_age_seconds` to something that covers realistic run-once jobs (e.g., 300 seconds):

```python
async def run_once(self, job_name: str) -> dict[str, Any]:
    self._logger = self._setup_logging()
    await init_db(self._config.db_path)
    await reconcile_aborted_jobs(self._config.db_path, min_age_seconds=300)
    ...
```

---

### WR-02: `prune_signal_history` Violates Two-Connection Isolation — `_end_job_run_log` Shares the Job Transaction Connection

**Severity:** warning
**File:** `daemon/jobs.py:936-983`
**Category:** concurrency / correctness

**Finding:**
The FOUND-07 design intent is that `job_run_log` writes use a **separate** connection from the job transaction so a `ROLLBACK` on the job body cannot erase the log row. All other jobs (`run_daily_check`, `run_weekly_revaluation`, etc.) correctly open `log_conn` independently of the `conn` used for the job work. However, `prune_signal_history` (lines 936-960) reuses the **same** connection for both the prune `DELETE` and the `_end_job_run_log` call:

```python
# jobs.py lines 936-959 — SAME conn used for job work AND log update
async with aiosqlite.connect(db_path) as conn:
    await conn.execute("PRAGMA foreign_keys=ON;")
    row_id = await _begin_job_run_log(conn, "prune_signal_history", started_at)  # ← log on job conn
    cursor = await conn.execute("DELETE FROM signal_history WHERE ...")
    ...
    await conn.commit()  # commits both the DELETE and the job_run_log INSERT atomically
    await _end_job_run_log(conn, row_id, "success", ...)  # ← second commit on same conn
```

`_begin_job_run_log` does its own `conn.commit()` immediately (line 867), which commits the `INSERT INTO job_run_log` row before the `DELETE FROM signal_history` is committed. This incidentally works here, but the error path (lines 968-983) opens a NEW connection to call `_end_job_run_log`, meaning on error the log update is on a different connection than the failure context — inconsistent with the success path. The deeper issue is that if SQLite WAL has a write conflict on the job connection that prevents `conn.commit()` from completing (e.g., a timeout), `_end_job_run_log` is never called and the row stays `'running'`.

**Recommendation:**
Refactor `prune_signal_history` to use the same two-connection pattern as the other jobs:

```python
async def prune_signal_history(db_path, retention_days=90, logger=None):
    ...
    row_id: int | None = None
    try:
        async with aiosqlite.connect(db_path) as log_conn:
            row_id = await _begin_job_run_log(log_conn, "prune_signal_history", started_at)
    except Exception as log_exc:
        if logger:
            logger.warning("_begin_job_run_log failed (non-fatal): %s", log_exc)

    try:
        async with aiosqlite.connect(db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM signal_history WHERE created_at < date('now', ? || ' days')",
                (f"-{int(retention_days)}",),
            )
            ...
            await conn.commit()
        duration_ms = ...
        if row_id is not None:
            async with aiosqlite.connect(db_path) as log_conn:
                await _end_job_run_log(log_conn, row_id, "success", ...)
        ...
    except Exception as exc:
        ...
        if row_id is not None:
            async with aiosqlite.connect(db_path) as log_conn:
                await _end_job_run_log(log_conn, row_id, "error", error_message=str(exc), ...)
```

---

### WR-03: `get_price_history_batch` Rate Limiter Consumed by Single Batch Call

**Severity:** warning
**File:** `data_providers/yfinance_provider.py:177-178`
**Category:** correctness

**Finding:**
`get_price_history_batch` calls `async with self._limiter:` once for the entire batch download, consuming exactly one "call slot" from the shared `AsyncRateLimiter` (2 calls/second) regardless of how many tickers are in the batch. Meanwhile, `get_price_history` (the per-ticker path) also consumes one slot per call. This asymmetry means:

- A 100-ticker batch consumes 1 rate-limit slot.
- 100 sequential single-ticker calls consume 100 slots (taking 50 seconds).

The intent appears to be: batch is faster and fairer. However, the issue is that callers mixing batch and single-ticker paths can end up contending on the same 2-call/s budget in unexpected ways. More concretely, `backtesting/engine.py::cache_price_data` (lines 76-90) still uses `yf.download(ticker, ...)` with `_yfinance_lock` but does NOT go through the rate limiter at all (it creates a new `YFinanceProvider()` instance but doesn't call through it — it directly imports and uses `yf.download` inline). This bypasses both the rate limiter and the class-level limiter, making it possible to fire unlimited yfinance downloads from the backtest path.

**Recommendation:**
The `cache_price_data` function in `backtesting/engine.py` should use `YFinanceProvider().get_price_history()` (which goes through the rate limiter and lock) rather than calling `yf.download` directly. This is a regression risk for the rate limiting strategy.

```python
# backtesting/engine.py lines 76-92 — bypasses rate limiter
provider = YFinanceProvider()

def _download() -> pd.DataFrame:
    import yfinance as yf
    with _yfinance_lock:
        return yf.download(...)   # no rate limiter

raw = await asyncio.to_thread(_download)
```

Should be:

```python
provider = YFinanceProvider()
raw = await provider.get_price_history(ticker, period=None, interval="1d")
# (or use start/end via a date-range overload if get_price_history is extended)
```

---

### WR-04: `_auto_select_block_size` Fallback Clamp Applied to `fallback` Before Knowing `len(returns)`

**Severity:** warning
**File:** `engine/monte_carlo.py:88`
**Category:** bug / correctness

**Finding:**
In `_auto_select_block_size`, the fallback path returns:

```python
return max(1, min(fallback, len(returns)))
```

But `len(returns)` at the static method call site is `len(self._returns)` which was clamped when passed in. This is fine in normal cases. However, the return on the success path (line 89) uses:

```python
return max(3, min(block, len(returns) - 1))
```

Note `len(returns) - 1`. If `len(returns)` equals 10 (the minimum `MIN_DATA_POINTS`), `len(returns) - 1` = 9, and a block of 9 is valid. But if by some degenerate edge case `optimal_block_length` returns a value > `len(returns) - 1` AND the fallback path clamps with `len(returns)` (without the `-1`), the fallback block size can equal `len(returns)` exactly. The block bootstrap logic on line 140 then computes:

```python
max_start = n_data - bs  # = 0 if bs == n_data
starts = rng.integers(0, max_start + 1, ...)  # = rng.integers(0, 1) → always 0
```

A `max_start = 0` is degenerate — the only block start is index 0, so every simulation samples the same block. This is not a crash but produces completely useless simulations: all N paths are identical.

**Recommendation:**
Apply the same `-1` guard in the fallback path for consistency:

```python
# Line 88 — change:
return max(1, min(fallback, len(returns)))
# To:
return max(1, min(fallback, len(returns) - 1))
```

---

## Info

### IN-01: `test_partial_write_rolled_back` Does Not Exercise Atomic Rollback

**Severity:** info
**File:** `tests/test_foundation_07_job_run_log.py:183-216`
**Category:** test quality

**Finding:**
Test E (`test_partial_write_rolled_back`) patches `AnalysisPipeline.analyze_ticker` to raise `RuntimeError("data feed down")`. However, `run_weekly_revaluation` wraps per-position errors in a `try/except` at lines 283-286 that catches all position-level exceptions and appends them to `errors` — it does NOT re-raise them. The outer `COMMIT` on line 305 is still reached. The test then asserts `result.get("signals_saved", 0) == 0` and `signal_history == 0`, which passes vacuously because no signals were saved (the mock raised before any `signal_store.save_signal()` call) — not because the `ROLLBACK` on line 307 was triggered.

The actual atomic rollback path (line 307: `await conn.execute("ROLLBACK")`) is only reached if the code OUTSIDE the per-position loop raises (e.g., the `portfolio_snapshots` INSERT or the `COMMIT` itself fails). This path has no test coverage.

**Recommendation:**
Add a supplementary test that patches `conn.execute("COMMIT")` to raise `aiosqlite.OperationalError("disk full")` and verifies that (a) the ROLLBACK is executed, (b) `job_run_log.status == 'error'`, and (c) no partial signal_history rows persist. Alternatively, rename the existing test to accurately describe what it tests: "all per-position failures produce zero signals_saved."

---

### IN-02: `test_foundation_05` eth Renorm Tests Reuse btc Agent Names

**Severity:** info
**File:** `tests/test_foundation_05_agent_renorm.py:92-102`
**Category:** test quality

**Finding:**
Test C (`test_eth_renormalizes_with_one_agent_missing`) is parametrized over `BTC_AGENTS = ["CryptoAgent", "TechnicalAgent"]` and calls `agg.aggregate(outputs, "ETH-USD", "eth")`. This is intentional and correct because `DEFAULT_WEIGHTS["eth"]` uses the same two agents as `DEFAULT_WEIGHTS["btc"]`. However, the test comment says "2 agents × drop each → 2 parametrized cases" for eth but does not explain why eth uses `BTC_AGENTS` as the parametrize source. A future maintainer adding an eth-specific agent to `DEFAULT_WEIGHTS["eth"]` would need to also update this parametrize list, but there is no guard against the list going stale.

**Recommendation:**
Derive the parametrize list dynamically from `SignalAggregator.DEFAULT_WEIGHTS`:

```python
ETH_AGENTS = list(SignalAggregator.DEFAULT_WEIGHTS.get("eth", {}).keys())

@pytest.mark.parametrize("missing", ETH_AGENTS)
def test_eth_renormalizes_with_one_agent_missing(missing: str) -> None:
    ...
```

---

### IN-03: `backtesting/engine.py` `_make_agent("FundamentalAgent")` Passes `HistoricalDataProvider` to a Provider-Typed Constructor

**Severity:** info
**File:** `backtesting/engine.py:421-422`
**Category:** correctness / type safety

**Finding:**
`_make_agent` at line 421-422 passes a `HistoricalDataProvider` instance as the `provider` argument to `FundamentalAgent(provider)`. `HistoricalDataProvider` is a data slicer that implements `get_price_history()` but almost certainly does NOT implement `get_key_stats()` or `get_financials()`. In `backtest_mode=True`, `FundamentalAgent.analyze()` returns early before touching the provider (line 50), so this never raises. But if `_make_agent` is called with `FundamentalAgent` outside of `backtest_mode=True` (e.g., someone adds `"FundamentalAgent"` to `agents` in a `BacktestConfig` and overrides `backtest_mode` somehow), the `get_key_stats` call at line 77 of `fundamental.py` will raise `AttributeError` from `HistoricalDataProvider`.

The current code is safe because `AgentInput(backtest_mode=True)` is always passed in the backtester loop. But the defensive comment at the top of `FundamentalAgent.analyze()` notes the design intent, and the `_make_agent` factory silently creates a mis-wired agent that would break outside this context.

**Recommendation:**
Add a guard in `_make_agent` to document the provider mismatch:

```python
if agent_name == "FundamentalAgent":
    from agents.fundamental import FundamentalAgent
    # NOTE: HistoricalDataProvider does not support get_key_stats/get_financials.
    # FundamentalAgent is only safe here because backtest_mode=True is enforced
    # by the Backtester loop (AgentInput.backtest_mode=True).
    return FundamentalAgent(provider)
```

Or better, pass a `NullProvider` that raises `NotImplementedError` with a clear message if called:

```python
class _BacktestFundamentalProvider:
    async def get_key_stats(self, ticker): raise NotImplementedError("not available in backtest_mode")
    async def get_financials(self, ticker, period="annual"): raise NotImplementedError("not available in backtest_mode")
```

---

## Test Coverage Notes

**test_foundation_01_yfinance_batch.py:** Solid coverage of behaviors A-G. The MultiIndex helper `_make_multiindex_df` correctly replicates yfinance's actual level ordering (level 0 = ticker, level 1 = price type). Test G is a useful regression guard for the lock. No issues.

**test_foundation_02_parquet_cache.py:** Comprehensive coverage of all 15 behaviors. The `test_corrupt_parquet_falls_through_to_inner_and_heals` test correctly verifies the healing path. Missing: a test for the Windows `os.replace()` failure case (see CR-01). Missing: a concurrent write+read race test.

**test_foundation_03_block_length.py:** Thorough. Test D correctly patches at the `arch.bootstrap.optimal_block_length` call site. Test G (full-array pass-through) is a good regression guard. No issues.

**test_foundation_04_backtest_mode.py:** Test D correctly verifies zero provider calls in `backtest_mode=True`. Test F (grep check) is a lightweight but effective regression guard. No issues.

**test_foundation_05_agent_renorm.py:** Parametrized correctly across all 8 single-agent-missing scenarios plus 4 supplementary regression tests. Test F (data_completeness scaling) is a useful invariant guard. See IN-02 for the eth agent name derivation concern.

**test_foundation_06_db_wal_indexes.py:** The 50k-row analytics timing test is a good durability check. The EXPLAIN QUERY PLAN test is the right way to validate index usage. The concurrency soak test (`test_concurrent_writes_and_reads_no_lock_error`) correctly sets `busy_timeout=5000` on connections that bypass the pool, matching production behavior.

**test_foundation_07_job_run_log.py:** Tests A, B, C, D, H are correct and well-isolated. Test E has a vacuousness problem (see IN-01). Tests F+G (`test_prune_signal_history_respects_retention`) are solid. The crash-simulation in Test B (`PortfolioMonitor.run_check` raises) correctly exercises the `except` path on the `run_daily_check` outer try/except, but `run_daily_check` does not wrap its work in an explicit BEGIN/COMMIT transaction — only `run_weekly_revaluation` does. This means Test B's "rolls back" assertion in the docstring is misleading for `daily_check`.

---

## Clean Files

- `agents/models.py` — `AgentInput.backtest_mode: bool = False` is clean; `__post_init__` validation is correct.
- `agents/fundamental.py` — `backtest_mode` short-circuit is correct and returns `data_completeness=0.0` to trigger weight exclusion. The `_score_pe_trailing` linear interpolation math is correct.
- `engine/aggregator.py` — Weight renormalization logic is correct. The `data_completeness` scaling is applied before renormalization (not after), which is the right order.
- `daemon/scheduler.py` — `run_once` missing reconciliation is flagged in WR-01; otherwise the scheduler registration and signal handler code is clean.
- `pyproject.toml` — `arch>=6.0` and `pyarrow>=14.0` additions are correct. `pytest-asyncio` is in `[dev]` extras, which is appropriate.

---

_Reviewed: 2026-04-21T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
