---
phase: 01-foundation-hardening
plan: 01
subsystem: data-providers
tags: [data-providers, caching, yfinance, parquet, performance, FOUND-01, FOUND-02]
dependency_graph:
  requires: []
  provides:
    - data_providers.yfinance_provider.get_price_history_batch
    - data_providers.parquet_cache.ParquetOHLCVCache
    - CachedProvider.parquet_cache kwarg
  affects:
    - backtesting/engine.py (imports _yfinance_lock — preserved, no breakage)
    - data_providers/factory.py (CachedProvider still constructed without parquet_cache — backward compat)
tech_stack:
  added:
    - arch>=6.0 (pyproject.toml dependency — required by Plan 01-03 FOUND-03)
    - pyarrow>=14.0 (parquet read/write backend for ParquetOHLCVCache)
  patterns:
    - Batch yfinance download via yf.download([tickers], group_by="ticker", threads=True)
    - Disk TTL cache: file mtime vs. time.time() comparison
    - Atomic disk writes: df.to_parquet(tmp) then os.replace(tmp, final)
    - Optional second-level cache: read-through + write-through behind in-memory TTLCache
key_files:
  created:
    - data_providers/parquet_cache.py (113 lines)
    - tests/test_foundation_01_yfinance_batch.py (219 lines)
    - tests/test_foundation_02_parquet_cache.py (354 lines)
  modified:
    - pyproject.toml (61 -> 64 lines, +arch>=6.0, +pyarrow>=14.0)
    - data_providers/yfinance_provider.py (153 -> 228 lines, +get_price_history_batch)
    - data_providers/cached_provider.py (128 -> 156 lines, +parquet_cache wiring)
decisions:
  - "_yfinance_lock preserved for Ticker.info-based paths only; batch path has no lock because yf.download with list+threads=True is thread-safe"
  - "ParquetOHLCVCache is a standalone synchronous class (not async) because file I/O on OHLCV is fast and keeps the API simple"
  - "Atomic write via os.replace(tmp, final) works on both Windows and POSIX for same-filesystem moves"
  - "parquet_cache=None default ensures CachedProvider is 100% backward-compatible with all existing callers"
metrics:
  duration_seconds: 502
  completed_date: "2026-04-21"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 3
  new_tests: 22
  test_result: "30 passed, 1 skipped (network), 0 failed"
---

# Phase 1 Plan 01: Foundation Hardening — Batch Download + Parquet Cache Summary

**One-liner:** yfinance batch OHLCV via single `yf.download([tickers], group_by="ticker", threads=True)` call plus a new `ParquetOHLCVCache` disk layer wired into `CachedProvider` as a read-through/write-through second-level cache.

## What Was Built

### Task 1 — Batch Download + Dependencies (FOUND-01)

`pyproject.toml` gained `arch>=6.0` and `pyarrow>=14.0`. `YFinanceProvider.get_price_history_batch()` was added — it issues a single `yf.download` call with `group_by="ticker"` and `threads=True` for an arbitrary list of tickers, then splits the resulting MultiIndex DataFrame into a `dict[str, pd.DataFrame]`. Tickers missing from the batch response get an empty DataFrame with the expected OHLCV columns (not a missing key, not an exception), so callers can detect via `.empty`.

