from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from agents.base import BaseAgent
from agents.models import AgentInput, AgentOutput, Regime, Signal

# BTC halving dates (most recent first)
HALVING_DATES = [
    datetime(2024, 4, 19, tzinfo=timezone.utc),
    datetime(2020, 5, 11, tzinfo=timezone.utc),
    datetime(2016, 7, 9, tzinfo=timezone.utc),
    datetime(2012, 11, 28, tzinfo=timezone.utc),
]

HALVING_CYCLE_MONTHS = 48  # ~4 years between halvings

# Static adoption constants (Phase 1)
CRYPTO_ADOPTION: dict[str, dict[str, Any]] = {
    "btc": {"age_years": 16, "etf_access": True, "regulatory": "FAVORABLE", "bear_survivals": 5},
    "eth": {"age_years": 10, "etf_access": True, "regulatory": "NEUTRAL", "bear_survivals": 4},
}

# Factor weights — v2: network_adoption reduced from 10% to 5% because it uses
# hardcoded static constants (age, ETF status) that act as a fixed bias rather
# than a dynamic signal.  The freed 5% goes to momentum (+2.5%) and volatility
# (+2.5%) which are data-driven.
FACTOR_WEIGHTS = {
    "market_structure": 0.15,
    "momentum_trend": 0.225,
    "volatility_risk": 0.175,
    "liquidity_volume": 0.10,
    "macro_correlation": 0.15,
    "network_adoption": 0.05,
    "cycle_timing": 0.15,
}


