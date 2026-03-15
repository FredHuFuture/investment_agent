from __future__ import annotations

"""Regime Detection Engine.

Analyses macro-economic indicators and price data to classify the current
market regime.  The detected regime can then be used to adjust agent weights
in the signal aggregator, improving signal quality across different market
conditions.

Regime types:
    bull_market      -- strong uptrend, low volatility, positive macro
    bear_market      -- downtrend, rising volatility, negative macro
    sideways         -- flat trend, low volatility
    high_volatility  -- any trend with elevated volatility
    risk_off         -- rising rates, weak macro environment
"""

import math
from dataclasses import dataclass, field
from typing import Any

from agents.models import AgentOutput, Regime


# ------------------------------------------------------------------
# Legacy constants (kept for backward compatibility)
# ------------------------------------------------------------------

REGIME_WEIGHT_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "RISK_ON": {
        "TechnicalAgent": 1.1,
        "FundamentalAgent": 1.3,
        "MacroAgent": 0.8,
        "SentimentAgent": 1.0,
    },
    "RISK_OFF": {
        "TechnicalAgent": 1.0,
        "FundamentalAgent": 0.8,
        "MacroAgent": 1.4,
        "SentimentAgent": 1.2,
    },
    "NEUTRAL": {
        "TechnicalAgent": 1.0,
        "FundamentalAgent": 1.0,
        "MacroAgent": 1.0,
        "SentimentAgent": 1.0,
    },
}


@dataclass
class RegimeInfo:
    """Result of regime detection with weight adjustments (legacy API)."""

    regime: Regime
    adjustments: dict[str, float]
    source: str = "macro_agent"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime.value,
            "adjustments": self.adjustments,
            "source": self.source,
            "metadata": self.metadata,
        }


# ------------------------------------------------------------------
# RegimeDetector
# ------------------------------------------------------------------

