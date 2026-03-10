"""Analysis charts: price candlestick with indicators and agent signal breakdown."""
from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from agents.models import AgentOutput, Signal

CHART_TEMPLATE = "plotly_dark"
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
        xaxis3=dict(
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=3, label="3M", step="month", stepmode="backward"),
                    dict(count=6, label="6M", step="month", stepmode="backward"),
                    dict(count=1, label="1Y", step="year", stepmode="backward"),
                    dict(step="all", label="All"),
                ]
            )
        ),
        height=700,
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1, range=[0, 100])

    return fig


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
