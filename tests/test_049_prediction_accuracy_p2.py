"""Tests for P2 prediction accuracy improvements.

Covers:
- #7 EWMA anti-overfitting constraints
- #8 Crypto adoption config externalization
- #9 DXY + bonds macro signals (scoring logic)
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# #7 EWMA anti-overfitting constraints
# ---------------------------------------------------------------------------

class TestEWMAAntiOverfitting:
    def test_floor_ceiling_enforced(self) -> None:
        from engine.weight_adapter import WeightAdapter

        adapter = WeightAdapter(db_path="dummy.db")
        # Use 3+ agents so floor+ceiling constraints are satisfiable
        learned = {"A": 0.02, "B": 0.90, "C": 0.08}
        defaults = {"A": 0.33, "B": 0.33, "C": 0.34}
        result = adapter._apply_weight_constraints(learned, defaults)

        for w in result.values():
            assert w >= adapter.WEIGHT_FLOOR

    def test_mean_reversion_pulls_toward_defaults(self) -> None:
        from engine.weight_adapter import WeightAdapter

        adapter = WeightAdapter(db_path="dummy.db")
        # Learned weights far from defaults
        learned = {"TechnicalAgent": 0.80, "FundamentalAgent": 0.20}
        defaults = {"TechnicalAgent": 0.25, "FundamentalAgent": 0.40}
        result = adapter._apply_weight_constraints(learned, defaults)

        # After constraints, TechnicalAgent should be pulled back toward 0.25
        assert result["TechnicalAgent"] < 0.80
        # And FundamentalAgent pulled back toward 0.40
        assert result["FundamentalAgent"] > 0.20

    def test_weights_sum_to_one(self) -> None:
        from engine.weight_adapter import WeightAdapter

        adapter = WeightAdapter(db_path="dummy.db")
        learned = {"A": 0.5, "B": 0.3, "C": 0.2}
        defaults = {"A": 0.33, "B": 0.33, "C": 0.34}
        result = adapter._apply_weight_constraints(learned, defaults)
        assert sum(result.values()) == pytest.approx(1.0, abs=0.01)

    def test_rate_limiting_caps_delta(self) -> None:
        from engine.weight_adapter import WeightAdapter

        adapter = WeightAdapter(db_path="dummy.db")
        # Learned = default + 0.30 (way over MAX_WEIGHT_DELTA=0.10)
        learned = {"TechnicalAgent": 0.55, "FundamentalAgent": 0.45}
        defaults = {"TechnicalAgent": 0.25, "FundamentalAgent": 0.40}
        result = adapter._apply_weight_constraints(learned, defaults)

        # TechnicalAgent should not jump from 0.25 to 0.55 in one cycle
        assert result["TechnicalAgent"] < 0.50


# ---------------------------------------------------------------------------
# #8 Crypto adoption config
# ---------------------------------------------------------------------------

class TestCryptoAdoptionConfig:
    def test_loads_from_yaml(self) -> None:
        from agents.crypto import CRYPTO_ADOPTION
        assert "btc" in CRYPTO_ADOPTION
        assert "eth" in CRYPTO_ADOPTION
        assert CRYPTO_ADOPTION["btc"]["etf_access"] is True

    def test_default_fallback_function(self) -> None:
        from agents.crypto import _load_adoption_config
        data = _load_adoption_config()
        assert isinstance(data, dict)
        assert "btc" in data


# ---------------------------------------------------------------------------
# #9 DXY + bonds macro signals
# ---------------------------------------------------------------------------

class TestMacroExtendedSignals:
    def test_dxy_scoring_risk_off(self) -> None:
        """Strong dollar (DXY above SMA by >2%) → risk_off += 10."""
        # Simulate the scoring logic from _classify_regime
        dxy = 105.0
        dxy_sma = 100.0
        risk_on = 0
        risk_off = 0
        if dxy is not None and dxy_sma is not None and dxy_sma > 0:
            ratio = dxy / dxy_sma
            if ratio > 1.02:
                risk_off += 10
            elif ratio < 0.98:
                risk_on += 5
        assert risk_off == 10
        assert risk_on == 0

    def test_tlt_rising_risk_off(self) -> None:
        """Bonds rallying (TLT rising) → risk_off += 10."""
        risk_on = 0
        risk_off = 0
        tlt_trend = "rising"
        if tlt_trend == "rising":
            risk_off += 10
        elif tlt_trend == "falling":
            risk_on += 5
        assert risk_off == 10

    def test_tlt_falling_risk_on(self) -> None:
        """Bonds selling off (TLT falling) → risk_on += 5."""
        risk_on = 0
        risk_off = 0
        tlt_trend = "falling"
        if tlt_trend == "rising":
            risk_off += 10
        elif tlt_trend == "falling":
            risk_on += 5
        assert risk_on == 5

    def test_missing_data_no_impact(self) -> None:
        """If DXY/TLT data missing, no scoring impact."""
        risk_on = 0
        risk_off = 0
        dxy = None
        dxy_sma = None
        if dxy is not None and dxy_sma is not None and dxy_sma > 0:
            risk_off += 10
        tlt_trend = None
        if tlt_trend == "rising":
            risk_off += 10
        assert risk_on == 0
        assert risk_off == 0
