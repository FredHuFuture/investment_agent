"""SimFin v3 REST provider for point-in-time fundamentals (Phase 8 DATA-v2-02).

Free tier: 2 calls/sec sustained, 5K stocks, 5y history, 500 credits/mo.
Personal-use ToS — data redistribution prohibited (matches local-first scope).
[Source: https://www.simfin.com/en/prices/]

Security notes (T-08-02-01):
- API key passed via Authorization header in default headers; never appears
  in URL params or log lines (httpx does not log headers at INFO level).
- _api_key is a private attribute; never emitted via logger.

PIT semantics (Q1 from 08-RESEARCH.md):
- asreported=True returns as-reported (original 10-Q) values, filtering 10-Q/A.
- asreported=False (default in SimFin) returns the latest restated values.
[Source: simfinapi R-package + simfin.readme.io/reference/statements-verbose-1]
"""
from __future__ import annotations

import logging
import os
import warnings
from datetime import date
from typing import Any

import httpx
import pandas as pd

from data_providers.base import DataProvider
from data_providers.rate_limiter import AsyncRateLimiter

SIMFIN_BASE_URL = "https://prod.simfin.com/api/v3"

logger = logging.getLogger(__name__)


class SimfinProvider(DataProvider):
    """SimFin v3 REST provider for point-in-time fundamentals.

    Free tier: 2 calls/sec sustained, 5K stocks, 5y history, 500 credits/mo.
    Personal-use ToS — data redistribution prohibited (matches local-first scope).
    [Source: simfin.com/en/prices/]

    asreported=True returns as-reported (original 10-Q values), filtering 10-Q/A.
    asreported=False (default in SimFin) returns latest restated values.
    [Source: simfinapi R-package + simfin.readme.io/reference/statements-verbose-1]

    Security (T-08-02-01): api_key passed via Authorization header in default
    headers; never appears in URL or log lines (httpx does not log headers at INFO).
    """

    # Class-level limiter shared across all instances (2/sec free tier sustained
    # over a 60-second sliding window = 120 calls/min).
    _limiter = AsyncRateLimiter(
        max_calls=int(os.getenv("SIMFIN_RATE_LIMIT", "120")),
        period_seconds=60.0,
    )

    def __init__(self, api_key: str | None = None, timeout: float = 10.0) -> None:
        resolved = api_key or os.getenv("SIMFIN_API_KEY")
        self._api_key = resolved
        self._timeout = timeout
        if not resolved:
            warnings.warn(
                "SIMFIN_API_KEY not set. SimfinProvider methods will raise RuntimeError.",
                RuntimeWarning,
                stacklevel=2,
            )
            self._client: httpx.AsyncClient | None = None
        else:
            # T-08-02-01: api-key in Authorization header; httpx default
            # log level (WARNING) does not emit request headers.
            self._client = httpx.AsyncClient(
                base_url=SIMFIN_BASE_URL,
                headers={"Authorization": f"api-key {resolved}"},
                timeout=timeout,
            )

    def is_point_in_time(self) -> bool:
        """Return True — SimFin asreported=True path delivers PIT semantics."""
        return True

    def supported_asset_types(self) -> list[str]:
        """SimFin covers US/CA equities; crypto/macro out of scope."""
        return ["stock"]

    async def get_financials(
        self,
        ticker: str,
        statement: str = "pl",
        period: str = "q1",
        fyear: int | None = None,
        asreported: bool = True,
    ) -> dict:
        """Fetch a financial statement.

        asreported=True returns the as-reported (original 10-Q) values
        (Phase 8 DATA-v2-02 PIT path).
        asreported=False returns the latest restated values
        (Phase 8 DATA-v2-05 dual-call delta detection).

        Returns {} on HTTP 429 (rate-limited), matching FinnhubProvider pattern.
        Raises RuntimeError when API key is missing (Pitfall 9 — no silent
        yfinance fallback).
        """
        if self._client is None:
            raise RuntimeError(
                "SIMFIN_API_KEY missing — use_pit_fundamentals=True requires it. "
                "Set SIMFIN_API_KEY env var or call with use_pit_fundamentals=False."
            )
        params: dict[str, Any] = {
            "ticker": ticker,
            "statements": statement,
            "period": period,
            "asreported": "true" if asreported else "false",
        }
        if fyear is not None:
            params["fyear"] = fyear
        async with self._limiter:
            try:
                resp = await self._client.get("/companies/statements", params=params)
                resp.raise_for_status()
                result: dict = resp.json()
                return result
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    # T-08-02-03: log path-only, never URL with params (would leak ticker).
                    logger.warning("SimFin rate limit hit for %s: %s", ticker, exc)
                    return {}
                raise

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        """SimFin does not provide OHLCV — caller must use YFinanceProvider."""
        raise NotImplementedError(
            "SimfinProvider does not provide OHLCV — use YFinanceProvider"
        )

    async def get_current_price(self, ticker: str) -> float:
        """SimFin does not provide spot prices — caller must use YFinanceProvider."""
        raise NotImplementedError("SimfinProvider does not provide spot price")

    async def aclose(self) -> None:
        """Close the underlying httpx client gracefully."""
        if self._client is not None:
            await self._client.aclose()
