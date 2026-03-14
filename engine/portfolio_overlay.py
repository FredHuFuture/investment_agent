"""Portfolio overlay: concentration checks and position sizing.

Analyses how adding a new position would affect portfolio composition.
Sprint 11.1 -- sector concentration warnings, same-ticker detection,
position sizing, and before/after exposure calculation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from portfolio.models import Portfolio


@dataclass
class PortfolioImpact:
    """Result of analyzing how a new position would affect the portfolio."""

    ticker: str
    # Concentration
    current_sector_pct: float  # current sector exposure %
    projected_sector_pct: float  # projected if position added
    sector: str | None
    concentration_warning: str | None  # set if > threshold
    # Correlation
    correlated_positions: list[dict[str, Any]]  # [{ticker, correlation}]
    correlation_warning: str | None
    # Position sizing
    suggested_quantity: int | None
    suggested_allocation_pct: float
    max_position_pct: float
    # Before/after summary
    before_exposure: dict[str, float]  # {stock_pct, crypto_pct, cash_pct}
    after_exposure: dict[str, float]  # projected

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "current_sector_pct": round(self.current_sector_pct, 4),
            "projected_sector_pct": round(self.projected_sector_pct, 4),
            "sector": self.sector,
            "concentration_warning": self.concentration_warning,
            "correlated_positions": self.correlated_positions,
            "correlation_warning": self.correlation_warning,
            "suggested_quantity": self.suggested_quantity,
            "suggested_allocation_pct": round(self.suggested_allocation_pct, 4),
            "max_position_pct": round(self.max_position_pct, 4),
            "before_exposure": {k: round(v, 4) for k, v in self.before_exposure.items()},
            "after_exposure": {k: round(v, 4) for k, v in self.after_exposure.items()},
        }


def compute_portfolio_impact(
    ticker: str,
    asset_type: str,
    current_price: float,
    portfolio: Portfolio,
    sector: str | None = None,
    target_allocation_pct: float = 0.05,  # default 5% of portfolio
    max_sector_pct: float = 0.40,  # warn if sector > 40%
    max_position_pct: float = 0.15,  # max single position 15%
) -> PortfolioImpact:
    """Compute the impact of adding a new position to *portfolio*.

    Parameters
    ----------
    ticker:
        The ticker symbol of the asset to be added.
    asset_type:
        One of "stock", "btc", "eth".
    current_price:
        Latest price of the asset.
    portfolio:
        Current portfolio snapshot.
    sector:
        Sector label for stocks (e.g. "Technology").  For crypto positions
        the sector is treated as "Crypto".
    target_allocation_pct:
        Desired allocation as a fraction of total portfolio value (0-1).
    max_sector_pct:
        Concentration threshold -- warn if projected sector pct exceeds this.
    max_position_pct:
        Maximum allowed single-position size as a fraction (0-1).

    Returns
    -------
    PortfolioImpact with all computed fields filled in.
    """
    total_value = portfolio.total_value

    # Determine the effective sector label
    is_crypto = asset_type in ("btc", "eth", "crypto")
    effective_sector: str | None
    if is_crypto:
        effective_sector = "Crypto"
    else:
        effective_sector = sector if sector else "Other"

    # ------------------------------------------------------------------
    # 1. Concentration check
    # ------------------------------------------------------------------
    current_sector_pct = portfolio.sector_breakdown.get(effective_sector, 0.0) if effective_sector else 0.0

    # Cap allocation at max_position_pct
    effective_allocation_pct = min(target_allocation_pct, max_position_pct)
    allocation_amount = effective_allocation_pct * total_value if total_value > 0 else 0.0

    # Projected sector pct: current sector value + allocation, divided by
    # new total (total_value stays the same -- we're deploying cash, not
    # adding external capital).
    if total_value > 0:
        current_sector_value = current_sector_pct * total_value
        projected_sector_value = current_sector_value + allocation_amount
        projected_sector_pct = projected_sector_value / total_value
    else:
        projected_sector_pct = effective_allocation_pct

    concentration_warning: str | None = None
    if projected_sector_pct > max_sector_pct:
        concentration_warning = (
            f"Adding {ticker} would bring {effective_sector} sector exposure to "
            f"{projected_sector_pct:.1%}, exceeding the {max_sector_pct:.0%} limit."
        )

    # ------------------------------------------------------------------
    # 2. Correlated positions (sector-overlap heuristic for Sprint 11.1)
    # ------------------------------------------------------------------
    correlated_positions: list[dict[str, Any]] = []
    correlation_warning: str | None = None
    already_in_portfolio = False

    for pos in portfolio.positions:
        if pos.ticker.upper() == ticker.upper():
            already_in_portfolio = True
            correlated_positions.append({"ticker": pos.ticker, "correlation": 1.0})
        elif effective_sector and pos.sector == effective_sector and pos.asset_type == "stock":
            correlated_positions.append({"ticker": pos.ticker, "correlation": 0.7})
        elif is_crypto and pos.asset_type in ("btc", "eth", "crypto"):
            correlated_positions.append({"ticker": pos.ticker, "correlation": 0.7})

    if already_in_portfolio:
        correlation_warning = f"{ticker} is already in the portfolio."
    elif len(correlated_positions) >= 3:
        correlation_warning = (
            f"{len(correlated_positions)} existing positions share the "
            f"{effective_sector} sector -- consider diversification."
        )

    # ------------------------------------------------------------------
    # 3. Position sizing
    # ------------------------------------------------------------------
    suggested_quantity: int | None = None
    if current_price > 0 and total_value > 0:
        suggested_quantity = math.floor(allocation_amount / current_price)

    # ------------------------------------------------------------------
    # 4. Before/after exposure
    # ------------------------------------------------------------------
    before_exposure = {
        "stock_pct": portfolio.stock_exposure_pct,
        "crypto_pct": portfolio.crypto_exposure_pct,
        "cash_pct": portfolio.cash_pct,
    }

    # Project after exposure: allocation_amount moves from cash to the
    # appropriate asset class.
    if total_value > 0:
        delta_pct = allocation_amount / total_value
        if is_crypto:
            after_stock_pct = portfolio.stock_exposure_pct
            after_crypto_pct = portfolio.crypto_exposure_pct + delta_pct
        else:
            after_stock_pct = portfolio.stock_exposure_pct + delta_pct
            after_crypto_pct = portfolio.crypto_exposure_pct
        after_cash_pct = portfolio.cash_pct - delta_pct
        # Clamp to 0 in case allocation exceeds available cash
        after_cash_pct = max(after_cash_pct, 0.0)
    else:
        after_stock_pct = 0.0
        after_crypto_pct = 0.0
        after_cash_pct = 0.0

    after_exposure = {
        "stock_pct": after_stock_pct,
        "crypto_pct": after_crypto_pct,
        "cash_pct": after_cash_pct,
    }

    return PortfolioImpact(
        ticker=ticker,
        current_sector_pct=current_sector_pct,
        projected_sector_pct=projected_sector_pct,
        sector=effective_sector,
        concentration_warning=concentration_warning,
        correlated_positions=correlated_positions,
        correlation_warning=correlation_warning,
        suggested_quantity=suggested_quantity,
        suggested_allocation_pct=effective_allocation_pct,
        max_position_pct=max_position_pct,
        before_exposure=before_exposure,
        after_exposure=after_exposure,
    )
