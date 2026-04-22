"""Tests for DATA-03: SEC EDGAR Form 4 insider-transaction provider and
FundamentalAgent integration (Plan 03-03).

Test structure:
- Tests 1-9  (test_edgar_*): EdgarProvider unit tests — aggregation math,
  edge cases, graceful degradation.
- Tests 10-17 (test_fundamental_agent_*): FundamentalAgent integration
  tests — insider tilt, coexistence with Plan 03-01 Finnhub path,
  FOUND-04 backtest_mode regression.

All tests use fake modules injected via monkeypatch.setitem(sys.modules)
to avoid hitting SEC EDGAR's live API.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from agents.models import AgentInput, Signal
from data_providers.base import DataProvider


# ---------------------------------------------------------------------------
# Shared fakes for edgartools API
# ---------------------------------------------------------------------------

class _FakeTx:
    """Minimal stand-in for an edgartools Form 4 transaction row."""

    def __init__(self, code: str, shares: int) -> None:
        self.transaction_code = code
        self.shares = shares


class _FakeObj:
    """Minimal stand-in for a parsed Form 4 filing object."""

    def __init__(self, txs: list[_FakeTx]) -> None:
        self.non_derivative_transactions = txs


class _FakeFiling:
    """Minimal stand-in for an edgartools filing entry."""

    def __init__(self, txs: list[_FakeTx]) -> None:
        self._txs = txs

    def obj(self) -> _FakeObj:
        return _FakeObj(self._txs)


class _FakeCompany:
    """Minimal stand-in for an edgartools Company object."""

    def __init__(self, filings: list[_FakeFiling]) -> None:
        self._filings = filings

    def get_filings(self, form: str = "4", filing_date: str | None = None) -> list[_FakeFiling]:
        return self._filings


def _make_fake_edgar_module(filings: list[_FakeFiling]) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        set_identity=lambda s: None,
        Company=lambda ticker: _FakeCompany(filings),
    )


def _install_fake_edgar(monkeypatch: pytest.MonkeyPatch, filings: list[_FakeFiling]) -> None:
    """Inject a fake edgar module into sys.modules for the test duration."""
    monkeypatch.setitem(sys.modules, "edgar", _make_fake_edgar_module(filings))


# ---------------------------------------------------------------------------
# Provider unit tests (T1–T9)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_edgar_aggregates_buys_and_sells(monkeypatch: pytest.MonkeyPatch) -> None:
    """5 buys (10 000 shares) + 2 sales (2 000 shares) → ratio ≈ 0.833."""
    filings = [
        _FakeFiling([_FakeTx("P", 2000), _FakeTx("P", 2000), _FakeTx("P", 2000)]),
        _FakeFiling([_FakeTx("P", 2000), _FakeTx("P", 2000), _FakeTx("S", 1000)]),
        _FakeFiling([_FakeTx("S", 1000)]),
    ]
    _install_fake_edgar(monkeypatch, filings)
    # Force fresh import of EdgarProvider so the monkeypatched edgar module is used
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]
    from data_providers.edgar_provider import EdgarProvider

    provider = EdgarProvider()
    result = await provider.get_insider_transactions("AAPL", since_days=90)

    assert result is not None
    assert result["transaction_count"] == 7
    assert result["buys_shares"] == 10_000
    assert result["sells_shares"] == 2_000
    assert result["since_days"] == 90
    assert result["net_buy_ratio"] == pytest.approx(10_000 / 12_000, rel=1e-3)


@pytest.mark.asyncio
async def test_edgar_handles_all_buys_ratio_1_0(monkeypatch: pytest.MonkeyPatch) -> None:
    """All purchases, no sales → ratio = 1.0."""
    filings = [
        _FakeFiling([_FakeTx("P", 5000), _FakeTx("P", 3000)]),
    ]
    _install_fake_edgar(monkeypatch, filings)
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]
    from data_providers.edgar_provider import EdgarProvider

    provider = EdgarProvider()
    result = await provider.get_insider_transactions("MSFT", since_days=90)

    assert result is not None
    assert result["net_buy_ratio"] == pytest.approx(1.0)
    assert result["sells_shares"] == 0


@pytest.mark.asyncio
async def test_edgar_handles_all_sells_ratio_0_0(monkeypatch: pytest.MonkeyPatch) -> None:
    """All sales, no purchases → ratio = 0.0."""
    filings = [
        _FakeFiling([_FakeTx("S", 5000), _FakeTx("S", 3000)]),
    ]
    _install_fake_edgar(monkeypatch, filings)
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]
    from data_providers.edgar_provider import EdgarProvider

    provider = EdgarProvider()
    result = await provider.get_insider_transactions("GOOG", since_days=90)

    assert result is not None
    assert result["net_buy_ratio"] == pytest.approx(0.0)
    assert result["buys_shares"] == 0


@pytest.mark.asyncio
async def test_edgar_zero_transactions_returns_none_ratio(monkeypatch: pytest.MonkeyPatch) -> None:
    """No transactions at all → transaction_count=0, net_buy_ratio=None."""
    filings: list[_FakeFiling] = []
    _install_fake_edgar(monkeypatch, filings)
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]
    from data_providers.edgar_provider import EdgarProvider

    provider = EdgarProvider()
    result = await provider.get_insider_transactions("XYZ", since_days=90)

    assert result is not None
    assert result["transaction_count"] == 0
    assert result["buys_shares"] == 0
    assert result["sells_shares"] == 0
    assert result["net_buy_ratio"] is None


@pytest.mark.asyncio
async def test_edgar_ignores_non_P_S_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    """A (award), G (gift), M (exercise) codes are excluded from ratio."""
    filings = [
        _FakeFiling([
            _FakeTx("P", 1000),   # buy — counted
            _FakeTx("A", 5000),   # award — excluded
            _FakeTx("G", 2000),   # gift — excluded
            _FakeTx("M", 3000),   # exercise — excluded
            _FakeTx("S", 500),    # sale — counted
        ]),
    ]
    _install_fake_edgar(monkeypatch, filings)
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]
    from data_providers.edgar_provider import EdgarProvider

    provider = EdgarProvider()
    result = await provider.get_insider_transactions("AAPL", since_days=90)

    assert result is not None
    # transaction_count = 5 (all codes including non-P/S)
    assert result["transaction_count"] == 5
    # buys: only P code
    assert result["buys_shares"] == 1000
    # sells: only S code
    assert result["sells_shares"] == 500
    # ratio = 1000 / 1500
    assert result["net_buy_ratio"] == pytest.approx(1000 / 1500, rel=1e-3)


@pytest.mark.asyncio
async def test_edgar_returns_none_when_edgartools_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """When edgar is not installed, get_insider_transactions returns None."""
    # Remove edgar from sys.modules and inject ImportError sentinel
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]
    monkeypatch.setitem(sys.modules, "edgar", None)  # None sentinel → ImportError on `import edgar`

    from data_providers.edgar_provider import EdgarProvider

    provider = EdgarProvider()
    result = await provider.get_insider_transactions("AAPL", since_days=90)

    assert result is None


@pytest.mark.asyncio
async def test_edgar_returns_none_when_fetch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Company(...) raises, get_insider_transactions returns None (no crash)."""
    fake_module = types.SimpleNamespace(
        set_identity=lambda s: None,
        Company=MagicMock(side_effect=RuntimeError("EDGAR outage")),
    )
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]
    monkeypatch.setitem(sys.modules, "edgar", fake_module)
    from data_providers.edgar_provider import EdgarProvider

    provider = EdgarProvider()
    result = await provider.get_insider_transactions("AAPL", since_days=90)

    assert result is None