The per-ticker `_yfinance_lock` serialization is **bypassed** for batch calls (yfinance's internal thread pool handles concurrency safely when given a list). The lock is preserved on the existing single-ticker Ticker.info paths (`get_financials`, `get_key_stats`, `get_current_price`) which still share yfinance's `_DFS` internal dict.

### Task 2 — ParquetOHLCVCache (FOUND-02 core)

New file `data_providers/parquet_cache.py` implements `ParquetOHLCVCache`:
- Keys are `(ticker, period, interval)` tuples serialized to `{ticker}_{period}_{interval}.parquet`
- TTL enforced by `time.time() - file.stat().st_mtime > ttl`
- Atomic writes: `df.to_parquet(tmp)` then `os.replace(tmp, final)` (safe on Windows + POSIX same-FS)
- `invalidate(key)` → removes one file; `clear_all()` → removes all `*.parquet` in cache dir
- `stats()` returns `{hits, misses, total, size_files, total_bytes, hit_rate}`
- Fails fast at construction with `ImportError("pyarrow is required…")` if pyarrow is absent
- Cache dir created lazily on first `write()`
- `data_providers/cache.py` (in-memory `TTLCache`) is **not modified**

### Task 3 — CachedProvider Integration (FOUND-02 integration)

`CachedProvider.__init__` gained two optional kwargs: `parquet_cache: ParquetOHLCVCache | None = None` and `parquet_ttl: float = 86400.0`. When `parquet_cache` is set, `get_price_history` reads from it first (within TTL), primes the in-memory `TTLCache` on hit, and falls through to the inner provider on miss. Upstream fetches are written through to parquet. Parquet read/write errors are caught and logged; the call falls through to the inner provider transparently. `parquet_cache=None` (default) leaves all existing behavior identical.

## Test Results

```
pytest tests/test_foundation_01_yfinance_batch.py tests/test_foundation_02_parquet_cache.py tests/test_004_data_providers.py -v
30 passed, 1 skipped (network), 0 failed
```

| File | Tests | Coverage |
|------|-------|----------|
| test_foundation_01_yfinance_batch.py | 7 | Behaviors A-G: dict return, single call, empty-list error, MultiIndex split, missing ticker, regression, lock presence |
| test_foundation_02_parquet_cache.py (Part 1) | 10 | Behaviors A-J: write/read equality, file creation, TTL expiry, miss, invalidate, clear_all, stats, pyarrow missing, lazy dir, empty DF |
| test_foundation_02_parquet_cache.py (Part 2) | 5 | Behaviors A-E: first call writes parquet, second call skips inner, None default, corrupt fallthrough, no parquet for other methods |
| test_004_data_providers.py | 8 passed + 1 skipped | Regression: all pre-existing tests pass |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `threading.Lock` is a factory function, not a class**

- **Found during:** Task 1, Test G implementation
- **Issue:** The plan's test spec called `isinstance(_yfinance_lock, threading.Lock)`, but `threading.Lock` is a factory function returning a C-level `_thread.lock` object. `isinstance()` raised `TypeError: isinstance() arg 2 must be a type`.
- **Fix:** Changed the assertion to check `"lock" in type(_yfinance_lock).__name__.lower()`, which correctly identifies the internal lock type on all Python 3.11+ runtimes.
- **Files modified:** `tests/test_foundation_01_yfinance_batch.py`
- **Commit:** `5d42b8e`

**2. [Rule 1 - Bug] Windows locale encoding (GBK) breaks `Path.read_text()`**

- **Found during:** Task 1, Test G on Windows
- **Issue:** `source_path.read_text()` used the locale encoding (GBK on Windows), but the source file is UTF-8, causing `UnicodeDecodeError`.
- **Fix:** Added `encoding="utf-8"` to the `read_text()` call.
- **Files modified:** `tests/test_foundation_01_yfinance_batch.py`
- **Commit:** `5d42b8e`

## Known Stubs

None — all implemented functionality is fully wired. `get_price_history_batch` is a complete implementation (not a stub); `ParquetOHLCVCache` is fully functional; `CachedProvider` integration is live with real read-through/write-through logic.

## Threat Flags

No new trust boundary surfaces beyond those already declared in the plan's threat model (T-01-01 through T-01-05). The `ParquetOHLCVCache` write path and `CachedProvider` integration match the planned threat surface exactly.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| data_providers/parquet_cache.py | FOUND |
| data_providers/yfinance_provider.py | FOUND |
| data_providers/cached_provider.py | FOUND |
| tests/test_foundation_01_yfinance_batch.py | FOUND |
| tests/test_foundation_02_parquet_cache.py | FOUND |
| .planning/phases/01-foundation-hardening/01-01-SUMMARY.md | FOUND |
| commit 5d42b8e (Task 1) | FOUND |
| commit 5fd3d48 (Task 2) | FOUND |
| commit c53eb6d (Task 3) | FOUND |
