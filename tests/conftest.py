"""Shared pytest fixtures for the investment_agent test suite.

WR-02 fix: autouse fixture that resets module-level globals in
data_providers.sector_pe_cache before and after every test.

Without this reset, a test that calls get_sector_pe_median() (directly or via
FundamentalAgent.analyze) with FINNHUB_API_KEY set will leave a live
FinnhubProvider instance in _finnhub_provider, which then leaks into subsequent
tests in the same process.  The reset is idempotent: if the module has never
been imported the import inside the fixture is a no-op.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_sector_pe_cache() -> None:  # type: ignore[return]
    """Clear sector_pe_cache module-level state before and after each test.

    Resets:
      - _cache          : TTL-keyed PE values
      - _source_cache   : source label per sector key
      - _finnhub_provider: lazily-created singleton (prevents cross-test leak)
    """
    from data_providers import sector_pe_cache

    sector_pe_cache._cache.clear()
    sector_pe_cache._source_cache.clear()
    sector_pe_cache._finnhub_provider = None

    yield

    sector_pe_cache._cache.clear()
    sector_pe_cache._source_cache.clear()
    sector_pe_cache._finnhub_provider = None
