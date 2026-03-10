from __future__ import annotations

import math
from typing import Any

import pandas as pd
import pandas_ta as ta

from agents.base import BaseAgent
from agents.models import AgentInput, AgentOutput, Signal


class TechnicalAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "TechnicalAgent"

    def supported_asset_types(self) -> list[str]:
        return ["stock", "btc", "eth"]

    async def analyze(self, agent_input: AgentInput) -> AgentOutput:
        self._validate_asset_type(agent_input)

        warnings: list[str] = []
        daily_df = await self._provider.get_price_history(
            agent_input.ticker, period="1y", interval="1d"
        )
        if daily_df is None or daily_df.empty:
            raise ValueError(f"No price history for {agent_input.ticker}.")

        weekly_df: pd.DataFrame | None = None
        try:
            weekly_df = await self._provider.get_price_history(
                agent_input.ticker, period="2y", interval="1wk"
            )
        except Exception as exc:
            warnings.append(f"Weekly data unavailable: {exc}")
            weekly_df = None

        close = daily_df["Close"]
        high = daily_df["High"]
        low = daily_df["Low"]
        volume = daily_df["Volume"]

        sma_20 = ta.sma(close, length=20)
        sma_50 = ta.sma(close, length=50)
        sma_200 = ta.sma(close, length=200)
        rsi_14 = ta.rsi(close, length=14)
        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        bbands_df = ta.bbands(close, length=20, std=2.0)
        atr_14 = ta.atr(high, low, close, length=14)
        volume_sma_20 = ta.sma(volume, length=20)

        current_price = float(close.iloc[-1])

        sma20_last = _safe_last(sma_20)
        sma50_last = _safe_last(sma_50)
        sma200_last = _safe_last(sma_200)

        trend_score = 0.0
        if sma20_last is None or sma50_last is None:
            warnings.append("Insufficient data for SMA 20/50.")
        if sma200_last is None:
            warnings.append("Insufficient data for SMA 200.")

        if sma20_last is not None:
            if current_price > sma20_last:
                trend_score += 10
            elif current_price < sma20_last:
                trend_score -= 10
        if sma50_last is not None:
            if current_price > sma50_last:
                trend_score += 10
            elif current_price < sma50_last:
                trend_score -= 10
        if sma200_last is not None:
            if current_price > sma200_last:
                trend_score += 15
            elif current_price < sma200_last:
                trend_score -= 15

        if sma20_last is not None and sma50_last is not None:
            if sma20_last > sma50_last:
                trend_score += 15
            elif sma20_last < sma50_last:
                trend_score -= 15
        if sma50_last is not None and sma200_last is not None:
            if sma50_last > sma200_last:
                trend_score += 15
            elif sma50_last < sma200_last:
                trend_score -= 15

        weekly_trend_confirms: bool | None = None
        if weekly_df is not None and not weekly_df.empty:
            weekly_close = weekly_df["Close"]
            weekly_sma20 = _safe_last(ta.sma(weekly_close, length=20))
            weekly_sma50 = _safe_last(ta.sma(weekly_close, length=50))
            if weekly_sma20 is not None and weekly_sma50 is not None:
                if weekly_sma20 > weekly_sma50:
                    trend_score += 10
                    weekly_trend_confirms = True
                elif weekly_sma20 < weekly_sma50:
                    trend_score -= 10
                    weekly_trend_confirms = False
            else:
                warnings.append("Weekly data insufficient for SMA 20/50 confirmation.")
        else:
            warnings.append("Weekly data unavailable; skipping trend confirmation.")

        momentum_score = 0.0
        rsi_last = _safe_last(rsi_14)
        if rsi_last is None:
            warnings.append("RSI unavailable.")
        else:
            if 50 < rsi_last < 70:
                momentum_score += 20
            elif rsi_last >= 70:
                momentum_score -= 10
            elif rsi_last < 30:
                momentum_score += 10
            elif 30 <= rsi_last < 50:
                momentum_score -= 15

        macd_line = None
        macd_signal = None
        macd_hist = None
        if macd_df is not None and not macd_df.empty:
            macd_line = _safe_last(macd_df.iloc[:, 0])
            macd_signal = _safe_last(macd_df.iloc[:, 2])
            macd_hist = _safe_last(macd_df.iloc[:, 1])
            if macd_line is None or macd_signal is None:
                warnings.append("MACD unavailable.")
            else:
                macd_delta = macd_line - macd_signal
                if abs(macd_delta) <= 1e-6:
                    pass
                elif macd_delta > 0:
                    momentum_score += 20
                else:
                    momentum_score -= 20

            hist_series = macd_df.iloc[:, 1].dropna()
            if len(hist_series) >= 3:
                last_three = hist_series.iloc[-3:].tolist()
                if last_three[2] > last_three[1] > last_three[0]:
                    if rsi_last is None or rsi_last < 70:
                        momentum_score += 15
                elif last_three[2] < last_three[1] < last_three[0]:
                    momentum_score -= 15
        else:
            warnings.append("MACD unavailable.")

        volume_ratio = None
        volume_sma_last = _safe_last(volume_sma_20)
        if volume_sma_last is None or volume_sma_last == 0:
            warnings.append("Volume SMA unavailable.")
        else:
            volume_ratio = float(volume.iloc[-1]) / volume_sma_last
            if volume_ratio > 1.5 and trend_score > 0:
                momentum_score += 10
            elif volume_ratio < 0.5:
                momentum_score -= 5

        volatility_score = 0.0
        bb_upper = None
        bb_lower = None
        bb_middle = None
        if bbands_df is not None and not bbands_df.empty:
            upper_col = _find_col(bbands_df, "BBU")
            middle_col = _find_col(bbands_df, "BBM")
            lower_col = _find_col(bbands_df, "BBL")
            if upper_col and middle_col and lower_col:
                bb_upper = _safe_last(bbands_df[upper_col])
                bb_middle = _safe_last(bbands_df[middle_col])
                bb_lower = _safe_last(bbands_df[lower_col])
            else:
                warnings.append("Bollinger Bands columns unavailable.")
        else:
            warnings.append("Bollinger Bands unavailable.")

        if bb_upper is not None and bb_lower is not None and bb_middle is not None:
            if current_price != 0:
                if (current_price - bb_lower) / current_price < 0.05:
                    volatility_score += 15
                elif (bb_upper - current_price) / current_price < 0.05:
                    volatility_score -= 10
                else:
                    volatility_score += 5

                width = (bb_upper - bb_lower) / bb_middle if bb_middle else None
                if width is not None and width < 0.05:
                    volatility_score += 5

        atr_last = _safe_last(atr_14)
        if atr_last is None:
            warnings.append("ATR unavailable.")
        else:
            atr_series = atr_14.dropna()
            if len(atr_series) >= 5:
                last_five = atr_series.iloc[-5:].tolist()
                if all(last_five[i] > last_five[i - 1] for i in range(1, 5)):
                    if trend_score < 0:
                        volatility_score -= 15
                    elif trend_score > 0:
                        volatility_score += 5
                elif all(last_five[i] < last_five[i - 1] for i in range(1, 5)):
                    volatility_score += 10
            else:
                warnings.append("ATR insufficient for trend check.")

        composite = trend_score * 0.45 + momentum_score * 0.35 + volatility_score * 0.20

        if composite >= 25:
            signal = Signal.BUY
            confidence = 50 + (composite - 25) * (50 / 75)
        elif composite <= -25:
            signal = Signal.SELL
            confidence = 50 + (abs(composite) - 25) * (50 / 75)
        else:
            signal = Signal.HOLD
            confidence = 50 - abs(composite) * (50 / 25)

        confidence = self._clamp_confidence(confidence)
        confidence = max(30.0, min(95.0, confidence))

        reasoning = _build_reasoning(
            trend_score=trend_score,
            momentum_score=momentum_score,
            volatility_score=volatility_score,
            sma200=sma200_last,
            rsi=rsi_last,
            macd_line=macd_line,
            macd_signal=macd_signal,
            weekly_confirm=weekly_trend_confirms,
        )

        metrics = {
            "trend_score": float(trend_score),
            "momentum_score": float(momentum_score),
            "volatility_score": float(volatility_score),
            "composite_score": float(composite),
            "sma_20": _to_float(sma20_last),
            "sma_50": _to_float(sma50_last),
            "sma_200": _to_float(sma200_last),
            "rsi_14": _to_float(rsi_last),
            "macd_line": _to_float(macd_line),
            "macd_signal": _to_float(macd_signal),
            "macd_histogram": _to_float(macd_hist),
            "bb_upper": _to_float(bb_upper),
            "bb_lower": _to_float(bb_lower),
            "bb_middle": _to_float(bb_middle),
            "atr_14": _to_float(atr_last),
            "current_price": float(current_price),
            "volume_ratio": _to_float(volume_ratio),
            "weekly_trend_confirms": weekly_trend_confirms,
        }

        return AgentOutput(
            agent_name=self.name,
            ticker=agent_input.ticker,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            metrics=metrics,
            warnings=warnings,
        )


