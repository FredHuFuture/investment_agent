from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

import ccxt.async_support as ccxt

from data_providers.base import DataProvider


class CcxtProvider(DataProvider):
    """Crypto data provider backed by ccxt async exchanges."""

    def __init__(self, exchange_id: str = "binance") -> None:
        exchange_class = getattr(ccxt, exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Unknown exchange id: {exchange_id}")
        self.exchange = exchange_class({"enableRateLimit": True})

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        symbol = self._normalize_symbol(ticker)
        since = self._period_to_since(period)
        timeframe = self._normalize_interval(interval)

        ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since)
        if not ohlcv:
            raise ValueError(f"No OHLCV data returned for {symbol}.")

        data = pd.DataFrame(
            ohlcv, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"]
        )
        data["Timestamp"] = pd.to_datetime(data["Timestamp"], unit="ms", utc=True)
        data = data.set_index("Timestamp")
        return data[["Open", "High", "Low", "Close", "Volume"]]

    async def get_current_price(self, ticker: str) -> float:
        symbol = self._normalize_symbol(ticker)
        ticker_data: dict[str, Any] = await self.exchange.fetch_ticker(symbol)
        for key in ("last", "close", "bid", "ask"):
            value = ticker_data.get(key)
            if value is not None:
                return float(value)
        raise ValueError(f"Unable to determine current price for {symbol}.")

    async def get_funding_rate(self, ticker: str) -> float | None:
        if not hasattr(self.exchange, "fetch_funding_rate"):
            return None
        symbol = self._normalize_symbol(ticker)
        try:
            data = await self.exchange.fetch_funding_rate(symbol)
        except Exception:
            return None
        if data is None:
            return None
        rate = data.get("fundingRate") if isinstance(data, dict) else None
        return float(rate) if rate is not None else None

    def is_point_in_time(self) -> bool:
        return True

    def supported_asset_types(self) -> list[str]:
        return ["btc", "eth"]

    async def close(self) -> None:
        if self.exchange is not None:
            await self.exchange.close()

    def _normalize_symbol(self, ticker: str) -> str:
        if "/" in ticker:
            return ticker
        ticker_upper = ticker.upper()
        if ticker_upper in {"BTC", "ETH"}:
            return f"{ticker_upper}/USDT"
        return f"{ticker_upper}/USDT"

    def _normalize_interval(self, interval: str) -> str:
        return interval

    def _period_to_since(self, period: str) -> int:
        now = datetime.now(timezone.utc)
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

        since = now - timedelta(days=days)
        return int(since.timestamp() * 1000)
