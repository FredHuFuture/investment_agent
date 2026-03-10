# Task 014.5 -- Analysis Detail Mode (`--detail`)

## Objective

Add a `--detail` / `-d` flag to `analyze_cli` that expands the terminal report to show **full agent analysis breakdowns**: all computed metrics, sub-score decompositions, reasoning strings, and aggregation weight contributions. The standard report shows only 4 key metrics per agent; detail mode shows everything the agents computed.

**Rationale**: An investor needs to understand *why* an agent recommends BUY/SELL -- which indicators are significant, how sub-scores combine, and what the aggregation weighting actually contributes. This data already exists in `AgentOutput.metrics` and `AgentOutput.reasoning` but is not displayed.

---

## Scope

**Files to MODIFY (3):**

| File | Change |
|------|--------|
| `cli/report.py` | Add `format_analysis_report(signal, detail=False)` parameter, add `_format_agent_detailed()` function |
| `cli/analyze_cli.py` | Add `--detail` / `-d` flag, pass to `format_analysis_report()` |
| `tests/test_009_cli_report.py` | Add 3-4 tests for detail mode output |

**No new files. No data layer changes. No new dependencies.**

---

## Detailed Design

### 1. `cli/analyze_cli.py` -- Add `--detail` flag

```python
parser.add_argument(
    "--detail", "-d",
    dest="detail",
    action="store_true",
    help="Show full agent analysis breakdown (all metrics, reasoning, weights).",
)
```

Pass `detail=args.detail` to `format_analysis_report()`. The `--json` flag already dumps everything; `--detail` is the human-readable equivalent.

### 2. `cli/report.py` -- Expand agent breakdown in detail mode

#### 2a. Signature change

```python
def format_analysis_report(signal: AggregatedSignal, detail: bool = False) -> str:
```

Backward compatible -- existing callers (including daemon CLI `_print_weekly_result`) are unaffected.

#### 2b. Agent section: standard vs detail

In the existing agent loop (lines 72-77), when `detail=True`, replace the single-line `_format_agent_detail(output)` with a multi-section expanded view via `_format_agent_detailed(output, contributions)`.

**Standard mode** (unchanged):
```
  Technical:    BUY  (72%)
    RSI: 45.2 | Trend: +8 | Momentum: +6 | Volatility: -2
```

**Detail mode** (new):
```
  Technical:    BUY  (72%)
  ..............................................................
    Sub-scores:
      Trend:       +8   (SMA20 > SMA50 > SMA200, clear uptrend)
      Momentum:    +6   (RSI: 45.2, MACD histogram: +0.32)
      Volatility:  -2   (ATR: 3.45, BB width: normal)
      Composite:   +12

    Key Indicators:
      SMA 20/50/200:  $182.30 / $178.50 / $165.20
      RSI (14):        45.2
      MACD:            Line: 1.23  Signal: 0.91  Hist: +0.32
      Bollinger:       Upper: $188.50  Mid: $182.00  Lower: $175.50
      ATR (14):        3.45
      Volume Ratio:    1.12x
      Weekly Trend:    confirms

    Reasoning:
      "Bullish trend structure with SMA alignment. RSI neutral zone
       leaves room for upside. MACD positive crossover supports
       momentum. Moderate volatility within normal range."

    Weight: 0.35 x BUY(+1.0) x 72% conf = +0.2520 contribution
  ..............................................................
```

#### 2c. New function: `_format_agent_detailed(output, contributions)`

```python
def _format_agent_detailed(
    output: AgentOutput,
    contributions: dict[str, dict[str, Any]] | None = None,
) -> str:
```

This function takes an `AgentOutput` and the `agent_contributions` dict from `AggregatedSignal.metrics` and produces the expanded multi-line view.

**Per agent type, display ALL metrics grouped logically:**

**TechnicalAgent** groups:
- Sub-scores: trend_score, momentum_score, volatility_score, composite_score
- Price/Moving Averages: current_price, sma_20, sma_50, sma_200
- Momentum: rsi_14, macd_line, macd_signal, macd_histogram
- Volatility: bb_upper, bb_middle, bb_lower, atr_14
- Volume: volume_ratio
- Confirmation: weekly_trend_confirms

