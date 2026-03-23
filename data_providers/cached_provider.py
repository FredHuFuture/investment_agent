from __future__ import annotations

import pandas as pd

from data_providers.base import DataProvider
from data_providers.cache import CACHE_MISS, TTLCache

_DEFAULT_TTL: float = 300.0   # 5 minutes — market data
_MACRO_TTL: float = 900.0     # 15 minutes — slowly-changing macro series


class CachedProvider(DataProvider):
    """Wraps any DataProvider and caches results with a TTL.

    Usage::

        raw = YFinanceProvider()
        provider = CachedProvider(raw)           # shares a new TTLCache
        # or inject a shared cache instance:
        provider = CachedProvider(raw, cache=shared_cache)
    """

    def __init__(
        self,
        provider: DataProvider,
        cache: TTLCache | None = None,
    ) -> None:
        self._provider = provider
        self._cache = cache or TTLCache(default_ttl=_DEFAULT_TTL)

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
        # Defensive copy: DataFrames are mutable; callers must not corrupt
        # the cached object.
        result: pd.DataFrame = await self._cached(
            "get_price_history", (ticker, period, interval), {}
        )
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
