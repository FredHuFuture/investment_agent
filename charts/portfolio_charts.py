"""Portfolio charts: allocation pie and sector exposure bar."""
from __future__ import annotations

import plotly.graph_objects as go

from portfolio.models import Portfolio

CHART_TEMPLATE = "plotly_dark"


def create_allocation_chart(portfolio: Portfolio) -> go.Figure:
    """Pie chart of portfolio allocation by cost_basis.

    Args:
        portfolio: Portfolio object with positions and cash.
    Returns:
        go.Figure with pie chart including cash slice.
    """
    labels: list[str] = []
    values: list[float] = []
    hover_texts: list[str] = []

    for pos in portfolio.positions:
        cb = pos.cost_basis
        if cb > 0:
            labels.append(pos.ticker)
            values.append(cb)
            hover_texts.append(
                f"{pos.ticker}<br>Cost Basis: ${cb:,.0f}<br>Qty: {pos.quantity:.4f}"
            )

    if portfolio.cash > 0:
        labels.append("Cash")
        values.append(portfolio.cash)
        hover_texts.append(f"Cash<br>${portfolio.cash:,.0f}")

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hovertext=hover_texts,
            hoverinfo="text+percent",
            textinfo="label+percent",
        )
    )
    fig.update_layout(
        title="Portfolio Allocation",
        template=CHART_TEMPLATE,
        height=500,
    )
    return fig


def create_sector_chart(portfolio: Portfolio) -> go.Figure:
    """Horizontal bar chart of sector exposure by cost_basis.

    Args:
        portfolio: Portfolio object with positions.
    Returns:
        go.Figure with one bar per sector sorted descending.
    """
    sector_values: dict[str, float] = {}
    for pos in portfolio.positions:
        sector = pos.sector or "Unknown"
        sector_values[sector] = sector_values.get(sector, 0.0) + pos.cost_basis

    if not sector_values:
        fig = go.Figure()
        fig.update_layout(
            title="Sector Exposure",
            template=CHART_TEMPLATE,
            annotations=[
                dict(
                    text="No positions",
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

    sorted_sectors = sorted(sector_values.items(), key=lambda x: x[1])
    sectors = [s[0] for s in sorted_sectors]
    values = [s[1] for s in sorted_sectors]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=sectors,
            orientation="h",
            marker_color="#4C72B0",
            text=[f"${v:,.0f}" for v in values],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Sector Exposure",
        template=CHART_TEMPLATE,
        xaxis=dict(title="Cost Basis ($)"),
        yaxis=dict(title="Sector"),
        height=max(300, 60 * len(sectors) + 100),
    )
    return fig
