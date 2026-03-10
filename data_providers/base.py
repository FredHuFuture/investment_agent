from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class DataProvider(ABC):
    """Abstract data source interface."""

    @abstractmethod
    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        """Return OHLCV DataFrame."""

    @abstractmethod
    async def get_current_price(self, ticker: str) -> float:
        """Return latest price."""

    async def get_financials(self, ticker: str, period: str = "annual") -> dict:
        """Return financial statements for equities."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support financials."
        )

    async def get_key_stats(self, ticker: str) -> dict:
        """Return key statistics."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support key_stats."
        )

    @abstractmethod
    def is_point_in_time(self) -> bool:
        """Whether data is point-in-time for backtests."""

    @abstractmethod
    def supported_asset_types(self) -> list[str]:
        """Return supported asset types."""
