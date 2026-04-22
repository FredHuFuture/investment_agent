"""SEC EDGAR Form 4 insider-transaction provider (DATA-03).

Public-domain data via the ``edgartools`` library (Apache 2.0).
Rate limited to 10 req/s per SEC courtesy policy.

Note: edgartools API is synchronous; all calls are wrapped in
``asyncio.to_thread`` to avoid blocking the async event loop.

Environment variables:
  EDGAR_USER_AGENT  — Identifies the operator to SEC (required by policy).
                      Defaults to "Investment Agent solo-operator@localhost"
                      which SEC accepts for low-volume non-commercial use.
  EDGAR_RATE_LIMIT  — Max requests per second (default: 10).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, timedelta
from typing import Any

from data_providers.rate_limiter import AsyncRateLimiter

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = "Investment Agent solo-operator@localhost"

# Transaction codes that count toward open-market buy/sell counts.
# Source: SEC Form 4 / Form 5 transaction code reference.
_BUY_CODE = "P"   # Open-market purchase
_SELL_CODE = "S"  # Open-market sale
# Excluded: A (award/grant), M (option exercise), G (gift),
#           D (return-to-issuer), F (tax withholding), etc.

_MIN_TRANSACTIONS_FOR_SIGNAL = 3


class EdgarProvider:
    """SEC EDGAR data provider — Form 4 insider transactions.

    Does not implement the full ``DataProvider`` interface; this is a
    specialised auxiliary provider injected directly into ``FundamentalAgent``
    (not exposed via the factory pattern).

    The edgartools library is imported lazily at construction time.  If the
    library is absent ``get_insider_transactions`` returns ``None`` immediately
    so ``FundamentalAgent`` can continue with the remaining signal components.

    Rate limiting: class-level ``AsyncRateLimiter`` shared across all instances
    enforces the SEC courtesy limit of ≤10 req/s.
    """

    # Class-level rate limiter — shared across all EdgarProvider instances
    # to stay within the SEC courtesy limit of 10 req/s.
    _limiter = AsyncRateLimiter(
        max_calls=int(os.getenv("EDGAR_RATE_LIMIT", "10")),
        period_seconds=1.0,
    )

    def __init__(self, user_agent: str | None = None) -> None:
        self._user_agent: str = user_agent or os.getenv(
            "EDGAR_USER_AGENT", _DEFAULT_USER_AGENT
        )
        self._edgar_module: Any = None
        try:
            import edgar as _edgar  # type: ignore[import-not-found]

            _edgar.set_identity(self._user_agent)
            self._edgar_module = _edgar
        except ImportError:
            logger.warning(
                "edgartools not installed; EdgarProvider will return None. "
                "Install with: pip install edgartools>=3.0"
            )
        except Exception as exc:
            logger.warning("edgartools initialisation failed: %s", exc)

    async def get_insider_transactions(
        self, ticker: str, since_days: int = 90
    ) -> dict[str, Any] | None:
        """Fetch Form 4 insider transactions for ``ticker`` in the trailing window.

        Returns a dict::

            {
                "transaction_count": int,    # all tx rows seen (any code)
                "buys_shares":       int,    # sum of P-code shares
                "sells_shares":      int,    # sum of S-code shares
                "net_buy_ratio":     float | None,  # buys / (buys + sells)
                "since_days":        int,
            }

        Returns ``None`` when edgartools is unavailable or the fetch fails,
        so the caller can treat the signal as absent rather than crashing.
        """
        if self._edgar_module is None:
            return None

        def _fetch() -> dict[str, Any] | None:
            try:
                Company = self._edgar_module.Company
                company = Company(ticker)
                since = date.today() - timedelta(days=since_days)
                filings = company.get_filings(
                    form="4", filing_date=f"{since.isoformat()}:"
                )
                tx_count = 0
                buys = 0
                sells = 0
                for f in filings:
                    try:
                        obj = f.obj()
                        txs = getattr(obj, "non_derivative_transactions", None) or []
                        for tx in txs:
                            tx_count += 1
                            code = getattr(tx, "transaction_code", None) or ""
                            raw_shares = getattr(tx, "shares", None) or 0
                            try:
                                shares_int = int(float(raw_shares))
                            except (TypeError, ValueError):
                                continue
                            if code == _BUY_CODE:
                                buys += shares_int
                            elif code == _SELL_CODE:
                                sells += shares_int
                    except Exception as per_filing_exc:
                        logger.debug(
                            "Skipping filing for %s: %s", ticker, per_filing_exc
                        )
                        continue

                denom = buys + sells
                ratio: float | None = buys / denom if denom > 0 else None
                return {
                    "transaction_count": tx_count,
                    "buys_shares": buys,
                    "sells_shares": sells,
                    "net_buy_ratio": ratio,
                    "since_days": since_days,
                }
            except Exception as exc:
                logger.info("Edgar fetch failed for %s: %s", ticker, exc)
                return None

        async with self._limiter:
            return await asyncio.to_thread(_fetch)
