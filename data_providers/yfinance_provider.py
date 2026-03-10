from __future__ import annotations

import asyncio
import threading
from typing import Any

import pandas as pd
import yfinance as yf

from data_providers.base import DataProvider

# yfinance is NOT thread-safe — concurrent yf.download() calls corrupt
# internal state (MultiIndex column handling). Serialize all downloads.
_yfinance_lock = threading.Lock()


class YFinanceProvider(DataProvider):
    """Data provider backed by yfinance. Supports stocks and crypto."""

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        def _download() -> pd.DataFrame:
            with _yfinance_lock:
                return yf.download(
                    ticker,
                    period=period,
                    interval=interval,
                    progress=False,
                    auto_adjust=False,
                )

        data = await asyncio.to_thread(_download)
        if data is None or data.empty:
            raise ValueError(f"No price history found for {ticker}.")

        if isinstance(data.columns, pd.MultiIndex):
            # yfinance 0.2+ returns MultiIndex: (PriceType, Ticker)
            # Level 0 = price types (Open, Close, High, Low, Volume, Adj Close)
            # Level 1 = ticker symbols (AAPL, BTC-USD, etc.)
            if ticker in data.columns.get_level_values(1):
                data = data.droplevel(1, axis=1)
            elif ticker in data.columns.get_level_values(0):
                data = data[ticker]
            else:
                data = data.droplevel(0, axis=1)

        rename_map = {col: str(col).title() for col in data.columns}
        data = data.rename(columns=rename_map)

        if "Adj Close" in data.columns:
            data = data.drop(columns=["Adj Close"])

        expected = ["Open", "High", "Low", "Close", "Volume"]
        missing = [col for col in expected if col not in data.columns]
        if missing:
            raise ValueError(f"Missing columns {missing} for {ticker}.")

        return data[expected]

    async def get_current_price(self, ticker: str) -> float:
        def _fetch() -> float:
            with _yfinance_lock:
                ticker_obj = yf.Ticker(ticker)
                fast_info = getattr(ticker_obj, "fast_info", None)
                if fast_info:
                    for key in ("lastPrice", "regularMarketPrice", "last_price"):
                        if key in fast_info and fast_info[key] is not None:
                            return float(fast_info[key])

                info: dict[str, Any] = ticker_obj.info or {}
                for key in (
                    "regularMarketPrice",
                    "currentPrice",
                    "previousClose",
                    "open",
                ):
                    value = info.get(key)
                    if value is not None:
                        return float(value)

                raise ValueError(f"Unable to determine current price for {ticker}.")

        return await asyncio.to_thread(_fetch)

    async def get_financials(self, ticker: str, period: str = "annual") -> dict:
        def _fetch() -> dict:
            with _yfinance_lock:
                ticker_obj = yf.Ticker(ticker)
                if period == "quarterly":
                    return {
                        "income_statement": ticker_obj.quarterly_financials,
                        "balance_sheet": ticker_obj.quarterly_balance_sheet,
                        "cash_flow": ticker_obj.quarterly_cashflow,
                    }
                return {
                    "income_statement": ticker_obj.financials,
                    "balance_sheet": ticker_obj.balance_sheet,
                    "cash_flow": ticker_obj.cashflow,
                }

        return await asyncio.to_thread(_fetch)

    async def get_key_stats(self, ticker: str) -> dict:
        def _fetch() -> dict:
            with _yfinance_lock:
                info = yf.Ticker(ticker).info or {}

            def _safe_float(value: Any) -> float | None:
                if value is None:
                    return None
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            return {
                "name": info.get("shortName") or info.get("longName"),
                "market_cap": _safe_float(info.get("marketCap")),
                "pe_ratio": _safe_float(info.get("trailingPE")),
                "forward_pe": _safe_float(info.get("forwardPE")),
                "beta": _safe_float(info.get("beta")),
                "dividend_yield": _safe_float(info.get("dividendYield")),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "52w_high": _safe_float(info.get("fiftyTwoWeekHigh")),
                "52w_low": _safe_float(info.get("fiftyTwoWeekLow")),
            }

        return await asyncio.to_thread(_fetch)

    def is_point_in_time(self) -> bool:
        return False

    def supported_asset_types(self) -> list[str]:
        return ["stock"]
