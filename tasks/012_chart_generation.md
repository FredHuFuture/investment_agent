# Task 012: CLI Chart Generation (plotly)

## Goal

Generate interactive HTML charts from analysis results and stored data, opened in the browser. Deliver a `charts/` package with pure functions returning plotly Figures and a `cli/charts_cli.py` entry point.

## Context

- `engine/pipeline.py` (Task 008) -- `AnalysisPipeline.analyze_ticker()` returns `AggregatedSignal` with `ticker_info`, `agent_signals`, `metrics`.
- `data_providers/yfinance_provider.py` (Task 004) -- `get_price_history()` returns OHLCV DataFrame, `get_key_stats()` returns name/sector/etc.
- `tracking/store.py` (Task 011) -- `SignalStore.get_signal_history()`, `get_resolved_signals()`.
- `tracking/tracker.py` (Task 011) -- `SignalTracker.compute_calibration_data()`, `compute_accuracy_stats()`, `compute_agent_performance()`.
- `engine/drift_analyzer.py` (Task 008.5) -- `compute_drift_summary()`.
- `portfolio/manager.py` (Task 003) -- `PortfolioManager.load_portfolio()` returns `Portfolio`.
- `agents/technical.py` (Task 005) -- computes SMA(20/50/200), RSI(14), MACD, Bollinger Bands via pandas_ta.
- Thread-safety: all yfinance calls go through `_yfinance_lock` (see yfinance_provider.py).
- Windows: CLI files must set `asyncio.WindowsSelectorEventLoopPolicy` if using async network.

## Requirements

### 1. New Dependency

Add to `pyproject.toml`:
```
"plotly>=5.0",
```

Also add `charts` to the hatch packages list.

### 2. Package Structure

```
charts/
    __init__.py         # Exports: create_analysis_chart, create_portfolio_chart, etc.
    analysis_charts.py  # Price candlestick + indicators, agent breakdown
    portfolio_charts.py # Asset allocation, sector exposure, value over time
    tracking_charts.py  # Calibration line, accuracy bar, drift scatter
```

### 3. Chart Functions (Pure Functions)

Every chart function takes data as input and returns a `plotly.graph_objects.Figure`. **No I/O inside chart functions** -- data fetching happens in CLI or caller.

#### 3.1 `analysis_charts.py`

**`create_price_chart(ohlcv: pd.DataFrame, ticker: str, indicators: dict | None = None) -> go.Figure`**

- Candlestick chart from OHLCV DataFrame (columns: Open, High, Low, Close, Volume).
- Subplots: main price chart (row 1, 70% height), volume bars (row 2, 15%), RSI line (row 3, 15%).
- Overlays on main chart (if `indicators` dict provided):
  - SMA lines: `indicators["sma_20"]`, `indicators["sma_50"]`, `indicators["sma_200"]` (Series). Colors: blue, orange, red.
  - Bollinger Bands: `indicators["bb_upper"]`, `indicators["bb_lower"]` (Series). Fill between with light gray.
- RSI subplot: line + horizontal lines at 30 (green, oversold) and 70 (red, overbought).
- Volume subplot: bar chart, green for up days, red for down days.
- Title: `"{ticker} -- Price Analysis"`.
- x-axis: date. Disable rangeslider. Enable range selector buttons (1M, 3M, 6M, 1Y, All).

**`create_agent_breakdown_chart(agent_signals: list[AgentOutput]) -> go.Figure`**

- Horizontal bar chart showing each agent's signal and confidence.
- X-axis: confidence (0-100). Y-axis: agent names (without "Agent" suffix).
- Bar color: green (BUY), gray (HOLD), red (SELL).
- Text annotation on each bar: signal name + confidence%.
- Title: `"Agent Signal Breakdown"`.

#### 3.2 `portfolio_charts.py`

**`create_allocation_chart(portfolio: Portfolio) -> go.Figure`**

- Pie chart of portfolio positions by cost_basis weight.
- Include cash as a slice ("Cash").
- Labels: ticker + percentage. Hover: ticker, cost_basis, qty.
- Title: `"Portfolio Allocation"`.

**`create_sector_chart(portfolio: Portfolio) -> go.Figure`**

- Horizontal bar chart of sector exposure by cost_basis.
- Group positions by `position.sector` (use "Unknown" for None).
- Color-coded bars. Sorted by value descending.
- Title: `"Sector Exposure"`.

#### 3.3 `tracking_charts.py`

**`create_calibration_chart(calibration_data: list[dict]) -> go.Figure`**

- Input: output of `SignalTracker.compute_calibration_data()` -- list of dicts with `confidence_bucket`, `expected_win_rate`, `actual_win_rate`, `sample_size`.
- Line chart: X = confidence bucket (midpoint), Y = win rate (%).
- Two lines: "Expected" (diagonal reference) and "Actual" (from data).
- Shaded area between lines to visualize calibration gap.
- Above diagonal = under-confident (good). Below = over-confident (bad).
- Title: `"Confidence Calibration"`.
- If empty data: return Figure with annotation "Insufficient data for calibration".

**`create_drift_scatter(drift_data: list[dict]) -> go.Figure`**

