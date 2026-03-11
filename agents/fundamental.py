from __future__ import annotations

from typing import Any

import pandas as pd

from agents.base import BaseAgent
from agents.models import AgentInput, AgentOutput, Signal

NON_PIT_WARNING = (
    "Data sourced from yfinance (non-point-in-time). "
    "Fundamental metrics may reflect restated financials. "
    "Do not use for backtesting without PIT adjustment."
)


class FundamentalAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "FundamentalAgent"

    def supported_asset_types(self) -> list[str]:
        return ["stock"]

    async def analyze(self, agent_input: AgentInput) -> AgentOutput:
        self._validate_asset_type(agent_input)

        warnings: list[str] = [NON_PIT_WARNING]
        try:
            key_stats = await self._provider.get_key_stats(agent_input.ticker)
            financials = await self._provider.get_financials(agent_input.ticker)
        except Exception as exc:
            warnings.append(f"Fundamental data unavailable: {exc}")
            return AgentOutput(
                agent_name=self.name,
                ticker=agent_input.ticker,
                signal=Signal.HOLD,
                confidence=30.0,
                reasoning="Fundamental data unavailable; defaulting to HOLD.",
                metrics=self._empty_metrics(),
                warnings=warnings,
            )

        metrics = self._extract_metrics(key_stats, financials)

        # Extract additional metrics from key_stats (available via yfinance info dict)
        peg = _to_float(key_stats.get("pegRatio"))
        earnings_growth = _to_float(key_stats.get("earningsGrowth"))
        analyst_rating = _to_float(key_stats.get("recommendationMean"))
        metrics["peg_ratio"] = peg
        metrics["earnings_growth"] = earnings_growth
        metrics["analyst_rating"] = analyst_rating

        if _all_metrics_missing(metrics):
            return AgentOutput(
                agent_name=self.name,
                ticker=agent_input.ticker,
                signal=Signal.HOLD,
                confidence=30.0,
                reasoning="No fundamental metrics available; defaulting to HOLD.",
                metrics={**self._empty_metrics(), **metrics},
                warnings=warnings,
            )
        value_score = self._compute_value_score(metrics)
        quality_score = self._compute_quality_score(metrics)
        growth_score = self._compute_growth_score(metrics)

        composite = value_score * 0.35 + quality_score * 0.35 + growth_score * 0.30
        signal, confidence = self._composite_to_signal(composite)

        reasoning = self._build_reasoning(metrics, value_score, quality_score, growth_score)

        metrics.update(
            {
                "value_score": value_score,
                "quality_score": quality_score,
                "growth_score": growth_score,
                "composite_score": composite,
            }
        )

        return AgentOutput(
            agent_name=self.name,
            ticker=agent_input.ticker,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            metrics=metrics,
            warnings=warnings,
        )

    def _extract_metrics(self, key_stats: dict, financials: dict) -> dict[str, Any]:
        market_cap = _to_float(key_stats.get("market_cap"))
        pe_trailing = _to_float(key_stats.get("pe_ratio"))
        pe_forward = _to_float(key_stats.get("forward_pe"))
        dividend_yield = _to_float(key_stats.get("dividend_yield"))
        sector = key_stats.get("sector")
        pct_52w_high = None

        current_price = key_stats.get("current_price")
        if current_price is None:
            current_price = key_stats.get("regular_market_price")
        current_price = _to_float(current_price)
        high_52w = _to_float(key_stats.get("52w_high"))

        if current_price is not None and high_52w is not None and high_52w != 0:
            pct_52w_high = (current_price - high_52w) / high_52w

        income_statement = financials.get("income_statement")
        balance_sheet = financials.get("balance_sheet")
        cash_flow = financials.get("cash_flow")

        total_revenue = _safe_extract(income_statement, ["Total Revenue", "Revenue"])
        net_income = _safe_extract(income_statement, ["Net Income", "Net Income Common Stockholders"])
        equity = _safe_extract(
            balance_sheet,
            ["Total Stockholders Equity", "Total Stockholder Equity", "Stockholders Equity"],
        )
        total_debt = _safe_extract(
            balance_sheet,
            ["Total Debt", "Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
        )
        current_assets = _safe_extract(balance_sheet, ["Current Assets"])
        current_liabilities = _safe_extract(balance_sheet, ["Current Liabilities"])
        fcf = _safe_extract(cash_flow, ["Free Cash Flow"])
        ebitda = _safe_extract(income_statement, ["EBITDA"])
        cash = _safe_extract(balance_sheet, ["Cash And Cash Equivalents", "Cash"])

        # Guard: negative equity (heavy buybacks, e.g. Starbucks/McDonald's)
        # makes P/B, ROE, D/E economically meaningless → treat as None
        equity_valid = equity is not None and equity > 0

        pb_ratio = None
        if market_cap is not None and equity_valid:
            pb_ratio = market_cap / equity

        ev_ebitda = None
        if market_cap is not None and ebitda not in (None, 0):
            debt_val = total_debt or 0.0
            cash_val = cash or 0.0
            ev_ebitda = (market_cap + debt_val - cash_val) / ebitda

        roe = None
        if net_income is not None and equity_valid:
            roe = net_income / equity

        profit_margin = None
        if net_income is not None and total_revenue not in (None, 0):
            profit_margin = net_income / total_revenue

        revenue_growth = None
        if isinstance(income_statement, pd.DataFrame) and total_revenue is not None:
            revenue_series = _safe_series(income_statement, ["Total Revenue", "Revenue"])
            if revenue_series is not None and len(revenue_series) >= 2:
                latest = _to_float(revenue_series.iloc[0])
                prior = _to_float(revenue_series.iloc[1])
                if latest is not None and prior not in (None, 0):
                    revenue_growth = (latest - prior) / prior

        debt_equity = None
        if total_debt is not None and equity_valid:
            debt_equity = total_debt / equity

        current_ratio = None
        if current_assets is not None and current_liabilities not in (None, 0):
            current_ratio = current_assets / current_liabilities

        fcf_yield = None
        if fcf is not None and market_cap not in (None, 0):
            fcf_yield = fcf / market_cap

        return {
            "pe_trailing": pe_trailing,
            "pe_forward": pe_forward,
            "pb_ratio": pb_ratio,
            "ev_ebitda": ev_ebitda,
            "roe": roe,
            "profit_margin": profit_margin,
            "revenue_growth": revenue_growth,
            "debt_equity": debt_equity,
            "current_ratio": current_ratio,
            "fcf_yield": fcf_yield,
            "pct_from_52w_high": pct_52w_high,
            "market_cap": market_cap,
            "dividend_yield": dividend_yield,
            "sector": sector,
        }

    def _compute_value_score(self, metrics: dict[str, Any]) -> float:
        score = 0.0
        score += _score_pe_trailing(metrics.get("pe_trailing"))
        score += _score_linear(
            metrics.get("pe_forward"), 12, 25, 15, -15, higher_is_better=False
        )
        score += _score_linear(
            metrics.get("pb_ratio"), 2, 5, 15, -15, higher_is_better=False
        )
        score += _score_linear(
            metrics.get("ev_ebitda"), 10, 20, 20, -15, higher_is_better=False
        )
        score += _score_linear(metrics.get("fcf_yield"), 0.08, 0.02, 15, -10, higher_is_better=True)
        score += _score_linear(
            metrics.get("pct_from_52w_high"), -0.30, -0.05, 10, -5, higher_is_better=False
        )
        # PEG < 1.0 is undervalued relative to growth, > 2.5 is expensive
        score += _score_linear(
            metrics.get("peg_ratio"), 1.0, 2.5, 15, -10, higher_is_better=False
        )
        return _clamp(score)

    def _compute_quality_score(self, metrics: dict[str, Any]) -> float:
        score = 0.0
        score += _score_linear(
            metrics.get("roe"), 0.20, 0.05, 25, -20, higher_is_better=True
        )
        score += _score_linear(
            metrics.get("profit_margin"), 0.20, 0.05, 20, -15, higher_is_better=True
        )
        score += _score_linear(
            metrics.get("debt_equity"), 0.5, 2.0, 20, -20, higher_is_better=False
        )
        score += _score_linear(
            metrics.get("current_ratio"), 2.0, 1.0, 15, -20, higher_is_better=True
        )
        # Analyst consensus: 1.0 = Strong Buy, 3.0 = Hold, 5.0 = Strong Sell
        score += _score_linear(
            metrics.get("analyst_rating"), 1.5, 3.5, 10, -10, higher_is_better=False
        )
        return _clamp(score)

    def _compute_growth_score(self, metrics: dict[str, Any]) -> float:
        score = 0.0
        revenue_growth = metrics.get("revenue_growth")
        if revenue_growth is not None:
            if revenue_growth > 0.50:
                score += 40
            elif revenue_growth > 0.20:
                score += 30
            elif revenue_growth >= 0.0:
                score += _score_linear(
                    revenue_growth, 0.20, 0.0, 30, -25, higher_is_better=True
                )
            elif revenue_growth < -0.10:
                score -= 35
            else:
                score -= 25

        # Earnings growth scoring
        earnings_growth = metrics.get("earnings_growth")
        if earnings_growth is not None:
            if earnings_growth > 0.30:
                score += 25
            elif earnings_growth > 0.10:
                score += 15
            elif earnings_growth >= 0:
                score += 5
            elif earnings_growth > -0.10:
                score -= 15
            else:
                score -= 25

        # Dividend yield bonus for yield > 3%
        dividend_yield = metrics.get("dividend_yield")
        if dividend_yield is not None and dividend_yield > 0.03:
            score += 5

        pe_trailing = metrics.get("pe_trailing")
        pe_forward = metrics.get("pe_forward")
        if pe_trailing is not None and pe_forward is not None and pe_trailing != 0:
            if pe_forward < pe_trailing:
                score += 15
            elif pe_forward > pe_trailing * 1.2:
                score -= 10
            else:
                score += 5
        return _clamp(score)

    def _composite_to_signal(self, composite: float) -> tuple[Signal, float]:
        if composite >= 20:
            signal = Signal.BUY
        elif composite <= -20:
            signal = Signal.SELL
        else:
            signal = Signal.HOLD

        confidence = 50 + (abs(composite) - 20) * (40 / 80)
        confidence = max(30.0, min(90.0, confidence))
        return signal, confidence

    def _build_reasoning(
        self,
        metrics: dict[str, Any],
        value_score: float,
        quality_score: float,
        growth_score: float,
    ) -> str:
        pe = metrics.get("pe_trailing")
        pb = metrics.get("pb_ratio")
        fcf = metrics.get("fcf_yield")
        roe = metrics.get("roe")
        margin = metrics.get("profit_margin")
        debt = metrics.get("debt_equity")
        growth = metrics.get("revenue_growth")
        forward_pe = metrics.get("pe_forward")

        value_desc = f"Value: {'attractive' if value_score > 10 else 'mixed'}"
        if pe is not None and pb is not None and fcf is not None:
            value_desc += f" (P/E {pe:.1f}, P/B {pb:.1f}, FCF yield {fcf*100:.1f}%)."
        else:
            value_desc += "."

        quality_desc = f"Quality: {'strong' if quality_score > 10 else 'mixed'}"
        if roe is not None and margin is not None and debt is not None:
            quality_desc += f" (ROE {roe*100:.1f}%, margin {margin*100:.1f}%, D/E {debt:.2f})."
        else:
            quality_desc += "."

        growth_desc = f"Growth: {'strong' if growth_score > 10 else 'moderate'}"
        if growth is not None:
            growth_desc += f" (revenue {growth*100:.1f}% YoY"
            if pe is not None and forward_pe is not None:
                growth_desc += ", forward P/E vs trailing suggests earnings trend"
            growth_desc += ")."
        else:
            growth_desc += "."

        return f"{value_desc} {quality_desc} {growth_desc} Non-PIT data -- fundamental metrics may reflect restated financials."

    def _empty_metrics(self) -> dict[str, Any]:
        return {
            "value_score": 0.0,
            "quality_score": 0.0,
            "growth_score": 0.0,
            "composite_score": 0.0,
            "pe_trailing": None,
            "pe_forward": None,
            "pb_ratio": None,
            "ev_ebitda": None,
            "roe": None,
            "profit_margin": None,
            "revenue_growth": None,
            "debt_equity": None,
            "current_ratio": None,
            "fcf_yield": None,
            "pct_from_52w_high": None,
            "market_cap": None,
            "dividend_yield": None,
            "sector": None,
            "peg_ratio": None,
            "earnings_growth": None,
            "analyst_rating": None,
        }


def _safe_extract(df: pd.DataFrame | None, row_names: list[str]) -> float | None:
    if df is None or df.empty:
        return None
    for name in row_names:
        if name in df.index:
            value = df.loc[name]
            if isinstance(value, pd.Series):
                return _to_float(value.iloc[0])
            return _to_float(value)
    return None


def _safe_series(df: pd.DataFrame | None, row_names: list[str]) -> pd.Series | None:
    if df is None or df.empty:
        return None
    for name in row_names:
        if name in df.index:
            row = df.loc[name]
            if isinstance(row, pd.Series):
                return row
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_linear(
    value: float | None,
    bullish_threshold: float,
    bearish_threshold: float,
    bullish_score: float,
    bearish_score: float,
    *,
    higher_is_better: bool = True,
) -> float:
    if value is None:
        return 0.0

    if higher_is_better:
        if value >= bullish_threshold:
            return bullish_score
        if value <= bearish_threshold:
            return bearish_score
        return bullish_score + (bearish_score - bullish_score) * (
            (value - bullish_threshold) / (bearish_threshold - bullish_threshold)
        )
    if value <= bullish_threshold:
        return bullish_score
    if value >= bearish_threshold:
        return bearish_score
    return bullish_score + (bearish_score - bullish_score) * (
        (value - bullish_threshold) / (bearish_threshold - bullish_threshold)
    )


def _clamp(value: float) -> float:
    return max(-100.0, min(100.0, value))


def _score_pe_trailing(value: float | None) -> float:
    if value is None:
        return 0.0
    if value < 15:
        return 25.0
    if value > 30:
        return -20.0
    # interpolate from +15 at 15 to -10 at 30
    return 15.0 + (value - 15.0) * ((-10.0 - 15.0) / (30.0 - 15.0))


def _all_metrics_missing(metrics: dict[str, Any]) -> bool:
    keys = [
        "pe_trailing",
        "pe_forward",
        "pb_ratio",
        "ev_ebitda",
        "roe",
        "profit_margin",
        "revenue_growth",
        "debt_equity",
        "current_ratio",
        "fcf_yield",
        "pct_from_52w_high",
    ]
    return all(metrics.get(key) is None for key in keys)
