from __future__ import annotations

import os

from data_providers.base import DataProvider
from data_providers.cached_provider import CachedFredProvider, CachedProvider
from data_providers.fred_provider import FredProvider
from data_providers.yfinance_provider import YFinanceProvider


def get_provider(asset_type: str, cached: bool | None = None) -> DataProvider:
    """Return the appropriate DataProvider for the given asset type.

    Phase 1: YFinanceProvider handles both stocks and crypto (BTC-USD, ETH-USD).
    Phase 2: CcxtProvider can be opted-in for exchange-specific features
    (funding rate, order book, etc.) via explicit CcxtProvider(exchange_id=...).

    Args:
        asset_type: One of ``"stock"``, ``"btc"``, ``"eth"``, ``"macro"``.
        cached: Whether to wrap the provider with TTL caching.  Defaults to
            ``True`` unless the environment variable
            ``INVESTMENT_AGENT_CACHE_DISABLED=1`` is set.
    """
    if cached is None:
        disabled = os.getenv("INVESTMENT_AGENT_CACHE_DISABLED", "").strip()
        cached = disabled not in ("1", "true", "yes")

    asset_type = asset_type.lower()
    if asset_type in {"stock", "btc", "eth"}:
        provider = YFinanceProvider()
        return CachedProvider(provider) if cached else provider
    if asset_type == "macro":
        provider = FredProvider()
        return CachedFredProvider(provider) if cached else provider
    raise ValueError(f"Unsupported asset_type: {asset_type}")
