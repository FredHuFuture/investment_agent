"""Parquet-backed dividend disk cache for YFinanceProvider (AN-01).

Mirrors the ParquetOHLCVCache pattern (FOUND-02) but stores per-ticker dividend
series as a two-column DataFrame: ``ex_date`` (object/string) and ``amount``
(float64). TTL is 24 hours — dividends change quarterly so daily staleness is
acceptable.

Cache layout:
    data/cache/dividends/{safe_ticker}.parquet

Atomic-rename writes prevent partial reads. Windows fallback matches the
ParquetOHLCVCache strategy (delete-then-rename with 3 retries).
"""
from __future__ import annotations

import logging
import os
import re
import sys
import time
from datetime import date as _date
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9_.-]")

_24H_SECONDS = 24 * 3600


def _ticker_to_filename(ticker: str) -> str:
    safe = _FILENAME_SAFE.sub("-", ticker)
    return f"{safe}.parquet"


class DividendCache:
    """Parquet-backed disk cache for dividend series with 24-hour TTL.

    Each entry is a DataFrame with columns ``["ex_date", "amount"]``.
    ``ex_date`` is stored as an ISO-format string (YYYY-MM-DD) so it survives
    Parquet round-trips without timezone issues.
    """

    def __init__(self, cache_dir: str | Path = "data/cache/dividends") -> None:
        try:
            import pyarrow  # noqa: F401 — import check only
        except ImportError as exc:
            raise ImportError(
                "pyarrow is required for DividendCache. "
                "Install with: pip install pyarrow>=14.0"
            ) from exc
        self._cache_dir = Path(cache_dir)
        self._hits = 0
        self._misses = 0

    def _path_for(self, ticker: str) -> Path:
        return self._cache_dir / _ticker_to_filename(ticker)

    def read(
        self, ticker: str, ttl: float = _24H_SECONDS
    ) -> list[tuple[_date, float]] | None:
        """Return cached dividend list or None on miss / TTL expiry.

        Returns list of ``(date, float)`` tuples sorted by date ascending.
        Never raises on cache miss.
        """
        path = self._path_for(ticker)
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
            logger.warning("DividendCache: failed to read %s: %s", path, exc)
            self._misses += 1
            return None

        if df.empty or "ex_date" not in df.columns or "amount" not in df.columns:
            self._misses += 1
            return None

        result: list[tuple[_date, float]] = []
        for _, row in df.iterrows():
            try:
                ex_date = _date.fromisoformat(str(row["ex_date"]))
                result.append((ex_date, float(row["amount"])))
            except (ValueError, TypeError):
                continue

        self._hits += 1
        return sorted(result, key=lambda x: x[0])

    def write(self, ticker: str, dividends: list[tuple[_date, float]]) -> None:
        """Persist dividend list to disk using atomic-rename.

        ``dividends`` is a list of ``(date, float)`` tuples. Empty list writes
        an empty DataFrame so subsequent reads return ``[]`` (not a cache miss).

        On Windows, uses delete-then-rename with up to 3 retries to avoid
        ERROR_SHARING_VIOLATION (WinError 32) from concurrent readers.
        """
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(ticker)
        tmp = path.with_suffix(".parquet.tmp")

        df = pd.DataFrame(
            [{"ex_date": d.isoformat(), "amount": float(amt)} for d, amt in dividends]
            if dividends
            else [],
            columns=["ex_date", "amount"],
        )
        df.to_parquet(tmp, engine="pyarrow", compression="snappy")

        if sys.platform == "win32":
            # MoveFileEx raises when target is open by another reader;
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
                            "DividendCache: replace failed for %s after 3 attempts",
                            path,
                        )
                        tmp.unlink(missing_ok=True)
        else:
            os.replace(tmp, path)  # atomic on POSIX for same FS

    def invalidate(self, ticker: str) -> bool:
        """Delete one cache entry. Returns True if a file was removed."""
        path = self._path_for(ticker)
        if path.exists():
            path.unlink()
            return True
        return False

    def stats(self) -> dict:
        """Return cache statistics including hit/miss counts and disk usage."""
        files = (
            list(self._cache_dir.glob("*.parquet"))
            if self._cache_dir.exists()
            else []
        )
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