class CryptoAgent(BaseAgent):
    """Dedicated 7-factor scoring agent for cryptocurrency assets."""

    @property
    def name(self) -> str:
        return "CryptoAgent"

    def supported_asset_types(self) -> list[str]:
        return ["btc", "eth"]

    async def analyze(self, agent_input: AgentInput) -> AgentOutput:
        self._validate_asset_type(agent_input)

        warnings: list[str] = []
        ticker = agent_input.ticker
        asset_type = agent_input.asset_type

        # Fetch price history
        try:
            price_df = await self._provider.get_price_history(ticker, period="1y", interval="1d")
        except Exception as exc:
            warnings.append(f"Price history unavailable: {exc}")
            return self._hold_fallback(ticker, warnings)

        if price_df is None or price_df.empty or len(price_df) < 30:
            warnings.append("Insufficient price data (need at least 30 days).")
            return self._hold_fallback(ticker, warnings)

        # Fetch key stats (market cap, supply, volume)
        key_stats: dict[str, Any] = {}
        try:
            key_stats = await self._provider.get_key_stats(ticker)
        except Exception as exc:
            warnings.append(f"Key stats unavailable: {exc}")

        # Fetch S&P 500 for correlation (best-effort)
        spy_df: pd.DataFrame | None = None
        try:
            spy_df = await self._fetch_spy_prices()
        except Exception as exc:
            warnings.append(f"S&P 500 data unavailable: {exc}")

        # Fetch VIX (best-effort)
        vix_value: float | None = None
        try:
            vix_value = await self._fetch_vix()
        except Exception as exc:
            warnings.append(f"VIX data unavailable: {exc}")

        # Compute each factor score
        close = price_df["Close"]
        volume = price_df["Volume"]

        f1, f1_metrics = self._score_market_structure(asset_type, key_stats, warnings)
        f2, f2_metrics = self._score_momentum_trend(close, warnings, key_stats=key_stats)
        f3, f3_metrics = self._score_volatility_risk(close, warnings)
        f4, f4_metrics = self._score_liquidity_volume(close, volume, key_stats, warnings)
        f5, f5_metrics = self._score_macro_correlation(close, spy_df, vix_value, warnings)
        f6, f6_metrics = self._score_network_adoption(asset_type, warnings)
        f7, f7_metrics = self._score_cycle_timing(close, volume, vix_value, warnings)

        # Composite score
        composite = (
            f1 * FACTOR_WEIGHTS["market_structure"]
            + f2 * FACTOR_WEIGHTS["momentum_trend"]
            + f3 * FACTOR_WEIGHTS["volatility_risk"]
            + f4 * FACTOR_WEIGHTS["liquidity_volume"]
            + f5 * FACTOR_WEIGHTS["macro_correlation"]
            + f6 * FACTOR_WEIGHTS["network_adoption"]
            + f7 * FACTOR_WEIGHTS["cycle_timing"]
        )

        # Signal determination
        if composite >= 20:
            signal = Signal.BUY
        elif composite <= -20:
            signal = Signal.SELL
        else:
            signal = Signal.HOLD

        # Confidence (same formula as FundamentalAgent)
        confidence = 50 + (abs(composite) - 20) * (40 / 80)
        confidence = max(30.0, min(90.0, confidence))

        # Regime from macro/cycle context
        regime = self._determine_regime(f5, f7, vix_value)

        # Build reasoning
        reasoning = self._build_reasoning(
            f1, f2, f3, f4, f5, f6, f7, composite, regime, asset_type,
        )

        # Collect all metrics
        metrics: dict[str, Any] = {
            "market_structure_score": float(f1),
            "momentum_trend_score": float(f2),
            "volatility_risk_score": float(f3),
            "liquidity_volume_score": float(f4),
            "macro_correlation_score": float(f5),
            "network_adoption_score": float(f6),
            "cycle_timing_score": float(f7),
            "composite_score": float(composite),
            "regime": regime.value,
            "current_price": float(close.iloc[-1]),
        }
        metrics.update(f1_metrics)
        metrics.update(f2_metrics)
        metrics.update(f3_metrics)
        metrics.update(f4_metrics)
        metrics.update(f5_metrics)
        metrics.update(f6_metrics)
        metrics.update(f7_metrics)

        return AgentOutput(
            agent_name=self.name,
            ticker=ticker,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            metrics=metrics,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Factor 1: Market Structure (15%)
    # ------------------------------------------------------------------

    def _score_market_structure(
        self,
        asset_type: str,
        key_stats: dict[str, Any],
        warnings: list[str],
    ) -> tuple[float, dict[str, Any]]:
        score = 0.0
        metrics: dict[str, Any] = {}

        market_cap = _to_float(key_stats.get("market_cap"))
        metrics["market_cap"] = market_cap

        # BTC dominance proxy: we use the market cap rank heuristic
        # BTC = rank #1, ETH = rank #2
        if asset_type == "btc":
            score += 10  # flight to quality for BTC
            metrics["dominance_signal"] = "positive"
        else:
            # ETH: BTC dominance high means risk-off rotation to BTC
            score -= 5
            metrics["dominance_signal"] = "neutral"

        # Supply scarcity
        circulating = _to_float(key_stats.get("circulatingSupply"))
        max_supply = _to_float(key_stats.get("maxSupply"))
        metrics["circulating_supply"] = circulating
        metrics["max_supply"] = max_supply

        if circulating is not None and max_supply is not None and max_supply > 0:
            supply_ratio = circulating / max_supply
            metrics["supply_ratio"] = supply_ratio
            if supply_ratio > 0.90:
                score += 10  # scarcity premium
            elif supply_ratio > 0.50:
                score += 5
            # else: 0 (neutral)
        elif asset_type == "btc":
            # BTC has known supply dynamics even if yfinance misses it
            metrics["supply_ratio"] = 0.94  # ~19.8M / 21M
            score += 10
        else:
            metrics["supply_ratio"] = None
            # ETH has unlimited supply -- neutral
            score += 0

        return _clamp(score), metrics

    # ------------------------------------------------------------------
    # Factor 2: Momentum & Trend (20%)
    # ------------------------------------------------------------------

    def _score_momentum_trend(
        self,
        close: pd.Series,
        warnings: list[str],
        key_stats: dict[str, Any] | None = None,
    ) -> tuple[float, dict[str, Any]]:
        score = 0.0
        metrics: dict[str, Any] = {}
        n = len(close)
        current_price = float(close.iloc[-1])

        # 3-month return (63 trading days)
        if n >= 63:
            ret_3m = (current_price / float(close.iloc[-63]) - 1) * 100
            metrics["return_3m_pct"] = ret_3m
            score += _clamp(ret_3m * 0.3)  # scale contribution
        else:
            metrics["return_3m_pct"] = None
            warnings.append("Insufficient data for 3-month return.")

        # 6-month return (126 trading days)
        if n >= 126:
            ret_6m = (current_price / float(close.iloc[-126]) - 1) * 100
            metrics["return_6m_pct"] = ret_6m
            score += _clamp(ret_6m * 0.2)
        else:
            metrics["return_6m_pct"] = None

        # 12-month return (252 trading days)
        if n >= 252:
            ret_12m = (current_price / float(close.iloc[-252]) - 1) * 100
            metrics["return_12m_pct"] = ret_12m
            score += _clamp(ret_12m * 0.1)
        else:
            metrics["return_12m_pct"] = None

        # Distance from ATH — prefer key_stats '52w_high' (covers full 52 weeks)
        # over close.max() (only covers the fetched 1y window which may be shorter).
        ath_from_stats = _to_float(key_stats.get("52w_high")) if key_stats else None
        ath_from_data = float(close.max())
        if ath_from_stats is not None and ath_from_stats > ath_from_data:
            ath = ath_from_stats
        else:
            ath = ath_from_data
            if ath_from_stats is None:
                warnings.append(
                    "ATH based on available price window only (not true all-time high)."
                )
        ath_distance = (current_price / ath - 1) * 100 if ath > 0 else 0
        metrics["ath_distance_pct"] = ath_distance
        if ath_distance > -10:
            score += 15  # near ATH, strong trend
        elif ath_distance < -50:
            score -= 10  # deep correction
        elif ath_distance < -30:
            score -= 5

        # 200 DMA position
        if n >= 200:
            sma200 = float(close.rolling(200).mean().iloc[-1])
            metrics["sma_200"] = sma200
            if current_price > sma200:
                score += 10
            else:
                score -= 10
        else:
            metrics["sma_200"] = None
            warnings.append("Insufficient data for 200-day SMA.")

        return _clamp(score), metrics

    # ------------------------------------------------------------------
    # Factor 3: Volatility & Risk (15%)
    # ------------------------------------------------------------------

    def _score_volatility_risk(
        self,
        close: pd.Series,
        warnings: list[str],
    ) -> tuple[float, dict[str, Any]]:
        score = 0.0
        metrics: dict[str, Any] = {}
        n = len(close)

        daily_returns = close.pct_change().dropna()

        # 30-day annualized volatility
        if len(daily_returns) >= 30:
            vol_30d = float(daily_returns.iloc[-30:].std() * np.sqrt(252)) * 100
            metrics["volatility_30d_pct"] = vol_30d
            if vol_30d < 40:
                score += 10  # low for crypto
            elif vol_30d > 80:
                score -= 15  # extreme
            # else: 0 (normal 40-80%)
        else:
            metrics["volatility_30d_pct"] = None
            warnings.append("Insufficient data for 30-day volatility.")

        # Max drawdown (90 days)
        if n >= 90:
            recent_close = close.iloc[-90:]
            running_max = recent_close.cummax()
            drawdowns = (recent_close - running_max) / running_max
            max_dd = float(drawdowns.min()) * 100
            metrics["max_drawdown_90d_pct"] = max_dd
            if max_dd > -15:
                score += 10  # shallow drawdown
            elif max_dd < -30:
                score -= 15  # deep drawdown
        else:
            metrics["max_drawdown_90d_pct"] = None

        # Sharpe ratio (90 days)
        if len(daily_returns) >= 90:
            recent_returns = daily_returns.iloc[-90:]
            ann_return = float(recent_returns.mean()) * 252
            ann_vol = float(recent_returns.std()) * np.sqrt(252)
            risk_free = 0.05  # 5% risk-free rate assumption
            sharpe = (ann_return - risk_free) / ann_vol if ann_vol > 0 else 0
            metrics["sharpe_90d"] = sharpe
            if sharpe > 1.5:
                score += 15
            elif sharpe < 0:
                score -= 10
        else:
            metrics["sharpe_90d"] = None

        # Recovery time: days since last 20%+ drawdown
        if n >= 30:
            running_max_full = close.cummax()
            dd_full = (close - running_max_full) / running_max_full
            big_drops = dd_full[dd_full <= -0.20]
            if len(big_drops) > 0:
                last_big_drop_idx = big_drops.index[-1]
                days_since = len(close.loc[last_big_drop_idx:]) - 1
                metrics["recovery_days"] = days_since
                if days_since > 60:
                    score += 5  # stability
                elif days_since < 14:
                    score -= 10  # very recent big drop
            else:
                metrics["recovery_days"] = None  # no 20%+ drawdown in data
                score += 5  # no major drawdown is positive
        else:
            metrics["recovery_days"] = None

        return _clamp(score), metrics

    # ------------------------------------------------------------------
    # Factor 4: Liquidity & Volume (10%)
    # ------------------------------------------------------------------

    def _score_liquidity_volume(
        self,
        close: pd.Series,
        volume: pd.Series,
        key_stats: dict[str, Any],
        warnings: list[str],
    ) -> tuple[float, dict[str, Any]]:
        score = 0.0
        metrics: dict[str, Any] = {}
        n = len(volume)

        # Average daily volume (20-day) in USD
        if n >= 20:
            recent_volume = volume.iloc[-20:]
            recent_close = close.iloc[-20:]
            avg_usd_volume = float((recent_volume * recent_close).mean())
            metrics["avg_daily_volume_usd"] = avg_usd_volume
            if avg_usd_volume > 1_000_000_000:
                score += 10  # highly liquid
            elif avg_usd_volume > 100_000_000:
                score += 5
        else:
            metrics["avg_daily_volume_usd"] = None

        # Volume trend: 5-day avg vs 20-day avg
        if n >= 20:
            vol_5d = float(volume.iloc[-5:].mean())
            vol_20d = float(volume.iloc[-20:].mean())
            if vol_20d > 0:
                volume_trend = vol_5d / vol_20d
                metrics["volume_trend"] = volume_trend
                if volume_trend > 1.5:
                    score += 5  # increasing interest
                elif volume_trend < 0.5:
                    score -= 5  # fading interest
            else:
                metrics["volume_trend"] = None
        else:
            metrics["volume_trend"] = None

        # Turnover ratio: volume / market cap
        market_cap = _to_float(key_stats.get("market_cap"))
        if market_cap is not None and market_cap > 0 and n >= 1:
            daily_volume_usd = float(volume.iloc[-1] * close.iloc[-1])
            turnover = daily_volume_usd / market_cap * 100
            metrics["turnover_pct"] = turnover
            if turnover > 5:
                score += 5  # active trading
        else:
            metrics["turnover_pct"] = None

        return _clamp(score), metrics

    # ------------------------------------------------------------------
    # Factor 5: Macro & Correlation (15%)
    # ------------------------------------------------------------------

    def _score_macro_correlation(
        self,
        close: pd.Series,
        spy_df: pd.DataFrame | None,
        vix_value: float | None,
        warnings: list[str],
    ) -> tuple[float, dict[str, Any]]:
        score = 0.0
        metrics: dict[str, Any] = {}

        # S&P 500 correlation (90-day rolling)
        if spy_df is not None and not spy_df.empty and len(close) >= 90:
            try:
                # Align dates
                crypto_returns = close.pct_change().dropna()
                spy_close = spy_df["Close"]
                spy_returns = spy_close.pct_change().dropna()

                # Find overlapping dates
                common_idx = crypto_returns.index.intersection(spy_returns.index)
                if len(common_idx) >= 60:
                    cr = crypto_returns.loc[common_idx].iloc[-90:]
                    sr = spy_returns.loc[common_idx].iloc[-90:]
                    if len(cr) >= 30 and len(sr) >= 30:
                        correlation = float(cr.corr(sr))
                        metrics["sp500_correlation_90d"] = correlation
                        if not math.isnan(correlation):
                            if correlation < 0.3:
                                score += 10  # diversification value
                            elif correlation > 0.7:
                                score -= 5  # no diversification benefit
                        else:
                            metrics["sp500_correlation_90d"] = None
                    else:
                        metrics["sp500_correlation_90d"] = None
                        warnings.append("Insufficient overlapping data for S&P correlation.")
                else:
                    metrics["sp500_correlation_90d"] = None
                    warnings.append("Insufficient overlapping dates for S&P correlation.")
            except Exception as exc:
                metrics["sp500_correlation_90d"] = None
                warnings.append(f"S&P correlation calculation failed: {exc}")
        else:
            metrics["sp500_correlation_90d"] = None

        # VIX sensitivity
        metrics["vix_level"] = vix_value
        if vix_value is not None:
            if vix_value > 30:
                score -= 10  # risk-off contagion
            elif vix_value < 15:
                score += 5  # low vol environment, good for risk assets
        else:
            warnings.append("VIX unavailable for macro scoring.")

        # Rate environment (simplified: use VIX as proxy since we don't
        # import FredProvider here -- keeping the agent self-contained)
        # A falling VIX environment correlates with accommodative policy
        # This is a simplification; full rate data would come from MacroAgent
        metrics["rate_environment"] = None  # placeholder for FRED integration

        return _clamp(score), metrics

    # ------------------------------------------------------------------
    # Factor 6: Network & Adoption (10%)
    # ------------------------------------------------------------------

    def _score_network_adoption(
        self,
        asset_type: str,
        warnings: list[str],
    ) -> tuple[float, dict[str, Any]]:
        score = 0.0
        metrics: dict[str, Any] = {}

        adoption = CRYPTO_ADOPTION.get(asset_type)
        if adoption is None:
            warnings.append(f"No adoption data for {asset_type}.")
            return 0.0, metrics

        metrics["age_years"] = adoption["age_years"]
        metrics["etf_access"] = adoption["etf_access"]
        metrics["regulatory_status"] = adoption["regulatory"]
        metrics["bear_survivals"] = adoption["bear_survivals"]
        metrics["adoption_data_source"] = "static"
        warnings.append(
            "Network adoption uses static constants (not live chain data). "
            "Factor weight reduced to 5%."
        )

        # Age > 10 years: +10 (battle-tested)
        if adoption["age_years"] > 10:
            score += 10
        elif adoption["age_years"] > 5:
            score += 5

        # ETF access: +10 (institutional adoption)
        if adoption["etf_access"]:
            score += 10

        # Regulatory status
        reg = adoption["regulatory"]
        if reg == "FAVORABLE":
            score += 5
        elif reg == "HOSTILE":
            score -= 10

        # Bear market survivals >= 4: +10 (antifragile)
        if adoption["bear_survivals"] >= 4:
            score += 10
        elif adoption["bear_survivals"] >= 2:
            score += 5

        return _clamp(score), metrics

    # ------------------------------------------------------------------
    # Factor 7: Cycle & Timing (15%)
    # ------------------------------------------------------------------

    def _score_cycle_timing(
        self,
        close: pd.Series,
        volume: pd.Series,
        vix_value: float | None,
        warnings: list[str],
    ) -> tuple[float, dict[str, Any]]:
        score = 0.0
        metrics: dict[str, Any] = {}

        now = datetime.now(timezone.utc)

        # BTC halving cycle position
        last_halving = HALVING_DATES[0]  # most recent
        months_since = (now - last_halving).days / 30.44
        cycle_position = months_since / HALVING_CYCLE_MONTHS
        cycle_position = min(1.0, max(0.0, cycle_position))
        metrics["halving_cycle_position"] = cycle_position
        metrics["months_since_halving"] = round(months_since, 1)

        if cycle_position <= 0.25:
            # Early cycle (0-12 months post-halving): +15
            score += 15
            metrics["cycle_phase"] = "early"
        elif cycle_position <= 0.50:
            # Mid cycle (12-24 months): +5
            score += 5
            metrics["cycle_phase"] = "mid"
        elif cycle_position <= 0.75:
            # Late cycle (24-36 months): -5
            score -= 5
            metrics["cycle_phase"] = "late"
        else:
            # Bear phase (36-48 months): -15
            score -= 15
            metrics["cycle_phase"] = "bear"

        # Fear & Greed proxy (VIX + volume + momentum composite)
        fg_proxy = self._compute_fear_greed_proxy(close, volume, vix_value)
        metrics["fear_greed_proxy"] = fg_proxy
        if fg_proxy is not None:
            if fg_proxy < 25:
                score += 10  # extreme fear -> contrarian buy
            elif fg_proxy > 75:
                score -= 10  # extreme greed -> caution

        return _clamp(score), metrics

    def _compute_fear_greed_proxy(
        self,
        close: pd.Series,
        volume: pd.Series,
        vix_value: float | None,
    ) -> float | None:
        """Compute a 0-100 fear/greed proxy from available data."""
        components: list[float] = []

        n = len(close)

        # Momentum component: 30-day return normalized to 0-100
        if n >= 30:
            ret_30d = float(close.iloc[-1] / close.iloc[-30] - 1) * 100
            # Map: -30% -> 0 (extreme fear), 0% -> 50, +30% -> 100
            momentum_score = max(0, min(100, 50 + ret_30d * (50 / 30)))
            components.append(momentum_score)

        # Volatility component: low vol = greed, high vol = fear
        if vix_value is not None:
            # Map: VIX 10 -> 90 (greed), VIX 30 -> 10 (fear)
            vol_score = max(0, min(100, 100 - (vix_value - 10) * (90 / 20)))
            components.append(vol_score)

        # Volume component: high relative volume = greed
        if n >= 20:
            vol_5d = float(volume.iloc[-5:].mean())
            vol_20d = float(volume.iloc[-20:].mean())
            if vol_20d > 0:
                vol_ratio = vol_5d / vol_20d
                # Map: 0.5x -> 30 (fear), 1.0x -> 50, 2.0x -> 80 (greed)
                vol_component = max(0, min(100, 50 + (vol_ratio - 1) * 30))
                components.append(vol_component)

        if not components:
            return None

        return round(sum(components) / len(components), 1)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _fetch_spy_prices(self) -> pd.DataFrame:
        """Fetch S&P 500 price history for correlation calculation.

        Uses the injected provider for testability; falls back to direct
        yfinance only when the provider cannot serve index tickers.
        """
        try:
            data = await self._provider.get_price_history(
                "^GSPC", period="6mo", interval="1d"
            )
            if data is not None and not data.empty:
                return data
        except Exception:
            pass

        # Fallback: direct yfinance (provider may not support index tickers)
        import yfinance as yf
        from data_providers.yfinance_provider import _yfinance_lock

        def _download() -> pd.DataFrame:
            with _yfinance_lock:
                data = yf.download("^GSPC", period="6mo", interval="1d", progress=False)
            if data is None or data.empty:
                raise ValueError("No S&P 500 data returned.")
            if isinstance(data.columns, pd.MultiIndex):
                data = data.droplevel(1, axis=1)
            rename_map = {col: str(col).title() for col in data.columns}
            data = data.rename(columns=rename_map)
            return data

        return await asyncio.to_thread(_download)

    async def _fetch_vix(self) -> float:
        """Fetch current VIX level.

        Uses the injected provider first; falls back to direct yfinance.
        """
        try:
            data = await self._provider.get_price_history(
                "^VIX", period="5d", interval="1d"
            )
            if data is not None and not data.empty:
                return float(data["Close"].iloc[-1])
        except Exception:
            pass

        # Fallback: direct yfinance
        import yfinance as yf
        from data_providers.yfinance_provider import _yfinance_lock

        def _fetch() -> float:
            with _yfinance_lock:
                data = yf.download("^VIX", period="5d", interval="1d", progress=False)
            if data is None or data.empty:
                raise ValueError("No VIX data returned.")
            if isinstance(data.columns, pd.MultiIndex):
                data = data.droplevel(1, axis=1)
            return float(data["Close"].iloc[-1])

        return await asyncio.to_thread(_fetch)

    def _determine_regime(
        self,
        macro_score: float,
        cycle_score: float,
        vix_value: float | None,
    ) -> Regime:
        """Determine regime from macro + cycle scores."""
        combined = macro_score + cycle_score
        if vix_value is not None and vix_value > 30:
            combined -= 20  # risk-off bias during high vol
        if combined > 20:
            return Regime.RISK_ON
        if combined < -20:
            return Regime.RISK_OFF
        return Regime.NEUTRAL

    def _build_reasoning(
        self,
        f1: float,
        f2: float,
        f3: float,
        f4: float,
        f5: float,
        f6: float,
        f7: float,
        composite: float,
        regime: Regime,
        asset_type: str,
    ) -> str:
        parts: list[str] = []

        # Overall
        if composite >= 20:
            direction = "bullish"
        elif composite <= -20:
            direction = "bearish"
        else:
            direction = "neutral"
        parts.append(f"Crypto 7-factor model: {direction} (composite {composite:+.1f}).")

        # Factor breakdown
        factor_desc = []
        if abs(f2) > 10:
            label = "strong" if f2 > 0 else "weak"
            factor_desc.append(f"momentum {label} ({f2:+.0f})")
        if abs(f3) > 10:
            label = "low-risk" if f3 > 0 else "high-risk"
            factor_desc.append(f"volatility {label} ({f3:+.0f})")
        if abs(f5) > 5:
            label = "favorable" if f5 > 0 else "unfavorable"
            factor_desc.append(f"macro {label} ({f5:+.0f})")
        if abs(f7) > 5:
            label = "supportive" if f7 > 0 else "cautionary"
            factor_desc.append(f"cycle {label} ({f7:+.0f})")

        if factor_desc:
            parts.append("Key factors: " + ", ".join(factor_desc) + ".")

        parts.append(f"Regime: {regime.value}.")

        return " ".join(parts)

    def _hold_fallback(self, ticker: str, warnings: list[str]) -> AgentOutput:
        """Return a HOLD signal when insufficient data is available."""
        return AgentOutput(
            agent_name=self.name,
            ticker=ticker,
            signal=Signal.HOLD,
            confidence=30.0,
            reasoning="Insufficient data for crypto analysis; defaulting to HOLD.",
            metrics=self._empty_metrics(),
            warnings=warnings,
        )

    def _empty_metrics(self) -> dict[str, Any]:
        return {
            "market_structure_score": 0.0,
            "momentum_trend_score": 0.0,
            "volatility_risk_score": 0.0,
            "liquidity_volume_score": 0.0,
            "macro_correlation_score": 0.0,
            "network_adoption_score": 0.0,
            "cycle_timing_score": 0.0,
            "composite_score": 0.0,
            "regime": Regime.NEUTRAL.value,
            "current_price": None,
        }


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
        if math.isnan(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _clamp(value: float) -> float:
    return max(-100.0, min(100.0, value))
