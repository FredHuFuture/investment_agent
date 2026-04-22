from __future__ import annotations

from typing import Any

import pandas as pd

from agents.base import BaseAgent
from agents.models import AgentInput, AgentOutput, Signal
from agents.utils import _clamp, _to_float

NON_PIT_WARNING = (
    "Data sourced from yfinance (non-point-in-time). "
    "Fundamental metrics may reflect restated financials. "
    "Do not use for backtesting without PIT adjustment."
)

# Sector median P/E ratios for relative valuation.
# Source: long-run averages; updated periodically.
SECTOR_PE_MEDIANS: dict[str, float] = {
    "technology": 28.0,
    "healthcare": 22.0,
    "financial services": 13.0,
    "financials": 13.0,
    "consumer cyclical": 20.0,
    "consumer defensive": 22.0,
    "industrials": 20.0,
    "energy": 12.0,
    "utilities": 17.0,
    "real estate": 35.0,
    "basic materials": 15.0,
    "communication services": 18.0,
}


class FundamentalAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "FundamentalAgent"

    def supported_asset_types(self) -> list[str]:
        return ["stock"]

    async def analyze(self, agent_input: AgentInput) -> AgentOutput:
        self._validate_asset_type(agent_input)

        # FOUND-04: short-circuit in backtest_mode to prevent look-ahead bias.
        # yfinance returns current/restated financials, not point-in-time data.
        # Returning HOLD with data_completeness=0.0 ensures the aggregator
        # excludes this agent's contribution entirely when renormalizing weights.
        if agent_input.backtest_mode:
            self._logger.info(
                "Analyzing %s in backtest_mode: returning HOLD (no provider calls)",
                agent_input.ticker,
            )
            return AgentOutput(
                agent_name=self.name,
                ticker=agent_input.ticker,
                signal=Signal.HOLD,
                confidence=30.0,
                reasoning=(
                    "FundamentalAgent is disabled in backtest_mode because yfinance "
                    "returns current/restated financials, which would inject look-ahead "
                    "bias into historical backtests. Defaulting to HOLD."
                ),
                metrics=self._empty_metrics(),
                warnings=[
                    "backtest_mode: skipping restated fundamentals to prevent "
                    "look-ahead bias."
                ],
                data_completeness=0.0,
            )

        self._logger.info("Analyzing %s", agent_input.ticker)

        warnings: list[str] = [NON_PIT_WARNING]
        try:
            key_stats = await self._provider.get_key_stats(agent_input.ticker)
            financials = await self._provider.get_financials(agent_input.ticker)
        except Exception as exc:
            self._logger.warning("Fundamental data unavailable for %s: %s", agent_input.ticker, exc)
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
            self._logger.warning("All fundamental metrics missing for %s", agent_input.ticker)
            return AgentOutput(
                agent_name=self.name,
                ticker=agent_input.ticker,
                signal=Signal.HOLD,
                confidence=30.0,
                reasoning="No fundamental metrics available; defaulting to HOLD.",
                metrics={**self._empty_metrics(), **metrics},
                warnings=warnings,
            )
        # Dynamic sector P/E median (async, cached 24h, prefers Finnhub when
        # FINNHUB_API_KEY is set, falls back to yfinance ETF, then static table).
        sector_pe_median: float | None = None
        sector_pe_source: str = "static"  # default; overwritten on success
        try:
            from data_providers.sector_pe_cache import (
                get_sector_pe_median,
                get_sector_pe_source,
            )
            sector_pe_median = await get_sector_pe_median(
                metrics.get("sector"), provider=self._provider,
            )
            sector_pe_source = await get_sector_pe_source(metrics.get("sector"))
        except Exception:
            pass  # use static fallback inside _score_pe_trailing

        value_score = self._compute_value_score(metrics, sector_pe_median=sector_pe_median)
        quality_score = self._compute_quality_score(metrics)
        growth_score = self._compute_growth_score(metrics)

        composite = value_score * 0.35 + quality_score * 0.35 + growth_score * 0.30
        signal, confidence = self._composite_to_signal(composite)

        # Penalise confidence when many core metrics are missing —
        # a score built on sparse data is unreliable.
        core_keys = [
            "pe_trailing", "pb_ratio", "ev_ebitda", "roe",
            "profit_margin", "revenue_growth", "debt_equity", "fcf_yield",
        ]
        missing_count = sum(1 for k in core_keys if metrics.get(k) is None)
        data_completeness = (len(core_keys) - missing_count) / len(core_keys)
        if missing_count >= 4:
            confidence *= 0.75
            warnings.append(f"{missing_count}/8 core metrics missing — confidence reduced.")
            self._logger.warning("%d/8 core metrics missing for %s", missing_count, agent_input.ticker)
        elif missing_count >= 2:
            confidence *= 0.90
            warnings.append(f"{missing_count}/8 core metrics missing — confidence slightly reduced.")
        confidence = max(30.0, min(90.0, confidence))

        reasoning = self._build_reasoning(
            metrics, value_score, quality_score, growth_score,
            sector_pe_source=sector_pe_source,
        )

        metrics.update(
            {
                "value_score": value_score,
                "quality_score": quality_score,
                "growth_score": growth_score,
                "composite_score": composite,
            }
        )

        self._logger.info(
            "Completed %s: %s @ %.0f%% confidence", agent_input.ticker, signal.value, confidence
        )
        return AgentOutput(
            agent_name=self.name,
            ticker=agent_input.ticker,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            metrics=metrics,
            warnings=warnings,
            data_completeness=data_completeness,
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

    def _compute_value_score(
        self, metrics: dict[str, Any], sector_pe_median: float | None = None,
    ) -> float:
        score = 0.0
        score += _score_pe_trailing(
            metrics.get("pe_trailing"), metrics.get("sector"),
            sector_pe_median=sector_pe_median,
        )
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
        sector_pe_source: str = "static",
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

        # Sector P/E source note — distinguishes live Finnhub data from static fallback.
        _source_notes: dict[str, str] = {
            "finnhub": "Finnhub sector P/E (live peer basket).",
            "yfinance": "Sector P/E from yfinance ETF lookup.",
            "static": "Sector P/E from static sector median.",
        }
        source_note = _source_notes.get(sector_pe_source, "Sector P/E from static sector median.")

        return (
            f"{value_desc} {quality_desc} {growth_desc} {source_note} "
            "Non-PIT data -- fundamental metrics may reflect restated financials."
        )

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


def _score_pe_trailing(
    value: float | None,
    sector: str | None = None,
    sector_pe_median: float | None = None,
) -> float:
    """Score P/E relative to sector median (if available) or absolute thresholds.

    Sector-relative scoring prevents penalising high-P/E growth sectors
    (Technology) or rewarding naturally low-P/E sectors (Energy/Financials)
    when compared against a single universal threshold.
    """
    if value is None:
        return 0.0
    median = sector_pe_median or SECTOR_PE_MEDIANS.get((sector or "").lower())
    if median is not None and median > 0:
        ratio = value / median
        if ratio < 0.75:
            return 25.0          # 25%+ below sector median → cheap
        if ratio > 1.50:
            return -20.0         # 50%+ above sector median → expensive
        # Linear interpolation between cheap and expensive
        return 25.0 + (ratio - 0.75) * ((-20.0 - 25.0) / (1.50 - 0.75))
    # Fallback: absolute thresholds (no sector info)
    if value < 15:
        return 25.0
    if value > 30:
        return -20.0
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
