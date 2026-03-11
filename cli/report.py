from __future__ import annotations

import json
import textwrap
from typing import Any

from agents.models import AgentOutput, Signal
from engine.aggregator import AggregatedSignal

REPORT_WIDTH = 64
_DOT_SEP = "." * 62
_SIGNAL_VALUES: dict[str, str] = {"BUY": "+1.0", "HOLD": "0.0", "SELL": "-1.0"}


def format_analysis_report(signal: AggregatedSignal, detail: bool = False) -> str:
    """Format an AggregatedSignal into a human-readable terminal report.

    Args:
        signal:  The aggregated analysis result.
        detail:  When True, expand each agent block to show all metrics,
                 sub-score decompositions, reasoning strings, and
                 aggregation weight math.  Defaults to False (standard
                 one-line-per-agent summary).
    """
    line_major = "=" * REPORT_WIDTH
    line_minor = "-" * REPORT_WIDTH

    ticker = signal.ticker.upper()
    asset_type = signal.asset_type
    final_signal = signal.final_signal.value
    confidence = f"{signal.final_confidence:.0f}%"
    regime = signal.regime.value if signal.regime else "NEUTRAL"

    # Header with company name if available
    info = getattr(signal, "ticker_info", {}) or {}
    name = info.get("name")
    if name:
        header = f"  ANALYSIS REPORT: {name} ({ticker})"
    else:
        header = f"  ANALYSIS REPORT: {ticker} ({asset_type})"

    lines: list[str] = [
        line_major,
        header,
        line_major,
    ]

    # Key metrics section
    price = _as_float(info.get("current_price"))
    if price is not None or info.get("sector") or info.get("market_cap"):
        lines.append("")
        if price is not None:
            lines.append(f"  Price:      ${price:,.2f}")
        market_cap = _as_float(info.get("market_cap"))
        if market_cap is not None:
            lines.append(f"  Market Cap: {_format_large_number(market_cap)}")
        high_52w = _as_float(info.get("52w_high"))
        low_52w = _as_float(info.get("52w_low"))
        if high_52w is not None and low_52w is not None:
            lines.append(f"  52W Range:  ${low_52w:,.2f} - ${high_52w:,.2f}")
            if price is not None and high_52w > 0:
                off_high = (price - high_52w) / high_52w * 100
                lines.append(f"  vs 52W High: {off_high:+.1f}%")
        sector = info.get("sector")
        industry = info.get("industry")
        if sector:
            label = f"{sector} / {industry}" if industry else sector
            lines.append(f"  Sector:     {label}")

    lines.extend([
        "",
        f"  SIGNAL:     {final_signal}",
        f"  CONFIDENCE: {confidence}",
        f"  REGIME:     {regime}",
        "",
        line_minor,
        "  AGENT BREAKDOWN",
        line_minor,
        "",
    ])

    if signal.agent_signals:
        contributions = signal.metrics.get("agent_contributions", {}) if signal.metrics else {}
        weights_used = signal.metrics.get("weights_used", {}) if signal.metrics else {}
        for output in signal.agent_signals:
            short_name = output.agent_name.replace("Agent", "")
            label = f"{short_name}:"
            lines.append(f"  {label:<14}{output.signal.value:<5}({output.confidence:.0f}%)")
            if detail:
                lines.extend(_format_agent_detailed(output, contributions, weights_used))
            else:
                lines.append(f"    {_format_agent_detail(output)}")
            lines.append("")
    else:
        lines.append("  (no agents)")
        lines.append("")

    consensus = _format_consensus(signal.agent_signals)
    lines.extend(
        [
            line_minor,
            f"  CONSENSUS: {consensus}",
            line_minor,
            "",
        ]
    )

    if detail:
        lines.extend(_format_aggregation_detail(signal))
        lines.append("")

    # Sector adjustment section
    sector_modifier = (signal.metrics or {}).get("sector_modifier")
    sector_name = (signal.metrics or {}).get("sector_name")
    if sector_modifier is not None and sector_name is not None:
        regime = signal.regime.value if signal.regime else "NEUTRAL"
        if detail:
            pre_conf = (signal.metrics or {}).get("pre_sector_confidence")
            lines.extend(_format_sector_detail(
                sector_name, regime, sector_modifier,
                pre_conf, signal.final_confidence, line_minor,
            ))
            lines.append("")
        else:
            sign = "+" if sector_modifier >= 0 else ""
            lines.append(f"  Sector Adj: {sign}{sector_modifier} ({sector_name} in {regime})")
            lines.append("")

    lines.extend([
        "  WARNINGS:",
    ])

    if signal.warnings:
        for warning in signal.warnings:
            lines.append(f"    {warning}")
    else:
        lines.append("    (none)")

    lines.append("")
    lines.append(line_major)

    return "\n".join(lines)


