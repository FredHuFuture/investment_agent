from __future__ import annotations

from data_providers.base import DataProvider
from data_providers.ccxt_provider import CcxtProvider
from data_providers.fred_provider import FredProvider
from data_providers.yfinance_provider import YFinanceProvider


def get_provider(asset_type: str) -> DataProvider:
    asset_type = asset_type.lower()
    if asset_type == "stock":
        return YFinanceProvider()
    if asset_type in {"btc", "eth"}:
        return CcxtProvider()
    if asset_type == "macro":
        return FredProvider()
    raise ValueError(f"Unsupported asset_type: {asset_type}")
