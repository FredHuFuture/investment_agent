from __future__ import annotations

import asyncio
import time
from typing import Any

# Sentinel returned by TTLCache.get() on a cache miss.
CACHE_MISS: Any = object()


class TTLCache:
    """Async-safe, dict-backed TTL cache.

    All public methods are coroutines so they can be awaited inside async
    code without blocking the event loop.  Internally the lock is an
    asyncio.Lock, so the cache is safe for concurrent async callers but is
    *not* safe across OS threads (which matches the project's async
    architecture).
    """

    def __init__(self, default_ttl: float = 300.0) -> None:
        """
        Args:
            default_ttl: Seconds before an entry expires. Default 5 minutes.
        """
        self._default_ttl = default_ttl
        # {key: (value, expires_at_monotonic)}
        self._store: dict[tuple, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(method: str, args: tuple, kwargs: dict) -> tuple:
        """Build a hashable cache key from a method name + call arguments."""
        frozen_kwargs = tuple(sorted(kwargs.items()))
        return (method, *args, frozen_kwargs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, method: str, args: tuple, kwargs: dict) -> Any:
        """Return the cached value, or ``CACHE_MISS`` if absent / expired."""
        key = self._make_key(method, args, kwargs)
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return CACHE_MISS
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                self._misses += 1
                return CACHE_MISS
            self._hits += 1
            return value

    async def set(
        self,
        method: str,
        args: tuple,
        kwargs: dict,
        value: Any,
        ttl: float | None = None,
    ) -> None:
        """Store *value* under the given key with an optional TTL override."""
        key = self._make_key(method, args, kwargs)
        expires_at = time.monotonic() + (ttl if ttl is not None else self._default_ttl)
        async with self._lock:
            self._store[key] = (value, expires_at)

    async def clear(self) -> None:
        """Evict all entries and reset hit/miss counters."""
        async with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, int | float]:
        """Return a snapshot of hit/miss counters and current cache size."""
        hits, misses = self._hits, self._misses
        total = hits + misses
        return {
            "hits": hits,
            "misses": misses,
            "total": total,
            "size": len(self._store),
            "hit_rate": round(hits / total, 3) if total else 0.0,
        }
