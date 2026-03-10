from __future__ import annotations

from typing import Any

import pandas as pd

from agents.base import BaseAgent
from agents.models import AgentInput, AgentOutput, Regime, Signal
from data_providers.base import DataProvider


class MacroAgent(BaseAgent):
    """Macro environment analysis and regime detection."""

    def __init__(self, fred_provider: DataProvider, vix_provider: DataProvider) -> None:
        super().__init__(provider=fred_provider)
        self._vix_provider = vix_provider

    @property
    def name(self) -> str:
        return "MacroAgent"

    def supported_asset_types(self) -> list[str]:
        return ["stock", "btc", "eth"]

    async def analyze(self, agent_input: AgentInput) -> AgentOutput:
        self._validate_asset_type(agent_input)

        warnings: list[str] = []
        try:
            macro_data = await self._fetch_macro_data(warnings)
        except RuntimeError as exc:
            warnings.append(str(exc))
            return AgentOutput(
                agent_name=self.name,
                ticker=agent_input.ticker,
                signal=Signal.HOLD,
                confidence=30.0,
                reasoning="Macro analysis unavailable; defaulting to HOLD.",
                metrics=_empty_metrics(),
                warnings=warnings,
            )

        if _all_missing(macro_data):
            warnings.append("All macro data sources unavailable.")
            return AgentOutput(
                agent_name=self.name,
                ticker=agent_input.ticker,
                signal=Signal.HOLD,
                confidence=30.0,
                reasoning="Macro data unavailable; defaulting to HOLD.",
                metrics=_empty_metrics(),
                warnings=warnings,
            )

        regime, risk_on, risk_off, net_score = self._classify_regime(macro_data)
        signal = self._regime_to_signal(regime, agent_input.asset_type)
        confidence = self._compute_confidence(net_score)

        metrics = {
            "regime": regime.value,
            "net_score": net_score,
            "risk_on_points": risk_on,
            "risk_off_points": risk_off,
            "vix_current": macro_data.get("vix_current"),
            "vix_sma_20": macro_data.get("vix_sma_20"),
            "fed_funds_rate": macro_data.get("fed_funds_rate"),
            "treasury_10y": macro_data.get("treasury_10y"),
            "treasury_2y": macro_data.get("treasury_2y"),
            "yield_curve_spread": macro_data.get("yield_curve_spread"),
            "m2_yoy_growth": macro_data.get("m2_yoy_growth"),
            "fed_funds_trend": macro_data.get("fed_funds_trend"),
        }

        reasoning = _build_reasoning(regime, net_score, macro_data)

        return AgentOutput(
            agent_name=self.name,
            ticker=agent_input.ticker,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            metrics=metrics,
            warnings=warnings,
        )

    async def _fetch_macro_data(self, warnings: list[str]) -> dict[str, Any]:
        data: dict[str, Any] = {}

        try:
            vix_df = await self._vix_provider.get_price_history("^VIX", period="3mo", interval="1d")
            if vix_df is None or vix_df.empty:
                raise ValueError("VIX data empty.")
            vix_close = vix_df["Close"]
            data["vix_current"] = float(vix_close.iloc[-1])
            if len(vix_close) >= 20:
                data["vix_sma_20"] = float(vix_close.rolling(20).mean().iloc[-1])
            else:
                data["vix_sma_20"] = None
                warnings.append("Insufficient VIX data for SMA20.")
        except Exception as exc:
            warnings.append(f"VIX unavailable: {exc}")
            data["vix_current"] = None
            data["vix_sma_20"] = None

        try:
            fed_funds = await self._provider.get_fed_funds_rate()
            fed_funds = fed_funds.dropna()
            data["fed_funds_rate"] = float(fed_funds.iloc[-1]) if not fed_funds.empty else None
            if len(fed_funds) >= 4:
                prior = float(fed_funds.iloc[-4])
                latest = float(fed_funds.iloc[-1])
                if latest > prior:
                    data["fed_funds_trend"] = "increasing"
                elif latest < prior:
                    data["fed_funds_trend"] = "decreasing"
                else:
                    data["fed_funds_trend"] = "stable"
            else:
                data["fed_funds_trend"] = None
                warnings.append("Insufficient Fed Funds history for trend.")
        except RuntimeError:
            raise RuntimeError("FRED API key not configured. Macro analysis unavailable.")
        except Exception as exc:
            warnings.append(f"Fed Funds unavailable: {exc}")
            data["fed_funds_rate"] = None
            data["fed_funds_trend"] = None

        try:
            treasury_10y = await self._provider.get_treasury_yield("10y")
            treasury_2y = await self._provider.get_treasury_yield("2y")
            data["treasury_10y"] = float(treasury_10y.dropna().iloc[-1]) if not treasury_10y.empty else None
            data["treasury_2y"] = float(treasury_2y.dropna().iloc[-1]) if not treasury_2y.empty else None
            if data["treasury_10y"] is not None and data["treasury_2y"] is not None:
                data["yield_curve_spread"] = data["treasury_10y"] - data["treasury_2y"]
            else:
                data["yield_curve_spread"] = None
        except RuntimeError:
            raise RuntimeError("FRED API key not configured. Macro analysis unavailable.")
        except Exception as exc:
            warnings.append(f"Treasury yields unavailable: {exc}")
            data["treasury_10y"] = None
            data["treasury_2y"] = None
            data["yield_curve_spread"] = None

        try:
            m2_series = await self._provider.get_m2_money_supply()
            m2_series = m2_series.dropna()
            if len(m2_series) >= 13:
                latest = float(m2_series.iloc[-1])
                prior = float(m2_series.iloc[-13])
                if prior != 0:
                    data["m2_yoy_growth"] = latest / prior - 1
                else:
                    data["m2_yoy_growth"] = None
                    warnings.append("M2 prior value is zero.")
            else:
                data["m2_yoy_growth"] = None
                warnings.append("Insufficient M2 history for YoY.")
        except RuntimeError:
            raise RuntimeError("FRED API key not configured. Macro analysis unavailable.")
        except Exception as exc:
            warnings.append(f"M2 unavailable: {exc}")
            data["m2_yoy_growth"] = None

        return data

    def _classify_regime(self, macro_data: dict[str, Any]) -> tuple[Regime, float, float, float]:
        risk_on = 0.0
        risk_off = 0.0

        vix = macro_data.get("vix_current")
        vix_sma = macro_data.get("vix_sma_20")
        if vix is not None:
            if vix < 15:
                risk_on += 20
            elif 15 <= vix < 20:
                risk_on += 10
            elif 20 <= vix < 25:
                risk_off += 10
            elif 25 <= vix < 30:
                risk_off += 20
            else:
                risk_off += 30

        if vix is not None and vix_sma is not None:
            if vix < vix_sma:
                risk_on += 10
            elif vix > vix_sma * 1.2:
                risk_off += 15

        spread = macro_data.get("yield_curve_spread")
        if spread is not None:
            if spread > 0.5:
                risk_on += 15
            elif 0 <= spread <= 0.5:
                risk_on += 5
                risk_off += 5
            else:
                risk_off += 25

        trend = macro_data.get("fed_funds_trend")
        if trend == "decreasing":
            risk_on += 15
        elif trend == "increasing":
            risk_off += 10
        elif trend == "stable":
            risk_on += 5
            risk_off += 5

        m2_growth = macro_data.get("m2_yoy_growth")
        if m2_growth is not None:
            if m2_growth > 0.05:
                risk_on += 15
            elif 0 <= m2_growth <= 0.05:
                risk_on += 5
                risk_off += 5
            else:
                risk_off += 20

        net_score = risk_on - risk_off
        if net_score >= 15:
            regime = Regime.RISK_ON
        elif net_score <= -15:
            regime = Regime.RISK_OFF
        else:
            regime = Regime.NEUTRAL

        return regime, risk_on, risk_off, net_score

    def _regime_to_signal(self, regime: Regime, asset_type: str) -> Signal:
        if regime == Regime.RISK_ON:
            return Signal.BUY
        if regime == Regime.RISK_OFF:
            return Signal.SELL
        return Signal.HOLD

    def _compute_confidence(self, net_score: float) -> float:
        max_possible = 80.0
        raw_confidence = 40 + abs(net_score) * (50 / max_possible)
        return max(35.0, min(85.0, raw_confidence))


