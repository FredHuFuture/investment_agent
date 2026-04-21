"""Tests for ParquetOHLCVCache (FOUND-02) and CachedProvider parquet integration.

Part 1 — ParquetOHLCVCache standalone (behaviors A-J from Task 2):
A - write() then read() returns an equal DataFrame
B - write() creates the expected parquet file on disk
C - read() after TTL expiry returns None
D - read() of non-existent key returns None (no raise)
E - invalidate() removes the file; subsequent read returns None
F - clear_all() removes all parquet files, preserves directory
G - stats() returns hits/misses/size_files/total_bytes
H - ImportError raised on construction when pyarrow unavailable
I - cache dir created lazily on first write
J - empty DataFrame write raises ValueError

Part 2 — CachedProvider parquet integration (behaviors A-E from Task 3):
A - First call triggers inner provider and writes parquet file
B - Second call within TTL skips inner provider (price_calls stays at 1)
C - parquet_cache=None preserves existing behavior
D - Corrupt parquet file falls through to inner provider, cache healed
E - parquet_cache only used for get_price_history (not other methods)
"""
from __future__ import annotations

import asyncio
import importlib
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from data_providers.base import DataProvider
from data_providers.parquet_cache import ParquetOHLCVCache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OHLCV_COLS = ["Open", "High", "Low", "Close", "Volume"]


def _make_ohlcv(rows: int = 5) -> pd.DataFrame:
    """Create a minimal OHLCV DataFrame matching project conventions."""
    now = datetime.now(timezone.utc)
    dates = [now - timedelta(days=(rows - i)) for i in range(rows)]
    close = pd.Series([100.0 + i for i in range(rows)], index=pd.to_datetime(dates))
    return pd.DataFrame(
        {
            "Open": close * 0.995,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": [1_000_000.0] * rows,
        },
        index=pd.to_datetime(dates),
    )


KEY = ("AAPL", "1y", "1d")


# ===========================================================================
# Part 1: ParquetOHLCVCache standalone
# ===========================================================================

# ---------------------------------------------------------------------------
# Test A: write then read returns equal DataFrame
# ---------------------------------------------------------------------------

def test_read_after_write_returns_equal_df(tmp_path: Path) -> None:
    """Behavior A: write(key, df) then read(key, ttl=60) == original df."""
    cache = ParquetOHLCVCache(cache_dir=tmp_path)
    df = _make_ohlcv()
    cache.write(KEY, df)
    result = cache.read(KEY, ttl=60.0)
    assert result is not None
    pd.testing.assert_frame_equal(result, df)


# ---------------------------------------------------------------------------
# Test B: write creates the expected parquet file
# ---------------------------------------------------------------------------

def test_write_creates_parquet_file(tmp_path: Path) -> None:
    """Behavior B: {cache_dir}/AAPL_1y_1d.parquet exists after write."""
    cache = ParquetOHLCVCache(cache_dir=tmp_path)
    df = _make_ohlcv()
    cache.write(KEY, df)
    expected_file = tmp_path / "AAPL_1y_1d.parquet"
    assert expected_file.exists(), f"Expected {expected_file} to exist after write"


# ---------------------------------------------------------------------------
# Test C: read returns None after TTL expiry (via os.utime)
# ---------------------------------------------------------------------------

def test_ttl_expiry_returns_none(tmp_path: Path) -> None:
    """Behavior C: read() returns None when file mtime is older than ttl."""
    cache = ParquetOHLCVCache(cache_dir=tmp_path)
    df = _make_ohlcv()
    cache.write(KEY, df)

    # Back-date the file's mtime by 1000 seconds (well past any TTL)
    parquet_path = tmp_path / "AAPL_1y_1d.parquet"
    old_time = time.time() - 1000
    os.utime(parquet_path, (old_time, old_time))

    result = cache.read(KEY, ttl=60.0)
    assert result is None, "Expected None after TTL expiry"


# ---------------------------------------------------------------------------
# Test D: read of non-existent key returns None
# ---------------------------------------------------------------------------

def test_read_missing_key_returns_none(tmp_path: Path) -> None:
    """Behavior D: read() returns None for a key that was never written."""
    cache = ParquetOHLCVCache(cache_dir=tmp_path)
    result = cache.read(("ZZZNONE", "1y", "1d"), ttl=60.0)
    assert result is None, "Expected None for missing key"


# ---------------------------------------------------------------------------
# Test E: invalidate removes the file; subsequent read returns None
# ---------------------------------------------------------------------------

