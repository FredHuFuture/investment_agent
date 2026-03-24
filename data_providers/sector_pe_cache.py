"""Cached sector P/E median lookup using sector ETF proxies.

Falls back to static estimates when live data is unavailable.
"""

from __future__ import annotations

import time
from typing import Any

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

# Module-level cache: {sector_lower: (pe_value, monotonic_timestamp)}
_cache: dict[str, tuple[float, float]] = {}
_TTL: float = 86400.0  # 24 hours


async def get_sector_pe_median(
    sector: str | None,
    provider: Any | None = None,
) -> float | None:
    """Return trailing P/E median for *sector*.

    Tries the live ETF lookup first (cached 24 h), then falls back to
    the static table.

    Args:
        sector: Sector name (case-insensitive).  ``None`` → ``None``.
        provider: A DataProvider with ``get_key_stats``; if *None* or fetch
            fails, the static fallback is used.
    """
    if sector is None:
        return None

    key = sector.lower()
    now = time.monotonic()

    # Check cache
    if key in _cache:
        pe, ts = _cache[key]
        if now - ts < _TTL:
            return pe

    # Try live fetch
    if provider is not None:
        etf = SECTOR_ETFS.get(key)
        if etf is not None:
            try:
                stats = await provider.get_key_stats(etf)
                pe = stats.get("pe_ratio")
                if pe is not None and isinstance(pe, (int, float)) and pe > 0:
                    _cache[key] = (float(pe), now)
                    return float(pe)
            except Exception:
                pass

    # Fallback
    return STATIC_SECTOR_PE.get(key)