def _safe_last(series: pd.Series | None) -> float | None:
    if series is None or series.empty:
        return None
    value = series.iloc[-1]
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric):
        return None
    return numeric


def _find_col(df: pd.DataFrame, prefix: str) -> str | None:
    for col in df.columns:
        if str(col).startswith(prefix):
            return col
    return None


def _to_float(value: float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _build_reasoning(
    *,
    trend_score: float,
    momentum_score: float,
    volatility_score: float,
    sma200: float | None,
    rsi: float | None,
    macd_line: float | None,
    macd_signal: float | None,
    weekly_confirm: bool | None,
) -> str:
    trend_label = "bullish" if trend_score > 15 else "bearish" if trend_score < -15 else "neutral"
    momentum_label = (
        "bullish"
        if momentum_score > 15
        else "bearish"
        if momentum_score < -15
        else "neutral"
    )
    volatility_label = (
        "favorable" if volatility_score > 10 else "unfavorable" if volatility_score < -10 else "neutral"
    )

    parts = [f"Trend: {trend_label}."]
    if sma200 is not None:
        parts.append("SMA 200 available for trend alignment.")
    if rsi is not None:
        parts.append(f"RSI {rsi:.1f}.")
    if macd_line is not None and macd_signal is not None:
        relation = "above" if macd_line > macd_signal else "below"
        parts.append(f"MACD {relation} signal.")

    parts.append(f"Momentum: {momentum_label}.")
    parts.append(f"Volatility: {volatility_label}.")
    if weekly_confirm is True:
        parts.append("Weekly: confirms daily trend.")
    elif weekly_confirm is False:
        parts.append("Weekly: conflicts with daily trend.")

    return " ".join(parts)
