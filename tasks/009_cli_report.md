# Task 009: CLI Analysis Report + E2E Integration

## 🎯 Goal

Create a CLI command to run the full analysis pipeline for a single ticker and display a formatted terminal report. This is the **capstone of Phase 1** — the first user-facing feature that ties together all components (DataProviders → Agents → Aggregator → Report).

## 📥 Context

- `engine/pipeline.py` (Task 008) — `AnalysisPipeline.analyze_ticker()` runs the full pipeline.
- `engine/aggregator.py` (Task 008) — `AggregatedSignal` is the output dataclass.
- `cli/portfolio_cli.py` (Task 003) — existing CLI pattern using argparse.
- `agents/models.py` — `Signal`, `Regime`, `AgentOutput`.

## 🛠️ Requirements

### 1. Report Formatter (`cli/report.py`)

A pure formatting module — no I/O, no async. Takes an `AggregatedSignal` and returns formatted strings.

```python
from __future__ import annotations
from engine.aggregator import AggregatedSignal


def format_analysis_report(signal: AggregatedSignal) -> str:
    """Format an AggregatedSignal into a human-readable terminal report.

    Returns a multi-line string ready for print().
    """
    ...


def format_analysis_json(signal: AggregatedSignal) -> str:
    """Format an AggregatedSignal as pretty-printed JSON.

    Uses signal.to_dict() and json.dumps(indent=2).
    """
    ...
```

**Report format:**

```
================================================================
  ANALYSIS REPORT: AAPL (stock)
================================================================

  SIGNAL:     BUY
  CONFIDENCE: 72%
  REGIME:     RISK_ON

----------------------------------------------------------------
  AGENT BREAKDOWN
----------------------------------------------------------------

  Technical:    BUY  (72%)
    RSI: 42.3 | SMA alignment: bullish | MACD: positive crossover

  Fundamental:  BUY  (65%)
    P/E: 18.2 | ROE: 35.1% | Revenue Growth: +12.4%

  Macro:        BUY  (58%)
    Regime: RISK_ON | VIX: 14.2 | Yield Curve: +1.2%

----------------------------------------------------------------
  CONSENSUS: 3/3 agents agree (strong consensus)
----------------------------------------------------------------

  WARNINGS:
    (none)

================================================================
```

