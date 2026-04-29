"""Parquet-backed SimFin statement disk cache (Phase 8 DATA-v2-02).

Mirrors the DividendCache pattern (AN-01) but keys cache entries on the
5-tuple ``(ticker, statement, period, fyear, asreported)`` since SimFin
returns different rows for as-filed vs restated values. TTL is 24 hours —
fundamental statements amend infrequently so daily staleness is acceptable
for the operator-facing badge surface.

Cache layout:
    data/cache/simfin/{safe_ticker}_{statement}_{period}_{fyear}_{asreported}.parquet

Atomic-rename writes prevent partial reads. Windows fallback matches the
DividendCache strategy (delete-then-rename with 3 retries).

Path-traversal mitigation (T-08-02-05):
    safe_ticker = re.sub(r'[^A-Za-z0-9_.-]', '-', ticker) — same regex as
    DividendCache so attacker-controlled ticker cannot escape the cache dir.
"""
from __future__ import annotations

import logging
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9_.-]")

_24H_SECONDS = 24 * 3600


def _key_to_filename(
    ticker: str,
    statement: str,
    period: str,
    fyear: int | None,
    asreported: bool,
) -> str:
    """Build a filesystem-safe filename for a cache key.

    T-08-02-05 mitigation: ticker is sanitized via the same regex used by
    DividendCache so adversarial inputs (e.g. ``../../etc/passwd``) cannot
    escape the cache directory.
    """
    safe_ticker = _FILENAME_SAFE.sub("-", ticker)
    safe_stmt = _FILENAME_SAFE.sub("-", statement)
    safe_period = _FILENAME_SAFE.sub("-", period)
    fyear_part = "any" if fyear is None else str(fyear)
    asr_part = "true" if asreported else "false"
    return (
        f"{safe_ticker}_{safe_stmt}_{safe_period}_{fyear_part}_{asr_part}.parquet"
    )


class SimfinStatementCache:
    """Parquet-backed disk cache for SimFin statement responses with 24h TTL.

    Stores the SimFin v3 ``data`` array as a flattened DataFrame. Keys are
    the 5-tuple ``(ticker, statement, period, fyear, asreported)`` so as-filed
    and restated payloads do not collide.
    """

    def __init__(self, cache_dir: str | Path = "data/cache/simfin") -> None:
        try:
            import pyarrow  # noqa: F401 — import check only
        except ImportError as exc:
            raise ImportError(
                "pyarrow is required for SimfinStatementCache. "
                "Install with: pip install pyarrow>=14.0"
            ) from exc
        self._cache_dir = Path(cache_dir)
        self._hits = 0
        self._misses = 0

    def _path_for(
        self,
        ticker: str,
        statement: str,
        period: str,
        fyear: int | None,
        asreported: bool,
    ) -> Path:
        return self._cache_dir / _key_to_filename(
            ticker, statement, period, fyear, asreported
        )

    def get(
        self,
        ticker: str,
        statement: str = "pl",
        period: str = "q1",
        fyear: int | None = None,
        asreported: bool = True,
        ttl: float = _24H_SECONDS,
    ) -> pd.DataFrame | None:
        """Return cached statement DataFrame or None on miss / TTL expiry."""
        path = self._path_for(ticker, statement, period, fyear, asreported)
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
            logger.warning("SimfinStatementCache: failed to read %s: %s", path, exc)
            self._misses += 1
            return None
        self._hits += 1
        return df

    def set(
        self,
        ticker: str,
        statement: str,
        period: str,
        fyear: int | None,
        asreported: bool,
        df: pd.DataFrame,
    ) -> None:
        """Persist statement DataFrame to disk using atomic-rename.

        On Windows, uses delete-then-rename with up to 3 retries to avoid
        ERROR_SHARING_VIOLATION (WinError 32) from concurrent readers.
        """
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(ticker, statement, period, fyear, asreported)
        tmp = path.with_suffix(".parquet.tmp")

        df.to_parquet(tmp, engine="pyarrow", compression="snappy")

        if sys.platform == "win32":
            for attempt in range(3):
                try:
                    if path.exists():
                        path.unlink()
                    tmp.rename(path)
                    break
                except OSError:
                    if attempt == 2:
                        logger.warning(
                            "SimfinStatementCache: replace failed for %s after 3 attempts",
                            path,
                        )
                        tmp.unlink(missing_ok=True)
        else:
            os.replace(tmp, path)

    def invalidate(
        self,
        ticker: str,
        statement: str = "pl",
        period: str = "q1",
        fyear: int | None = None,
        asreported: bool = True,
    ) -> bool:
        """Delete a single cache entry. Returns True if a file was removed."""
        path = self._path_for(ticker, statement, period, fyear, asreported)
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