def test_edgar_user_agent_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """EDGAR_USER_AGENT env var overrides the default user-agent string."""
    monkeypatch.setenv("EDGAR_USER_AGENT", "TestUser test@example.com")
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]
    monkeypatch.setitem(sys.modules, "edgar", types.SimpleNamespace(
        set_identity=lambda s: None,
        Company=lambda t: None,
    ))
    from data_providers.edgar_provider import EdgarProvider

    provider = EdgarProvider()
    assert provider._user_agent == "TestUser test@example.com"


def test_edgar_rate_limiter_defaults_10_per_second(monkeypatch: pytest.MonkeyPatch) -> None:
    """EdgarProvider class-level limiter has max_calls=10, period=1.0s."""
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]
    monkeypatch.setitem(sys.modules, "edgar", types.SimpleNamespace(
        set_identity=lambda s: None,
        Company=lambda t: None,
    ))
    from data_providers.edgar_provider import EdgarProvider

    limiter = EdgarProvider._limiter
    assert limiter._max_calls == 10
    assert limiter._period == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Helper: minimal MockProvider for FundamentalAgent integration tests
# ---------------------------------------------------------------------------

class _MockProvider(DataProvider):
    def __init__(self) -> None:
        self._key_stats = {
            "market_cap": 500_000_000_000,
            "pe_ratio": 18.0,
            "forward_pe": 15.0,
            "beta": 1.1,
            "dividend_yield": 0.01,
            "sector": "Technology",
            "industry": "Software",
            "52w_high": 200.0,
            "52w_low": 140.0,
            "current_price": 180.0,
        }
        self._financials = _build_financials()

    async def get_price_history(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        raise NotImplementedError

    async def get_current_price(self, ticker: str) -> float:
        return 180.0

    async def get_financials(self, ticker: str, period: str = "annual") -> dict:
        return self._financials

    async def get_key_stats(self, ticker: str) -> dict:
        return self._key_stats

    def is_point_in_time(self) -> bool:
        return False

    def supported_asset_types(self) -> list[str]:
        return ["stock"]


def _build_financials() -> dict:
    income_statement = pd.DataFrame(
        {
            "2025": [120_000_000_000, 25_000_000_000, 30_000_000_000],
            "2024": [105_000_000_000, 20_000_000_000, 25_000_000_000],
        },
        index=["Total Revenue", "Net Income", "EBITDA"],
    )
    balance_sheet = pd.DataFrame(
        {
            "2025": [
                100_000_000_000,
                50_000_000_000,
                70_000_000_000,
                30_000_000_000,
                20_000_000_000,
            ]
        },
        index=[
            "Total Stockholders Equity",
            "Total Debt",
            "Current Assets",
            "Current Liabilities",
            "Cash And Cash Equivalents",
        ],
    )
    cash_flow = pd.DataFrame(
        {"2025": [18_000_000_000]},
        index=["Free Cash Flow"],
    )
    return {
        "income_statement": income_statement,
        "balance_sheet": balance_sheet,
        "cash_flow": cash_flow,
    }


# ---------------------------------------------------------------------------
# FundamentalAgent integration tests (T10–T17)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fundamental_agent_includes_insider_in_reasoning(monkeypatch: pytest.MonkeyPatch) -> None:
    """With 5 buy txs, reasoning contains 'Insider' substring."""
    filings = [_FakeFiling([
        _FakeTx("P", 2000), _FakeTx("P", 2000), _FakeTx("P", 2000),
        _FakeTx("P", 2000), _FakeTx("P", 2000),
    ])]
    _install_fake_edgar(monkeypatch, filings)
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]

    # Disable sector_pe_cache to avoid Finnhub env-var dependency
    monkeypatch.setitem(sys.modules, "data_providers.sector_pe_cache", types.SimpleNamespace(
        get_sector_pe_median=AsyncMock(return_value=None),
        get_sector_pe_source=AsyncMock(return_value="static"),
    ))

    from agents.fundamental import FundamentalAgent

    agent = FundamentalAgent(_MockProvider())
    output = await agent.analyze(AgentInput(ticker="AAPL", asset_type="stock"))

    assert "Insider" in output.reasoning