**Design notes:**
- Use `signal.agent_signals` to iterate per-agent details.
- For each agent, extract key metrics from `agent_output.metrics` and display 3-5 most important values.
- Technical agent key metrics: `rsi`, `sma_alignment` or composite sub-scores, `trend_score`, `momentum_score`.
- Fundamental agent key metrics: `pe_trailing`, `roe`, `revenue_growth_yoy`, `debt_equity`.
- Macro agent key metrics: `regime`, `vix_level`, `yield_curve_spread`, `net_score`.
- If a metric key is missing from `agent_output.metrics`, skip it gracefully (don't crash).
- Confidence displayed as integer percentage (e.g. `72%`).
- Signal displayed in uppercase.
- Warnings section: show each warning on its own line, or "(none)" if empty.
- Width: 64 characters max. Use `=` for major separators, `-` for minor.

**Agent metrics extraction helper:**

```python
def _format_agent_detail(output: AgentOutput) -> str:
    """Extract 3-5 key metrics from an agent's output.metrics for display."""
    name = output.agent_name
    m = output.metrics

    if name == "TechnicalAgent":
        parts = []
        if "rsi" in m and m["rsi"] is not None:
            parts.append(f"RSI: {m['rsi']:.1f}")
        if "trend_score" in m:
            parts.append(f"Trend: {m['trend_score']:+.0f}")
        if "momentum_score" in m:
            parts.append(f"Momentum: {m['momentum_score']:+.0f}")
        if "volatility_score" in m:
            parts.append(f"Volatility: {m['volatility_score']:+.0f}")
        return " | ".join(parts) if parts else "(no detail)"

    elif name == "FundamentalAgent":
        parts = []
        if "pe_trailing" in m and m["pe_trailing"] is not None:
            parts.append(f"P/E: {m['pe_trailing']:.1f}")
        if "roe" in m and m["roe"] is not None:
            parts.append(f"ROE: {m['roe']:.1%}")
        if "revenue_growth_yoy" in m and m["revenue_growth_yoy"] is not None:
            parts.append(f"Rev Growth: {m['revenue_growth_yoy']:+.1%}")
        if "debt_equity" in m and m["debt_equity"] is not None:
            parts.append(f"D/E: {m['debt_equity']:.2f}")
        return " | ".join(parts) if parts else "(no detail)"

    elif name == "MacroAgent":
        parts = []
        if "regime" in m and m["regime"]:
            parts.append(f"Regime: {m['regime']}")
        if "vix_level" in m and m["vix_level"] is not None:
            parts.append(f"VIX: {m['vix_level']:.1f}")
        if "yield_curve_spread" in m and m["yield_curve_spread"] is not None:
            parts.append(f"Yield Curve: {m['yield_curve_spread']:+.2f}%")
        if "net_score" in m and m["net_score"] is not None:
            parts.append(f"Score: {m['net_score']:+d}")
        return " | ".join(parts) if parts else "(no detail)"

    else:
        return "(unknown agent)"
```

### 2. Analyze CLI (`cli/analyze_cli.py`)

```python
from __future__ import annotations
import argparse
import asyncio

from engine.pipeline import AnalysisPipeline
from cli.report import format_analysis_report, format_analysis_json


async def _run_analysis(ticker: str, asset_type: str, json_output: bool) -> None:
    """Run the analysis pipeline and print results."""
    pipeline = AnalysisPipeline()
    result = await pipeline.analyze_ticker(ticker, asset_type)

    if json_output:
        print(format_analysis_json(result))
    else:
        print(format_analysis_report(result))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run investment analysis for a single ticker."
    )
    parser.add_argument(
        "ticker",
        type=str,
        help="Ticker symbol (e.g. AAPL, MSFT, BTC).",
    )
    parser.add_argument(
        "--asset-type",
        dest="asset_type",
        choices=["stock", "btc", "eth"],
        default="stock",
        help="Asset type (default: stock).",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output as JSON instead of formatted report.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(_run_analysis(
        ticker=args.ticker.upper(),
        asset_type=args.asset_type,
        json_output=args.json_output,
    ))


if __name__ == "__main__":
    main()
```

**Usage:**
```bash
# Standard analysis
python -m cli.analyze_cli AAPL

# Crypto
python -m cli.analyze_cli BTC --asset-type btc

# JSON output
python -m cli.analyze_cli MSFT --json
```

### 3. Update `cli/__init__.py`

Export the new module:
```python
"""CLI package for investment analysis agent."""
```
(The __init__.py should just be a docstring — actual entry points are via `-m cli.analyze_cli` and `-m cli.portfolio_cli`.)

## 📝 Test Cases

### `tests/test_009_report.py` — Report formatting tests (4 tests)

All tests construct `AggregatedSignal` objects directly (no pipeline, no mocks needed for these).

1. **test_format_report_buy_signal**
   - Create an `AggregatedSignal` with `final_signal=BUY`, 3 agent outputs (Technical, Fundamental, Macro), regime=RISK_ON.
   - Call `format_analysis_report(signal)`.
   - Assert output contains: "BUY", "AAPL", "stock", "RISK_ON", "Technical", "Fundamental", "Macro".
   - Assert output contains confidence percentage.
   - Assert "WARNINGS:" section present.

2. **test_format_report_hold_with_warnings**
   - Create an `AggregatedSignal` with `final_signal=HOLD`, warnings=["Low agent consensus"].
   - Assert output contains "HOLD" and the warning text.
   - Assert output does NOT contain "(none)" after WARNINGS.

3. **test_format_report_missing_metrics**
   - Create `AgentOutput` with empty `metrics={}`.
   - `format_analysis_report` should not crash.
   - Agent detail line should show "(no detail)" or gracefully skip.

4. **test_format_json_roundtrip**
   - Create an `AggregatedSignal`.
   - Call `format_analysis_json(signal)`.
   - `json.loads()` the result → verify it's valid JSON.
   - Verify `result["final_signal"] == "BUY"`.

### `tests/test_009_e2e.py` — End-to-end CLI tests (4 tests)

These tests mock all DataProviders and verify the pipeline runs through the CLI layer.

**Helper:**
```python
def _make_output(agent_name, signal, confidence, ticker="AAPL", metrics=None):
    return AgentOutput(
        agent_name=agent_name,
        ticker=ticker,
        signal=signal,
        confidence=confidence,
        reasoning=f"{agent_name} says {signal.value}",
        metrics=metrics or {},
    )
```

5. **test_e2e_stock_analysis**
   - Mock `AnalysisPipeline.analyze_ticker` to return a pre-built `AggregatedSignal`.
   - Call `_run_analysis("AAPL", "stock", json_output=False)`.
   - Capture stdout (use `capsys` pytest fixture).
   - Assert output contains "ANALYSIS REPORT", "AAPL", "BUY", "SIGNAL".

6. **test_e2e_crypto_analysis**
   - Mock `AnalysisPipeline.analyze_ticker` to return a crypto signal (no Fundamental).
   - Call `_run_analysis("BTC", "btc", json_output=False)`.
   - Capture stdout.
   - Assert output contains "BTC", "btc".
   - Assert "FundamentalAgent" NOT in agent breakdown (crypto has no fundamental).

7. **test_e2e_json_output**
   - Mock `AnalysisPipeline.analyze_ticker`.
   - Call `_run_analysis("MSFT", "stock", json_output=True)`.
   - Capture stdout.
   - `json.loads(stdout)` → valid JSON.
   - Verify `result["ticker"] == "MSFT"`.

8. **test_e2e_pipeline_with_warnings**
   - Mock pipeline to return a signal with warnings (e.g. "MacroAgent skipped").
   - Capture stdout.
   - Assert warning text appears in output.

## 📂 Files

| Action | File |
|--------|------|
| CREATE | `cli/report.py` — report formatting (pure functions, no I/O) |
| CREATE | `cli/analyze_cli.py` — CLI entry point for analysis |
| CREATE | `tests/test_009_report.py` — 4 report formatting tests |
| CREATE | `tests/test_009_e2e.py` — 4 E2E integration tests |
| VERIFY | `cli/__init__.py` — ensure it exists (should already exist) |

## ✅ Acceptance Criteria

1. `pytest tests/test_009_report.py tests/test_009_e2e.py -v` — all 8 tests pass.
2. `pytest tests/ -v` — full suite passes (no regressions).
3. `format_analysis_report()` produces readable, well-aligned terminal output.
4. `format_analysis_json()` produces valid, pretty-printed JSON.
5. `python -m cli.analyze_cli --help` works and shows usage.
6. Code follows PEP 8, type hints, `from __future__ import annotations`.

## ⚠️ Out of Scope

- Save thesis to DB (`--save` flag) → Phase 2
- Portfolio-aware analysis (position sizing, exposure check) → Phase 2
- Drift summary in CLI (`portfolio show --with-drift`) → depends on Task 008.5
- Interactive mode → Phase 2
- HTML/PDF report generation → Phase 2
- Streaming output / progress bar → Phase 2

---
**Developer Agent instructions:**
Read `engine/aggregator.py` and `engine/pipeline.py` (Task 008) first to understand `AggregatedSignal` structure. Read `cli/portfolio_cli.py` (Task 003) for CLI patterns. Read `agents/technical.py`, `agents/fundamental.py`, `agents/macro.py` to understand what keys are in each agent's `metrics` dict. Create `cli/report.py` and `cli/analyze_cli.py`. The report formatter should be defensive — never crash on missing metrics keys. Run `pytest tests/test_009_report.py tests/test_009_e2e.py -v`, then `pytest tests/ -v`. Report in `docs/AGENT_SYNC.md`.
