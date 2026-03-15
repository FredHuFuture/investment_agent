"""Tests for Sprint 14.1: Regime Detection Engine.

Covers RegimeDetector.detect_regime() multi-signal analysis, weight
adjustments, confidence scoring, and graceful handling of missing data.
All tests are purely in-memory -- no network calls.
"""
from __future__ import annotations

import pytest

from engine.regime import RegimeDetector


# ---------------------------------------------------------------------------
# Helpers -- reusable data fixtures
# ---------------------------------------------------------------------------

def _bull_price_data() -> dict:
    """Steadily rising prices with positive returns."""
    prices = [100 + i * 2 for i in range(60)]  # 100 -> 218
    returns = [0.01] * 59  # ~1% daily gain
    return {"prices": prices, "returns": returns}


def _bear_price_data() -> dict:
    """Steadily falling prices with negative returns."""
    prices = [200 - i * 2 for i in range(60)]  # 200 -> 82
    returns = [-0.012] * 59  # ~-1.2% daily loss
    return {"prices": prices, "returns": returns}


def _flat_price_data() -> dict:
    """Flat price action with near-zero returns."""
    prices = [100 + (i % 3 - 1) * 0.2 for i in range(60)]
    returns = [0.0001 * ((-1) ** i) for i in range(59)]
    return {"prices": prices, "returns": returns}


def _high_vol_price_data() -> dict:
    """Large swings in returns -> high volatility."""
    prices = [100 + (i % 5 - 2) * 10 for i in range(60)]
    returns = [0.08 * ((-1) ** i) for i in range(59)]  # +-8% daily
    return {"prices": prices, "returns": returns}


def _positive_macro() -> dict:
    """Supportive macro environment."""
    return {
        "fed_funds_trend": "decreasing",
        "yield_curve_spread": 1.5,
        "m2_yoy_growth": 0.08,
        "unemployment_trend": "falling",
        "gdp_growth": 0.035,
        "vix_current": 13,
    }


def _negative_macro() -> dict:
    """Hostile macro environment."""
    return {
        "fed_funds_trend": "increasing",
        "yield_curve_spread": -0.5,
        "m2_yoy_growth": -0.02,
        "unemployment_trend": "rising",
        "gdp_growth": -0.01,
        "vix_current": 28,
    }


def _neutral_macro() -> dict:
    """Mixed / neutral macro."""
    return {
        "fed_funds_trend": "stable",
        "yield_curve_spread": 0.3,
        "m2_yoy_growth": 0.03,
        "vix_current": 17,
    }


# ---------------------------------------------------------------------------
# 1. Detect bull market
# ---------------------------------------------------------------------------

def test_detect_bull_market() -> None:
    """Strong uptrend + low vol + positive macro -> bull_market."""
    detector = RegimeDetector()
    result = detector.detect_regime(
        macro_data=_positive_macro(),
        price_data=_bull_price_data(),
    )

    assert result["regime"] == RegimeDetector.BULL
    assert result["confidence"] > 50
    assert result["indicators"]["trend_score"] > 0
    assert result["indicators"]["macro_score"] > 0
    assert isinstance(result["description"], str)
    assert len(result["description"]) > 0


# ---------------------------------------------------------------------------
# 2. Detect bear market
# ---------------------------------------------------------------------------

def test_detect_bear_market() -> None:
    """Downtrend + mildly negative macro (no rising rates) -> bear_market.

    Note: strongly negative macro + rising rates triggers risk_off instead,
    so we use a mild negative macro with stable rates to isolate the bear
    classification from the price trend.
    """
    detector = RegimeDetector()
    # Mild negative macro: rates are stable (not increasing), so risk_off
    # path is not triggered.  The strong downtrend dominates.
    mild_negative_macro = {
        "fed_funds_trend": "stable",
        "yield_curve_spread": 0.2,
        "m2_yoy_growth": 0.01,
        "vix_current": 18,
    }
    result = detector.detect_regime(
        macro_data=mild_negative_macro,
        price_data=_bear_price_data(),
    )

    assert result["regime"] == RegimeDetector.BEAR
    assert result["confidence"] > 50
    assert result["indicators"]["trend_score"] < 0


# ---------------------------------------------------------------------------
# 3. Detect sideways
# ---------------------------------------------------------------------------

def test_detect_sideways() -> None:
    """Flat trend, low vol, neutral macro -> sideways."""
    detector = RegimeDetector()
    result = detector.detect_regime(
        macro_data=_neutral_macro(),
        price_data=_flat_price_data(),
    )

    assert result["regime"] == RegimeDetector.SIDEWAYS
    assert 30 <= result["confidence"] <= 85


# ---------------------------------------------------------------------------
# 4. Detect high volatility
# ---------------------------------------------------------------------------

