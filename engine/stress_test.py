"""Stress-test engine: predefined macro scenarios applied to portfolio positions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

@dataclass
class _Scenario:
    name: str
    description: str
    # Impact multipliers by asset category (negative = loss)
    stock_impact: float
    crypto_impact: float
    # Optional per-sector overrides for stocks (sector_name_lower -> impact)
    sector_overrides: dict[str, float] = field(default_factory=dict)


_SCENARIOS: list[_Scenario] = [
    _Scenario(
        name="2008 Financial Crisis",
        description="Broad equity collapse and crypto sell-off mirroring 2008 conditions",
        stock_impact=-0.38,
        crypto_impact=-0.50,
    ),
    _Scenario(
        name="COVID Crash",
        description="Rapid market sell-off similar to March 2020",
        stock_impact=-0.34,
        crypto_impact=-0.45,
    ),
    _Scenario(
        name="Rate Hike Shock",
        description="Aggressive interest-rate increases pressure growth assets",
        stock_impact=-0.15,
        crypto_impact=-0.25,
    ),
    _Scenario(
        name="Sector Rotation (Tech Crash)",
        description="Technology sector rout with milder impact on other sectors",
        stock_impact=-0.10,
        crypto_impact=-0.20,
        sector_overrides={"technology": -0.25, "tech": -0.25},
    ),
    _Scenario(
        name="Crypto Winter",
        description="Prolonged cryptocurrency downturn with limited equity impact",
        stock_impact=-0.05,
        crypto_impact=-0.70,
    ),
]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class StressTestEngine:
    """Run predefined stress-test scenarios against a list of positions."""

    def run_scenarios(
        self,
        positions: list[dict[str, Any]],
        cash: float,
    ) -> list[dict[str, Any]]:
        """Compute scenario impacts for every predefined scenario.

        Parameters
        ----------
        positions:
            Each dict must contain at least ``ticker``, ``asset_type``,
            ``market_value``. ``sector`` is optional but used for
            sector-specific overrides.
        cash:
            Cash balance (unaffected by scenarios, but included in total
            portfolio value for percentage calculations).

        Returns
        -------
        List of scenario result dicts matching the ``StressScenario``
        frontend type.
        """
        total_portfolio_value = cash + sum(
            p.get("market_value", 0.0) for p in positions
        )
        if total_portfolio_value <= 0:
            return [
                {
                    "name": s.name,
                    "description": s.description,
                    "portfolio_impact_pct": 0.0,
                    "affected_positions": [],
                }
                for s in _SCENARIOS
            ]

        results: list[dict[str, Any]] = []
        for scenario in _SCENARIOS:
            affected: list[dict[str, Any]] = []
            total_impact_dollars = 0.0

            for pos in positions:
                mv = pos.get("market_value", 0.0)
                if mv == 0.0:
                    continue

                asset_type = (pos.get("asset_type") or "stock").lower()
                sector = (pos.get("sector") or "").lower()

                # Determine impact percentage for this position
                if asset_type in ("btc", "eth", "crypto"):
                    impact_pct = scenario.crypto_impact
                else:
                    # Check sector-specific overrides first
                    if sector and sector in scenario.sector_overrides:
                        impact_pct = scenario.sector_overrides[sector]
                    else:
                        impact_pct = scenario.stock_impact

                position_impact = mv * impact_pct
                total_impact_dollars += position_impact

                affected.append({
                    "ticker": pos.get("ticker", "???"),
                    "impact_pct": round(impact_pct * 100, 2),
                })

            portfolio_impact_pct = round(
                (total_impact_dollars / total_portfolio_value) * 100, 2
            )

            results.append({
                "name": scenario.name,
                "description": scenario.description,
                "portfolio_impact_pct": portfolio_impact_pct,
                "affected_positions": affected,
            })

        return results
