"""Tests for Sprint 11.1: Portfolio concentration check overlay.

All tests build Portfolio objects in-memory -- no network calls, no DB.
"""
from __future__ import annotations

import math

import pytest

from engine.portfolio_overlay import PortfolioImpact, compute_portfolio_impact
from portfolio.models import Portfolio, Position


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_portfolio(
    positions: list[Position] | None = None,
    cash: float = 10_000.0,
) -> Portfolio:
    """Build a Portfolio from a list of positions and cash amount.

    Computes total_value, exposure percentages, sector_breakdown, and
    top_concentration the same way PortfolioManager.load_portfolio does.
    """
    positions = positions or []

    effective_values = [
        p.market_value if p.current_price > 0 else p.cost_basis
        for p in positions
    ]
    total_positions_value = sum(effective_values)
    total_value = total_positions_value + cash

    stock_value = sum(
        v for p, v in zip(positions, effective_values)
        if p.asset_type == "stock"
    )
    crypto_value = sum(
        v for p, v in zip(positions, effective_values)
        if p.asset_type in ("btc", "eth", "crypto")
    )

    if total_value > 0:
        stock_exposure_pct = stock_value / total_value
        crypto_exposure_pct = crypto_value / total_value
        cash_pct = cash / total_value
    else:
        stock_exposure_pct = 0.0
        crypto_exposure_pct = 0.0
        cash_pct = 0.0

    sector_values: dict[str, float] = {}
    for p, v in zip(positions, effective_values):
        if p.asset_type == "stock":
            label = p.sector if p.sector else "Other"
            sector_values[label] = sector_values.get(label, 0.0) + v
        elif p.asset_type in ("btc", "eth", "crypto"):
            sector_values["Crypto"] = sector_values.get("Crypto", 0.0) + v

    sector_breakdown = (
        {s: v / total_value for s, v in sector_values.items()}
        if total_value > 0
        else {}
    )

    concentration: list[tuple[str, float]] = []
    for p, v in zip(positions, effective_values):
        pct = v / total_value if total_value > 0 else 0.0
        concentration.append((p.ticker, pct))
    concentration.sort(key=lambda x: x[1], reverse=True)

    return Portfolio(
        positions=positions,
        cash=cash,
        total_value=total_value,
        stock_exposure_pct=stock_exposure_pct,
        crypto_exposure_pct=crypto_exposure_pct,
        cash_pct=cash_pct,
        sector_breakdown=sector_breakdown,
        top_concentration=concentration,
    )


def _pos(
    ticker: str,
    asset_type: str = "stock",
    quantity: float = 100,
    avg_cost: float = 100.0,
    current_price: float = 100.0,
    sector: str | None = None,
) -> Position:
    return Position(
        ticker=ticker,
        asset_type=asset_type,
        quantity=quantity,
        avg_cost=avg_cost,
        current_price=current_price,
        sector=sector,
        entry_date="2026-01-01",
    )


# ---------------------------------------------------------------------------
# 1. test_concentration_check_warns_above_threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concentration_check_warns_above_threshold():
    """Portfolio with 35% Technology + adding another Tech stock -> warns."""
    # 35_000 in Tech out of 100_000 total => 35% tech exposure
    positions = [
        _pos("AAPL", sector="Technology", quantity=200, current_price=100.0),  # 20k
        _pos("MSFT", sector="Technology", quantity=150, current_price=100.0),  # 15k
        _pos("JNJ", sector="Healthcare", quantity=100, current_price=100.0),  # 10k
    ]
    portfolio = _make_portfolio(positions, cash=55_000.0)
    # total_value = 20k + 15k + 10k + 55k = 100k
    # Technology = 35k / 100k = 0.35

    impact = compute_portfolio_impact(
        ticker="NVDA",
        asset_type="stock",
        current_price=50.0,
        portfolio=portfolio,
        sector="Technology",
        target_allocation_pct=0.10,  # 10% of 100k = 10k
        max_sector_pct=0.40,
    )

    # projected = (35k + 10k) / 100k = 0.45 > 0.40 => should warn
    assert impact.concentration_warning is not None
    assert "Technology" in impact.concentration_warning
    assert "45.0%" in impact.concentration_warning
    assert impact.projected_sector_pct == pytest.approx(0.45, abs=1e-4)