def test_detect_high_volatility() -> None:
    """Any trend + high vol -> high_volatility."""
    detector = RegimeDetector()
    # Use elevated VIX alongside high-vol returns to push score over 0.70
    high_vix_macro = {
        "fed_funds_trend": "stable",
        "yield_curve_spread": 0.3,
        "m2_yoy_growth": 0.03,
        "vix_current": 35,
    }
    result = detector.detect_regime(
        macro_data=high_vix_macro,
        price_data=_high_vol_price_data(),
    )

    assert result["regime"] == RegimeDetector.HIGH_VOLATILITY
    assert result["confidence"] > 50
    assert result["indicators"]["volatility_score"] >= 0.70


# ---------------------------------------------------------------------------
# 5. Detect risk_off
# ---------------------------------------------------------------------------

def test_detect_risk_off() -> None:
    """Rising rates + weak macro -> risk_off."""
    detector = RegimeDetector()
    macro = _negative_macro()
    # Make sure VIX is not so extreme that it triggers high_volatility first
    macro["vix_current"] = 22
    result = detector.detect_regime(
        macro_data=macro,
        price_data=_flat_price_data(),
    )

    assert result["regime"] == RegimeDetector.RISK_OFF
    assert result["confidence"] > 45
    assert result["indicators"]["macro_score"] < 0


# ---------------------------------------------------------------------------
# 6. Handle missing price data gracefully
# ---------------------------------------------------------------------------

def test_missing_price_data() -> None:
    """When price_data is None, detection should still work with macro only."""
    detector = RegimeDetector()
    result = detector.detect_regime(
        macro_data=_positive_macro(),
        price_data=None,
    )

    assert result["regime"] in {
        RegimeDetector.BULL,
        RegimeDetector.SIDEWAYS,
        RegimeDetector.BEAR,
        RegimeDetector.HIGH_VOLATILITY,
        RegimeDetector.RISK_OFF,
    }
    assert result["indicators"]["trend_score"] == 0.0
    assert result["indicators"]["momentum_score"] == 0.0
    assert result["confidence"] > 0


# ---------------------------------------------------------------------------
# 7. Handle missing macro data gracefully
# ---------------------------------------------------------------------------

def test_missing_macro_data() -> None:
    """When macro_data is None, detection should work with price only."""
    detector = RegimeDetector()
    result = detector.detect_regime(
        macro_data=None,
        price_data=_bull_price_data(),
    )

    assert result["regime"] in {
        RegimeDetector.BULL,
        RegimeDetector.SIDEWAYS,
        RegimeDetector.BEAR,
        RegimeDetector.HIGH_VOLATILITY,
        RegimeDetector.RISK_OFF,
    }
    assert result["indicators"]["macro_score"] == 0.0
    assert result["confidence"] > 0


# ---------------------------------------------------------------------------
# 8. Handle all None inputs
# ---------------------------------------------------------------------------

def test_all_none_inputs() -> None:
    """Both inputs None -> sideways with low confidence."""
    detector = RegimeDetector()
    result = detector.detect_regime(macro_data=None, price_data=None)

    assert result["regime"] == RegimeDetector.SIDEWAYS
    assert result["confidence"] == 30.0
    assert result["indicators"]["trend_score"] == 0.0
    assert result["indicators"]["volatility_score"] == 0.0
    assert result["indicators"]["momentum_score"] == 0.0
    assert result["indicators"]["macro_score"] == 0.0


# ---------------------------------------------------------------------------
# 9. Weight adjustments for each regime
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("regime", [
    RegimeDetector.BULL,
    RegimeDetector.BEAR,
    RegimeDetector.SIDEWAYS,
    RegimeDetector.HIGH_VOLATILITY,
    RegimeDetector.RISK_OFF,
])
def test_weight_adjustments_known_regimes(regime: str) -> None:
    """Each known regime returns specific non-empty adjustments."""
    detector = RegimeDetector()
    adjustments = detector.get_weight_adjustments(regime)

    assert isinstance(adjustments, dict)
    assert "TechnicalAgent" in adjustments
    assert "FundamentalAgent" in adjustments
    assert "MacroAgent" in adjustments
    assert "SentimentAgent" in adjustments
    # All multipliers should be positive
    for val in adjustments.values():
        assert val > 0


def test_weight_adjustments_unknown_regime() -> None:
    """Unknown regime string returns neutral (all 1.0) adjustments."""
    detector = RegimeDetector()
    adjustments = detector.get_weight_adjustments("unknown_regime")

    assert adjustments == {
        "TechnicalAgent": 1.0,
        "FundamentalAgent": 1.0,
        "MacroAgent": 1.0,
        "SentimentAgent": 1.0,
    }


def test_bull_weight_adjustments_values() -> None:
    """Bull market should boost FundamentalAgent and reduce MacroAgent."""
    detector = RegimeDetector()
    adj = detector.get_weight_adjustments(RegimeDetector.BULL)

    assert adj["FundamentalAgent"] > 1.0
    assert adj["MacroAgent"] < 1.0