- Input: list of drift summaries with `expected_return_pct` and `actual_return_pct` fields.
- Scatter plot: X = expected return, Y = actual return.
- Diagonal reference line (y=x): perfect prediction.
- Points above line = conservative estimates. Below = optimistic.
- Color by outcome (WIN=green, LOSS=red).
- Title: `"Expected vs Actual Return"`.
- If empty data: return Figure with annotation "No resolved signals yet".

### 4. CLI Entry Point (`cli/charts_cli.py`)

```bash
# Run fresh analysis and show price chart with indicators + agent breakdown
python -m cli.charts_cli analysis AAPL
python -m cli.charts_cli analysis BTC-USD --asset-type btc

# Portfolio allocation charts (from stored portfolio)
python -m cli.charts_cli portfolio

# Signal quality charts (from stored signal_history)
python -m cli.charts_cli calibration
python -m cli.charts_cli calibration --lookback 200

# Drift analysis (from stored data)
python -m cli.charts_cli drift
```

**Flags:**
- `--no-open`: save chart HTML without opening browser.
- `--output-dir PATH`: custom output directory (default: `data/charts/`).

**Chart delivery mechanism:**
1. Each subcommand fetches data (async), calls chart function, gets `Figure`.
2. Write to `{output_dir}/{chart_name}_{ticker}_{timestamp}.html` via `fig.write_html()`.
3. Open in browser via `webbrowser.open()` (unless `--no-open`).
4. Print file path to stdout.

**For `analysis` subcommand workflow:**
1. Run `AnalysisPipeline.analyze_ticker(ticker, asset_type)` to get signals.
2. Fetch OHLCV via `provider.get_price_history(ticker, period="1y")`.
3. Compute indicators via pandas_ta (SMA 20/50/200, RSI 14, Bollinger Bands 20).
4. Call `create_price_chart(ohlcv, ticker, indicators)` and `create_agent_breakdown_chart(signal.agent_signals)`.
5. Output: two HTML files, both opened.

**For `portfolio` subcommand:**
1. Load portfolio via `PortfolioManager.load_portfolio()`.
2. Call `create_allocation_chart(portfolio)` and `create_sector_chart(portfolio)`.
3. Output: two HTML files.

**For `calibration` subcommand:**
1. Load via `SignalTracker.compute_calibration_data(lookback=N)`.
2. Call `create_calibration_chart(data)`.
3. Output: one HTML file.

**For `drift` subcommand:**
1. Load via `DriftAnalyzer.compute_drift_summary()`.
2. Call `create_drift_scatter(data)`.
3. Output: one HTML file.

**Windows event loop policy:**
```python
import sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

### 5. Chart Styling Defaults

Apply consistent dark theme for financial charts:
```python
CHART_TEMPLATE = "plotly_dark"
CHART_COLORS = {
    "buy": "#00CC66",     # green
    "hold": "#888888",    # gray
    "sell": "#CC3333",    # red
    "sma_20": "#1f77b4",  # blue
    "sma_50": "#ff7f0e",  # orange
    "sma_200": "#d62728", # red
    "volume_up": "#00CC66",
    "volume_down": "#CC3333",
}
```

### 6. Output Directory

Create `data/charts/` directory if it doesn't exist (use `os.makedirs(path, exist_ok=True)`).

## Tests (`tests/test_012_charts.py`)

7-8 test cases, all mocked data (no network):

1. **`test_price_chart_valid_figure`**: Pass synthetic OHLCV DataFrame (50 rows), verify returns `go.Figure` with > 0 traces.
2. **`test_price_chart_with_indicators`**: Pass OHLCV + SMA/RSI/BB indicators dict, verify Figure has candlestick + line traces.
3. **`test_agent_breakdown_chart`**: Pass 3 mock `AgentOutput` objects (BUY/SELL/HOLD), verify Figure has 3 bars.
4. **`test_allocation_chart`**: Create mock `Portfolio` with 3 positions + cash, verify pie chart has 4 slices.
5. **`test_sector_chart`**: Mock portfolio with 2 sectors, verify bar chart has 2 bars.
6. **`test_calibration_chart_with_data`**: Pass mock calibration data (3 buckets), verify 2 line traces (expected + actual).
7. **`test_calibration_chart_empty`**: Pass empty list, verify Figure with annotation text.
8. **`test_drift_scatter_empty`**: Pass empty list, verify Figure with annotation text.

**No network tests.** All chart functions are pure -- they take data in, return Figure out.

## Verification

```bash
# Run tests
pytest tests/test_012_charts.py -v

# Manual verification
python -m cli.charts_cli analysis AAPL    # Should open 2 HTML files in browser
python -m cli.charts_cli portfolio        # Should open 2 HTML files
python -m cli.charts_cli calibration      # Should show "insufficient data" annotation
```

## Hints

- Import `plotly.graph_objects as go` and `plotly.subplots.make_subplots`.
- Use `fig.update_layout(template=CHART_TEMPLATE)` for consistent dark styling.
- For subplots: `make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.7, 0.15, 0.15])`.
- For candlestick: `go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])`.
- For volume colors: `colors = ['#00CC66' if c >= o else '#CC3333' for c, o in zip(df['Close'], df['Open'])]`.
- `fig.write_html(path, include_plotlyjs=True)` for standalone HTML.
- `webbrowser.open(f"file://{os.path.abspath(path)}")` for opening.
- pandas_ta indicator computation: `df.ta.sma(length=20)`, `df.ta.rsi(length=14)`, `df.ta.bbands(length=20, std=2)`.