def format_analysis_json(signal: AggregatedSignal) -> str:
    """Format an AggregatedSignal as pretty-printed JSON."""
    return json.dumps(signal.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# Standard (compact) agent detail -- one line
# ---------------------------------------------------------------------------

def _format_agent_detail(output: AgentOutput) -> str:
    """Extract key metrics from an agent's output for display."""
    name = output.agent_name
    metrics = output.metrics or {}

    if name == "TechnicalAgent":
        parts: list[str] = []
        rsi = _first_present(metrics, ["rsi", "rsi_14"])
        rsi_val = _as_float(rsi)
        if rsi_val is not None:
            parts.append(f"RSI: {rsi_val:.1f}")
        trend = _as_float(metrics.get("trend_score"))
        if trend is not None:
            parts.append(f"Trend: {trend:+.0f}")
        momentum = _as_float(metrics.get("momentum_score"))
        if momentum is not None:
            parts.append(f"Momentum: {momentum:+.0f}")
        volatility = _as_float(metrics.get("volatility_score"))
        if volatility is not None:
            parts.append(f"Volatility: {volatility:+.0f}")
        return " | ".join(parts) if parts else "(no detail)"

    if name == "FundamentalAgent":
        parts = []
        pe = _as_float(metrics.get("pe_trailing"))
        if pe is not None:
            parts.append(f"P/E: {pe:.1f}")
        peg = _as_float(metrics.get("peg_ratio"))
        if peg is not None:
            parts.append(f"PEG: {peg:.1f}")
        roe = _as_float(metrics.get("roe"))
        if roe is not None:
            parts.append(f"ROE: {roe:.1%}")
        eps_growth = _as_float(metrics.get("earnings_growth"))
        if eps_growth is not None:
            parts.append(f"EPS Gr: {eps_growth:+.1%}")
        debt_equity = _as_float(metrics.get("debt_equity"))
        if debt_equity is not None:
            parts.append(f"D/E: {debt_equity:.2f}")
        return " | ".join(parts) if parts else "(no detail)"

    if name == "MacroAgent":
        parts = []
        regime = metrics.get("regime")
        if regime:
            parts.append(f"Regime: {regime}")
        vix = _first_present(metrics, ["vix_level", "vix_current", "vix"])
        vix_val = _as_float(vix)
        if vix_val is not None:
            parts.append(f"VIX: {vix_val:.1f}")
        spread = _as_float(metrics.get("yield_curve_spread"))
        if spread is not None:
            parts.append(f"Yield Curve: {spread:+.2f}%")
        net_score = _as_float(metrics.get("net_score"))
        if net_score is not None:
            parts.append(f"Score: {int(round(net_score)):+d}")
        return " | ".join(parts) if parts else "(no detail)"

    if name == "CryptoAgent":
        parts = []
        cycle_phase = metrics.get("cycle_phase")
        if cycle_phase:
            parts.append(f"Cycle: {cycle_phase}")
        momentum = _as_float(metrics.get("momentum_trend_score"))
        if momentum is not None:
            parts.append(f"Momentum: {momentum:+.0f}")
        vol = _as_float(metrics.get("volatility_30d_pct"))
        if vol is not None:
            parts.append(f"Vol: {vol:.0f}%")
        regime = metrics.get("regime")
        if regime:
            parts.append(f"Regime: {regime}")
        return " | ".join(parts) if parts else "(no detail)"

    return "(unknown agent)"


# ---------------------------------------------------------------------------
# Detail mode -- expanded per-agent block
# ---------------------------------------------------------------------------

def _format_agent_detailed(
    output: AgentOutput,
    contributions: dict[str, Any],
    weights_used: dict[str, float],
) -> list[str]:
    """Return lines for the expanded per-agent detail block (detail=True)."""
    lines: list[str] = []
    metrics = output.metrics or {}
    name = output.agent_name

    lines.append(f"  {_DOT_SEP}")

    if name == "TechnicalAgent":
        _append_technical_groups(lines, metrics)
    elif name == "FundamentalAgent":
        _append_fundamental_groups(lines, metrics)
    elif name == "MacroAgent":
        _append_macro_groups(lines, metrics)
    elif name == "CryptoAgent":
        _append_crypto_groups(lines, metrics)

    # Reasoning block
    reasoning = (output.reasoning or "").strip()
    if reasoning:
        lines.append("    Reasoning:")
        for chunk in textwrap.wrap(reasoning, width=56):
            lines.append(f"      {chunk}")

    # Weight contribution math
    contrib = contributions.get(name, {})
    weight = weights_used.get(name)
    if weight is not None and contrib:
        sig = contrib.get("signal", "")
        sig_val_str = _SIGNAL_VALUES.get(sig, "?")
        conf = contrib.get("confidence", 0.0)
        wc = contrib.get("weighted_contribution", 0.0)
        sign = "+" if wc >= 0 else ""
        lines.append(
            f"    Weight: {weight:.2f} x {sig}({sig_val_str})"
            f" x {conf:.0f}% conf = {sign}{wc:.4f} contribution"
        )

    lines.append(f"  {_DOT_SEP}")
    return lines


def _append_technical_groups(lines: list[str], metrics: dict[str, Any]) -> None:
    """Append TechnicalAgent metric groups to lines."""
    # Sub-scores
    _append_group(lines, "Sub-scores", [
        ("Trend", _fmt_score(metrics.get("trend_score"))),
        ("Momentum", _fmt_score(metrics.get("momentum_score"))),
        ("Volatility", _fmt_score(metrics.get("volatility_score"))),
        ("Price", _fmt_score(metrics.get("price_score"))),
        ("Volume", _fmt_score(metrics.get("volume_score"))),
        ("Composite", _fmt_score(metrics.get("composite_score"))),
    ])

    # Key Indicators
    indicator_items: list[tuple[str, str]] = []

    sma20 = _as_float(metrics.get("sma_20"))
    sma50 = _as_float(metrics.get("sma_50"))
    sma200 = _as_float(metrics.get("sma_200"))
    sma_parts = [f"${v:,.2f}" for v in [sma20, sma50, sma200] if v is not None]
    if sma_parts:
        indicator_items.append(("SMA 20/50/200", " / ".join(sma_parts)))

    rsi_val = _as_float(_first_present(metrics, ["rsi_14", "rsi"]))
    if rsi_val is not None:
        indicator_items.append(("RSI (14)", f"{rsi_val:.1f}"))

    ml = _as_float(metrics.get("macd_line"))
    ms = _as_float(metrics.get("macd_signal"))
    mh = _as_float(metrics.get("macd_histogram"))
    if ml is not None:
        indicator_items.append(("MACD Line", f"{ml:.2f}"))
    if ms is not None:
        indicator_items.append(("MACD Signal", f"{ms:.2f}"))
    if mh is not None:
        indicator_items.append(("MACD Hist", f"{mh:+.2f}"))

    bu = _as_float(metrics.get("bb_upper"))
    bm = _as_float(metrics.get("bb_middle"))
    bl = _as_float(metrics.get("bb_lower"))
    if bu is not None:
        indicator_items.append(("BB Upper", f"${bu:,.2f}"))
    if bm is not None:
        indicator_items.append(("BB Mid", f"${bm:,.2f}"))
    if bl is not None:
        indicator_items.append(("BB Lower", f"${bl:,.2f}"))

    atr = _as_float(metrics.get("atr_14"))
    if atr is not None:
        indicator_items.append(("ATR (14)", f"{atr:.2f}"))

    vol_ratio = _as_float(metrics.get("volume_ratio"))
    if vol_ratio is not None:
        indicator_items.append(("Volume Ratio", f"{vol_ratio:.2f}x"))

    weekly = metrics.get("weekly_trend_confirms")
    if weekly is not None:
        indicator_items.append(("Weekly Trend", "confirms" if weekly else "does not confirm"))

    _append_group(lines, "Key Indicators", indicator_items)


def _append_fundamental_groups(lines: list[str], metrics: dict[str, Any]) -> None:
    """Append FundamentalAgent metric groups to lines."""
    # Sub-scores
    _append_group(lines, "Sub-scores", [
        ("Value", _fmt_score(metrics.get("value_score"))),
        ("Quality", _fmt_score(metrics.get("quality_score"))),
        ("Growth", _fmt_score(metrics.get("growth_score"))),
        ("Composite", _fmt_score(metrics.get("composite_score"))),
    ])

    # Valuation
    val_items: list[tuple[str, str]] = []
    pe = _as_float(metrics.get("pe_trailing"))
    if pe is not None:
        val_items.append(("P/E (trailing)", f"{pe:.1f}"))
    pe_fwd = _as_float(metrics.get("pe_forward"))
    if pe_fwd is not None:
        val_items.append(("P/E (forward)", f"{pe_fwd:.1f}"))
    pb = _as_float(metrics.get("pb_ratio"))
    if pb is not None:
        val_items.append(("P/B", f"{pb:.2f}"))
    ev_ebitda = _as_float(metrics.get("ev_ebitda"))
    if ev_ebitda is not None:
        val_items.append(("EV/EBITDA", f"{ev_ebitda:.1f}"))
    fcf_yield = _as_float(metrics.get("fcf_yield"))
    if fcf_yield is not None:
        val_items.append(("FCF Yield", f"{fcf_yield:.1%}"))
    peg = _as_float(metrics.get("peg_ratio"))
    if peg is not None:
        val_items.append(("PEG Ratio", f"{peg:.2f}"))
    _append_group(lines, "Valuation", val_items)

    # Quality
    qual_items: list[tuple[str, str]] = []
    roe = _as_float(metrics.get("roe"))
    if roe is not None:
        qual_items.append(("ROE", f"{roe:.1%}"))
    pm = _as_float(metrics.get("profit_margin"))
    if pm is not None:
        qual_items.append(("Profit Margin", f"{pm:.1%}"))
    de = _as_float(metrics.get("debt_equity"))
    if de is not None:
        qual_items.append(("Debt/Equity", f"{de:.2f}"))
    cr = _as_float(metrics.get("current_ratio"))
    if cr is not None:
        qual_items.append(("Current Ratio", f"{cr:.2f}"))
    ar = _as_float(metrics.get("analyst_rating"))
    if ar is not None:
        qual_items.append(("Analyst Rating", f"{ar:.1f} ({_analyst_label(ar)})"))
    _append_group(lines, "Quality", qual_items)

    # Growth
    growth_items: list[tuple[str, str]] = []
    rev_growth = _as_float(_first_present(metrics, ["revenue_growth_yoy", "revenue_growth"]))
    if rev_growth is not None:
        growth_items.append(("Revenue Growth", f"{rev_growth:+.1%}"))
    eps_growth = _as_float(metrics.get("earnings_growth"))
    if eps_growth is not None:
        growth_items.append(("Earnings Growth", f"{eps_growth:+.1%}"))
    div_yield = _as_float(metrics.get("dividend_yield"))
    if div_yield is not None:
        growth_items.append(("Dividend Yield", f"{div_yield:.1%}"))
    _append_group(lines, "Growth", growth_items)


def _append_macro_groups(lines: list[str], metrics: dict[str, Any]) -> None:
    """Append MacroAgent metric groups to lines."""
    # Score
    score_items: list[tuple[str, str]] = []
    net = _as_float(metrics.get("net_score"))
    if net is not None:
        score_items.append(("Net Score", f"{int(round(net)):+d}"))
    rop = _as_float(metrics.get("risk_on_points"))
    if rop is not None:
        score_items.append(("Risk-On Pts", f"{int(round(rop)):+d}"))
    roff = _as_float(metrics.get("risk_off_points"))
    if roff is not None:
        score_items.append(("Risk-Off Pts", f"{int(round(roff)):+d}"))
    _append_group(lines, "Score", score_items)

    # Volatility
    vol_items: list[tuple[str, str]] = []
    vix = _as_float(_first_present(metrics, ["vix_current", "vix_level", "vix"]))
    if vix is not None:
        vol_items.append(("VIX", f"{vix:.1f}"))
    vix_sma = _as_float(metrics.get("vix_sma_20"))
    if vix_sma is not None:
        vol_items.append(("VIX SMA(20)", f"{vix_sma:.1f}"))
    _append_group(lines, "Volatility", vol_items)

    # Rates
    rate_items: list[tuple[str, str]] = []
    t10 = _as_float(metrics.get("treasury_10y"))
    if t10 is not None:
        rate_items.append(("Treasury 10Y", f"{t10:.2f}%"))
    t2 = _as_float(metrics.get("treasury_2y"))
    if t2 is not None:
        rate_items.append(("Treasury 2Y", f"{t2:.2f}%"))
    spread = _as_float(metrics.get("yield_curve_spread"))
    if spread is not None:
        rate_items.append(("Yield Curve", f"{spread:+.2f}%"))
    _append_group(lines, "Rates", rate_items)

    # Policy
    policy_items: list[tuple[str, str]] = []
    ffr = _as_float(metrics.get("fed_funds_rate"))
    if ffr is not None:
        policy_items.append(("Fed Funds Rate", f"{ffr:.2f}%"))
    fft = metrics.get("fed_funds_trend")
    if fft is not None:
        policy_items.append(("Fed Trend", str(fft)))
    m2 = _as_float(metrics.get("m2_yoy_growth"))
    if m2 is not None:
        policy_items.append(("M2 YoY Growth", f"{m2:+.1%}"))
    _append_group(lines, "Policy", policy_items)

    # Regime
    regime = metrics.get("regime")
    if regime is not None:
        _append_group(lines, "Regime", [("Regime", str(regime))])


def _append_crypto_groups(lines: list[str], metrics: dict[str, Any]) -> None:
    """Append CryptoAgent 7-factor metric groups to lines."""
    # Factor scores
    _append_group(lines, "Factor Scores", [
        ("Market Structure", _fmt_score(metrics.get("market_structure_score"))),
        ("Momentum & Trend", _fmt_score(metrics.get("momentum_trend_score"))),
        ("Volatility & Risk", _fmt_score(metrics.get("volatility_risk_score"))),
        ("Liquidity & Volume", _fmt_score(metrics.get("liquidity_volume_score"))),
        ("Macro & Correlation", _fmt_score(metrics.get("macro_correlation_score"))),
        ("Network & Adoption", _fmt_score(metrics.get("network_adoption_score"))),
        ("Cycle & Timing", _fmt_score(metrics.get("cycle_timing_score"))),
        ("Composite", _fmt_score(metrics.get("composite_score"))),
    ])

    # Momentum details
    momentum_items: list[tuple[str, str | None]] = []
    ret_3m = _as_float(metrics.get("return_3m_pct"))
    if ret_3m is not None:
        momentum_items.append(("3M Return", f"{ret_3m:+.1f}%"))
    ret_6m = _as_float(metrics.get("return_6m_pct"))
    if ret_6m is not None:
        momentum_items.append(("6M Return", f"{ret_6m:+.1f}%"))
    ret_12m = _as_float(metrics.get("return_12m_pct"))
    if ret_12m is not None:
        momentum_items.append(("12M Return", f"{ret_12m:+.1f}%"))
    ath_dist = _as_float(metrics.get("ath_distance_pct"))
    if ath_dist is not None:
        momentum_items.append(("ATH Distance", f"{ath_dist:+.1f}%"))
    sma200 = _as_float(metrics.get("sma_200"))
    if sma200 is not None:
        momentum_items.append(("SMA 200", f"${sma200:,.2f}"))
    _append_group(lines, "Momentum & Trend", momentum_items)

    # Volatility details
    vol_items: list[tuple[str, str | None]] = []
    vol_30d = _as_float(metrics.get("volatility_30d_pct"))
    if vol_30d is not None:
        vol_items.append(("30D Volatility", f"{vol_30d:.1f}%"))
    max_dd = _as_float(metrics.get("max_drawdown_90d_pct"))
    if max_dd is not None:
        vol_items.append(("Max DD (90D)", f"{max_dd:.1f}%"))
    sharpe = _as_float(metrics.get("sharpe_90d"))
    if sharpe is not None:
        vol_items.append(("Sharpe (90D)", f"{sharpe:.2f}"))
    recovery = _as_float(metrics.get("recovery_days"))
    if recovery is not None:
        vol_items.append(("Recovery Days", f"{int(recovery)}"))
    _append_group(lines, "Volatility & Risk", vol_items)

    # Liquidity details
    liq_items: list[tuple[str, str | None]] = []
    avg_vol = _as_float(metrics.get("avg_daily_volume_usd"))
    if avg_vol is not None:
        liq_items.append(("Avg Daily Vol", _format_large_number(avg_vol)))
    vol_trend = _as_float(metrics.get("volume_trend"))
    if vol_trend is not None:
        liq_items.append(("Volume Trend", f"{vol_trend:.2f}x"))
    turnover = _as_float(metrics.get("turnover_pct"))
    if turnover is not None:
        liq_items.append(("Turnover", f"{turnover:.2f}%"))
    _append_group(lines, "Liquidity & Volume", liq_items)

    # Macro details
    macro_items: list[tuple[str, str | None]] = []
    sp_corr = _as_float(metrics.get("sp500_correlation_90d"))
    if sp_corr is not None:
        macro_items.append(("S&P500 Corr (90D)", f"{sp_corr:.2f}"))
    vix = _as_float(metrics.get("vix_level"))
    if vix is not None:
        macro_items.append(("VIX", f"{vix:.1f}"))
    _append_group(lines, "Macro & Correlation", macro_items)

    # Adoption details
    adopt_items: list[tuple[str, str | None]] = []
    age = _as_float(metrics.get("age_years"))
    if age is not None:
        adopt_items.append(("Asset Age", f"{int(age)} years"))
    etf = metrics.get("etf_access")
    if etf is not None:
        adopt_items.append(("ETF Access", "Yes" if etf else "No"))
    reg = metrics.get("regulatory_status")
    if reg is not None:
        adopt_items.append(("Regulatory", str(reg)))
    bear = _as_float(metrics.get("bear_survivals"))
    if bear is not None:
        adopt_items.append(("Bear Survivals", str(int(bear))))
    _append_group(lines, "Network & Adoption", adopt_items)

    # Cycle details
    cycle_items: list[tuple[str, str | None]] = []
    phase = metrics.get("cycle_phase")
    if phase is not None:
        cycle_items.append(("Cycle Phase", str(phase)))
    months = _as_float(metrics.get("months_since_halving"))
    if months is not None:
        cycle_items.append(("Months Since Halving", f"{months:.0f}"))
    pos = _as_float(metrics.get("halving_cycle_position"))
    if pos is not None:
        cycle_items.append(("Cycle Position", f"{pos:.2f}"))
    fg = _as_float(metrics.get("fear_greed_proxy"))
    if fg is not None:
        cycle_items.append(("Fear/Greed Proxy", f"{fg:.0f}"))
    _append_group(lines, "Cycle & Timing", cycle_items)

    # Regime
    regime = metrics.get("regime")
    if regime is not None:
        _append_group(lines, "Regime", [("Regime", str(regime))])


def _append_group(
    lines: list[str],
    title: str,
    items: list[tuple[str, str | None]],
) -> None:
    """Append a named group of key-value metric lines, skipping None values."""
    valid = [(k, v) for k, v in items if v is not None]
    if not valid:
        return
    lines.append(f"    {title}:")
    for key, val in valid:
        lines.append(f"      {key:<18} {val}")


def _fmt_score(value: Any) -> str | None:
    """Format a numeric score as '+N' / '-N', or None if absent."""
    v = _as_float(value)
    if v is None:
        return None
    return f"{int(round(v)):+d}"


# ---------------------------------------------------------------------------
# Aggregation transparency section (detail=True only)
# ---------------------------------------------------------------------------

def _format_aggregation_detail(signal: AggregatedSignal) -> list[str]:
    """Return lines for the aggregation math transparency block."""
    line_minor = "-" * REPORT_WIDTH
    lines: list[str] = [
        line_minor,
        "  AGGREGATION DETAIL",
        line_minor,
    ]

    metrics = signal.metrics or {}
    weights_used: dict[str, float] = metrics.get("weights_used", {})
    raw_score = _as_float(metrics.get("raw_score"))
    consensus_score = _as_float(metrics.get("consensus_score"))

    # Weights
    if weights_used:
        parts = [
            f"{name.replace('Agent', '')} {w:.2f}"
            for name, w in weights_used.items()
        ]
        lines.append(f"    Weights:         {', '.join(parts)}")

    # Raw score
    if raw_score is not None:
        sign = "+" if raw_score >= 0 else ""
        lines.append(f"    Raw Score:       {sign}{raw_score:.4f} (threshold: +/-0.30)")

    # Consensus
    buy_count = metrics.get("buy_count", 0)
    sell_count = metrics.get("sell_count", 0)
    hold_count = metrics.get("hold_count", 0)
    total = buy_count + sell_count + hold_count
    if total > 0 and consensus_score is not None:
        max_count = max(buy_count, sell_count, hold_count)
        if buy_count == max_count:
            dominant = "BUY"
        elif sell_count == max_count:
            dominant = "SELL"
        else:
            dominant = "HOLD"
        strength = (
            "strong" if consensus_score >= 1.0
            else "moderate" if consensus_score >= 0.5
            else "low"
        )
        lines.append(f"    Consensus:       {max_count}/{total} agents {dominant} ({strength})")

    # Consensus adjustment
    if consensus_score is not None:
        if consensus_score < 0.5:
            lines.append("    Consensus Adj:   0.8x penalty applied (< 50% agreement)")
        else:
            lines.append("    Consensus Adj:   none (>= 50%)")

    # Final
    lines.append(
        f"    Final:           {signal.final_signal.value}"
        f" @ {signal.final_confidence:.0f}% confidence"
    )

    return lines


# ---------------------------------------------------------------------------
# Sector adjustment section (detail=True only for full block)
# ---------------------------------------------------------------------------

def _format_sector_detail(
    sector: str,
    regime: str,
    modifier: int,
    pre_confidence: float | None,
    post_confidence: float,
    line_minor: str,
) -> list[str]:
    """Return lines for the SECTOR ADJUSTMENT block (detail=True)."""
    lines: list[str] = [
        line_minor,
        "  SECTOR ADJUSTMENT",
        line_minor,
    ]
    lines.append(f"    Sector:     {sector}")
    lines.append(f"    Regime:     {regime}")

    sign = "+" if modifier >= 0 else ""
    if modifier > 0:
        flavor = "sector favored in current regime"
    elif modifier < 0:
        flavor = "sector faces headwinds in current regime"
    else:
        flavor = "no adjustment"
    lines.append(f"    Modifier:   {sign}{modifier} ({flavor})")

    if pre_confidence is not None:
        lines.append(
            f"    Adjusted:   {pre_confidence:.0f}% -> {post_confidence:.0f}% confidence"
        )

    return lines


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _format_consensus(agent_outputs: list[AgentOutput]) -> str:
    if not agent_outputs:
        return "0/0 agents (no signals)"

    signals = [output.signal for output in agent_outputs]
    buy_count = signals.count(Signal.BUY)
    sell_count = signals.count(Signal.SELL)
    hold_count = signals.count(Signal.HOLD)
    total = len(signals)
    max_count = max(buy_count, sell_count, hold_count)
    consensus_score = max_count / total if total else 0.0

    if consensus_score >= 1.0:
        suffix = "agents agree (strong consensus)"
    elif consensus_score >= 0.5:
        suffix = "agents agree"
    else:
        suffix = "agents (low consensus)"
    return f"{max_count}/{total} {suffix}"


def _first_present(metrics: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in metrics:
            return metrics.get(key)
    return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _analyst_label(rating: float) -> str:
    """Convert numeric analyst rating to human-readable label."""
    if rating <= 1.5:
        return "Strong Buy"
    if rating <= 2.5:
        return "Buy"
    if rating <= 3.5:
        return "Hold"
    if rating <= 4.5:
        return "Sell"
    return "Strong Sell"


def _format_large_number(value: float) -> str:
    """Format large numbers with B/M/K suffixes."""
    abs_val = abs(value)
    if abs_val >= 1e12:
        return f"${value / 1e12:,.2f}T"
    if abs_val >= 1e9:
        return f"${value / 1e9:,.2f}B"
    if abs_val >= 1e6:
        return f"${value / 1e6:,.1f}M"
    if abs_val >= 1e3:
        return f"${value / 1e3:,.0f}K"
    return f"${value:,.0f}"