class RegimeDetector:
    """Detect market regime from multiple signals.

    Supports two modes:
    1. ``detect_regime(macro_data, price_data)`` -- multi-signal analysis
       using raw macro indicators and price arrays.
    2. ``detect(agent_outputs)`` -- legacy API that extracts regime from
       MacroAgent output objects.
    """

    # Regime type constants
    BULL = "bull_market"
    BEAR = "bear_market"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    RISK_OFF = "risk_off"

    _ALL_REGIMES = {BULL, BEAR, SIDEWAYS, HIGH_VOLATILITY, RISK_OFF}

    def __init__(
        self,
        custom_adjustments: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self._indicators: dict[str, float] = {}
        self._adjustments = custom_adjustments or REGIME_WEIGHT_ADJUSTMENTS

    # ------------------------------------------------------------------
    # Primary API -- multi-signal detection
    # ------------------------------------------------------------------

    def detect_regime(
        self,
        macro_data: dict[str, Any] | None = None,
        price_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyse macro + price data to determine the current market regime.

        Parameters
        ----------
        macro_data : dict | None
            Macro-economic signals.  Expected keys (all optional):
            - ``fed_funds_rate``: current rate (float)
            - ``fed_funds_trend``: ``"increasing"`` / ``"decreasing"`` / ``"stable"``
            - ``yield_curve_spread``: 10Y-2Y spread (float)
            - ``m2_yoy_growth``: M2 money supply YoY growth (float, 0.05 = 5%)
            - ``vix_current``: current VIX level (float)
            - ``vix_sma_20``: 20-day SMA of VIX (float)
            - ``unemployment_trend``: ``"rising"`` / ``"falling"`` / ``"stable"``
            - ``gdp_growth``: latest GDP growth rate (float, 0.03 = 3%)

        price_data : dict | None
            Price-derived signals.  Expected keys (all optional):
            - ``prices``: list[float] -- recent closing prices (oldest first)
            - ``returns``: list[float] -- daily percentage returns

        Returns
        -------
        dict with keys:
            ``regime``      -- one of the regime type constants
            ``confidence``  -- 0-100
            ``indicators``  -- sub-scores used for the decision
            ``description`` -- human-readable summary
        """
        trend_score = self._compute_trend_score(price_data)
        volatility_score = self._compute_volatility_score(price_data, macro_data)
        momentum_score = self._compute_momentum_score(price_data)
        macro_score = self._compute_macro_score(macro_data)

        self._indicators = {
            "trend_score": round(trend_score, 4),
            "volatility_score": round(volatility_score, 4),
            "momentum_score": round(momentum_score, 4),
            "macro_score": round(macro_score, 4),
        }

        regime, confidence = self._classify(
            trend_score, volatility_score, momentum_score, macro_score,
            macro_data, price_data,
        )

        description = self._build_description(regime, confidence)

        return {
            "regime": regime,
            "confidence": round(confidence, 2),
            "indicators": dict(self._indicators),
            "description": description,
        }

    def get_weight_adjustments(self, regime: str) -> dict[str, float]:
        """Return multipliers for agent weights based on detected regime.

        In bear markets: increase MacroAgent weight, decrease FundamentalAgent.
        In bull markets: increase FundamentalAgent, decrease MacroAgent.
        In high volatility: increase TechnicalAgent weight.
        """
        adjustments: dict[str, dict[str, float]] = {
            self.BULL: {
                "TechnicalAgent": 1.0,
                "FundamentalAgent": 1.2,
                "MacroAgent": 0.8,
                "SentimentAgent": 1.1,
            },
            self.BEAR: {
                "TechnicalAgent": 1.1,
                "FundamentalAgent": 0.8,
                "MacroAgent": 1.3,
                "SentimentAgent": 1.0,
            },
            self.SIDEWAYS: {
                "TechnicalAgent": 1.2,
                "FundamentalAgent": 1.0,
                "MacroAgent": 0.9,
                "SentimentAgent": 1.0,
            },
            self.HIGH_VOLATILITY: {
                "TechnicalAgent": 1.3,
                "FundamentalAgent": 0.7,
                "MacroAgent": 1.1,
                "SentimentAgent": 1.0,
            },
            self.RISK_OFF: {
                "TechnicalAgent": 0.9,
                "FundamentalAgent": 0.7,
                "MacroAgent": 1.4,
                "SentimentAgent": 1.1,
            },
        }
        return adjustments.get(regime, {
            "TechnicalAgent": 1.0,
            "FundamentalAgent": 1.0,
            "MacroAgent": 1.0,
            "SentimentAgent": 1.0,
        })

    # ------------------------------------------------------------------
    # Legacy API -- detect from AgentOutputs
    # ------------------------------------------------------------------

    def detect(self, agent_outputs: list[AgentOutput]) -> RegimeInfo:
        """Detect regime from agent outputs and return weight adjustments.

        Scans agent outputs for MacroAgent's regime metric.
        Falls back to NEUTRAL if not found.
        """
        regime = Regime.NEUTRAL
        metadata: dict[str, Any] = {}

        for output in agent_outputs:
            if output.agent_name == "MacroAgent":
                regime_str = output.metrics.get("regime")
                if regime_str:
                    try:
                        regime = Regime(regime_str)
                    except ValueError:
                        regime = Regime.NEUTRAL
                net_score = output.metrics.get("net_score")
                if net_score is not None:
                    metadata["macro_net_score"] = net_score
                break

        adjustments = self.get_adjustments_legacy(regime)
        return RegimeInfo(
            regime=regime,
            adjustments=adjustments,
            source="macro_agent",
            metadata=metadata,
        )

    def get_adjustments_legacy(self, regime: Regime) -> dict[str, float]:
        """Get weight adjustment multipliers for a given Regime enum value.

        Returns a copy of the adjustment dict.  Unknown regimes fall back to
        NEUTRAL (all multipliers = 1.0).
        """
        regime_key = regime.value if isinstance(regime, Regime) else str(regime)
        adj = self._adjustments.get(regime_key)
        if adj is None:
            return dict(self._adjustments.get("NEUTRAL", {}))
        return dict(adj)

    # ------------------------------------------------------------------
    # Indicator computations
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_trend_score(price_data: dict[str, Any] | None) -> float:
        """Compute trend score using SMA crossover logic.

        Returns a value in [-1, 1].  Positive = bullish, negative = bearish.
        """
        if price_data is None:
            return 0.0

        prices = price_data.get("prices")
        if not prices or len(prices) < 5:
            return 0.0

        prices_list: list[float] = [float(p) for p in prices]

        short_window = min(20, len(prices_list))
        long_window = min(50, len(prices_list))

        short_ma = sum(prices_list[-short_window:]) / short_window
        long_ma = sum(prices_list[-long_window:]) / long_window

        if long_ma == 0:
            return 0.0

        diff_pct = (short_ma - long_ma) / long_ma

        # +-10% difference maps roughly to +-1.0
        score = max(-1.0, min(1.0, diff_pct * 10.0))
        return score

    @staticmethod
    def _compute_volatility_score(
        price_data: dict[str, Any] | None,
        macro_data: dict[str, Any] | None,
    ) -> float:
        """Compute volatility score.  Returns [0, 1].  Higher = more volatile."""
        vol_from_returns = 0.0
        vol_from_vix = 0.0
        has_returns = False
        has_vix = False

        if price_data is not None:
            returns = price_data.get("returns")
            if returns and len(returns) >= 2:
                has_returns = True
                returns_list = [float(r) for r in returns]
                mean_r = sum(returns_list) / len(returns_list)
                variance = sum((r - mean_r) ** 2 for r in returns_list) / len(returns_list)
                std_dev = math.sqrt(variance)
                annualized = std_dev * math.sqrt(252)
                vol_from_returns = min(1.0, annualized / 0.40)

        if macro_data is not None:
            vix = macro_data.get("vix_current")
            if vix is not None:
                has_vix = True
                vol_from_vix = min(1.0, max(0.0, (float(vix) - 5.0) / 45.0))

        if has_returns and has_vix:
            return (vol_from_returns + vol_from_vix) / 2.0
        if has_returns:
            return vol_from_returns
        if has_vix:
            return vol_from_vix
        return 0.0

    @staticmethod
    def _compute_momentum_score(price_data: dict[str, Any] | None) -> float:
        """Compute momentum score from recent returns.

        Returns [-1, 1].  Positive = bullish momentum.
        """
        if price_data is None:
            return 0.0

        returns = price_data.get("returns")
        if not returns or len(returns) < 2:
            return 0.0

        returns_list = [float(r) for r in returns]
        window = min(20, len(returns_list))
        recent = returns_list[-window:]
        avg_return = sum(recent) / len(recent)

        # +-0.5% average daily return maps to +-1.0
        score = max(-1.0, min(1.0, avg_return / 0.005))
        return score

    @staticmethod
    def _compute_macro_score(macro_data: dict[str, Any] | None) -> float:
        """Compute macro-economic score from FRED indicators.

        Returns [-1, 1].  Positive = supportive macro, negative = hostile.
        """
        if macro_data is None:
            return 0.0

        points = 0.0
        max_points = 0.0

        fed_trend = macro_data.get("fed_funds_trend")
        if fed_trend is not None:
            max_points += 1.0
            if fed_trend == "decreasing":
                points += 1.0
            elif fed_trend == "increasing":
                points -= 1.0

        spread = macro_data.get("yield_curve_spread")
        if spread is not None:
            max_points += 1.0
            if spread > 0.5:
                points += 1.0
            elif spread < 0:
                points -= 1.0
            else:
                points += 0.3

        m2_growth = macro_data.get("m2_yoy_growth")
        if m2_growth is not None:
            max_points += 1.0
            if m2_growth > 0.05:
                points += 1.0
            elif m2_growth < 0:
                points -= 1.0
            else:
                points += 0.2

        unemp_trend = macro_data.get("unemployment_trend")
        if unemp_trend is not None:
            max_points += 1.0
            if unemp_trend == "falling":
                points += 1.0
            elif unemp_trend == "rising":
                points -= 1.0

        gdp_growth = macro_data.get("gdp_growth")
        if gdp_growth is not None:
            max_points += 1.0
            if gdp_growth > 0.02:
                points += 1.0
            elif gdp_growth < 0:
                points -= 1.0
            else:
                points += 0.3

        if max_points == 0:
            return 0.0

        return max(-1.0, min(1.0, points / max_points))

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify(
        self,
        trend_score: float,
        volatility_score: float,
        momentum_score: float,
        macro_score: float,
        macro_data: dict[str, Any] | None,
        price_data: dict[str, Any] | None,
    ) -> tuple[str, float]:
        """Map indicator scores to a regime label and confidence.

        Priority logic:
        1. If volatility is extremely high -> HIGH_VOLATILITY
        2. If macro signals are strongly negative + rates rising -> RISK_OFF
        3. If trend & momentum are clearly positive -> BULL
        4. If trend & momentum are clearly negative -> BEAR
        5. Otherwise -> SIDEWAYS
        """
        has_price = price_data is not None and bool(price_data.get("prices"))
        has_macro = macro_data is not None and any(
            macro_data.get(k) is not None
            for k in ("fed_funds_trend", "yield_curve_spread", "m2_yoy_growth",
                       "unemployment_trend", "gdp_growth", "vix_current")
        )

        # No data at all -> sideways with low confidence
        if not has_price and not has_macro:
            return self.SIDEWAYS, 30.0

        # 1. High volatility takes precedence
        if volatility_score >= 0.70:
            confidence = 50.0 + volatility_score * 40.0
            return self.HIGH_VOLATILITY, min(95.0, confidence)

        # 2. Risk-off: negative macro + rising rates
        fed_trend = (macro_data or {}).get("fed_funds_trend")
        if macro_score <= -0.5 and fed_trend == "increasing":
            confidence = 50.0 + abs(macro_score) * 40.0
            return self.RISK_OFF, min(95.0, confidence)
        if macro_score <= -0.7:
            confidence = 45.0 + abs(macro_score) * 35.0
            return self.RISK_OFF, min(90.0, confidence)

        # Combined directional score
        if has_price and has_macro:
            directional = trend_score * 0.4 + momentum_score * 0.3 + macro_score * 0.3
        elif has_price:
            directional = trend_score * 0.55 + momentum_score * 0.45
        else:
            directional = macro_score

        # 3. Bull market
        if directional >= 0.3:
            confidence = 45.0 + directional * 45.0
            return self.BULL, min(95.0, confidence)

        # 4. Bear market
        if directional <= -0.3:
            confidence = 45.0 + abs(directional) * 45.0
            return self.BEAR, min(95.0, confidence)

        # 5. Sideways
        confidence = 40.0 + (1.0 - abs(directional)) * 30.0
        return self.SIDEWAYS, min(85.0, confidence)

    # ------------------------------------------------------------------
    # Description builder
    # ------------------------------------------------------------------

    def _build_description(self, regime: str, confidence: float) -> str:
        """Build a human-readable summary of the regime detection."""
        regime_labels = {
            self.BULL: "Bull Market",
            self.BEAR: "Bear Market",
            self.SIDEWAYS: "Sideways / Range-bound",
            self.HIGH_VOLATILITY: "High Volatility",
            self.RISK_OFF: "Risk-Off Environment",
        }
        label = regime_labels.get(regime, regime)

        parts = [f"Regime: {label} (confidence {confidence:.0f}%)."]

        ind = self._indicators
        if ind.get("trend_score", 0.0) != 0.0:
            direction = "bullish" if ind["trend_score"] > 0 else "bearish"
            parts.append(f"Trend is {direction} ({ind['trend_score']:+.2f}).")

        if ind.get("volatility_score", 0.0) > 0.0:
            if ind["volatility_score"] > 0.5:
                level = "elevated"
            elif ind["volatility_score"] > 0.25:
                level = "moderate"
            else:
                level = "low"
            parts.append(f"Volatility is {level} ({ind['volatility_score']:.2f}).")

        if ind.get("momentum_score", 0.0) != 0.0:
            direction = "positive" if ind["momentum_score"] > 0 else "negative"
            parts.append(f"Momentum is {direction} ({ind['momentum_score']:+.2f}).")

        if ind.get("macro_score", 0.0) != 0.0:
            tone = "supportive" if ind["macro_score"] > 0 else "cautious"
            parts.append(f"Macro environment is {tone} ({ind['macro_score']:+.2f}).")

        return " ".join(parts)
