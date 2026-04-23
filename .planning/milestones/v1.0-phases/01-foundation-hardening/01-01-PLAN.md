---
phase: 01-foundation-hardening
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - data_providers/yfinance_provider.py
  - data_providers/parquet_cache.py
  - data_providers/cached_provider.py
  - tests/test_foundation_01_yfinance_batch.py
  - tests/test_foundation_02_parquet_cache.py
autonomous: true
requirements: [FOUND-01, FOUND-02]
tags: [data-providers, caching, yfinance, parquet, performance]

must_haves:
  truths:
    - "A 100-ticker OHLCV download uses a single yfinance.download() call with group_by='ticker', not 100 serialized per-ticker calls."
    - "On a fresh cache, the first OHLCV request writes a Parquet file under data/cache/ohlcv/{ticker}_{period}_{interval}.parquet."
    - "On a warm cache, repeated OHLCV requests within TTL read from Parquet without invoking yfinance at all."
    - "The Parquet cache supports explicit invalidation via clear(ticker=...) / clear_all()."
    - "Backtesting a 100-ticker portfolio completes in <=50% of the baseline wall-clock time once batch + cache are in place."
  artifacts:
    - path: "pyproject.toml"
      provides: "arch>=6 and pyarrow>=14 dependencies available at install"
      contains: ["arch>=6", "pyarrow>="]
    - path: "data_providers/yfinance_provider.py"
      provides: "Batch OHLCV download + scoped per-Ticker.info lock"
      contains: ["yf.download", "group_by=\"ticker\"", "get_price_history_batch"]
    - path: "data_providers/parquet_cache.py"
      provides: "ParquetOHLCVCache class with TTL, read/write/invalidate/clear_all"
      contains: ["class ParquetOHLCVCache", "def read", "def write", "def invalidate", "to_parquet", "read_parquet"]
    - path: "data_providers/cached_provider.py"
      provides: "Parquet-backed OHLCV path in CachedProvider"
      contains: ["ParquetOHLCVCache"]
    - path: "tests/test_foundation_01_yfinance_batch.py"
      provides: "Batch-download unit tests with mocked yf.download"
      contains: ["test_batch_download", "group_by"]
    - path: "tests/test_foundation_02_parquet_cache.py"
      provides: "Parquet cache read/write/TTL/invalidation tests"
      contains: ["test_read_after_write", "test_ttl_expiry", "test_invalidate"]
  key_links:
    - from: "data_providers/yfinance_provider.py::get_price_history_batch"
      to: "yfinance.download"
      via: "single batched HTTP call"
      pattern: "yf\\.download\\([^)]*group_by=\"ticker\""
    - from: "data_providers/cached_provider.py::get_price_history"
      to: "data_providers/parquet_cache.py::ParquetOHLCVCache"
      via: "read-through cache on OHLCV path"
      pattern: "ParquetOHLCVCache"
    - from: "backtesting/engine.py::cache_price_data"
      to: "Parquet cache"
      via: "OHLCV path goes through CachedProvider once wired (wiring in a later phase; Plan 01 ships the cache layer + provider wiring)"
      pattern: "ParquetOHLCVCache|get_price_history"
---

<objective>
Eliminate the `_yfinance_lock` serial-download bottleneck by switching to yfinance batch mode for multi-ticker OHLCV, and add a durable Parquet-backed OHLCV cache layer so repeat requests do not hit yfinance at all. This plan delivers FOUND-01 and FOUND-02 from the Phase 1 Foundation Hardening scope.

Purpose: Backtests for larger portfolios (50+ tickers) are currently gated on a process-wide lock that allows ~2 yfinance calls/sec. The root cause is that `yfinance.download()` is not thread-safe across per-ticker calls, but `yfinance.download([list_of_tickers], group_by="ticker")` IS safe and performs a single batched HTTP round-trip. Once batch is in place, a Parquet disk cache means subsequent runs bypass yfinance entirely for any ticker whose data is still within TTL, so daily backtest iteration is dominated by compute, not I/O.

