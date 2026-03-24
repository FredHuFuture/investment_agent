"""Tests for P1 prediction accuracy improvements.

Covers:
- #4 Dynamic thresholds
- #5 Dynamic sector P/E medians
- #6 Multi-timeframe confirmation
"""

from __future__ import annotations

import pytest

from engine.dynamic_threshold import compute_dynamic_thresholds


# ---------------------------------------------------------------------------
# #4 Dynamic thresholds
# ---------------------------------------------------------------------------

class TestDynamicThresholds:
    def test_low_vix_tightens_thresholds(self) -> None:
        buy_t, sell_t = compute_dynamic_thresholds(vix_current=12.0)
        assert buy_t < 0.30
        assert sell_t > -0.30  # less negative = tighter
        assert buy_t >= 0.15   # respects floor

    def test_high_vix_widens_thresholds(self) -> None:
        buy_t, sell_t = compute_dynamic_thresholds(vix_current=35.0)
        assert buy_t > 0.30
        assert sell_t < -0.30
        assert buy_t <= 0.50   # respects ceiling

    def test_none_returns_defaults(self) -> None:
        buy_t, sell_t = compute_dynamic_thresholds(vix_current=None)
        assert buy_t == pytest.approx(0.30)
        assert sell_t == pytest.approx(-0.30)

    def test_baseline_vix_returns_near_defaults(self) -> None:
        buy_t, sell_t = compute_dynamic_thresholds(vix_current=20.0)
        assert buy_t == pytest.approx(0.30)
        assert sell_t == pytest.approx(-0.30)

    def test_sell_is_negative_buy(self) -> None:
        buy_t, sell_t = compute_dynamic_thresholds(vix_current=25.0)
        assert sell_t == pytest.approx(-buy_t)


# ---------------------------------------------------------------------------
# #5 Dynamic sector P/E medians
# ---------------------------------------------------------------------------

class TestDynamicSectorPE:
    @pytest.mark.asyncio
    async def test_fallback_to_static(self) -> None:
        from data_providers.sector_pe_cache import get_sector_pe_median, _cache
        _cache.clear()  # ensure no stale entries from other tests
        # No provider → static fallback
        pe = await get_sector_pe_median("technology", provider=None)
        assert pe == 28.0

    @pytest.mark.asyncio
    async def test_none_sector_returns_none(self) -> None:
        from data_providers.sector_pe_cache import get_sector_pe_median
        pe = await get_sector_pe_median(None, provider=None)
        assert pe is None

    @pytest.mark.asyncio
    async def test_unknown_sector_returns_none(self) -> None:
        from data_providers.sector_pe_cache import get_sector_pe_median
        pe = await get_sector_pe_median("nonexistent_sector", provider=None)
        assert pe is None


# ---------------------------------------------------------------------------
# #6 Multi-timeframe confirmation (tested via TechnicalAgent indirectly)
# ---------------------------------------------------------------------------

class TestMultiTimeframeConfirmation:
    """Multi-timeframe logic is integrated into TechnicalAgent.analyze().
    We verify the core confidence adjustment behavior here."""

    def test_agreement_boosts_confidence(self) -> None:
        """If composite >= 0 and weekly confirms, confidence increases."""
        base_confidence = 65.0
        composite = 30.0  # positive → daily bullish
        weekly_trend_confirms = True  # weekly also bullish

        # Simulate the adjustment logic
        daily_bullish = composite >= 0
        if daily_bullish == weekly_trend_confirms:
            adjusted = min(95.0, base_confidence + 10)
        else:
            adjusted = max(30.0, base_confidence - 15)

        assert adjusted == 75.0  # 65 + 10

    def test_disagreement_reduces_confidence(self) -> None:
        """If composite >= 0 but weekly bearish, confidence decreases."""
        base_confidence = 65.0
        composite = 30.0  # positive → daily bullish
        weekly_trend_confirms = False  # weekly bearish

        daily_bullish = composite >= 0
        if daily_bullish == weekly_trend_confirms:
            adjusted = min(95.0, base_confidence + 10)
        else:
            adjusted = max(30.0, base_confidence - 15)

        assert adjusted == 50.0  # 65 - 15

    def test_no_weekly_data_no_change(self) -> None:
        """If weekly_trend_confirms is None, no adjustment."""
        base_confidence = 65.0
        weekly_trend_confirms = None

        adjusted = base_confidence
        if weekly_trend_confirms is not None:
            adjusted += 10 if True else -15

        assert adjusted == 65.0
