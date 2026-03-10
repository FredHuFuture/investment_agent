"""Tests for Task 012: Chart generation (pure functions, no network)."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import pytest

from agents.models import AgentOutput, Signal
from charts.analysis_charts import create_agent_breakdown_chart, create_price_chart
from charts.portfolio_charts import create_allocation_chart, create_sector_chart
from charts.tracking_charts import create_calibration_chart, create_drift_scatter
from portfolio.models import Portfolio, Position


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 50) -> pd.DataFrame:
    """Synthetic OHLCV DataFrame with n rows."""
    base = date(2024, 1, 1)
    dates = [base + timedelta(days=i) for i in range(n)]
    close = [100.0 + i * 0.5 for i in range(n)]
    open_ = [c - 0.3 for c in close]
    high = [c + 1.0 for c in close]
    low = [c - 1.0 for c in close]
    volume = [1_000_000.0] * n
    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=pd.to_datetime(dates),
    )
    return df


def _make_agent_output(name: str, signal: Signal, confidence: float) -> AgentOutput:
    return AgentOutput(
        agent_name=name,
        ticker="TEST",
        signal=signal,
        confidence=confidence,
        reasoning=f"{name} says {signal.value}",
    )


def _make_position(
    ticker: str,
    qty: float = 10.0,
    avg_cost: float = 100.0,
    sector: str | None = "Technology",
) -> Position:
    return Position(
        ticker=ticker,
        asset_type="stock",
        quantity=qty,
        avg_cost=avg_cost,
        sector=sector,
        entry_date="2024-01-01",
    )


def _make_portfolio(positions: list[Position], cash: float = 5_000.0) -> Portfolio:
    total = cash + sum(p.cost_basis for p in positions)
    sectors: dict[str, float] = {}
    for p in positions:
        s = p.sector or "Unknown"
        sectors[s] = sectors.get(s, 0.0) + p.cost_basis
    return Portfolio(
        positions=positions,
        cash=cash,
        total_value=total,
        stock_exposure_pct=(total - cash) / total if total else 0.0,
        crypto_exposure_pct=0.0,
        cash_pct=cash / total if total else 1.0,
        sector_breakdown=sectors,
        top_concentration=[],
    )


# ---------------------------------------------------------------------------
# 1. Price chart: valid figure
# ---------------------------------------------------------------------------

def test_price_chart_valid_figure() -> None:
    ohlcv = _make_ohlcv(50)
    fig = create_price_chart(ohlcv, "AAPL")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0


# ---------------------------------------------------------------------------
# 2. Price chart with indicators
# ---------------------------------------------------------------------------

def test_price_chart_with_indicators() -> None:
    import pandas_ta as ta

    ohlcv = _make_ohlcv(60)
    close = ohlcv["Close"]
    sma_20 = ta.sma(close, length=20)
    rsi = ta.rsi(close, length=14)
    bbands = ta.bbands(close, length=20, std=2.0)

    bb_upper = None
    bb_lower = None
    if bbands is not None and not bbands.empty:
        upper_cols = [c for c in bbands.columns if "BBU" in c]
        lower_cols = [c for c in bbands.columns if "BBL" in c]
        if upper_cols:
            bb_upper = bbands[upper_cols[0]]
        if lower_cols:
            bb_lower = bbands[lower_cols[0]]

    indicators = {"sma_20": sma_20, "rsi_14": rsi, "bb_upper": bb_upper, "bb_lower": bb_lower}
    fig = create_price_chart(ohlcv, "AAPL", indicators)

    assert isinstance(fig, go.Figure)
    trace_types = {type(t).__name__ for t in fig.data}
    assert "Candlestick" in trace_types
    # SMA / BB traces are Scatter
    assert "Scatter" in trace_types or "Bar" in trace_types


# ---------------------------------------------------------------------------
# 3. Agent breakdown chart: 3 bars
# ---------------------------------------------------------------------------

def test_agent_breakdown_chart() -> None:
    agents = [
        _make_agent_output("TechnicalAgent", Signal.BUY, 72.0),
        _make_agent_output("FundamentalAgent", Signal.SELL, 55.0),
        _make_agent_output("MacroAgent", Signal.HOLD, 48.0),
    ]
    fig = create_agent_breakdown_chart(agents)

    assert isinstance(fig, go.Figure)
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar)]
    assert len(bar_traces) == 1
    assert len(bar_traces[0].x) == 3


# ---------------------------------------------------------------------------
# 4. Allocation chart: 4 slices (3 positions + cash)
# ---------------------------------------------------------------------------

def test_allocation_chart() -> None:
    positions = [
        _make_position("AAPL", qty=10, avg_cost=150),
        _make_position("MSFT", qty=5, avg_cost=300),
        _make_position("BTC-USD", qty=0.5, avg_cost=40_000),
    ]
    portfolio = _make_portfolio(positions, cash=5_000)
    fig = create_allocation_chart(portfolio)

    assert isinstance(fig, go.Figure)
    pie_traces = [t for t in fig.data if isinstance(t, go.Pie)]
    assert len(pie_traces) == 1
    # 3 positions + 1 cash = 4 labels
    assert len(pie_traces[0].labels) == 4


# ---------------------------------------------------------------------------
# 5. Sector chart: 2 bars for 2 sectors
# ---------------------------------------------------------------------------

def test_sector_chart() -> None:
    positions = [
        _make_position("AAPL", qty=10, avg_cost=150, sector="Technology"),
        _make_position("MSFT", qty=5, avg_cost=300, sector="Technology"),
        _make_position("JPM", qty=20, avg_cost=200, sector="Financials"),
    ]
    portfolio = _make_portfolio(positions, cash=0)
    fig = create_sector_chart(portfolio)

    assert isinstance(fig, go.Figure)
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar)]
    assert len(bar_traces) == 1
    assert len(bar_traces[0].x) == 2  # Technology + Financials


# ---------------------------------------------------------------------------
# 6. Calibration chart with data: 2 line traces
# ---------------------------------------------------------------------------

def test_calibration_chart_with_data() -> None:
    calibration_data = [
        {"confidence_bucket": "30-40", "bucket_midpoint": 35.0, "expected_win_rate": 35.0, "actual_win_rate": 40.0, "sample_size": 10},
        {"confidence_bucket": "50-60", "bucket_midpoint": 55.0, "expected_win_rate": 55.0, "actual_win_rate": 50.0, "sample_size": 8},
        {"confidence_bucket": "70-80", "bucket_midpoint": 75.0, "expected_win_rate": 75.0, "actual_win_rate": 80.0, "sample_size": 6},
    ]
    fig = create_calibration_chart(calibration_data)

    assert isinstance(fig, go.Figure)
    scatter_traces = [t for t in fig.data if isinstance(t, go.Scatter)]
    assert len(scatter_traces) == 2  # expected + actual


# ---------------------------------------------------------------------------
# 7. Calibration chart empty: annotation present
# ---------------------------------------------------------------------------

def test_calibration_chart_empty() -> None:
    fig = create_calibration_chart([])

    assert isinstance(fig, go.Figure)
    annotations = fig.layout.annotations
    assert len(annotations) > 0
    texts = [a.text for a in annotations]
    assert any("Insufficient data" in t for t in texts)


# ---------------------------------------------------------------------------
# 8. Drift scatter empty: annotation present
# ---------------------------------------------------------------------------

def test_drift_scatter_empty() -> None:
    fig = create_drift_scatter([])

    assert isinstance(fig, go.Figure)
    annotations = fig.layout.annotations
    assert len(annotations) > 0
    texts = [a.text for a in annotations]
    assert any("No resolved signals" in t for t in texts)