Output:
- New `data_providers/yfinance_provider.py::get_price_history_batch()` that uses `yf.download([tickers], group_by="ticker")` in a single call and returns `dict[str, pd.DataFrame]`.
- The existing `_yfinance_lock` is restricted to `Ticker.info`-based paths (`get_financials`, `get_key_stats`, `get_current_price` fallback) which still touch yfinance's shared `_DFS` — it is NOT removed because those paths are still single-ticker.
- New `data_providers/parquet_cache.py::ParquetOHLCVCache` class with `.read(key, ttl)`, `.write(key, df)`, `.invalidate(key)`, `.clear_all()`, backed by Parquet files under `data/cache/ohlcv/{ticker}_{period}_{interval}.parquet` using `pyarrow`.
- `CachedProvider` gains a `parquet_cache: ParquetOHLCVCache | None` constructor arg; when set, `get_price_history` reads Parquet first before falling through to the wrapped provider; writes to Parquet on every miss.
- New tests proving batch mode, TTL read/write, invalidation, and graceful degradation when pyarrow is missing.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/research/SUMMARY.md
@.planning/research/FEATURES.md
@.planning/research/PITFALLS.md
@.planning/codebase/ARCHITECTURE.md
@.planning/codebase/CONVENTIONS.md
@.planning/codebase/CONCERNS.md

<interfaces>
<!-- Key types and contracts the executor MUST use. Extracted from the existing codebase. -->
<!-- The executor should implement against these — no codebase exploration needed. -->

From data_providers/base.py:
```python
class DataProvider(ABC):
    @abstractmethod
    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame: ...
    @abstractmethod
    async def get_current_price(self, ticker: str) -> float: ...
    async def get_financials(self, ticker: str, period: str = "annual") -> dict: ...
    async def get_key_stats(self, ticker: str) -> dict: ...
    @abstractmethod
    def is_point_in_time(self) -> bool: ...
    @abstractmethod
    def supported_asset_types(self) -> list[str]: ...
```

From data_providers/yfinance_provider.py (current — lock-scoped to preserve):
```python
# KEEP this module-level lock; it still guards Ticker.info paths which share
# yfinance's internal _DFS dictionary on single-ticker calls.
_yfinance_lock = threading.Lock()

class YFinanceProvider(DataProvider):
    _limiter = AsyncRateLimiter(
        max_calls=int(os.getenv("YFINANCE_RATE_LIMIT", "2")),
        period_seconds=1.0,
    )
    # Note: backtesting/engine.py imports `_yfinance_lock` directly; do NOT rename or delete it.
```

From data_providers/cache.py (existing — do NOT modify; this is the async in-memory TTLCache used by CachedProvider):
```python
CACHE_MISS: Any = object()

class TTLCache:
    def __init__(self, default_ttl: float = 300.0) -> None: ...
    async def get(self, method, args, kwargs) -> Any: ...
    async def set(self, method, args, kwargs, value, ttl=None) -> None: ...
    async def clear(self) -> None: ...
    def stats(self) -> dict[str, int | float]: ...
```

From data_providers/cached_provider.py (existing — extend, do NOT break):
```python
class CachedProvider(DataProvider):
    def __init__(self, provider: DataProvider, cache: TTLCache | None = None) -> None:
        self._provider = provider
        self._cache = cache or TTLCache(default_ttl=300.0)
    # All get_* methods read through self._cache.
```

From pyproject.toml (relevant slice):
```toml
dependencies = [
    "aiosqlite>=0.19",
    "yfinance>=0.2",
    "fredapi>=0.5",
    "pandas>=2.0",
    "pandas-ta>=0.4.25b0",
    # ... etc ...
]
```

