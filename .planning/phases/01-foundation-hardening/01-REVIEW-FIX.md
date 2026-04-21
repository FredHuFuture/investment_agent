---
phase: 01-foundation-hardening
date: 2026-04-21
iteration: 1
fix_scope: critical_warning
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 01 Code Review Fix Report

**Fixed at:** 2026-04-21
**Source review:** .planning/phases/01-foundation-hardening/01-REVIEW.md
**Iteration:** 1

## Summary

All 6 in-scope findings (2 Critical, 4 Warning) were fixed and committed atomically. Two new test files received additional regression tests (CR-01 and CR-02). All 58 foundation tests (01-05) continue to pass after all fixes.

## Fixed

### CR-01: Windows `os.replace()` Data-Loss Race on Open Parquet Reader

**File:** `data_providers/parquet_cache.py:78`
**Commit:** `81ba351`
**What changed:**
- Added `import sys` to module imports.
- `write()` now detects `sys.platform == "win32"` and falls back to an explicit `path.unlink() + tmp.rename(path)` sequence with up to 3 retries. On retry exhaustion the stranded `.parquet.tmp` is cleaned up and a warning is logged. POSIX path is unchanged (`os.replace`).
- `clear_all()` now iterates both `"*.parquet"` and `"*.parquet.tmp"` glob patterns so stranded tmp files from a failed Windows write are also removed.

**Tests added:**
- `test_clear_all_removes_stranded_tmp_files` — verifies `clear_all()` counts and removes `.parquet.tmp` files alongside `.parquet` files.
- `test_write_windows_path_cleans_tmp_on_all_retries_exhausted` — simulates Windows platform with `Path.rename` always raising; verifies no stranded `.parquet.tmp` remains after all 3 retries are exhausted.

---

### CR-02: Thundering-Herd Cache Miss — Concurrent Async Callers All Hit Upstream

**File:** `data_providers/cached_provider.py:67-89`
**Commit:** `4db53d2`
**What changed:**
- Added `import asyncio` to imports.
- `__init__` now initialises `self._inflight: dict[tuple[str, str, str], asyncio.Event] = {}`.
- `get_price_history` coalesces concurrent misses: the first caller registers an `asyncio.Event` in `_inflight[key]`; subsequent callers for the same key `await` that event, then serve from the in-memory TTLCache. The `finally` block always deletes the key and sets the event, even on upstream error.

**Tests added:**
- `test_concurrent_cache_misses_deduplicate_to_single_upstream_call` — fires 5 concurrent `asyncio.gather` calls on a cold cache; asserts `inner.price_calls == 1`.
- `test_inflight_registry_cleared_after_fetch` — asserts `provider._inflight` is empty after a successful fetch (no resource leak).

---

### WR-01: `run_once` Skips Startup Reconciliation

**File:** `daemon/scheduler.py:223-248`
**Commit:** `ae36b74`
**What changed:**
- `run_once()` now calls `await reconcile_aborted_jobs(self._config.db_path, min_age_seconds=300)` immediately after `await init_db(...)`, mirroring `start()`.
- `min_age_seconds` set to 300 (was 5 in `start()`). The old value of 5 s was too short for jobs that legitimately run for several minutes; 5 min provides a safe window while still catching genuinely stale rows from crashed processes.
- Logs a WARNING if any rows were reconciled, consistent with `start()` behaviour.
- Docstring updated to explain the rationale.

**Tests added/updated:** None — the existing `test_foundation_07` suite covers `reconcile_aborted_jobs` behaviour; all 7 tests passed after the change.

---

### WR-02: `prune_signal_history` Violates Two-Connection Isolation

**File:** `daemon/jobs.py:936-983`
**Commit:** `59d26ab`
**What changed:**
- Refactored `prune_signal_history` to use the two-connection pattern matching all other daemon jobs (`run_daily_check`, `run_weekly_revaluation`, etc.).
- `_begin_job_run_log` is now called on a dedicated `log_conn` that is opened and **closed** before the job body runs. The job DELETE uses a separate `conn`. `_end_job_run_log` (both success and error paths) opens a fresh `log_conn` so the log update is independent of the job transaction.
- The previous code called `_begin_job_run_log(conn, ...)` on the same connection used for the DELETE, meaning a write conflict on the job body could prevent `_end_job_run_log` from being called, leaving the row stuck in `'running'`.

**Tests added/updated:** None — the existing `test_prune_signal_history_respects_retention` test covers the happy path and continues to pass.

---

### WR-03: `cache_price_data` Bypasses Rate Limiter

**File:** `backtesting/engine.py:75-90`
**Commit:** `4b74ee3`
**What changed:**
- The `_download` call in `cache_price_data` is now wrapped in `async with provider._limiter:` using the `YFinanceProvider` class-level `AsyncRateLimiter`.
- Previously the code created a `YFinanceProvider()` instance but never used its limiter — calling `asyncio.to_thread(_download)` directly, making it possible for unlimited concurrent backtest downloads to fire without rate-limit accounting.
- `get_price_history()` was not used directly because it accepts only `period`, not `start`/`end` dates; the date-range fetch capability is preserved while adding rate-limit coverage.

**Tests added/updated:** None — `test_foundation_04_backtest_mode.py` 10 tests all pass.

---

### WR-04: `_auto_select_block_size` Fallback Clamp Missing `-1`

**File:** `engine/monte_carlo.py:88`
**Commit:** `e806356`
**What changed:**
- Changed `return max(1, min(fallback, len(returns)))` to `return max(1, min(fallback, len(returns) - 1))`.
- The success path already used `len(returns) - 1`; the fallback path was inconsistent. With `block_size == n_data`, `max_start = 0` and the bootstrap samples only index 0 for every simulation, producing N identical paths — statistically useless.
- The `-1` guard ensures `max_start >= 1` for any valid input, maintaining non-degenerate block sampling in the fallback path.

**Tests added/updated:** None — `test_foundation_03_block_length.py` 10 tests cover the fallback path and all pass after the fix.

---

## Skipped Issues

None — all 6 in-scope findings were fixed.

---

_Fixed: 2026-04-21_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
