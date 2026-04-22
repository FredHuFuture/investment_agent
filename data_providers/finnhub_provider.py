"""Finnhub data provider for sector P/E and company metrics.

Free tier: 60 req/min, no daily cap. Non-commercial / solo-operator use.
API docs: https://finnhub.io/docs/api/

Security notes (T-03-01-01, T-03-01-06):
- API key is passed via httpx default_params (not logged separately).
- _api_key is a private attribute; never emitted via logger.
- Log lines use path-only, never full URL with token.
"""
from __future__ import annotations

import logging
import os
import statistics
import warnings
from typing import Any

import httpx
import pandas as pd

from data_providers.base import DataProvider
from data_providers.rate_limiter import AsyncRateLimiter

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

logger = logging.getLogger(__name__)

# Peer-basket proxy tickers for sector P/E derivation.
# Finnhub's free tier does not expose sector aggregates directly, so we compute
# the median P/E of 3-5 well-known constituents per sector.  Matches the
# sector keys in agents/fundamental.py::SECTOR_PE_MEDIANS.
_SECTOR_PROXY_TICKERS: dict[str, list[str]] = {
    "technology": ["AAPL", "MSFT", "GOOGL", "NVDA", "META"],
    "healthcare": ["JNJ", "UNH", "LLY", "MRK", "PFE"],
    "financial services": ["JPM", "BAC", "WFC", "GS", "MS"],
    "financials": ["JPM", "BAC", "WFC", "GS", "MS"],
    "consumer cyclical": ["AMZN", "TSLA", "HD", "NKE", "MCD"],
    "consumer defensive": ["WMT", "PG", "KO", "PEP", "COST"],
    "industrials": ["HON", "UNP", "CAT", "BA", "GE"],
    "energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "utilities": ["NEE", "DUK", "SO", "AEP", "D"],
    "real estate": ["PLD", "AMT", "CCI", "EQIX", "SPG"],
    "basic materials": ["LIN", "SHW", "APD", "ECL", "FCX"],
    "communication services": ["GOOGL", "META", "NFLX", "DIS", "VZ"],
}


class FinnhubProvider(DataProvider):
    """Finnhub data provider for sector P/E, company metrics, and current prices.

    Free tier: 60 req/min, no daily cap. Non-commercial use only (solo-operator OK).
    Sector P/E is derived by computing the median trailing P/E of a hardcoded peer
    basket per sector.  Price history (OHLCV) is not supported — use YFinanceProvider.

    Security (T-03-01-01): The ``token`` query parameter is set in the httpx client's
    default params and is never emitted in log lines.
    """

    # Class-level limiter shared across all instances (60 req/min free tier).
    _limiter = AsyncRateLimiter(
        max_calls=int(os.getenv("FINNHUB_RATE_LIMIT", "60")),
        period_seconds=60.0,
    )

    def __init__(self, api_key: str | None = None, timeout: float = 10.0) -> None:
        resolved_key = api_key or os.getenv("FINNHUB_API_KEY")
        self._api_key = resolved_key
        self._timeout = timeout
        if not resolved_key:
            warnings.warn(
                "FINNHUB_API_KEY not set. FinnhubProvider methods will raise RuntimeError.",
                RuntimeWarning,
                stacklevel=2,
            )
            self._client: httpx.AsyncClient | None = None
        else:
            # T-03-01-01: token in default params; httpx does not log params at INFO+.
            self._client = httpx.AsyncClient(
                base_url=FINNHUB_BASE_URL,
                params={"token": resolved_key},
                timeout=timeout,
            )

    async def _rate_limited_get(self, path: str, params: dict[str, Any]) -> dict:
        """Perform a rate-limited GET, returning {} on 429 and raising on other errors.

        Security (T-03-01-01): logs path only, never the full URL (which includes token).
        """
        if self._client is None:
            raise RuntimeError("Finnhub API key missing")
        async with self._limiter:
            try:
                resp = await self._client.get(path, params=params)
                resp.raise_for_status()
                result: dict = resp.json()
                return result
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    # T-03-01-03: accept DoS — log and return empty rather than raising
                    logger.warning("Finnhub rate limit hit for %s: %s", path, exc)
                    return {}
                raise

    async def get_company_pe(self, ticker: str) -> float | None:
        """Return TTM trailing P/E for a single ticker, or None if unavailable.

        Applies sanity filter: drops values <= 0 or > 1000 (T-03-01-02).
        Prefers ``peBasicExclExtraTTM``; falls back to ``peNormalizedAnnual``.
        """
        data = await self._rate_limited_get(
            "/stock/metric", {"symbol": ticker, "metric": "all"}
        )
        metric = data.get("metric") or {}
        pe = metric.get("peBasicExclExtraTTM") or metric.get("peNormalizedAnnual")
        if pe is None:
            return None
        try:
            pe_f = float(pe)
        except (TypeError, ValueError):
            return None
        # Sanity filter: negative earnings / extreme outliers (T-03-01-02)
        if pe_f <= 0 or pe_f > 1000:
            return None
        return pe_f

    async def get_sector_pe(self, sector: str | None) -> float | None:
        """Compute median P/E of a hardcoded peer basket for the sector.

        Returns None if fewer than 2 peers return valid P/E (the call site in
        sector_pe_cache.py falls back to static SECTOR_PE_MEDIANS).

        Defensive parsing (T-03-01-02): median(N>=2) requires consensus from multiple
        peers to reject a single poisoned response.
        """
        if not sector:
            return None
        key = sector.lower().strip()
        peers = _SECTOR_PROXY_TICKERS.get(key)
        if not peers:
            return None

        pes: list[float] = []
        for peer in peers:
            try:
                pe = await self.get_company_pe(peer)
            except RuntimeError:
                # Propagate key-missing error so callers can detect and fall back.
                raise
            except Exception as exc:
                logger.warning("Failed to get P/E for %s: %s", peer, exc)
                pe = None
            if pe is not None:
                pes.append(pe)

        if len(pes) < 2:
            return None
        return float(statistics.median(pes))

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        # Finnhub historical OHLCV is premium-tier only.
        # yfinance remains the OHLCV source; FinnhubProvider is metrics-only.
        raise NotImplementedError(
            "FinnhubProvider does not provide OHLCV data; use YFinanceProvider."
        )

    async def get_current_price(self, ticker: str) -> float:
        """Return the last traded price for a ticker via Finnhub /quote."""
        data = await self._rate_limited_get("/quote", {"symbol": ticker})
        price = data.get("c")
        if price is None:
            raise ValueError(f"No Finnhub current price for {ticker}")
        return float(price)

    def is_point_in_time(self) -> bool:
        """Return False — Finnhub returns current TTM data, not point-in-time."""
        return False

    def supported_asset_types(self) -> list[str]:
        """Return supported asset types for FinnhubProvider."""
        return ["stock"]

    async def aclose(self) -> None:
        """Close the underlying httpx client gracefully."""
        if self._client is not None:
            await self._client.aclose()
