from __future__ import annotations

import asyncio

import pytest

from data_providers.cached_provider import CachedFredProvider, CachedProvider
from data_providers.ccxt_provider import CcxtProvider
from data_providers.factory import get_provider
from data_providers.fred_provider import FredProvider
from data_providers.yfinance_provider import YFinanceProvider


def test_factory_returns_correct_types() -> None:
    # With caching disabled, raw providers are returned.
    assert isinstance(get_provider("stock", cached=False), YFinanceProvider)
    assert isinstance(get_provider("btc", cached=False), YFinanceProvider)
    assert isinstance(get_provider("eth", cached=False), YFinanceProvider)
    assert isinstance(get_provider("macro", cached=False), FredProvider)
    with pytest.raises(ValueError):
        get_provider("unknown")


def test_factory_returns_cached_providers_by_default() -> None:
    assert isinstance(get_provider("stock"), CachedProvider)
    assert isinstance(get_provider("macro"), CachedFredProvider)
    # The wrapped provider should still satisfy the DataProvider interface.
    assert get_provider("stock").supported_asset_types() == ["stock"]


def test_is_point_in_time() -> None:
    assert YFinanceProvider().is_point_in_time() is False
    assert CcxtProvider().is_point_in_time() is True
    assert FredProvider(api_key="test").is_point_in_time() is True


def test_supported_asset_types() -> None:
    assert YFinanceProvider().supported_asset_types() == ["stock"]
    assert CcxtProvider().supported_asset_types() == ["btc", "eth"]
    assert FredProvider(api_key="test").supported_asset_types() == ["macro"]


@pytest.mark.network
def test_yfinance_get_price_history() -> None:
    provider = YFinanceProvider()

    try:
        data = asyncio.run(provider.get_price_history("AAPL", period="5d"))
    except Exception as exc:  # pragma: no cover - network guard
        pytest.skip(f"Network unavailable for yfinance: {exc}")

    assert not data.empty
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        assert col in data.columns


@pytest.mark.network
def test_yfinance_get_current_price() -> None:
    provider = YFinanceProvider()

    try:
        price = asyncio.run(provider.get_current_price("AAPL"))
    except Exception as exc:  # pragma: no cover - network guard
        pytest.skip(f"Network unavailable for yfinance: {exc}")

    assert isinstance(price, float)
    assert price > 0


@pytest.mark.network
def test_yfinance_get_key_stats() -> None:
    provider = YFinanceProvider()

    try:
        stats = asyncio.run(provider.get_key_stats("AAPL"))
    except Exception as exc:  # pragma: no cover - network guard
        pytest.skip(f"Network unavailable for yfinance: {exc}")

    assert "market_cap" in stats
    assert "sector" in stats


@pytest.mark.network
def test_ccxt_provider_interface() -> None:
    provider = CcxtProvider()
    try:
        price = asyncio.run(provider.get_current_price("BTC"))
    except Exception as exc:  # pragma: no cover - network guard
        asyncio.run(provider.close())
        pytest.skip(f"Network unavailable for ccxt: {exc}")
    else:
        assert isinstance(price, float)
        assert price > 0
        asyncio.run(provider.close())


def test_fred_provider_no_key_graceful(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    provider = FredProvider(api_key=None)

    with pytest.raises(RuntimeError):
        asyncio.run(provider.get_series("DGS10"))