@pytest.mark.asyncio
async def test_fundamental_agent_insider_bullish_tilts_composite_up(monkeypatch: pytest.MonkeyPatch) -> None:
    """net_buy_ratio=1.0 (all buys) → insider_score=+0.10, composite increases."""
    filings = [_FakeFiling([
        _FakeTx("P", 3000), _FakeTx("P", 3000), _FakeTx("P", 3000),  # 3 txs, ratio=1.0
    ])]
    _install_fake_edgar(monkeypatch, filings)
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]

    monkeypatch.setitem(sys.modules, "data_providers.sector_pe_cache", types.SimpleNamespace(
        get_sector_pe_median=AsyncMock(return_value=None),
        get_sector_pe_source=AsyncMock(return_value="static"),
    ))

    from agents.fundamental import FundamentalAgent

    agent = FundamentalAgent(_MockProvider())
    output = await agent.analyze(AgentInput(ticker="AAPL", asset_type="stock"))

    assert output.metrics["insider_score"] == pytest.approx(0.10)


@pytest.mark.asyncio
async def test_fundamental_agent_insider_bearish_tilts_composite_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """net_buy_ratio=0.0 (all sells) → insider_score=-0.10."""
    filings = [_FakeFiling([
        _FakeTx("S", 3000), _FakeTx("S", 3000), _FakeTx("S", 3000),  # 3 txs, ratio=0.0
    ])]
    _install_fake_edgar(monkeypatch, filings)
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]

    monkeypatch.setitem(sys.modules, "data_providers.sector_pe_cache", types.SimpleNamespace(
        get_sector_pe_median=AsyncMock(return_value=None),
        get_sector_pe_source=AsyncMock(return_value="static"),
    ))

    from agents.fundamental import FundamentalAgent

    agent = FundamentalAgent(_MockProvider())
    output = await agent.analyze(AgentInput(ticker="AAPL", asset_type="stock"))

    assert output.metrics["insider_score"] == pytest.approx(-0.10)


