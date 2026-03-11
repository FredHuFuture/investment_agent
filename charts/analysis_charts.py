"""Analysis charts: price candlestick with indicators and agent signal breakdown."""
from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from agents.models import AgentOutput, Signal

CHART_TEMPLATE = "plotly_dark"

_FACTOR_DISPLAY = {
    "market_structure_score": ("Market Structure", 15),
    "momentum_trend_score": ("Momentum & Trend", 20),
    "volatility_risk_score": ("Volatility & Risk", 15),
    "liquidity_volume_score": ("Liquidity & Volume", 10),
    "macro_correlation_score": ("Macro & Correlation", 15),
    "network_adoption_score": ("Network & Adoption", 10),
    "cycle_timing_score": ("Cycle & Timing", 15),
}
CHART_COLORS = {
    "buy": "#00CC66",
    "hold": "#888888",
    "sell": "#CC3333",
    "sma_20": "#1f77b4",
    "sma_50": "#ff7f0e",
    "sma_200": "#d62728",
    "volume_up": "#00CC66",
    "volume_down": "#CC3333",
}


def create_price_chart(
    ohlcv: pd.DataFrame,
    ticker: str,
    indicators: dict[str, Any] | None = None,
) -> go.Figure:
    """Candlestick price chart with volume and RSI subplots.

    Args:
        ohlcv: DataFrame with columns Open, High, Low, Close, Volume. Index is dates.
        ticker: Ticker symbol for title.
        indicators: Optional dict with Series for sma_20, sma_50, sma_200,
                    bb_upper, bb_lower, rsi_14.
    Returns:
        go.Figure with 3 subplots (price, volume, RSI).
    """
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.70, 0.15, 0.15],
        vertical_spacing=0.03,
    )

    # --- Row 1: Candlestick ---
    fig.add_trace(
        go.Candlestick(
            x=ohlcv.index,
            open=ohlcv["Open"],
            high=ohlcv["High"],
            low=ohlcv["Low"],
            close=ohlcv["Close"],
            name=ticker,
            increasing_line_color=CHART_COLORS["buy"],
            decreasing_line_color=CHART_COLORS["sell"],
        ),
        row=1,
        col=1,
    )

    if indicators:
        # Bollinger Bands fill
        bb_upper = indicators.get("bb_upper")
        bb_lower = indicators.get("bb_lower")
        if bb_upper is not None and bb_lower is not None:
            fig.add_trace(
                go.Scatter(
                    x=ohlcv.index,
                    y=bb_upper,
                    name="BB Upper",
                    line={"color": "rgba(150,150,150,0.4)", "width": 1},
                    showlegend=False,
                ),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=ohlcv.index,
                    y=bb_lower,
                    name="BB Lower",
                    fill="tonexty",
                    fillcolor="rgba(150,150,150,0.1)",
                    line={"color": "rgba(150,150,150,0.4)", "width": 1},
                    showlegend=False,
                ),
                row=1,
                col=1,
            )

        # SMA lines
        for key, color_key, label in [
            ("sma_20", "sma_20", "SMA 20"),
            ("sma_50", "sma_50", "SMA 50"),
            ("sma_200", "sma_200", "SMA 200"),
        ]:
            sma = indicators.get(key)
            if sma is not None:
                fig.add_trace(
                    go.Scatter(
                        x=ohlcv.index,
                        y=sma,
                        name=label,
                        line={"color": CHART_COLORS[color_key], "width": 1},
                    ),
                    row=1,
                    col=1,
                )

    # --- Row 2: Volume ---
    colors = [
        CHART_COLORS["volume_up"] if c >= o else CHART_COLORS["volume_down"]
        for c, o in zip(ohlcv["Close"], ohlcv["Open"])
    ]
    fig.add_trace(
        go.Bar(
            x=ohlcv.index,
            y=ohlcv["Volume"],
            name="Volume",
            marker_color=colors,
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    # --- Row 3: RSI ---
    rsi = indicators.get("rsi_14") if indicators else None
    if rsi is not None:
        fig.add_trace(
            go.Scatter(
                x=ohlcv.index,
                y=rsi,
                name="RSI 14",
                line={"color": "#9b59b6", "width": 1.5},
            ),
            row=3,
            col=1,
        )
    # RSI reference lines
    for level, color in [(30, "#00CC66"), (70, "#CC3333")]:
        fig.add_hline(
            y=level,
            line_color=color,
            line_dash="dash",
            line_width=1,
            row=3,
            col=1,
        )

    fig.update_layout(
        title=f"{ticker} -- Price Analysis",
        template=CHART_TEMPLATE,
        xaxis_rangeslider_visible=False,
        xaxis=dict(
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=3, label="3M", step="month", stepmode="backward"),
                    dict(count=6, label="6M", step="month", stepmode="backward"),
                    dict(count=1, label="1Y", step="year", stepmode="backward"),
                    dict(step="all", label="All"),
                ],
                bgcolor="rgba(60,60,60,0.9)",
                activecolor="#777",
                bordercolor="#555",
                borderwidth=1,
                font=dict(color="#ddd", size=11),
                x=0.0,
                y=1.03,
            ),
        ),
        height=700,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="right",
            x=1,
            font=dict(size=10),
        ),
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1, range=[0, 100])

    return fig


