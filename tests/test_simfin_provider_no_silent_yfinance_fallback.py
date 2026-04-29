from __future__ import annotations
import importlib.util
import pytest

SIMFIN_AVAILABLE = importlib.util.find_spec("data_providers.simfin_provider") is not None


@pytest.mark.skipif(
    not SIMFIN_AVAILABLE,
    reason="SimfinProvider lands in 08-02; tripwire arms once import succeeds",
)
@pytest.mark.asyncio
async def test_no_silent_yfinance_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pitfall 9 tripwire — SimfinProvider with missing SIMFIN_API_KEY MUST raise,
    not silently fall back to yfinance. Operator must not believe they are using
    PIT fundamentals when the API key is absent."""
    monkeypatch.delenv("SIMFIN_API_KEY", raising=False)
    from data_providers.simfin_provider import SimfinProvider  # noqa: WPS433

    provider = SimfinProvider()  # Should warn, not raise; lazy-key pattern
    with pytest.raises(RuntimeError, match="SIMFIN_API_KEY"):
        await provider.get_financials("AAPL", statement="pl", period="q1", fyear=2024)