# ---------------------------------------------------------------------------
# 2. test_concentration_check_ok_below_threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concentration_check_ok_below_threshold():
    """Portfolio with 20% Technology + adding Tech stock stays under 40% -> no warning."""
    positions = [
        _pos("AAPL", sector="Technology", quantity=200, current_price=100.0),  # 20k
        _pos("JNJ", sector="Healthcare", quantity=100, current_price=100.0),  # 10k
    ]
    portfolio = _make_portfolio(positions, cash=70_000.0)
    # total_value = 20k + 10k + 70k = 100k
    # Technology = 20k / 100k = 0.20

    impact = compute_portfolio_impact(
        ticker="MSFT",
        asset_type="stock",
        current_price=200.0,
        portfolio=portfolio,
        sector="Technology",
        target_allocation_pct=0.05,  # 5% of 100k = 5k
        max_sector_pct=0.40,
    )

    # projected = (20k + 5k) / 100k = 0.25 < 0.40 => no warning
    assert impact.concentration_warning is None
    assert impact.projected_sector_pct == pytest.approx(0.25, abs=1e-4)


# ---------------------------------------------------------------------------
# 3. test_already_in_portfolio_warning
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_already_in_portfolio_warning():
    """Ticker already exists in positions -> warning."""
    positions = [
        _pos("AAPL", sector="Technology", quantity=100, current_price=150.0),
    ]
    portfolio = _make_portfolio(positions, cash=85_000.0)

    impact = compute_portfolio_impact(
        ticker="AAPL",
        asset_type="stock",
        current_price=150.0,
        portfolio=portfolio,
        sector="Technology",
    )

    assert impact.correlation_warning is not None
    assert "already in the portfolio" in impact.correlation_warning
    # Should also appear in correlated_positions with correlation=1.0
    assert any(
        cp["ticker"] == "AAPL" and cp["correlation"] == 1.0
        for cp in impact.correlated_positions
    )


# ---------------------------------------------------------------------------
# 4. test_position_sizing_calculation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_position_sizing_calculation():
    """Verify suggested_quantity = floor(allocation / price)."""
    portfolio = _make_portfolio([], cash=100_000.0)

    impact = compute_portfolio_impact(
        ticker="GOOG",
        asset_type="stock",
        current_price=175.0,
        portfolio=portfolio,
        sector="Technology",
        target_allocation_pct=0.05,  # 5% of 100k = 5000
    )

    # floor(5000 / 175) = 28
    assert impact.suggested_quantity == 28
    assert impact.suggested_allocation_pct == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# 5. test_position_sizing_zero_price
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_position_sizing_zero_price():
    """Price=0 -> suggested_quantity=None."""
    portfolio = _make_portfolio([], cash=100_000.0)

    impact = compute_portfolio_impact(
        ticker="PENNY",
        asset_type="stock",
        current_price=0.0,
        portfolio=portfolio,
        sector="Other",
    )

    assert impact.suggested_quantity is None


# ---------------------------------------------------------------------------
# 6. test_before_after_exposure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_before_after_exposure():
    """Verify before/after percentages are correct."""
    positions = [
        _pos("AAPL", sector="Technology", quantity=100, current_price=200.0),  # 20k
    ]
    portfolio = _make_portfolio(positions, cash=80_000.0)
    # total_value = 20k + 80k = 100k
    # stock_pct = 0.20, crypto_pct = 0.0, cash_pct = 0.80

    impact = compute_portfolio_impact(
        ticker="MSFT",
        asset_type="stock",
        current_price=400.0,
        portfolio=portfolio,
        sector="Technology",
        target_allocation_pct=0.10,  # 10% of 100k = 10k
    )

    assert impact.before_exposure["stock_pct"] == pytest.approx(0.20)
    assert impact.before_exposure["crypto_pct"] == pytest.approx(0.0)
    assert impact.before_exposure["cash_pct"] == pytest.approx(0.80)

    # After: stock goes up by 10%, cash goes down by 10%
    assert impact.after_exposure["stock_pct"] == pytest.approx(0.30)
    assert impact.after_exposure["crypto_pct"] == pytest.approx(0.0)
    assert impact.after_exposure["cash_pct"] == pytest.approx(0.70)


# ---------------------------------------------------------------------------
# 7. test_max_position_pct_cap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_max_position_pct_cap():
    """Allocation doesn't exceed max_position_pct."""
    portfolio = _make_portfolio([], cash=100_000.0)

    impact = compute_portfolio_impact(
        ticker="TSLA",
        asset_type="stock",
        current_price=250.0,
        portfolio=portfolio,
        sector="Consumer Cyclical",
        target_allocation_pct=0.25,  # 25% requested
        max_position_pct=0.15,      # but capped at 15%
    )

    # effective allocation should be 15%, not 25%
    assert impact.suggested_allocation_pct == pytest.approx(0.15)
    # floor(15000 / 250) = 60
    assert impact.suggested_quantity == 60