def _build_signal_hover(s: dict) -> str:
    """Build rich hover HTML for a single historical signal point.

    Shows signal, confidence, sub-scores, key indicators, and reasoning.
    """
    sig = s["signal"].value
    conf = s["confidence"]
    m = s.get("metrics") or {}
    reason = s.get("reasoning", "")

    lines: list[str] = [
        f"<b>{s['date'].strftime('%Y-%m-%d')}</b>",
        f"<b>{sig}</b> @ {conf:.0f}% confidence",
        "",
    ]

    # Sub-scores
    sub = []
    for label, key in [
        ("Trend", "trend_score"),
        ("Momentum", "momentum_score"),
        ("Volatility", "volatility_score"),
    ]:
        v = m.get(key)
        if v is not None:
            sub.append(f"{label}: {v:+.0f}")
    if sub:
        lines.append("  ".join(sub))

    # Key indicators
    ind: list[str] = []
    rsi = m.get("rsi_14")
    if rsi is not None:
        ind.append(f"RSI: {rsi:.1f}")
    macd_h = m.get("macd_histogram")
    if macd_h is not None:
        ind.append(f"MACD Hist: {macd_h:+.2f}")
    vr = m.get("volume_ratio")
    if vr is not None:
        ind.append(f"Vol Ratio: {vr:.2f}x")
    if ind:
        lines.append("  ".join(ind))

    # Reasoning (truncated, wrapped)
    if reason:
        if len(reason) > 200:
            reason = reason[:200] + "..."
        lines.append("")
        lines.append(f"<i>{reason}</i>")

    return "<br>".join(lines)


def add_signal_markers(
    fig: go.Figure,
    signals: list[dict],
    ohlcv: pd.DataFrame,
    min_confidence: float = 70.0,
) -> None:
    """Overlay BUY/SELL markers on a price chart (row=1).

    BUY markers are green triangles below candles (at Low * 0.97).
    SELL markers are red inverted triangles above candles (at High * 1.03).
    Only signals meeting the ``min_confidence`` threshold are shown.
    Hover shows full analysis breakdown (sub-scores, indicators, reasoning).

    Args:
        fig: The go.Figure returned by :func:`create_price_chart` (3-row subplot).
        signals: List of dicts with keys ``date``, ``signal`` (Signal enum),
                 ``confidence`` (float 0-100), and optionally ``metrics`` (dict)
                 and ``reasoning`` (str) for rich hover.
        ohlcv: The same OHLCV DataFrame used to create the chart (for price lookup).
        min_confidence: Minimum confidence % to display a marker (default 70).
    """
    buys = [
        s for s in signals
        if s["signal"] == Signal.BUY and s["confidence"] >= min_confidence
    ]
    sells = [
        s for s in signals
        if s["signal"] == Signal.SELL and s["confidence"] >= min_confidence
    ]

    def _lookup_price(date, col: str) -> float | None:
        mask = ohlcv.index.normalize() == date.normalize()
        if mask.any():
            return float(ohlcv.loc[mask, col].iloc[0])
        return None

    if buys:
        buy_dates = [s["date"] for s in buys]
        buy_prices = [
            p * 0.97 if (p := _lookup_price(d, "Low")) is not None else None
            for d in buy_dates
        ]
        fig.add_trace(
            go.Scatter(
                x=buy_dates,
                y=buy_prices,
                mode="markers",
                marker=dict(
                    symbol="triangle-up",
                    size=13,
                    color=CHART_COLORS["buy"],
                    line=dict(width=1, color="white"),
                ),
                name=f"BUY (>={min_confidence:.0f}%)",
                hoverinfo="text",
                hovertext=[_build_signal_hover(s) for s in buys],
            ),
            row=1,
            col=1,
        )

    if sells:
        sell_dates = [s["date"] for s in sells]
        sell_prices = [
            p * 1.03 if (p := _lookup_price(d, "High")) is not None else None
            for d in sell_dates
        ]
        fig.add_trace(
            go.Scatter(
                x=sell_dates,
                y=sell_prices,
                mode="markers",
                marker=dict(
                    symbol="triangle-down",
                    size=13,
                    color=CHART_COLORS["sell"],
                    line=dict(width=1, color="white"),
                ),
                name=f"SELL (>={min_confidence:.0f}%)",
                hoverinfo="text",
                hovertext=[_build_signal_hover(s) for s in sells],
            ),
            row=1,
            col=1,
        )


