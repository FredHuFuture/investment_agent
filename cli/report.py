from __future__ import annotations

import json
from typing import Any

from agents.models import AgentOutput, Signal
from engine.aggregator import AggregatedSignal

REPORT_WIDTH = 64


def format_analysis_report(signal: AggregatedSignal) -> str:
    """Format an AggregatedSignal into a human-readable terminal report."""
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
        for output in signal.agent_signals:
            short_name = output.agent_name.replace("Agent", "")
            label = f"{short_name}:"
            lines.append(f"  {label:<14}{output.signal.value:<5}({output.confidence:.0f}%)")
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
            "  WARNINGS:",
        ]
    )

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
        roe = _as_float(metrics.get("roe"))
        if roe is not None:
            parts.append(f"ROE: {roe:.1%}")
        revenue_growth = _first_present(metrics, ["revenue_growth_yoy", "revenue_growth"])
        revenue_val = _as_float(revenue_growth)
        if revenue_val is not None:
            parts.append(f"Rev Growth: {revenue_val:+.1%}")
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

    return "(unknown agent)"


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