def test_bear_weight_adjustments_values() -> None:
    """Bear market should boost MacroAgent and reduce FundamentalAgent."""
    detector = RegimeDetector()
    adj = detector.get_weight_adjustments(RegimeDetector.BEAR)

    assert adj["MacroAgent"] > 1.0
    assert adj["FundamentalAgent"] < 1.0


def test_high_vol_weight_adjustments_values() -> None:
    """High volatility should boost TechnicalAgent."""
    detector = RegimeDetector()
    adj = detector.get_weight_adjustments(RegimeDetector.HIGH_VOLATILITY)

    assert adj["TechnicalAgent"] > 1.0
    assert adj["FundamentalAgent"] < 1.0


# ---------------------------------------------------------------------------
# 10. Confidence scoring
# ---------------------------------------------------------------------------

def test_confidence_range() -> None:
    """Confidence should always be in the 0-100 range."""
    detector = RegimeDetector()

    test_cases = [
        (None, None),
        (_positive_macro(), _bull_price_data()),
        (_negative_macro(), _bear_price_data()),
        (_neutral_macro(), _flat_price_data()),
        (_neutral_macro(), _high_vol_price_data()),
        (_negative_macro(), _flat_price_data()),
    ]

    for macro, price in test_cases:
        result = detector.detect_regime(macro_data=macro, price_data=price)
        assert 0 <= result["confidence"] <= 100, (
            f"Confidence {result['confidence']} out of range for "
            f"regime={result['regime']}"
        )


def test_strong_signal_higher_confidence() -> None:
    """Stronger signals should produce higher confidence than weak ones."""
    detector = RegimeDetector()

    strong = detector.detect_regime(
        macro_data=_positive_macro(),
        price_data=_bull_price_data(),
    )
    weak = detector.detect_regime(
        macro_data=_neutral_macro(),
        price_data=_flat_price_data(),
    )

    assert strong["confidence"] > weak["confidence"]


# ---------------------------------------------------------------------------
# 11. Return structure validation
# ---------------------------------------------------------------------------

def test_return_structure() -> None:
    """detect_regime should return all expected keys with correct types."""
    detector = RegimeDetector()
    result = detector.detect_regime(
        macro_data=_positive_macro(),
        price_data=_bull_price_data(),
    )

    assert "regime" in result
    assert "confidence" in result
    assert "indicators" in result
    assert "description" in result

    assert isinstance(result["regime"], str)
    assert isinstance(result["confidence"], float)
    assert isinstance(result["indicators"], dict)
    assert isinstance(result["description"], str)

    indicators = result["indicators"]
    for key in ("trend_score", "volatility_score", "momentum_score", "macro_score"):
        assert key in indicators
        assert isinstance(indicators[key], float)


# ---------------------------------------------------------------------------
# 12. Indicator score ranges
# ---------------------------------------------------------------------------

def test_indicator_score_ranges() -> None:
    """All indicator sub-scores should stay within documented ranges."""
    detector = RegimeDetector()

    test_cases = [
        (_positive_macro(), _bull_price_data()),
        (_negative_macro(), _bear_price_data()),
        (None, _high_vol_price_data()),
        (_neutral_macro(), None),
        (None, None),
    ]

    for macro, price in test_cases:
        result = detector.detect_regime(macro_data=macro, price_data=price)
        ind = result["indicators"]

        assert -1.0 <= ind["trend_score"] <= 1.0
        assert 0.0 <= ind["volatility_score"] <= 1.0
        assert -1.0 <= ind["momentum_score"] <= 1.0
        assert -1.0 <= ind["macro_score"] <= 1.0


# ---------------------------------------------------------------------------
# 13. Empty price / returns lists
# ---------------------------------------------------------------------------

def test_empty_prices_list() -> None:
    """Empty prices list should be handled like missing data."""
    detector = RegimeDetector()
    result = detector.detect_regime(
        macro_data=_neutral_macro(),
        price_data={"prices": [], "returns": []},
    )

    assert result["indicators"]["trend_score"] == 0.0
    assert result["indicators"]["momentum_score"] == 0.0


def test_too_few_prices() -> None:
    """Fewer than 5 prices should result in zero trend score."""
    detector = RegimeDetector()
    result = detector.detect_regime(
        macro_data=None,
        price_data={"prices": [100, 101, 102], "returns": [0.01, 0.01]},
    )

    assert result["indicators"]["trend_score"] == 0.0


# ---------------------------------------------------------------------------
# 14. Description contains regime label
# ---------------------------------------------------------------------------

def test_description_mentions_regime() -> None:
    """Description should mention the detected regime label."""
    detector = RegimeDetector()

    result = detector.detect_regime(
        macro_data=_positive_macro(),
        price_data=_bull_price_data(),
    )
    assert "Bull Market" in result["description"]

    result = detector.detect_regime(
        macro_data=None,
        price_data=None,
    )
    assert "Sideways" in result["description"]