def test_invalidate(tmp_path: Path) -> None:
    """Behavior E: invalidate(key) removes file; subsequent read -> None."""
    cache = ParquetOHLCVCache(cache_dir=tmp_path)
    df = _make_ohlcv()
    cache.write(KEY, df)

    removed = cache.invalidate(KEY)
    assert removed is True, "invalidate should return True when file existed"

    result = cache.read(KEY, ttl=60.0)
    assert result is None, "Expected None after invalidation"


# ---------------------------------------------------------------------------
# Test F: clear_all removes all parquet files, preserves dir
# ---------------------------------------------------------------------------

def test_clear_all_removes_parquet_files_preserves_dir(tmp_path: Path) -> None:
    """Behavior F: clear_all() deletes *.parquet but keeps the directory."""
    cache = ParquetOHLCVCache(cache_dir=tmp_path)
    # Write two different entries
    cache.write(("AAPL", "1y", "1d"), _make_ohlcv())
    cache.write(("MSFT", "6mo", "1d"), _make_ohlcv())

    count = cache.clear_all()
    assert count == 2, f"Expected 2 files removed, got {count}"
    assert tmp_path.exists(), "cache directory must survive clear_all"
    remaining = list(tmp_path.glob("*.parquet"))
    assert len(remaining) == 0, f"Expected 0 parquet files; found {remaining}"


# ---------------------------------------------------------------------------
# Test G: stats() returns correct shape and types
# ---------------------------------------------------------------------------

def test_stats_reflects_hits_and_misses(tmp_path: Path) -> None:
    """Behavior G: stats() has hits, misses, size_files, total_bytes."""
    cache = ParquetOHLCVCache(cache_dir=tmp_path)
    df = _make_ohlcv()
    cache.write(KEY, df)

    _ = cache.read(KEY, ttl=60.0)       # hit
    _ = cache.read(("ZZZ", "1y", "1d"), ttl=60.0)  # miss

    stats = cache.stats()
    assert "hits" in stats
    assert "misses" in stats
    assert "size_files" in stats
    assert "total_bytes" in stats
    assert isinstance(stats["hits"], int)
    assert isinstance(stats["misses"], int)
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["size_files"] >= 1
    assert stats["total_bytes"] > 0


# ---------------------------------------------------------------------------
# Test H: ImportError on construction when pyarrow is unimportable
# ---------------------------------------------------------------------------

def test_pyarrow_missing_raises_import_error(tmp_path: Path) -> None:
    """Behavior H: construction raises ImportError when pyarrow is unavailable."""
    import data_providers.parquet_cache as pc_module

    with patch.dict(sys.modules, {"pyarrow": None}):
        # Force re-evaluation of the import check by reloading the module
        reloaded = importlib.reload(pc_module)
        with pytest.raises(ImportError, match="pyarrow is required"):
            reloaded.ParquetOHLCVCache(cache_dir=tmp_path)

    # Restore by reloading again without the patch
    importlib.reload(pc_module)


# ---------------------------------------------------------------------------
# Test I: cache dir created lazily on first write
# ---------------------------------------------------------------------------

def test_cache_dir_created_lazily_on_write(tmp_path: Path) -> None:
    """Behavior I: cache dir doesn't need to exist before write()."""
    cache_dir = tmp_path / "deeply" / "nested" / "ohlcv"
    assert not cache_dir.exists(), "pre-condition: dir must not exist yet"

    cache = ParquetOHLCVCache(cache_dir=cache_dir)
    df = _make_ohlcv()
    cache.write(KEY, df)  # must not raise

    assert cache_dir.exists(), "cache dir should be created by write()"
    assert (cache_dir / "AAPL_1y_1d.parquet").exists()


# ---------------------------------------------------------------------------
# Test J: write of empty DataFrame raises ValueError
# ---------------------------------------------------------------------------

def test_write_empty_df_raises_value_error(tmp_path: Path) -> None:
    """Behavior J: writing an empty DataFrame raises ValueError."""
    cache = ParquetOHLCVCache(cache_dir=tmp_path)
    empty = pd.DataFrame(columns=OHLCV_COLS)
    with pytest.raises(ValueError, match="cannot cache empty DataFrame"):
        cache.write(KEY, empty)


# ===========================================================================
# Part 2: CachedProvider + parquet integration (Task 3 behaviors A-E)
# ===========================================================================