**FundamentalAgent** groups:
- Sub-scores: value_score, quality_score, growth_score, composite_score
- Valuation: pe_trailing, pe_forward, pb_ratio, ev_ebitda, fcf_yield
- Quality: roe, profit_margin, debt_equity, current_ratio
- Growth: revenue_growth, dividend_yield
- Context: market_cap, sector, pct_from_52w_high

**MacroAgent** groups:
- Score: net_score, risk_on_points, risk_off_points
- Volatility: vix_current, vix_sma_20
- Rates: treasury_10y, treasury_2y, yield_curve_spread
- Policy: fed_funds_rate, fed_funds_trend, m2_yoy_growth
- Regime: regime

**Reasoning**: Always show `output.reasoning` in a quoted block.

**Weight contribution**: Show the math: `weight x signal_value x confidence_factor = contribution`.

#### 2d. Aggregation transparency section

When `detail=True`, add a section after the agent breakdown showing the aggregation math:

```
  ----------------------------------------------------------------
  AGGREGATION DETAIL
  ----------------------------------------------------------------
    Weights: Technical 0.35, Fundamental 0.35, Macro 0.30
    Raw Score:       +0.4520 (threshold: +/-0.30)
    Consensus:       3/3 agents BUY (strong)
    Consensus Adj:   none (>= 50%)
    Final:           BUY @ 68% confidence
```

This uses `signal.metrics["weights_used"]`, `signal.metrics["raw_score"]`, `signal.metrics["consensus_score"]`, and `signal.metrics["agent_contributions"]`.

---

## Display Formatting Rules

- Use the existing `REPORT_WIDTH = 64` constant
- Dotted separator `"." * 62` for within-agent sections (visually lighter than `"-"`)
- Indent: 4 spaces for sub-items, 6 spaces for indicator values
- Numeric formatting:
  - Prices: `$xxx.xx`
  - Percentages: `xx.x%` or `+x.x%`
  - Scores: `+xx` or `-xx` (integer with sign)
  - Ratios: `x.xx`
  - Large numbers: use existing `_format_large_number()`
- Skip metrics that are `None` or missing -- don't show "N/A" clutter
- Reasoning string: wrap at ~58 chars, indent 6 spaces, prefix with `> `

---

## Test Plan (4 tests)

Add to existing `tests/test_009_cli_report.py`:

1. **`test_detail_mode_shows_all_metrics`** -- Create AggregatedSignal with full metrics dicts. Call `format_analysis_report(signal, detail=True)`. Assert key indicators appear in output (sma_20, pe_trailing, vix_current, etc.) that do NOT appear in standard mode.

2. **`test_detail_mode_shows_reasoning`** -- Assert `output.reasoning` text appears in detail output but not in standard output.

3. **`test_detail_mode_shows_aggregation_math`** -- Assert "AGGREGATION DETAIL" section appears with weights, raw score, consensus info.

4. **`test_standard_mode_unchanged`** -- Verify `format_analysis_report(signal)` (no detail flag) produces identical output to before -- regression guard.

---

## Integration Points

| Component | Usage |
|-----------|-------|
| `AgentOutput.metrics` | All computed indicators (17+ keys per agent) |
| `AgentOutput.reasoning` | Human-readable analysis narrative |
| `AggregatedSignal.metrics["agent_contributions"]` | Weight x signal x confidence per agent |
| `AggregatedSignal.metrics["weights_used"]` | Agent weight configuration |
| `AggregatedSignal.metrics["raw_score"]` | Pre-threshold weighted score |
| `AggregatedSignal.metrics["consensus_score"]` | Agreement ratio |

---

## Out of Scope

- Interactive/expandable terminal UI (TUI) -- plain text only for now
- Color/ANSI formatting -- keep it Windows CMD safe
- Saving detail reports to file -- user can redirect stdout
- Modifying `--json` output (already includes everything)
- Changing agent computation logic -- display only

---

## Acceptance Criteria

1. `python -m cli.analyze_cli AAPL` -- unchanged output (backward compatible)
2. `python -m cli.analyze_cli AAPL --detail` -- shows full breakdown with all metrics, reasoning, weights
3. `python -m cli.analyze_cli AAPL -d` -- same as `--detail`
4. `python -m cli.analyze_cli AAPL --detail --json` -- JSON takes precedence (detail ignored)
5. All existing tests pass unchanged
6. 4 new tests pass