From yfinance batch-mode docs (authoritative reference — memorize the signature):
```python
# yf.download supports a list of tickers in a single call.
# With group_by="ticker", returns a DataFrame with a MultiIndex where
# level 0 = ticker, level 1 = Open/High/Low/Close/Volume/Adj Close.
data = yf.download(
    tickers=["AAPL", "MSFT", "GOOGL"],
    period="1y",
    interval="1d",
    group_by="ticker",
    progress=False,
    auto_adjust=False,
    threads=True,  # yfinance's internal thread pool; safe with list input
)
# Split per-ticker:
per_ticker: dict[str, pd.DataFrame] = {t: data[t] for t in tickers}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add arch and pyarrow dependencies, implement yfinance batch download (FOUND-01)</name>
  <read_first>
    - pyproject.toml (whole file — dependencies list lines 20-32)
    - data_providers/yfinance_provider.py (whole file — 153 lines)
    - data_providers/base.py (DataProvider interface — 40 lines)
    - data_providers/fred_provider.py (pattern for async + rate-limiter + class-level limiter — lines 14-28)
    - data_providers/rate_limiter.py (AsyncRateLimiter contract)
    - tests/test_004_data_providers.py (existing test patterns for MockProvider)
  </read_first>
  <behavior>
    - Test A: `YFinanceProvider().get_price_history_batch(["AAPL", "MSFT"], period="1mo", interval="1d")` returns `dict[str, pd.DataFrame]` with exactly the requested keys, each DataFrame has columns `["Open", "High", "Low", "Close", "Volume"]`.
    - Test B: `get_price_history_batch` invokes `yfinance.download` exactly ONCE (mocked) for a 10-ticker list, with kwargs including `group_by="ticker"` and `progress=False` and `threads=True`.
    - Test C: Empty ticker list raises `ValueError("tickers must be non-empty")`.
    - Test D: When `yfinance.download` returns a MultiIndex DataFrame keyed `(ticker, price_type)`, the result dict splits correctly per ticker.
    - Test E: When `yfinance.download` returns an empty DataFrame for one ticker in the batch, that ticker's entry is a DataFrame with the expected columns but zero rows — NOT a missing key, NOT a raise. The caller can detect via `.empty`.
    - Test F: The existing single-ticker `get_price_history` still works unchanged (regression check) — behavior preserved.
    - Test G: `_yfinance_lock` is still imported and present in yfinance_provider.py (required by `backtesting/engine.py`). This is checked by grep, not behavior.
  </behavior>
  <action>
    1. Edit `pyproject.toml` lines 20-32 (`dependencies` list) to ADD two entries alphabetically between existing ones:
       - `"arch>=6.0"` (required by Plan 03 FOUND-03; added here because dep changes are atomic)
       - `"pyarrow>=14.0"` (Parquet backend for ParquetOHLCVCache)
       Do NOT remove any existing dependency. The final list must still include every current line.
    2. In `data_providers/yfinance_provider.py`, add a new public async method `get_price_history_batch` on the `YFinanceProvider` class:
       ```python
       async def get_price_history_batch(
           self,
           tickers: list[str],
           period: str = "1y",
           interval: str = "1d",
       ) -> dict[str, pd.DataFrame]:
           """Batch OHLCV download for multiple tickers in a single yfinance.download() call.

           Uses yfinance's built-in thread pool (threads=True) which is safe when called
           with a list. This bypasses the per-ticker _yfinance_lock serialization.

           Returns a dict keyed by ticker. A ticker with no data maps to an empty DataFrame
           with the expected OHLCV columns (not a missing key, not a raise).
           """
           if not tickers:
               raise ValueError("tickers must be non-empty")

           def _download() -> pd.DataFrame:
               # NOTE: no _yfinance_lock here. yf.download with list+threads=True is safe.
               return yf.download(
                   tickers=tickers,
                   period=period,
                   interval=interval,
                   group_by="ticker",
                   progress=False,
                   auto_adjust=False,
                   threads=True,
               )

           async with self._limiter:
               raw = await asyncio.to_thread(_download)

           result: dict[str, pd.DataFrame] = {}
           expected = ["Open", "High", "Low", "Close", "Volume"]

           if raw is None or raw.empty:
               # Yield empty frames for each requested ticker so callers don't KeyError
               empty = pd.DataFrame(columns=expected)
               return {t: empty.copy() for t in tickers}

           if isinstance(raw.columns, pd.MultiIndex):
               # group_by="ticker" yields MultiIndex (ticker, price_type)
               for t in tickers:
                   if t in raw.columns.get_level_values(0):
                       df = raw[t].copy()
                   elif t in raw.columns.get_level_values(1):
                       df = raw.xs(t, level=1, axis=1).copy()
                   else:
                       result[t] = pd.DataFrame(columns=expected)
                       continue
                   df = df.rename(columns={c: str(c).title() for c in df.columns})
                   if "Adj Close" in df.columns:
                       df = df.drop(columns=["Adj Close"])
                   # Ensure all expected columns exist; fill missing with NaN
                   for col in expected:
                       if col not in df.columns:
                           df[col] = pd.NA
                   result[t] = df[expected]
           else:
               # Single-ticker path (yfinance may flatten for len==1)
               df = raw.rename(columns={c: str(c).title() for c in raw.columns})
               if "Adj Close" in df.columns:
                   df = df.drop(columns=["Adj Close"])
               for col in expected:
                   if col not in df.columns:
                       df[col] = pd.NA
               result[tickers[0]] = df[expected]
               for t in tickers[1:]:
                   result[t] = pd.DataFrame(columns=expected)

           # Drop rows where all OHLCV are NaN (yfinance pads missing dates across tickers)
           for t in list(result.keys()):
               result[t] = result[t].dropna(how="all")
           return result
       ```
    3. Do NOT remove `_yfinance_lock` or change the existing `get_price_history`, `get_current_price`, `get_financials`, or `get_key_stats` methods. `backtesting/engine.py` imports `_yfinance_lock` at line 20 and that import must still resolve.
    4. Create `tests/test_foundation_01_yfinance_batch.py` with pytest-asyncio tests covering behaviors A-G. Mock `yfinance.download` with `unittest.mock.patch("data_providers.yfinance_provider.yf.download", ...)`. Construct realistic MultiIndex DataFrames in the mock return values. Use `pytest.raises(ValueError)` for Test C. Use `grep` style inside a test file check for Test G: assert `"_yfinance_lock" in open("data_providers/yfinance_provider.py").read()`.
  </action>
  <verify>
    <automated>
      pytest tests/test_foundation_01_yfinance_batch.py -x -v
      pytest tests/test_004_data_providers.py -x
      python -c "from data_providers.yfinance_provider import YFinanceProvider, _yfinance_lock; assert hasattr(YFinanceProvider, 'get_price_history_batch'); print('OK')"
      grep -q '"arch>=6' pyproject.toml
      grep -q '"pyarrow>=' pyproject.toml
      grep -q 'group_by="ticker"' data_providers/yfinance_provider.py
      grep -q '_yfinance_lock = threading.Lock()' data_providers/yfinance_provider.py
    </automated>
  </verify>
  <acceptance_criteria>
    - `pyproject.toml` contains the literal substrings `"arch>=6` AND `"pyarrow>=` in the `dependencies = [...]` list (exit 0 via grep).
    - `data_providers/yfinance_provider.py` contains the literal substring `get_price_history_batch` (new method name).
    - `data_providers/yfinance_provider.py` contains the literal substring `group_by="ticker"` in an argument position of `yf.download(`.
    - `data_providers/yfinance_provider.py` STILL contains the literal line `_yfinance_lock = threading.Lock()` (so `from data_providers.yfinance_provider import _yfinance_lock` in `backtesting/engine.py` line 20 still works).
    - `pytest tests/test_foundation_01_yfinance_batch.py -x` → exit 0 with at least 7 tests (one per behavior A-G), all passing.
    - `pytest tests/test_004_data_providers.py -x` → exit 0 (regression: existing data-provider tests still pass).
    - `python -c "from data_providers.yfinance_provider import YFinanceProvider; assert hasattr(YFinanceProvider, 'get_price_history_batch')"` → exit 0.
  </acceptance_criteria>
  <done>
    Batch download method is implemented and tested with mocked yfinance. The method takes a list of N tickers, produces exactly ONE call to `yfinance.download(..., group_by="ticker", threads=True)`, and returns a dict keyed by ticker. The existing module-level `_yfinance_lock` is preserved for Ticker.info paths. `arch` and `pyarrow` are in `pyproject.toml` dependencies.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement ParquetOHLCVCache with TTL and explicit invalidation (FOUND-02 core)</name>
  <read_first>
    - data_providers/cache.py (existing TTLCache — 95 lines; do NOT modify)
    - data_providers/cached_provider.py (existing — pattern for wrapping provider)
    - data_providers/base.py (DataProvider interface contract)
    - tests/test_004_data_providers.py (test style: pytest-asyncio, tmp_path fixture, _make_ohlcv helper pattern)
    - .planning/research/FEATURES.md lines 149-155 (disk cache consensus — Parquet, TTL, incremental)
    - .planning/research/PITFALLS.md lines 59-65 (Phase 1 recommendation: local Parquet cache layer)
  </read_first>
  <behavior>
    - Test A: `ParquetOHLCVCache(cache_dir=tmp_path).write(("AAPL", "1y", "1d"), df)` then `.read(("AAPL", "1y", "1d"), ttl=60.0)` returns a DataFrame equal (via `pd.testing.assert_frame_equal`) to the written one.
    - Test B: After `.write(key, df)`, the file `{cache_dir}/AAPL_1y_1d.parquet` exists on disk.
    - Test C: Reading a key that was written more than `ttl` seconds ago returns `None` (miss due to TTL expiry). Use `time.time()` monkeypatch or `.write` with a synthesized mtime via `os.utime`.
    - Test D: `.read(non_existent_key, ttl=60.0)` returns `None` (miss, not raise).
    - Test E: `.invalidate(("AAPL", "1y", "1d"))` removes the file; subsequent `.read` returns `None`.
    - Test F: `.clear_all()` removes every parquet file in cache_dir but preserves the directory.
    - Test G: `stats()` returns `{"hits": int, "misses": int, "size_files": int, "total_bytes": int}` reflecting accumulated counts.
    - Test H: When `pyarrow` is unimportable (simulate with `sys.modules["pyarrow"] = None` + reimport), `ParquetOHLCVCache` raises a clear `ImportError("pyarrow is required for ParquetOHLCVCache")` on construction, not on first use.
    - Test I: Cache dir is created lazily on first `.write` if it does not exist.
    - Test J: A write of an empty DataFrame is rejected with `ValueError("cannot cache empty DataFrame")`.
  </behavior>
  <action>
    Create a new file `data_providers/parquet_cache.py` (do NOT edit the existing `data_providers/cache.py` which holds the in-memory `TTLCache`):

    ```python
    """Parquet-backed OHLCV disk cache for data providers.

    Stores OHLCV DataFrames as Parquet files under a configurable cache directory.
    Each cache key is a tuple (ticker, period, interval) serialized to a filename.
    TTL is enforced by comparing file mtime to time.time(). Explicit invalidation
    is supported via invalidate(key) and clear_all().

    This is distinct from data_providers/cache.py::TTLCache, which is an in-memory
    async cache used by CachedProvider. ParquetOHLCVCache survives process restarts.
    """
    from __future__ import annotations

    import logging
    import os
    import re
    import time
    from pathlib import Path
    from typing import Any

    import pandas as pd

    logger = logging.getLogger(__name__)

    _FILENAME_SAFE = re.compile(r"[^A-Za-z0-9_.-]")


    def _key_to_filename(key: tuple[str, str, str]) -> str:
        ticker, period, interval = key
        safe = [_FILENAME_SAFE.sub("-", str(part)) for part in (ticker, period, interval)]
        return f"{safe[0]}_{safe[1]}_{safe[2]}.parquet"


    class ParquetOHLCVCache:
        """Parquet-backed disk cache for OHLCV DataFrames with TTL + invalidation."""

        def __init__(self, cache_dir: str | Path = "data/cache/ohlcv") -> None:
            try:
                import pyarrow  # noqa: F401 — import check only
            except ImportError as exc:
                raise ImportError(
                    "pyarrow is required for ParquetOHLCVCache. "
                    "Install with: pip install pyarrow>=14.0"
                ) from exc
            self._cache_dir = Path(cache_dir)
            self._hits = 0
            self._misses = 0

        def _path_for(self, key: tuple[str, str, str]) -> Path:
            return self._cache_dir / _key_to_filename(key)

        def read(self, key: tuple[str, str, str], ttl: float = 300.0) -> pd.DataFrame | None:
            """Return cached DataFrame or None on miss / TTL expiry. Never raises on miss."""
            path = self._path_for(key)
            if not path.exists():
                self._misses += 1
                return None
            mtime = path.stat().st_mtime
            if time.time() - mtime > ttl:
                self._misses += 1
                return None
            try:
                df = pd.read_parquet(path)
            except Exception as exc:
                logger.warning("ParquetOHLCVCache: failed to read %s: %s", path, exc)
                self._misses += 1
                return None
            self._hits += 1
            return df

        def write(self, key: tuple[str, str, str], df: pd.DataFrame) -> None:
            """Persist a DataFrame to disk. Raises on empty DataFrame."""
            if df is None or df.empty:
                raise ValueError("cannot cache empty DataFrame")
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            path = self._path_for(key)
            tmp = path.with_suffix(".parquet.tmp")
            df.to_parquet(tmp, engine="pyarrow", compression="snappy")
            os.replace(tmp, path)  # atomic on POSIX & Windows for same FS

        def invalidate(self, key: tuple[str, str, str]) -> bool:
            """Delete one cache entry. Returns True if a file was removed."""
            path = self._path_for(key)
            if path.exists():
                path.unlink()
                return True
            return False

        def clear_all(self) -> int:
            """Delete every .parquet file in the cache directory. Returns file count removed."""
            if not self._cache_dir.exists():
                return 0
            count = 0
            for p in self._cache_dir.glob("*.parquet"):
                try:
                    p.unlink()
                    count += 1
                except Exception as exc:
                    logger.warning("ParquetOHLCVCache: failed to unlink %s: %s", p, exc)
            return count

        def stats(self) -> dict[str, Any]:
            files = list(self._cache_dir.glob("*.parquet")) if self._cache_dir.exists() else []
            total_bytes = sum(p.stat().st_size for p in files)
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "total": total,
                "size_files": len(files),
                "total_bytes": total_bytes,
                "hit_rate": round(self._hits / total, 3) if total else 0.0,
            }
    ```

    Then create `tests/test_foundation_02_parquet_cache.py` covering behaviors A-J. Use `tmp_path` for cache_dir. Build OHLCV DataFrames with the existing project helper pattern (2-3 rows, columns `["Open", "High", "Low", "Close", "Volume"]`). For Test C (TTL expiry), use `os.utime(path, (old, old))` where `old = time.time() - 1000`. For Test H (pyarrow missing), use `unittest.mock.patch.dict(sys.modules, {"pyarrow": None})` + trigger a fresh `importlib.reload(data_providers.parquet_cache)` and verify `ImportError` on `ParquetOHLCVCache()`.
  </action>
  <verify>
    <automated>
      pytest tests/test_foundation_02_parquet_cache.py -x -v
      python -c "from data_providers.parquet_cache import ParquetOHLCVCache; import tempfile; c = ParquetOHLCVCache(tempfile.mkdtemp()); print(c.stats())"
      grep -q "class ParquetOHLCVCache" data_providers/parquet_cache.py
      grep -q "to_parquet" data_providers/parquet_cache.py
      grep -q "read_parquet" data_providers/parquet_cache.py
      grep -q "def invalidate" data_providers/parquet_cache.py
      grep -q "def clear_all" data_providers/parquet_cache.py
    </automated>
  </verify>
  <acceptance_criteria>
    - File `data_providers/parquet_cache.py` exists.
    - Grep finds: `class ParquetOHLCVCache`, `to_parquet`, `read_parquet`, `def invalidate`, `def clear_all` in that file.
    - Existing file `data_providers/cache.py` is UNCHANGED — `git diff --stat data_providers/cache.py` shows 0 lines changed (verified via `git diff data_providers/cache.py | wc -l == 0`).
    - `pytest tests/test_foundation_02_parquet_cache.py -x` → exit 0 with at least 10 tests (one per behavior A-J), all passing.
    - `python -c "from data_providers.parquet_cache import ParquetOHLCVCache"` → exit 0 (no import errors when pyarrow is present).
  </acceptance_criteria>
  <done>
    `ParquetOHLCVCache` is a standalone class in a new module, with TTL, explicit invalidation, atomic writes, graceful pyarrow-missing failure, and stats. Existing `TTLCache` in `data_providers/cache.py` is untouched.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Wire ParquetOHLCVCache into CachedProvider for read-through OHLCV caching (FOUND-02 integration)</name>
  <read_first>
    - data_providers/cached_provider.py (existing — 128 lines; understand the `_cached()` helper pattern and how get_price_history uses it)
    - data_providers/parquet_cache.py (just created in Task 2)
    - data_providers/base.py (DataProvider interface contract)
    - tests/test_004_data_providers.py (MockProvider pattern, async test style)
  </read_first>
  <behavior>
    - Test A: `CachedProvider(inner, parquet_cache=pc)` with a mock `inner` provider. First call to `get_price_history("AAPL", "1mo", "1d")` triggers `inner.get_price_history()` exactly once AND writes a parquet file.
    - Test B: Second call within TTL returns the same DataFrame WITHOUT calling `inner.get_price_history` again (inner call count stays at 1).
    - Test C: Passing `parquet_cache=None` preserves existing behavior exactly — all existing `test_004_data_providers.py` tests still pass.
    - Test D: Parquet read errors (corrupt file) fall through to the inner provider and overwrite the cache file. Verified by writing invalid bytes to a parquet path and confirming the next call succeeds + the cache is healed.
    - Test E: `parquet_cache` is only used on `get_price_history` — `get_current_price`, `get_financials`, `get_key_stats` do NOT write parquet files.
  </behavior>
  <action>
    Edit `data_providers/cached_provider.py`. Do NOT change the existing `TTLCache`-based `_cached()` helper or any existing method signatures. ADD a new `parquet_cache` kwarg:

    ```python
    # at top of file, after existing imports:
    from data_providers.parquet_cache import ParquetOHLCVCache

    class CachedProvider(DataProvider):
        def __init__(
            self,
            provider: DataProvider,
            cache: TTLCache | None = None,
            parquet_cache: ParquetOHLCVCache | None = None,
            parquet_ttl: float = 86400.0,  # 24h default — OHLCV stable intraday
        ) -> None:
            self._provider = provider
            self._cache = cache or TTLCache(default_ttl=_DEFAULT_TTL)
            self._parquet_cache = parquet_cache
            self._parquet_ttl = parquet_ttl

        async def get_price_history(
            self, ticker: str, period: str = "1y", interval: str = "1d"
        ) -> pd.DataFrame:
            # Parquet read-through: only if enabled AND key is present
            if self._parquet_cache is not None:
                key = (ticker, period, interval)
                cached = self._parquet_cache.read(key, ttl=self._parquet_ttl)
                if cached is not None and not cached.empty:
                    # Also prime in-memory TTLCache so sibling calls in same process hit RAM
                    await self._cache.set("get_price_history", (ticker, period, interval), {}, cached.copy())
                    return cached.copy()

            # Fall through to existing TTLCache + inner provider
            result: pd.DataFrame = await self._cached(
                "get_price_history", (ticker, period, interval), {}
            )

            # Write-through to parquet on every upstream fetch
            if self._parquet_cache is not None and result is not None and not result.empty:
                try:
                    self._parquet_cache.write((ticker, period, interval), result)
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).warning(
                        "Parquet write failed for %s: %s", ticker, exc
                    )

            return result.copy()
    ```

    The `CachedFredProvider` subclass does NOT need a parquet_cache because FRED data is already cached via the existing `_MACRO_TTL` in-memory TTL; keep CachedFredProvider unchanged except it inherits the new `__init__` signature.

    Create `tests/test_foundation_02_parquet_cache.py` IF NOT ALREADY CREATED in Task 2, and ADD tests for CachedProvider integration (behaviors A-E). Use a counter-based MockProvider:
    ```python
    class _CountingProvider(DataProvider):
        def __init__(self, df):
            self.df = df
            self.price_calls = 0
        async def get_price_history(self, ticker, period="1y", interval="1d"):
            self.price_calls += 1
            return self.df.copy()
        async def get_current_price(self, ticker): return 100.0
        def is_point_in_time(self): return False
        def supported_asset_types(self): return ["stock"]
    ```
  </action>
  <verify>
    <automated>
      pytest tests/test_foundation_02_parquet_cache.py -x -v
      pytest tests/test_004_data_providers.py -x
      grep -q "parquet_cache" data_providers/cached_provider.py
      grep -q "ParquetOHLCVCache" data_providers/cached_provider.py
      python -c "from data_providers.cached_provider import CachedProvider; import inspect; sig = inspect.signature(CachedProvider.__init__); assert 'parquet_cache' in sig.parameters; print('OK')"
    </automated>
  </verify>
  <acceptance_criteria>
    - `data_providers/cached_provider.py` imports `ParquetOHLCVCache` from `data_providers.parquet_cache` (grep-verifiable: `grep -q "from data_providers.parquet_cache import ParquetOHLCVCache" data_providers/cached_provider.py`).
    - `CachedProvider.__init__` signature includes a `parquet_cache` parameter (verified by `inspect.signature` in the automated check above).
    - Existing `data_providers/cache.py` (TTLCache) is UNCHANGED (`git diff data_providers/cache.py` → empty).
    - `pytest tests/test_004_data_providers.py -x` → exit 0 (regression: all existing cached-provider tests still pass with `parquet_cache=None` default).
    - `pytest tests/test_foundation_02_parquet_cache.py -x` → exit 0 with the integration tests added (behaviors A-E), all passing.
    - On a second identical call with a warm parquet cache, the mock inner provider's `price_calls` counter is exactly 1 (not 2) — proving the read-through.
  </acceptance_criteria>
  <done>
    CachedProvider accepts an optional `parquet_cache` and uses it as a read-through + write-through cache for `get_price_history` ONLY. When `parquet_cache=None`, behavior is identical to the current code. When set, repeat calls skip the inner provider entirely if within TTL.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Filesystem → Process | Parquet cache files on disk; any local user with filesystem access can tamper with them (replacing with crafted parquet files). |
| Network (yfinance) → Process | yfinance responses are untrusted external data; we parse `pd.DataFrame` from them into our pipeline. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01 | Tampering | `ParquetOHLCVCache.read` reading attacker-supplied parquet files from `data/cache/ohlcv/` | accept | Local-first single-user deployment per PROJECT.md constraints; filesystem tampering implies the attacker already owns the box. On read, `pd.read_parquet` failures are caught and logged (healing re-fetches from yfinance). |
| T-01-02 | Information disclosure | Parquet cache stores full OHLCV history on disk indefinitely | accept | OHLCV is public market data; no PII. `clear_all()` is available for explicit purge. |
| T-01-03 | Denial of service | Unbounded parquet cache growth fills disk | mitigate | Task 3 gates write-through via `parquet_cache` being explicitly opt-in. Operators who enable it are responsible for TTL choice. A future phase (DATA-04 observability) will surface `total_bytes` via `/health`. |
| T-01-04 | Tampering (input) | yfinance response injection (crafted HTML/JSON) | accept | yfinance library handles parsing; we only trust the resulting DataFrame shape, not content. Out-of-range values would not cause memory safety issues because pandas is pure Python. |
| T-01-05 | Repudiation | Cache hit vs. fresh fetch is indistinguishable to the agent layer | mitigate | `ParquetOHLCVCache.stats()` exposes hits/misses counters. Phase 3 (DATA-04) will log these per job. |
</threat_model>

<verification>
Overall plan-level checks executed at the end of the plan:

```bash
pytest tests/test_foundation_01_yfinance_batch.py tests/test_foundation_02_parquet_cache.py tests/test_004_data_providers.py -x -v
grep -q '"arch>=6' pyproject.toml
grep -q '"pyarrow>=' pyproject.toml
grep -q 'get_price_history_batch' data_providers/yfinance_provider.py
grep -q 'group_by="ticker"' data_providers/yfinance_provider.py
grep -q '_yfinance_lock = threading.Lock()' data_providers/yfinance_provider.py
grep -q 'class ParquetOHLCVCache' data_providers/parquet_cache.py
grep -q 'parquet_cache' data_providers/cached_provider.py
test -z "$(git diff --name-only data_providers/cache.py)"  # cache.py (TTLCache) unchanged
```

All 9 checks must exit 0.
</verification>

<success_criteria>
- `YFinanceProvider` gains a batch download method that issues a single `yf.download(..., group_by="ticker", threads=True)` call for N tickers.
- `_yfinance_lock` remains in place (required for backwards compat with `backtesting/engine.py` import).
- A new `ParquetOHLCVCache` class persists OHLCV to Parquet with TTL, explicit invalidation, atomic writes, and pyarrow-missing graceful failure.
- `CachedProvider` accepts an optional `parquet_cache` and uses it as a read-through + write-through cache for `get_price_history`.
- Three new test files provide ≥17 new tests (7 batch + 10 Parquet + 5 integration).
- All pre-existing tests in `tests/test_004_data_providers.py` continue to pass.
- `arch>=6.0` and `pyarrow>=14.0` are declared in `pyproject.toml`.
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-hardening/01-PLAN-data-provider-caching-SUMMARY.md` that records:
- New files created
- Line counts for each modified file (before/after)
- Exact pytest command output confirming tests pass
- Baseline vs. post-change timing for a 10-ticker batch download (measured via the new batch method with yfinance mocked to return fixed fake data — this is a unit-level timing sanity check, not a network benchmark)
- Any deviations from the plan with rationale
</output>
</content>
</invoke>