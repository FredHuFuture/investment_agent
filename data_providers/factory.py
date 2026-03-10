from __future__ import annotations

from data_providers.base import DataProvider
from data_providers.fred_provider import FredProvider
from data_providers.yfinance_provider import YFinanceProvider


def get_provider(asset_type: str) -> DataProvider:
    """Return the appropriate DataProvider for the given asset type.

    Phase 1: YFinanceProvider handles both stocks and crypto (BTC-USD, ETH-USD).
    Phase 2: CcxtProvider can be opted-in for exchange-specific features
    (funding rate, order book, etc.) via explicit CcxtProvider(exchange_id=...).
    """
    asset_type = asset_type.lower()
    if asset_type in {"stock", "btc", "eth"}:
        return YFinanceProvider()
    if asset_type == "macro":
        return FredProvider()
    raise ValueError(f"Unsupported asset_type: {asset_type}")