def _build_reasoning(regime: Regime, net_score: float, macro_data: dict[str, Any]) -> str:
    vix = macro_data.get("vix_current")
    vix_sma = macro_data.get("vix_sma_20")
    spread = macro_data.get("yield_curve_spread")
    fed_rate = macro_data.get("fed_funds_rate")
    fed_trend = macro_data.get("fed_funds_trend")
    m2_growth = macro_data.get("m2_yoy_growth")

    parts = [f"Regime: {regime.value} (net score {net_score:+.0f})."]
    if vix is not None:
        vix_part = f"VIX: {vix:.1f}"
        if vix_sma is not None:
            vix_part += f" (SMA20 {vix_sma:.1f})"
        parts.append(vix_part + ".")
    if spread is not None:
        parts.append(f"Yield curve spread: {spread:+.2f}%.")
    if fed_rate is not None:
        parts.append(f"Fed Funds: {fed_rate:.2f}% ({fed_trend or 'unknown'}).")
    if m2_growth is not None:
        parts.append(f"M2 YoY: {m2_growth*100:.1f}%.")
    parts.append("Macro environment supports risk assets." if regime == Regime.RISK_ON else "Macro environment is cautious." if regime == Regime.RISK_OFF else "Macro environment is mixed.")
    return " ".join(parts)


def _empty_metrics() -> dict[str, Any]:
    return {
        "regime": Regime.NEUTRAL.value,
        "net_score": 0.0,
        "risk_on_points": 0.0,
        "risk_off_points": 0.0,
        "vix_current": None,
        "vix_sma_20": None,
        "fed_funds_rate": None,
        "treasury_10y": None,
        "treasury_2y": None,
        "yield_curve_spread": None,
        "m2_yoy_growth": None,
        "fed_funds_trend": None,
    }


def _all_missing(macro_data: dict[str, Any]) -> bool:
    return all(
        macro_data.get(key) is None
        for key in [
            "vix_current",
            "vix_sma_20",
            "fed_funds_rate",
            "treasury_10y",
            "treasury_2y",
            "yield_curve_spread",
            "m2_yoy_growth",
        ]
    )
