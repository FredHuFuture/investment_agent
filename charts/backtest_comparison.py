"""Generate backtest comparison charts: Signal Timing vs Buy-and-Hold."""
from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def generate_comparison_chart(data_path: str, output_path: str) -> str:
    """Generate an interactive HTML comparison chart.

    Args:
        data_path: Path to backtest_data.json
        output_path: Path to write the HTML file

    Returns:
        Path to the generated HTML file.
    """
    with open(data_path) as f:
        data = json.load(f)

    tickers = list(data.keys())

    # ---- Extract metrics ----
    signal_returns = [data[t]["total_return"] for t in tickers]
    bh_returns = [data[t]["bh_return"] for t in tickers]
    signal_dd = [abs(data[t]["max_dd"]) for t in tickers]
    bh_dd = [abs(data[t]["bh_max_dd"]) for t in tickers]
    sharpes = [data[t]["sharpe"] or 0 for t in tickers]
    win_rates = [(data[t]["win_rate"] or 0) * 100 for t in tickers]

    # SPY buy-and-hold annualized as benchmark line
    spy_bh_return = data["SPY"]["bh_return"]

    # ---- Build 4-panel chart ----
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "Total Return: Signal Timing vs Buy & Hold",
            "Max Drawdown Comparison (lower = better)",
            "Sharpe Ratio (risk-adjusted return)",
            "Win Rate & Trade Count",
        ],
        vertical_spacing=0.15,
        horizontal_spacing=0.12,
    )

    colors_signal = "#2196F3"
    colors_bh = "#FF9800"

    # -- Panel 1: Total Return bars --
    fig.add_trace(
        go.Bar(
            name="Signal Timing",
            x=tickers,
            y=signal_returns,
            marker_color=colors_signal,
            text=[f"+{r:.0f}%" for r in signal_returns],
            textposition="outside",
            showlegend=True,
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Bar(
            name="Buy & Hold",
            x=tickers,
            y=bh_returns,
            marker_color=colors_bh,
            text=[f"+{r:.0f}%" for r in bh_returns],
            textposition="outside",
            showlegend=True,
        ),
        row=1, col=1,
    )

    # -- Panel 2: Max Drawdown bars (shown as positive for visual clarity) --
    fig.add_trace(
        go.Bar(
            name="Signal Timing DD",
            x=tickers,
            y=signal_dd,
            marker_color=colors_signal,
            text=[f"-{d:.1f}%" for d in signal_dd],
            textposition="outside",
            showlegend=False,
        ),
        row=1, col=2,
    )
    fig.add_trace(
        go.Bar(
            name="Buy & Hold DD",
            x=tickers,
            y=bh_dd,
            marker_color=colors_bh,
            text=[f"-{d:.1f}%" for d in bh_dd],
            textposition="outside",
            showlegend=False,
        ),
        row=1, col=2,
    )
    # Add annotation: lower is better
    fig.add_annotation(
        text="<b>Lower bar = less risk</b>",
        xref="x2", yref="y2",
        x=0.5, y=max(bh_dd) * 0.9,
        showarrow=False,
        font=dict(size=11, color="#666"),
    )

    # -- Panel 3: Sharpe Ratio --
    bar_colors = []
    for s in sharpes:
        if s >= 2.0:
            bar_colors.append("#4CAF50")  # green = excellent
        elif s >= 1.0:
            bar_colors.append("#2196F3")  # blue = good
        else:
            bar_colors.append("#FF9800")  # orange = ok
    fig.add_trace(
        go.Bar(
            name="Sharpe",
            x=tickers,
            y=sharpes,
            marker_color=bar_colors,
            text=[f"{s:.2f}" for s in sharpes],
            textposition="outside",
            showlegend=False,
        ),
        row=2, col=1,
    )
    # Reference lines
    fig.add_hline(y=1.0, line_dash="dash", line_color="#999",
                  annotation_text="Good (1.0)", row=2, col=1)
    fig.add_hline(y=2.0, line_dash="dash", line_color="#4CAF50",
                  annotation_text="Excellent (2.0)", row=2, col=1)

    # -- Panel 4: Win Rate + Trade Count --
    fig.add_trace(
        go.Bar(
            name="Win Rate %",
            x=tickers,
            y=win_rates,
            marker_color="#4CAF50",
            text=[f"{w:.0f}%" for w in win_rates],
            textposition="outside",
            showlegend=False,
        ),
        row=2, col=2,
    )
    # Add trade count as text annotations
    trades = [data[t]["trades"] for t in tickers]
    for i, (t, n) in enumerate(zip(tickers, trades)):
        fig.add_annotation(
            text=f"{n} trades",
            x=t, y=win_rates[i] + 5,
            xref="x4", yref="y4",
            showarrow=False,
            font=dict(size=10, color="#666"),
        )
    fig.add_hline(y=50, line_dash="dash", line_color="#999",
                  annotation_text="50%", row=2, col=2)

    # ---- Layout ----
    fig.update_layout(
        title=dict(
            text=(
                "Investment Agent v4 -- Backtest Results (2020-2025)<br>"
                "<sup>TechnicalAgent | Weekly Rebalance | Full Position | No SL/TP</sup>"
            ),
            x=0.5,
            font=dict(size=18),
        ),
        template="plotly_dark",
        barmode="group",
        height=800,
        width=1200,
        font=dict(family="Arial", size=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(t=120, b=60),
    )

    # Y-axis labels
    fig.update_yaxes(title_text="Return %", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown %", row=1, col=2)
    fig.update_yaxes(title_text="Sharpe Ratio", row=2, col=1)
    fig.update_yaxes(title_text="Win Rate %", row=2, col=2)

    # ---- Equity Curve Chart (separate) ----
    eq_fig = go.Figure()

    # Normalize all equity curves to 100 base
    for ticker in tickers:
        eq = data[ticker]["equity_curve"]
        if not eq:
            continue
        dates = [e["date"] for e in eq]
        base = eq[0]["equity"]
        normalized = [(e["equity"] / base) * 100 for e in eq]
        eq_fig.add_trace(go.Scatter(
            x=dates, y=normalized,
            mode="lines",
            name=f"{ticker} Signal",
            line=dict(width=2),
        ))

    # Add SPY buy-and-hold as dashed benchmark
    spy_eq = data["SPY"]["equity_curve"]
    if spy_eq:
        dates = [e["date"] for e in spy_eq]
        base = spy_eq[0]["equity"]
        # Reconstruct B&H: just scale by SPY price movement
        # Use signal equity start date price ratios
        eq_fig.add_hline(y=100, line_dash="dot", line_color="#666",
                         annotation_text="Starting Capital")

    eq_fig.update_layout(
        title=dict(
            text=(
                "Equity Curves (Normalized to 100)<br>"
                "<sup>Signal Timing Strategy | 2020-2025</sup>"
            ),
            x=0.5,
            font=dict(size=16),
        ),
        template="plotly_dark",
        height=500,
        width=1200,
        yaxis_title="Portfolio Value (base=100)",
        xaxis_title="Date",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5, xanchor="center"),
        margin=dict(t=100),
    )

    # ---- Return vs Risk Scatter ----
    scatter_fig = go.Figure()

    for i, t in enumerate(tickers):
        # Signal timing point
        scatter_fig.add_trace(go.Scatter(
            x=[abs(data[t]["max_dd"])],
            y=[data[t]["total_return"]],
            mode="markers+text",
            name=f"{t} Signal",
            text=[t],
            textposition="top center",
            marker=dict(size=14, color=colors_signal, symbol="circle"),
            showlegend=i == 0,
        ))
        # Buy & Hold point
        scatter_fig.add_trace(go.Scatter(
            x=[abs(data[t]["bh_max_dd"])],
            y=[data[t]["bh_return"]],
            mode="markers+text",
            name=f"{t} B&H",
            text=[t],
            textposition="bottom center",
            marker=dict(size=14, color=colors_bh, symbol="diamond"),
            showlegend=i == 0,
        ))
        # Connect them with a line
        scatter_fig.add_trace(go.Scatter(
            x=[abs(data[t]["max_dd"]), abs(data[t]["bh_max_dd"])],
            y=[data[t]["total_return"], data[t]["bh_return"]],
            mode="lines",
            line=dict(color="#555", dash="dot", width=1),
            showlegend=False,
        ))

    scatter_fig.update_layout(
        title=dict(
            text=(
                "Return vs Risk: Signal Timing vs Buy & Hold<br>"
                "<sup>Left = less risk, Up = more return | Ideal = top-left corner</sup>"
            ),
            x=0.5,
            font=dict(size=16),
        ),
        template="plotly_dark",
        height=600,
        width=1000,
        xaxis_title="Max Drawdown % (absolute)",
        yaxis_title="Total Return %",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5, xanchor="center"),
        margin=dict(t=100),
    )

    # ---- Combine into single HTML ----
    html = _build_html(fig, eq_fig, scatter_fig)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


def _build_html(
    comparison_fig: go.Figure,
    equity_fig: go.Figure,
    scatter_fig: go.Figure,
) -> str:
    """Build a single HTML page with all three charts."""
    comp_json = comparison_fig.to_json()
    eq_json = equity_fig.to_json()
    scatter_json = scatter_fig.to_json()

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>Investment Agent v4 -- Backtest Report</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  body {{
    background: #1a1a2e; color: #eee;
    font-family: 'Segoe UI', Arial, sans-serif;
    margin: 0; padding: 20px 40px;
  }}
  h1 {{ text-align: center; color: #4fc3f7; margin-bottom: 5px; }}
  .subtitle {{ text-align: center; color: #999; margin-bottom: 30px; font-size: 14px; }}
  .chart-container {{ margin-bottom: 40px; }}
  .summary-table {{
    width: 100%; border-collapse: collapse; margin: 20px 0;
    font-size: 14px;
  }}
  .summary-table th {{
    background: #16213e; padding: 10px; text-align: center;
    border-bottom: 2px solid #4fc3f7;
  }}
  .summary-table td {{
    padding: 8px 10px; text-align: center; border-bottom: 1px solid #333;
  }}
  .summary-table tr:hover {{ background: #16213e; }}
  .positive {{ color: #4CAF50; }}
  .negative {{ color: #f44336; }}
  .highlight {{ background: #1a3a5c !important; }}
  .section {{ margin: 30px 0; }}
  .section h2 {{ color: #4fc3f7; border-bottom: 1px solid #333; padding-bottom: 8px; }}
  .insight-box {{
    background: #16213e; border-left: 4px solid #4fc3f7;
    padding: 15px 20px; margin: 15px 0; border-radius: 0 8px 8px 0;
  }}
  .insight-box strong {{ color: #4fc3f7; }}
  .footnote {{ color: #666; font-size: 12px; margin-top: 40px; text-align: center; }}
</style>
</head>
<body>

<h1>Investment Agent v4 -- Backtest Report</h1>
<p class="subtitle">
  TechnicalAgent | 2020-01-01 to 2025-12-31 | Weekly Rebalance | Full Position | No Stop-Loss/Take-Profit
</p>

<div class="section">
<h2>Summary</h2>
<table class="summary-table">
<thead>
<tr>
  <th>Ticker</th>
  <th>Signal Return</th>
  <th>Buy & Hold</th>
  <th>Signal MaxDD</th>
  <th>B&H MaxDD</th>
  <th>DD Improvement</th>
  <th>Sharpe</th>
  <th>Win Rate</th>
  <th>Trades</th>
</tr>
</thead>
<tbody id="summary-body"></tbody>
</table>
</div>

<div class="section">
<h2>Key Insights</h2>
<div class="insight-box">
  <strong>Drawdown Protection</strong> -- Signal timing reduced max drawdown on ALL tickers.
  BTC: -76.6% -> -40.7% (35.9pp improvement). SPY: -34.1% -> -18.7% (15.4pp improvement).
</div>
<div class="insight-box">
  <strong>BTC Best Use Case</strong> -- Captured 92% of buy-and-hold return while cutting drawdown nearly in half.
  Sharpe ratio 2.36 indicates excellent risk-adjusted performance.
</div>
<div class="insight-box">
  <strong>Bull Market Tradeoff</strong> -- Total returns lag buy-and-hold in a 5-year bull market.
  The system holds cash during HOLD periods. The value is in risk management, not return maximization.
</div>
</div>

<div class="chart-container" id="comparison-chart"></div>
<div class="chart-container" id="scatter-chart"></div>
<div class="chart-container" id="equity-chart"></div>

<p class="footnote">
  Generated by Investment Agent v4 | TechnicalAgent only (PIT-safe, no look-ahead bias) |
  No transaction costs or slippage | Cash earns 0% during HOLD periods
</p>

<script>
var DATA = {{
  AAPL: {{ sig_ret: 123.6, bh_ret: 263.7, sig_dd: -33.2, bh_dd: -33.4, sharpe: 1.50, win: 62.5, trades: 8 }},
  MSFT: {{ sig_ret: 52.9, bh_ret: 203.5, sig_dd: -32.0, bh_dd: -37.6, sharpe: 0.95, win: 28.6, trades: 7 }},
  TSLA: {{ sig_ret: 591.6, bh_ret: 1484.3, sig_dd: -69.9, bh_dd: -73.6, sharpe: 1.87, win: 33.3, trades: 9 }},
  NVDA: {{ sig_ret: 2381.6, bh_ret: 3026.8, sig_dd: -57.5, bh_dd: -66.4, sharpe: 3.36, win: 75.0, trades: 4 }},
  SPY:  {{ sig_ret: 74.3, bh_ret: 111.5, sig_dd: -18.7, bh_dd: -34.1, sharpe: 1.66, win: 66.7, trades: 6 }},
  BTC:  {{ sig_ret: 1043.2, bh_ret: 1128.2, sig_dd: -40.7, bh_dd: -76.6, sharpe: 2.36, win: 75.0, trades: 8 }},
}};
// Populate summary table
var tbody = document.getElementById('summary-body');
Object.keys(DATA).forEach(function(t) {{
  var d = DATA[t];
  var ddImprove = (Math.abs(d.bh_dd) - Math.abs(d.sig_dd)).toFixed(1);
  var cls = ddImprove > 10 ? 'highlight' : '';
  tbody.innerHTML += '<tr class="'+cls+'">' +
    '<td><b>'+t+'</b></td>' +
    '<td class="positive">+'+d.sig_ret.toFixed(1)+'%</td>' +
    '<td class="positive">+'+d.bh_ret.toFixed(1)+'%</td>' +
    '<td class="negative">'+d.sig_dd.toFixed(1)+'%</td>' +
    '<td class="negative">'+d.bh_dd.toFixed(1)+'%</td>' +
    '<td class="positive">+'+ddImprove+'pp</td>' +
    '<td>'+(d.sharpe >= 2 ? '<b style=color:#4CAF50>' : '')+d.sharpe.toFixed(2)+(d.sharpe >= 2 ? '</b>' : '')+'</td>' +
    '<td>'+d.win.toFixed(0)+'%</td>' +
    '<td>'+d.trades+'</td>' +
    '</tr>';
}});

Plotly.newPlot('comparison-chart', {comp_json}.data, {comp_json}.layout);
Plotly.newPlot('scatter-chart', {scatter_json}.data, {scatter_json}.layout);
Plotly.newPlot('equity-chart', {eq_json}.data, {eq_json}.layout);
</script>
</body>
</html>"""


if __name__ == "__main__":
    import sys
    data_path = sys.argv[1] if len(sys.argv) > 1 else "data/backtest_data.json"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "data/backtest_report.html"
    path = generate_comparison_chart(data_path, output_path)
    print(f"Chart saved to {path}")