# ---------------------------------------------------------------------------
# 8. test_empty_portfolio
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_portfolio():
    """No positions -> all clear, suggested sizing based on cash."""
    portfolio = _make_portfolio([], cash=50_000.0)

    impact = compute_portfolio_impact(
        ticker="AAPL",
        asset_type="stock",
        current_price=200.0,
        portfolio=portfolio,
        sector="Technology",
        target_allocation_pct=0.05,  # 5% of 50k = 2500
    )

    assert impact.concentration_warning is None
    assert impact.correlation_warning is None
    assert len(impact.correlated_positions) == 0
    # floor(2500 / 200) = 12
    assert impact.suggested_quantity == 12
    assert impact.current_sector_pct == pytest.approx(0.0)
    assert impact.projected_sector_pct == pytest.approx(0.05)

    # Before: all cash
    assert impact.before_exposure["stock_pct"] == pytest.approx(0.0)
    assert impact.before_exposure["cash_pct"] == pytest.approx(1.0)

    # After: 5% stock, 95% cash
    assert impact.after_exposure["stock_pct"] == pytest.approx(0.05)
    assert impact.after_exposure["cash_pct"] == pytest.approx(0.95)


# ---------------------------------------------------------------------------
# 9. test_crypto_position_impact
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_crypto_position_impact():
    """Adding BTC to a stock-heavy portfolio."""
    positions = [
        _pos("AAPL", sector="Technology", quantity=200, current_price=200.0),  # 40k
        _pos("JNJ", sector="Healthcare", quantity=100, current_price=100.0),  # 10k
    ]
    portfolio = _make_portfolio(positions, cash=50_000.0)
    # total_value = 40k + 10k + 50k = 100k
    # stock_pct = 0.50, crypto_pct = 0.0, cash_pct = 0.50

    impact = compute_portfolio_impact(
        ticker="BTC-USD",
        asset_type="btc",
        current_price=60_000.0,
        portfolio=portfolio,
        sector=None,  # crypto doesn't have a stock sector
        target_allocation_pct=0.05,  # 5% of 100k = 5k
    )

    assert impact.sector == "Crypto"
    assert impact.concentration_warning is None  # 5% < 40%
    assert impact.correlation_warning is None
    assert impact.projected_sector_pct == pytest.approx(0.05, abs=1e-4)

    # Position sizing: floor(5000 / 60000) = 0 (fractional BTC needed)
    assert impact.suggested_quantity == 0

    # Before/after: crypto goes from 0 to 5%, cash drops from 50% to 45%
    assert impact.before_exposure["crypto_pct"] == pytest.approx(0.0)
    assert impact.after_exposure["crypto_pct"] == pytest.approx(0.05)
    assert impact.before_exposure["cash_pct"] == pytest.approx(0.50)
    assert impact.after_exposure["cash_pct"] == pytest.approx(0.45)

    # Stock exposure unchanged
    assert impact.after_exposure["stock_pct"] == pytest.approx(0.50)


# ---------------------------------------------------------------------------
# 10. test_to_dict_roundtrip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_to_dict_roundtrip():
    """PortfolioImpact.to_dict() returns all expected keys."""
    portfolio = _make_portfolio([], cash=100_000.0)
    impact = compute_portfolio_impact(
        ticker="AAPL",
        asset_type="stock",
        current_price=150.0,
        portfolio=portfolio,
        sector="Technology",
    )

    d = impact.to_dict()
    expected_keys = {
        "ticker",
        "current_sector_pct",
        "projected_sector_pct",
        "sector",
        "concentration_warning",
        "correlated_positions",
        "correlation_warning",
        "suggested_quantity",
        "suggested_allocation_pct",
        "max_position_pct",
        "before_exposure",
        "after_exposure",
    }
    assert set(d.keys()) == expected_keys
    assert d["ticker"] == "AAPL"
    assert d["sector"] == "Technology"


# ---------------------------------------------------------------------------
# 11. test_sector_overlap_correlated_positions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sector_overlap_correlated_positions():
    """Positions in the same sector show up in correlated_positions."""
    positions = [
        _pos("AAPL", sector="Technology", quantity=100, current_price=150.0),
        _pos("MSFT", sector="Technology", quantity=100, current_price=300.0),
        _pos("GOOG", sector="Technology", quantity=50, current_price=140.0),
        _pos("JNJ", sector="Healthcare", quantity=100, current_price=160.0),
    ]
    portfolio = _make_portfolio(positions, cash=20_000.0)

    impact = compute_portfolio_impact(
        ticker="NVDA",
        asset_type="stock",
        current_price=800.0,
        portfolio=portfolio,
        sector="Technology",
    )

    # 3 tech stocks are correlated (AAPL, MSFT, GOOG). JNJ is not.
    tech_correlated = [
        cp for cp in impact.correlated_positions if cp["correlation"] == 0.7
    ]
    assert len(tech_correlated) == 3
    corr_tickers = {cp["ticker"] for cp in tech_correlated}
    assert corr_tickers == {"AAPL", "MSFT", "GOOG"}

    # 3 correlated positions => warning about diversification
    assert impact.correlation_warning is not None
    assert "3 existing positions" in impact.correlation_warning
