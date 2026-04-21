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
import sys
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
        """Persist a DataFrame to disk. Raises on empty DataFrame.

        On Windows, os.replace() raises ERROR_SHARING_VIOLATION (WinError 32)
        when the target file is open by a concurrent reader (e.g. pd.read_parquet
        in another async task). Fall back to a delete-then-rename sequence with
        up to 3 retries so stranded .parquet.tmp files are not leaked.
        """
        if df is None or df.empty:
            raise ValueError("cannot cache empty DataFrame")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(key)
        tmp = path.with_suffix(".parquet.tmp")
        df.to_parquet(tmp, engine="pyarrow", compression="snappy")
        if sys.platform == "win32":
            # MoveFileEx raises when the target is open by another reader;
            # retry up to 3 times with explicit delete + rename.
            for attempt in range(3):
                try:
                    if path.exists():
                        path.unlink()
                    tmp.rename(path)
                    break
                except OSError:
                    if attempt == 2:
                        logger.warning(
                            "ParquetOHLCVCache: replace failed for %s after 3 attempts",
                            path,
                        )
                        tmp.unlink(missing_ok=True)
        else:
            os.replace(tmp, path)  # atomic on POSIX for same FS

    def invalidate(self, key: tuple[str, str, str]) -> bool:
        """Delete one cache entry. Returns True if a file was removed."""
        path = self._path_for(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def clear_all(self) -> int:
        """Delete every .parquet and .parquet.tmp file in the cache directory.

        Also removes stranded .parquet.tmp files that may have been left by a
        failed Windows write() retry (see CR-01 fix). Returns file count removed.
        """
        if not self._cache_dir.exists():
            return 0
        count = 0
        for pattern in ("*.parquet", "*.parquet.tmp"):
            for p in self._cache_dir.glob(pattern):
                try:
                    p.unlink()
                    count += 1
                except Exception as exc:
                    logger.warning("ParquetOHLCVCache: failed to unlink %s: %s", p, exc)
        return count

    def stats(self) -> dict[str, Any]:
        """Return cache statistics including hit/miss counts and disk usage."""
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
