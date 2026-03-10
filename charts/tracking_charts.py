"""Tracking charts: calibration line and expected vs actual return scatter."""
from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

CHART_TEMPLATE = "plotly_dark"


def create_calibration_chart(calibration_data: list[dict[str, Any]]) -> go.Figure:
    """Confidence calibration chart: expected vs actual win rate.

    Args:
        calibration_data: List of dicts from SignalTracker.compute_calibration_data().
            Each dict has: confidence_bucket, bucket_midpoint, expected_win_rate,
            actual_win_rate, sample_size.
    Returns:
        go.Figure with two lines (expected + actual) and shaded gap area.
        If empty, returns figure with "Insufficient data" annotation.
    """
    if not calibration_data:
        fig = go.Figure()
        fig.update_layout(
            title="Confidence Calibration",
            template=CHART_TEMPLATE,
            annotations=[
                dict(
                    text="Insufficient data for calibration",
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

    midpoints = [d["bucket_midpoint"] for d in calibration_data]
    expected = [d["expected_win_rate"] for d in calibration_data]
    actual = [d["actual_win_rate"] for d in calibration_data]
    sample_sizes = [d["sample_size"] for d in calibration_data]

    # Shaded area between expected and actual
    fig = go.Figure()

    # Fill between: expected on top (upper boundary), actual on bottom
    fig.add_trace(
        go.Scatter(
            x=midpoints,
            y=expected,
            name="Expected",
            mode="lines+markers",
            line={"color": "#4C72B0", "width": 2, "dash": "dash"},
            marker={"size": 8},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=midpoints,
            y=actual,
            name="Actual",
            mode="lines+markers",
            fill="tonexty",
            fillcolor="rgba(76,114,176,0.15)",
            line={"color": "#DD8452", "width": 2},
            marker={"size": 8},
            text=[f"n={n}" for n in sample_sizes],
            hovertemplate="Confidence: %{x}<br>Actual Win Rate: %{y:.1f}%<br>%{text}<extra></extra>",
        )
    )

    fig.update_layout(
        title="Confidence Calibration",
        template=CHART_TEMPLATE,
        xaxis=dict(title="Confidence Bucket Midpoint (%)"),
        yaxis=dict(title="Win Rate (%)"),
        height=450,
        legend=dict(orientation="h", y=-0.15),
    )
    return fig


def create_drift_scatter(drift_data: list[dict[str, Any]]) -> go.Figure:
    """Scatter plot of expected vs actual return.

    Args:
        drift_data: List of dicts with expected_return_pct, actual_return_pct,
            and optionally outcome (WIN/LOSS) and ticker.
    Returns:
        go.Figure scatter. If empty, returns figure with annotation.
    """
    if not drift_data:
        fig = go.Figure()
        fig.update_layout(
            title="Expected vs Actual Return",
            template=CHART_TEMPLATE,
            annotations=[
                dict(
                    text="No resolved signals yet",
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

    expected = [d.get("expected_return_pct", 0) for d in drift_data]
    actual = [d.get("actual_return_pct", 0) for d in drift_data]
    outcomes = [d.get("outcome", "UNKNOWN") for d in drift_data]
    tickers = [d.get("ticker", "") for d in drift_data]

    colors = [
        "#00CC66" if o == "WIN"
        else "#CC3333" if o == "LOSS"
        else "#888888"
        for o in outcomes
    ]

    fig = go.Figure()

    # Diagonal reference line (y = x)
    all_vals = expected + actual
    if all_vals:
        min_val = min(all_vals)
        max_val = max(all_vals)
        fig.add_trace(
            go.Scatter(
                x=[min_val, max_val],
                y=[min_val, max_val],
                mode="lines",
                name="Perfect Prediction",
                line={"color": "#888888", "dash": "dash", "width": 1},
            )
        )

    fig.add_trace(
        go.Scatter(
            x=expected,
            y=actual,
            mode="markers",
            name="Signals",
            marker=dict(color=colors, size=10, opacity=0.8),
            text=[f"{t}<br>{o}" for t, o in zip(tickers, outcomes)],
            hovertemplate=(
                "%{text}<br>"
                "Expected: %{x:.1%}<br>"
                "Actual: %{y:.1%}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title="Expected vs Actual Return",
        template=CHART_TEMPLATE,
        xaxis=dict(title="Expected Return"),
        yaxis=dict(title="Actual Return"),
        height=500,
    )
    return fig
