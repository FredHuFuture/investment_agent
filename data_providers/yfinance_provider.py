from __future__ import annotations

import asyncio
import os
import threading
from typing import Any

import pandas as pd
import yfinance as yf

from data_providers.base import DataProvider
from data_providers.rate_limiter import AsyncRateLimiter

# yfinance is NOT thread-safe — concurrent yf.download() calls corrupt
# internal state (MultiIndex column handling). Serialize all downloads.
_yfinance_lock = threading.Lock()


class YFinanceProvider(DataProvider):
    """Data provider backed by yfinance. Supports stocks and crypto."""

    # Class-level limiter so all instances share the same call budget.
    # Yahoo Finance throttles aggressively; 2 calls/second is conservative.
    _limiter = AsyncRateLimiter(
        max_calls=int(os.getenv("YFINANCE_RATE_LIMIT", "2")),
        period_seconds=1.0,
    )

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

        async with self._limiter:
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

        async with self._limiter:
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

        async with self._limiter:
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
                "pegRatio": _safe_float(info.get("pegRatio")),
                "earningsGrowth": _safe_float(info.get("earningsGrowth")),
                "recommendationMean": _safe_float(info.get("recommendationMean")),
            }

        async with self._limiter:
            return await asyncio.to_thread(_fetch)

    async def get_price_history_batch(
        self,
        tickers: list[str],
        period: str = "1y",
        interval: str = "1d",
    ) -> dict[str, pd.DataFrame]:
        """Batch OHLCV download for multiple tickers in a single yfinance.download() call.

        Uses yfinance's built-in thread pool (threads=True) which is safe when called
        with a list. This bypasses the per-ticker _yfinance_lock serialization.

        Returns a dict keyed by ticker. A ticker with no data maps to an empty DataFrame
        with the expected OHLCV columns (not a missing key, not a raise).
        """
        if not tickers:
            raise ValueError("tickers must be non-empty")

        def _download() -> pd.DataFrame:
            # NOTE: no _yfinance_lock here. yf.download with list+threads=True is safe.
            return yf.download(
                tickers=tickers,
                period=period,
                interval=interval,
                group_by="ticker",
                progress=False,
                auto_adjust=False,
                threads=True,
            )

        async with self._limiter:
            raw = await asyncio.to_thread(_download)

        expected = ["Open", "High", "Low", "Close", "Volume"]

        if raw is None or raw.empty:
            # Yield empty frames for each requested ticker so callers don't KeyError
            empty = pd.DataFrame(columns=expected)
            return {t: empty.copy() for t in tickers}

        result: dict[str, pd.DataFrame] = {}

        if isinstance(raw.columns, pd.MultiIndex):
            # group_by="ticker" yields MultiIndex (ticker, price_type)
            for t in tickers:
                if t in raw.columns.get_level_values(0):
                    df = raw[t].copy()
                elif t in raw.columns.get_level_values(1):
                    df = raw.xs(t, level=1, axis=1).copy()
                else:
                    result[t] = pd.DataFrame(columns=expected)
                    continue
                df = df.rename(columns={c: str(c).title() for c in df.columns})
                if "Adj Close" in df.columns:
                    df = df.drop(columns=["Adj Close"])
                # Ensure all expected columns exist; fill missing with NaN
                for col in expected:
                    if col not in df.columns:
                        df[col] = pd.NA
                result[t] = df[expected]
        else:
            # Single-ticker path (yfinance may flatten for len==1)
            df = raw.rename(columns={c: str(c).title() for c in raw.columns})
            if "Adj Close" in df.columns:
                df = df.drop(columns=["Adj Close"])
            for col in expected:
                if col not in df.columns:
                    df[col] = pd.NA
            result[tickers[0]] = df[expected]
            for t in tickers[1:]:
                result[t] = pd.DataFrame(columns=expected)

        # Drop rows where all OHLCV are NaN (yfinance pads missing dates across tickers)
        for t in list(result.keys()):
            result[t] = result[t].dropna(how="all")
        return result

    async def get_dividends(self, ticker: str) -> list[tuple]:
        """Fetch historical dividend payments as (ex_date, amount_per_share) pairs (AN-01).

        Returns a list of ``(datetime.date, float)`` tuples sorted by date ascending.
        Returns ``[]`` for non-dividend-paying tickers or on fetch error.

        Uses ``yfinance.Ticker.dividends`` which returns split-adjusted amounts.
        Wrapped in ``_yfinance_lock`` (thread-safety) and ``_limiter`` (rate limit).
        """
        from datetime import date as _date

        def _fetch() -> pd.Series:
            with _yfinance_lock:
                t = yf.Ticker(ticker)
                return t.dividends  # DatetimeIndex series, float values

        try:
            async with self._limiter:
                series = await asyncio.to_thread(_fetch)
        except Exception:
            return []

        if series is None or series.empty:
            return []

        result: list[tuple] = []
        for idx, amount in series.items():
            try:
                ex_date: _date = idx.date() if hasattr(idx, "date") else idx
                result.append((ex_date, float(amount)))
            except (AttributeError, ValueError, TypeError):
                continue

        return sorted(result, key=lambda x: x[0])

    def is_point_in_time(self) -> bool:
        return False

    def supported_asset_types(self) -> list[str]:
        return ["stock"]
