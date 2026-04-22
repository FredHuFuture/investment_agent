"""Cached sector P/E median lookup.

Priority order:
1. Finnhub peer-basket median (when FINNHUB_API_KEY is set) — live, cached 24h
2. yfinance sector ETF trailing P/E — live, cached 24h
3. Static STATIC_SECTOR_PE table — always available

A sibling function ``get_sector_pe_source()`` returns the data source used for
the most recent cached value so ``agents/fundamental.py`` can embed the source
in its reasoning string.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# Static fallback — same values as the original hardcoded SECTOR_PE_MEDIANS
STATIC_SECTOR_PE: dict[str, float] = {
    "technology": 28.0,
    "healthcare": 22.0,
    "financial services": 13.0,
    "financials": 13.0,
    "consumer cyclical": 20.0,
    "consumer defensive": 22.0,
    "industrials": 20.0,
    "energy": 12.0,
    "utilities": 17.0,
    "real estate": 35.0,
    "basic materials": 15.0,
    "communication services": 18.0,
}

# Sector ETF tickers whose trailing P/E approximates the sector median
SECTOR_ETFS: dict[str, str] = {
    "technology": "XLK",
    "healthcare": "XLV",
    "financial services": "XLF",
    "financials": "XLF",
    "consumer cyclical": "XLY",
    "consumer defensive": "XLP",
    "industrials": "XLI",
    "energy": "XLE",
    "utilities": "XLU",
    "real estate": "XLRE",
    "basic materials": "XLB",
    "communication services": "XLC",
}

# Module-level caches:
#   _cache:        {sector_lower: (pe_value, monotonic_timestamp)}
#   _source_cache: {sector_lower: source_string}  ("finnhub" | "yfinance" | "static")
_cache: dict[str, tuple[float, float]] = {}
_source_cache: dict[str, str] = {}
_TTL: float = 86400.0  # 24 hours (>= 1 hour requirement satisfied)

# Lazily-created FinnhubProvider instance (reused across calls).
# Set to None when FINNHUB_API_KEY is absent or FinnhubProvider construction fails.
_finnhub_provider: Any | None = None


def _get_finnhub_provider() -> Any | None:
    """Return a shared FinnhubProvider if FINNHUB_API_KEY is set, else None."""
    global _finnhub_provider
    if _finnhub_provider is None and os.getenv("FINNHUB_API_KEY"):
        try:
            from data_providers.finnhub_provider import FinnhubProvider
            _finnhub_provider = FinnhubProvider()
        except Exception as exc:
            logger.warning("Failed to create FinnhubProvider: %s", exc)
    return _finnhub_provider


async def get_sector_pe_median(
    sector: str | None,
    provider: Any | None = None,
) -> float | None:
    """Return trailing P/E median for *sector*.

    Priority:
    1. Finnhub peer-basket (when FINNHUB_API_KEY is set) — cached 24h
    2. yfinance sector ETF (when *provider* supplied) — cached 24h
    3. Static STATIC_SECTOR_PE table

    Args:
        sector: Sector name (case-insensitive).  ``None`` → ``None``.
        provider: A DataProvider with ``get_key_stats``; used for yfinance fallback.
            If *None* or fetch fails, falls through to static table.

    Returns:
        Trailing P/E median as float, or None if sector is unrecognised.
    """
    if sector is None:
        return None

    key = sector.lower()
    now = time.monotonic()

    # Check TTL cache (shared by all sources)
    if key in _cache:
        pe, ts = _cache[key]
        if now - ts < _TTL:
            return pe

    # --- Priority 1: Finnhub live peer-basket ---
    finnhub = _get_finnhub_provider()
    if finnhub is not None:
        try:
            pe = await finnhub.get_sector_pe(sector)
            if pe is not None:
                _cache[key] = (pe, now)
                _source_cache[key] = "finnhub"
                return pe
        except Exception as exc:
            logger.warning("Finnhub sector P/E lookup failed, falling back: %s", exc)

    # --- Priority 2: yfinance sector ETF ---
    if provider is not None:
        etf = SECTOR_ETFS.get(key)
        if etf is not None:
            try:
                stats = await provider.get_key_stats(etf)
                pe = stats.get("pe_ratio")
                if pe is not None and isinstance(pe, (int, float)) and pe > 0:
                    _cache[key] = (float(pe), now)
                    _source_cache[key] = "yfinance"
                    return float(pe)
            except Exception:
                pass

    # --- Priority 3: Static fallback ---
    static_pe = STATIC_SECTOR_PE.get(key)
    if static_pe is not None:
        _source_cache[key] = "static"
    return static_pe


async def get_sector_pe_source(sector: str | None) -> str:
    """Return the data source used for the most recently cached sector P/E.

    This is a sibling to ``get_sector_pe_median`` and MUST be called after it
    (or in the same call site) so the source cache is populated.

    Returns:
        One of ``"finnhub"``, ``"yfinance"``, or ``"static"``.
        Falls back to ``"static"`` for unrecognised sectors.
    """
    if sector is None:
        return "static"
    key = sector.lower()
    return _source_cache.get(key, "static")