@pytest.mark.asyncio
async def test_fundamental_agent_insider_neutral_no_tilt(monkeypatch: pytest.MonkeyPatch) -> None:
    """net_buy_ratio=0.50 → insider_score=0.0 (between 0.30 and 0.70 thresholds)."""
    filings = [_FakeFiling([
        _FakeTx("P", 1000), _FakeTx("S", 1000), _FakeTx("P", 500),
    ])]
    _install_fake_edgar(monkeypatch, filings)
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]

    monkeypatch.setitem(sys.modules, "data_providers.sector_pe_cache", types.SimpleNamespace(
        get_sector_pe_median=AsyncMock(return_value=None),
        get_sector_pe_source=AsyncMock(return_value="static"),
    ))

    from agents.fundamental import FundamentalAgent

    agent = FundamentalAgent(_MockProvider())

    # 3 txs: P=1500 shares, S=1000 shares → ratio = 1500/2500 = 0.60 (neutral)
    output = await agent.analyze(AgentInput(ticker="AAPL", asset_type="stock"))

    assert output.metrics["insider_score"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_fundamental_agent_insider_threshold_min_transactions(monkeypatch: pytest.MonkeyPatch) -> None:
    """transaction_count=2 → no tilt even if ratio is extreme (needs >=3)."""
    filings = [_FakeFiling([
        _FakeTx("P", 5000), _FakeTx("P", 5000),  # only 2 txs
    ])]
    _install_fake_edgar(monkeypatch, filings)
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]

    monkeypatch.setitem(sys.modules, "data_providers.sector_pe_cache", types.SimpleNamespace(
        get_sector_pe_median=AsyncMock(return_value=None),
        get_sector_pe_source=AsyncMock(return_value="static"),
    ))

    from agents.fundamental import FundamentalAgent

    agent = FundamentalAgent(_MockProvider())
    output = await agent.analyze(AgentInput(ticker="AAPL", asset_type="stock"))

    assert output.metrics["insider_score"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_fundamental_agent_edgar_none_graceful_degradation(monkeypatch: pytest.MonkeyPatch) -> None:
    """When EdgarProvider returns None, agent completes without 'Insider' in reasoning."""
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]
    monkeypatch.setitem(sys.modules, "edgar", None)  # edgartools missing

    monkeypatch.setitem(sys.modules, "data_providers.sector_pe_cache", types.SimpleNamespace(
        get_sector_pe_median=AsyncMock(return_value=None),
        get_sector_pe_source=AsyncMock(return_value="static"),
    ))

    from agents.fundamental import FundamentalAgent

    agent = FundamentalAgent(_MockProvider())
    output = await agent.analyze(AgentInput(ticker="AAPL", asset_type="stock"))

    # Should complete without crash
    assert output.signal in (Signal.BUY, Signal.HOLD, Signal.SELL)
    # Insider should not appear in reasoning when data unavailable
    assert "Insider" not in output.reasoning


@pytest.mark.asyncio
async def test_fundamental_agent_backtest_mode_skips_edgar(monkeypatch: pytest.MonkeyPatch) -> None:
    """backtest_mode=True → short-circuit before Edgar call (FOUND-04 regression)."""
    edgar_called = False

    class _SpyEdgarProvider:
        async def get_insider_transactions(self, ticker: str, since_days: int = 90):  # noqa: ANN201
            nonlocal edgar_called
            edgar_called = True
            return None

    # Patch the EdgarProvider class itself
    fake_edgar_module = types.SimpleNamespace(
        EdgarProvider=_SpyEdgarProvider,
        _MIN_TRANSACTIONS_FOR_SIGNAL=3,
    )
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]
    monkeypatch.setitem(sys.modules, "data_providers.edgar_provider", fake_edgar_module)

    from agents.fundamental import FundamentalAgent

    agent = FundamentalAgent(_MockProvider())
    output = await agent.analyze(AgentInput(ticker="AAPL", asset_type="stock", backtest_mode=True))

    # FOUND-04: backtest_mode short-circuits before ANY provider calls
    assert output.signal == Signal.HOLD
    assert edgar_called is False


@pytest.mark.asyncio
async def test_fundamental_agent_both_sources_coexist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plan 03-01 Finnhub reasoning + Plan 03-03 Edgar insider both present in output."""
    # Set up 5 buy transactions for Edgar
    filings = [_FakeFiling([
        _FakeTx("P", 2000), _FakeTx("P", 2000), _FakeTx("P", 2000),
        _FakeTx("P", 2000), _FakeTx("P", 2000),
    ])]
    _install_fake_edgar(monkeypatch, filings)
    if "data_providers.edgar_provider" in sys.modules:
        del sys.modules["data_providers.edgar_provider"]

    # Wire Finnhub sector P/E source (Plan 03-01 contract)
    monkeypatch.setitem(sys.modules, "data_providers.sector_pe_cache", types.SimpleNamespace(
        get_sector_pe_median=AsyncMock(return_value=28.0),
        get_sector_pe_source=AsyncMock(return_value="finnhub"),
    ))

    from agents.fundamental import FundamentalAgent

    agent = FundamentalAgent(_MockProvider())
    output = await agent.analyze(AgentInput(ticker="AAPL", asset_type="stock"))

    # Plan 03-01 contract: Finnhub P/E source note still present
    assert "Finnhub" in output.reasoning
    # Plan 03-03 contract: insider information also present
    assert "Insider" in output.reasoning
