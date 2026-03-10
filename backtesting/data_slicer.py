"""HistoricalDataProvider — serves windowed OHLCV data with no lookahead bias."""
from __future__ import annotations

from typing import Any

import pandas as pd

from data_providers.base import DataProvider


class HistoricalDataProvider(DataProvider):
    """Wraps a full OHLCV DataFrame, serves only data up to current_date.

    This prevents lookahead bias in backtesting by masking future data.
    """

    def __init__(
        self,
        full_data: pd.DataFrame,
        current_date: str,
        ticker_info: dict[str, Any] | None = None,
    ) -> None:
        self._full_data = full_data
        self._current_date = pd.Timestamp(current_date)
        self._ticker_info = ticker_info or {}

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        """Return only rows where index <= current_date (no lookahead)."""
        mask = self._full_data.index <= self._current_date
        sliced = self._full_data.loc[mask].copy()
        if sliced.empty:
            raise ValueError(
                f"No data available for {ticker} up to {self._current_date.date()}"
            )
        return sliced

    async def get_current_price(self, ticker: str) -> float:
        """Return Close price on current_date (or last available before it)."""
        mask = self._full_data.index <= self._current_date
        sliced = self._full_data.loc[mask]
        if sliced.empty:
            raise ValueError(
                f"No price available for {ticker} on {self._current_date.date()}"
            )
        return float(sliced.iloc[-1]["Close"])

    async def get_key_stats(self, ticker: str) -> dict[str, Any]:
        """Return static ticker info (not used for technical backtest)."""
        return self._ticker_info

    async def get_financials(self, ticker: str, period: str = "annual") -> dict:
        raise NotImplementedError(
            "Financials not available in backtest mode (non-PIT data)"
        )

    def is_point_in_time(self) -> bool:
        """Sliced to current_date, so it is PIT by construction."""
        return True

    def supported_asset_types(self) -> list[str]:
        return ["stock", "btc", "eth"]
