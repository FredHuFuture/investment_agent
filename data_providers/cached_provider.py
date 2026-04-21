from __future__ import annotations

import logging

import pandas as pd

from data_providers.base import DataProvider
from data_providers.cache import CACHE_MISS, TTLCache
from data_providers.parquet_cache import ParquetOHLCVCache

_DEFAULT_TTL: float = 300.0   # 5 minutes — market data
_MACRO_TTL: float = 900.0     # 15 minutes — slowly-changing macro series

logger = logging.getLogger(__name__)


class CachedProvider(DataProvider):
    """Wraps any DataProvider and caches results with a TTL.

    Usage::

        raw = YFinanceProvider()
        provider = CachedProvider(raw)           # shares a new TTLCache
        # or inject a shared cache instance:
        provider = CachedProvider(raw, cache=shared_cache)
        # with Parquet disk cache for OHLCV:
        provider = CachedProvider(raw, parquet_cache=ParquetOHLCVCache())
    """

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

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    async def _cached(
        self,
        method: str,
        args: tuple,
        kwargs: dict,
        ttl: float | None = None,
    ):
        result = await self._cache.get(method, args, kwargs)
        if result is CACHE_MISS:
            result = await getattr(self._provider, method)(*args, **kwargs)
            await self._cache.set(method, args, kwargs, result, ttl)
        return result

    # ------------------------------------------------------------------
    # DataProvider interface
    # ------------------------------------------------------------------

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        # Parquet read-through: only if enabled AND key is present within TTL
        if self._parquet_cache is not None:
            key = (ticker, period, interval)
            cached = self._parquet_cache.read(key, ttl=self._parquet_ttl)
            if cached is not None and not cached.empty:
                # Prime in-memory TTLCache so sibling calls in same process hit RAM
                await self._cache.set(
                    "get_price_history", (ticker, period, interval), {}, cached.copy()
                )
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
                logger.warning("Parquet write failed for %s: %s", ticker, exc)

        return result.copy()

    async def get_current_price(self, ticker: str) -> float:
        return await self._cached("get_current_price", (ticker,), {})

    async def get_financials(self, ticker: str, period: str = "annual") -> dict:
        return await self._cached("get_financials", (ticker, period), {})

    async def get_key_stats(self, ticker: str) -> dict:
        return await self._cached("get_key_stats", (ticker,), {})

    def is_point_in_time(self) -> bool:
        return self._provider.is_point_in_time()

    def supported_asset_types(self) -> list[str]:
        return self._provider.supported_asset_types()

    # ------------------------------------------------------------------
    # Cache introspection
    # ------------------------------------------------------------------

    @property
    def cache(self) -> TTLCache:
        return self._cache


class CachedFredProvider(CachedProvider):
    """CachedProvider extended with cached versions of FRED-specific methods.

    FRED macro series change at most daily, so they use a longer TTL
    (``_MACRO_TTL``, 15 minutes) to minimise redundant API calls during
    batch daemon runs.
    """

    async def get_series(
        self,
        series_id: str,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.Series:
        result: pd.Series = await self._cached(
            "get_series", (series_id, start, end), {}, ttl=_MACRO_TTL
        )
        return result.copy()

    async def get_fed_funds_rate(self) -> pd.Series:
        result: pd.Series = await self._cached(
            "get_fed_funds_rate", (), {}, ttl=_MACRO_TTL
        )
        return result.copy()

    async def get_treasury_yield(self, maturity: str = "10y") -> pd.Series:
        result: pd.Series = await self._cached(
            "get_treasury_yield", (maturity,), {}, ttl=_MACRO_TTL
        )
        return result.copy()

    async def get_m2_money_supply(self) -> pd.Series:
        result: pd.Series = await self._cached(
            "get_m2_money_supply", (), {}, ttl=_MACRO_TTL
        )
        return result.copy()

    async def get_cpi(self) -> pd.Series:
        result: pd.Series = await self._cached(
            "get_cpi", (), {}, ttl=_MACRO_TTL
        )
        return result.copy()