def create_agent_breakdown_chart(agent_signals: list[AgentOutput]) -> go.Figure:
    """Horizontal bar chart of agent signals and confidence.

    Args:
        agent_signals: List of AgentOutput objects.
    Returns:
        go.Figure with one bar per agent.
    """
    if not agent_signals:
        fig = go.Figure()
        fig.update_layout(
            title="Agent Signal Breakdown",
            template=CHART_TEMPLATE,
            annotations=[
                dict(
                    text="No agent signals available",
                    x=0.5,
                    y=0.5,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                    font={"size": 16},
                )
            ],
        )
        return fig

    names = [a.agent_name.replace("Agent", "") for a in agent_signals]
    confidences = [a.confidence for a in agent_signals]
    colors = [
        CHART_COLORS["buy"] if a.signal == Signal.BUY
        else CHART_COLORS["sell"] if a.signal == Signal.SELL
        else CHART_COLORS["hold"]
        for a in agent_signals
    ]
    texts = [f"{a.signal.value}  {a.confidence:.0f}%" for a in agent_signals]

    fig = go.Figure(
        go.Bar(
            x=confidences,
            y=names,
            orientation="h",
            marker_color=colors,
            text=texts,
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Agent Signal Breakdown",
        template=CHART_TEMPLATE,
        xaxis=dict(title="Confidence", range=[0, 110]),
        yaxis=dict(title="Agent"),
        height=max(250, 80 * len(agent_signals)),
    )
    return fig


def create_crypto_factor_chart(crypto_output: AgentOutput) -> go.Figure:
    """Horizontal bar chart showing CryptoAgent's 7 factor scores.

    Each factor bar is colored green (positive) or red (negative),
    with weight percentage labels.

    Args:
        crypto_output: AgentOutput from CryptoAgent with factor scores in metrics.
    Returns:
        go.Figure with one bar per factor.
    """
    metrics = crypto_output.metrics or {}
    names: list[str] = []
    scores: list[float] = []
    colors: list[str] = []
    texts: list[str] = []

    for key, (label, weight) in _FACTOR_DISPLAY.items():
        score = metrics.get(key, 0.0)
        names.append(f"{label} ({weight}%)")
        scores.append(score)
        colors.append(CHART_COLORS["buy"] if score >= 0 else CHART_COLORS["sell"])
        texts.append(f"{score:+.0f}")

    composite = metrics.get("composite_score", 0.0)
    signal_str = crypto_output.signal.value
    conf = crypto_output.confidence

    fig = go.Figure(
        go.Bar(
            x=scores,
            y=names,
            orientation="h",
            marker_color=colors,
            text=texts,
            textposition="outside",
        )
    )
    fig.update_layout(
        title=f"CryptoAgent 7-Factor Breakdown  --  {signal_str} @ {conf:.0f}%  (composite: {composite:+.0f})",
        template=CHART_TEMPLATE,
        xaxis=dict(title="Factor Score", range=[-110, 110]),
        yaxis=dict(title="Factor", autorange="reversed"),
        height=450,
    )
    return fig