class _CountingProvider(DataProvider):
    """Mock DataProvider that counts how many times each method is called."""

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df
        self.price_calls = 0
        self.current_price_calls = 0

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        self.price_calls += 1
        return self.df.copy()

    async def get_current_price(self, ticker: str) -> float:
        self.current_price_calls += 1
        return 100.0

    def is_point_in_time(self) -> bool:
        return False

    def supported_asset_types(self) -> list[str]:
        return ["stock"]


def test_first_call_hits_inner_provider_and_writes_parquet(tmp_path: Path) -> None:
    """Task 3 Behavior A: first call invokes inner provider and writes parquet."""
    from data_providers.cached_provider import CachedProvider

    df = _make_ohlcv()
    inner = _CountingProvider(df)
    pc = ParquetOHLCVCache(cache_dir=tmp_path)
    provider = CachedProvider(inner, parquet_cache=pc, parquet_ttl=3600.0)

    asyncio.run(provider.get_price_history("AAPL", "1mo", "1d"))

    assert inner.price_calls == 1, "Inner provider must be called exactly once"
    assert (tmp_path / "AAPL_1mo_1d.parquet").exists(), "Parquet file must be written"


def test_second_call_within_ttl_skips_inner_provider(tmp_path: Path) -> None:
    """Task 3 Behavior B: second call within TTL returns cached DF; price_calls == 1."""
    from data_providers.cached_provider import CachedProvider

    df = _make_ohlcv()
    inner = _CountingProvider(df)
    pc = ParquetOHLCVCache(cache_dir=tmp_path)
    provider = CachedProvider(inner, parquet_cache=pc, parquet_ttl=3600.0)

    r1 = asyncio.run(provider.get_price_history("AAPL", "1mo", "1d"))
    r2 = asyncio.run(provider.get_price_history("AAPL", "1mo", "1d"))

    assert inner.price_calls == 1, (
        f"Inner provider must be called only once; got {inner.price_calls}"
    )
    pd.testing.assert_frame_equal(r1, r2)


def test_parquet_cache_none_preserves_existing_behavior(tmp_path: Path) -> None:
    """Task 3 Behavior C: parquet_cache=None → identical behavior to before."""
    from data_providers.cached_provider import CachedProvider

    df = _make_ohlcv()
    inner = _CountingProvider(df)
    provider = CachedProvider(inner, parquet_cache=None)

    result = asyncio.run(provider.get_price_history("AAPL", "1y", "1d"))

    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert inner.price_calls == 1


def test_corrupt_parquet_falls_through_to_inner_and_heals(tmp_path: Path) -> None:
    """Task 3 Behavior D: corrupt parquet -> falls through to inner, cache healed."""
    from data_providers.cached_provider import CachedProvider

    df = _make_ohlcv()
    inner = _CountingProvider(df)
    pc = ParquetOHLCVCache(cache_dir=tmp_path)
    provider = CachedProvider(inner, parquet_cache=pc, parquet_ttl=3600.0)

    # Write corrupted bytes to the parquet file directly
    bad_path = tmp_path / "AAPL_1y_1d.parquet"
    bad_path.write_bytes(b"this is not valid parquet data !@#$")

    # Call should fall through to inner provider (parquet read fails gracefully)
    result = asyncio.run(provider.get_price_history("AAPL", "1y", "1d"))

    assert inner.price_calls == 1, "Inner provider must be called after parquet read failure"
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    # Cache should be healed (overwritten with valid parquet)
    assert bad_path.exists(), "Healed parquet file must exist"
    healed = pd.read_parquet(bad_path)
    assert not healed.empty, "Healed parquet must contain valid data"


def test_parquet_cache_only_used_for_price_history(tmp_path: Path) -> None:
    """Task 3 Behavior E: parquet_cache NOT used for get_current_price."""
    from data_providers.cached_provider import CachedProvider

    df = _make_ohlcv()
    inner = _CountingProvider(df)
    pc = ParquetOHLCVCache(cache_dir=tmp_path)
    provider = CachedProvider(inner, parquet_cache=pc, parquet_ttl=3600.0)

    asyncio.run(provider.get_current_price("AAPL"))
    asyncio.run(provider.get_current_price("AAPL"))

    # No parquet files should be written for current price calls
    parquet_files = list(tmp_path.glob("*.parquet"))
    assert len(parquet_files) == 0, (
        f"Parquet must not be written for get_current_price; found {parquet_files}"
    )
