from __future__ import annotations

import asyncio
import os
import warnings
from datetime import date, timedelta

import pandas as pd
from fredapi import Fred

from data_providers.base import DataProvider
from data_providers.rate_limiter import AsyncRateLimiter


class FredProvider(DataProvider):
    """Macro data provider backed by FRED."""

    # Class-level limiter shared across all instances.
    # FRED API allows 120 req/min; 5/sec is a safe default.
    _limiter = AsyncRateLimiter(
        max_calls=int(os.getenv("FRED_RATE_LIMIT", "5")),
        period_seconds=1.0,
    )

    def __init__(self, api_key: str | None = None) -> None:
        resolved_key = api_key or os.getenv("FRED_API_KEY")
        self._api_key = resolved_key
        if not resolved_key:
            warnings.warn(
                "FRED_API_KEY not set. FredProvider will require mocks for data calls.",
                RuntimeWarning,
            )
            self._client: Fred | None = None
        else:
            self._client = Fred(api_key=resolved_key)

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        start = self._period_to_start(period)
        series = await self.get_series(ticker, start=start.isoformat(), end=None)
        data = series.to_frame(name="Close")
        data.index = pd.to_datetime(data.index)
        return data

    async def get_current_price(self, ticker: str) -> float:
        series = await self.get_series(ticker)
        series = series.dropna()
        if series.empty:
            raise ValueError(f"No FRED data returned for {ticker}.")
        return float(series.iloc[-1])

    async def get_series(
        self, series_id: str, start: str | None = None, end: str | None = None
    ) -> pd.Series:
        if self._client is None:
            raise RuntimeError("FRED API key missing. Unable to query series.")

        def _fetch() -> pd.Series:
            return self._client.get_series(series_id, observation_start=start, observation_end=end)

        async with self._limiter:
            return await asyncio.to_thread(_fetch)

    async def get_fed_funds_rate(self) -> pd.Series:
        return await self.get_series("FEDFUNDS")

    async def get_treasury_yield(self, maturity: str = "10y") -> pd.Series:
        mapping = {
            "2y": "DGS2",
            "5y": "DGS5",
            "10y": "DGS10",
            "30y": "DGS30",
        }
        series_id = mapping.get(maturity.lower())
        if not series_id:
            raise ValueError(f"Unsupported maturity '{maturity}'.")
        return await self.get_series(series_id)

    async def get_m2_money_supply(self) -> pd.Series:
        return await self.get_series("M2SL")

    async def get_cpi(self) -> pd.Series:
        return await self.get_series("CPIAUCSL")

    def is_point_in_time(self) -> bool:
        return True

    def supported_asset_types(self) -> list[str]:
        return ["macro"]

    def _period_to_start(self, period: str) -> date:
        period = period.lower()
        days = 365
        if period.endswith("y"):
            years = int(period[:-1])
            days = years * 365
        elif period.endswith("mo"):
            months = int(period[:-2])
            days = months * 30
        elif period.endswith("d"):
            days = int(period[:-1])
        return date.today() - timedelta(days=days)
