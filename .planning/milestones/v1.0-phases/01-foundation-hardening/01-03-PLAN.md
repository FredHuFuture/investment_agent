---
phase: 01-foundation-hardening
plan: 03
type: execute
wave: 1
depends_on: []
files_modified:
  - engine/monte_carlo.py
  - engine/aggregator.py
  - agents/fundamental.py
  - agents/models.py
  - backtesting/engine.py
  - tests/test_foundation_03_block_length.py
  - tests/test_foundation_04_backtest_mode.py
  - tests/test_foundation_05_agent_renorm.py
autonomous: true
requirements: [FOUND-03, FOUND-04, FOUND-05]
tags: [signal-quality, monte-carlo, backtesting, aggregator, look-ahead-bias]

must_haves:
  truths:
    - "MonteCarloSimulator uses arch.bootstrap.optimal_block_length() to pick block_size when none is explicitly supplied, rather than hardcoding 5."
    - "Explicitly passing block_size=K to the simulator still uses K (opt-in override preserved)."
    - "The optimal block length returned by arch is clamped into [3, len(returns)-1] and cached on the simulator so repeat simulations do not recompute it."
    - "AgentInput has a boolean backtest_mode field that defaults to False."
    - "When backtest_mode=True, FundamentalAgent.analyze() returns a HOLD signal with confidence <=40 AND a warning 'backtest_mode: skipping restated fundamentals to prevent look-ahead bias', without calling provider.get_financials() or provider.get_key_stats()."
    - "When backtest_mode=False, FundamentalAgent behavior is unchanged (all existing tests still pass)."
    - "backtesting/engine.py::Backtester passes backtest_mode=True in the AgentInput it constructs."
    - "SignalAggregator.aggregate with N<all expected agents (e.g., SentimentAgent missing) produces weights whose values sum to 1.0 within 1e-6, verified by a parametrized test that exercises every single-agent-disabled scenario for stock, btc, and eth asset types."
  artifacts:
    - path: "engine/monte_carlo.py"
      provides: "Auto block-size selection via arch.optimal_block_length"
      contains: ["from arch.bootstrap import optimal_block_length", "optimal_block_length("]
    - path: "agents/models.py"
      provides: "AgentInput.backtest_mode field"
      contains: ["backtest_mode: bool = False"]
    - path: "agents/fundamental.py"
      provides: "backtest_mode gate returning HOLD + warning with no network call"
      contains: ["backtest_mode", "skipping restated fundamentals", "look-ahead bias"]
    - path: "backtesting/engine.py"
      provides: "Backtester threads backtest_mode=True into every AgentInput it builds"
      contains: ["backtest_mode=True"]
    - path: "engine/aggregator.py"
      provides: "Documented renormalization behavior (already renormalizes; this task adds the warning-threshold log line per research recommendation)"
      contains: ["Weight renormalization", "sum"]
    - path: "tests/test_foundation_03_block_length.py"
      provides: "Unit tests for arch-based auto-selection and override"
      contains: ["optimal_block_length", "auto_select", "override"]
    - path: "tests/test_foundation_04_backtest_mode.py"
      provides: "backtest_mode smoke + assertion tests"
      contains: ["backtest_mode", "HOLD", "no_provider_calls"]
    - path: "tests/test_foundation_05_agent_renorm.py"
      provides: "Parametrized test across every single-agent-disabled scenario"
      contains: ["pytest.mark.parametrize", "sum_to_one", "TechnicalAgent", "FundamentalAgent", "MacroAgent", "SentimentAgent", "CryptoAgent"]
  key_links:
    - from: "engine/monte_carlo.py::MonteCarloSimulator.__init__"
      to: "arch.bootstrap.optimal_block_length"
      via: "call when block_size param is None (new default)"
      pattern: "optimal_block_length\\("
    - from: "agents/fundamental.py::analyze"
      to: "agents/models.py::AgentInput.backtest_mode"
      via: "early return when agent_input.backtest_mode is True"
      pattern: "agent_input\\.backtest_mode"
    - from: "backtesting/engine.py::Backtester.run"
      to: "AgentInput(backtest_mode=True)"
      via: "every call that constructs AgentInput inside the rebalance loop"
      pattern: "AgentInput\\([^)]*backtest_mode=True"
    - from: "engine/aggregator.py::SignalAggregator.aggregate"
      to: "weights renormalization"
      via: "existing `used_raw` / `total_raw` re-normalization block, now validated by parametrized test"
      pattern: "sum\\(weights\\.values"
---

<objective>
Fix three independent signal-math correctness issues: (1) replace the hardcoded Monte Carlo block size with automatic selection via the `arch` library's Patton-Politis-White method; (2) add a `backtest_mode` flag that prevents `FundamentalAgent` from silently injecting restated (look-ahead contaminated) financials into backtests; (3) add a parametrized test proving the existing `SignalAggregator` weight-renormalization math produces weights summing to 1.0 for every single-agent-disabled scenario across all three asset types.

Purpose:
- FOUND-03: `engine/monte_carlo.py` uses `block_size=5` as the default for block bootstrap. Literature (Politis & White, 2004; implemented in `arch.bootstrap.optimal_block_length`) says optimal block size depends on the sample's autocorrelation structure and varies by asset class (crypto ≈ 3, equities ≈ 10-15). Hardcoding 5 systematically mis-sizes variance estimates, especially for crypto and for regime-changing equities.
- FOUND-04: `FundamentalAgent.analyze()` currently fetches yfinance `key_stats` and `financials`, which return CURRENT (possibly restated) values. When the backtesting engine loops through historical dates and calls `FundamentalAgent`, the agent silently uses values from today's yfinance response. Backtest P&L is overstated because the agent has "seen the future." The fix is a `backtest_mode: bool` flag on `AgentInput`; when True, FundamentalAgent returns HOLD immediately with a warning AND does NOT call the provider (so it cannot even accidentally contaminate).
- FOUND-05: `engine/aggregator.py` already renormalizes weights to the set of agents actually present (lines 118-129). However there is no dedicated test that enumerates every "missing-agent" scenario for every asset type. ROADMAP success criterion 4 explicitly calls out this test. This plan adds the test and — if the test finds an edge case — fixes the underlying math.

Output:
- `engine/monte_carlo.py`: `block_size: int | None = None` default; when None, call `optimal_block_length(returns)` and clamp to `[3, len(returns)-1]`. The result is stored on `self._block_size`.
- `agents/models.py`: `AgentInput` gains `backtest_mode: bool = False`.
- `agents/fundamental.py`: early return at top of `analyze()` when `agent_input.backtest_mode is True`, returning HOLD + explicit warning string. Uses NO provider calls.
- `backtesting/engine.py`: `AgentInput(ticker=cfg.ticker, asset_type=cfg.asset_type)` → `AgentInput(ticker=cfg.ticker, asset_type=cfg.asset_type, backtest_mode=True)`.
- Three new test files covering the three requirements independently.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/research/STACK.md
@.planning/research/PITFALLS.md
@.planning/codebase/CONCERNS.md
@.planning/codebase/CONVENTIONS.md

<interfaces>
<!-- Contracts the executor MUST honor. Extracted from the existing codebase. -->

From engine/monte_carlo.py (existing — 140 lines; current signature):
```python
class MonteCarloSimulator:
    MIN_DATA_POINTS = 10
    def __init__(
        self,
        daily_returns: list[float],
        block_size: int = 5,   # <-- currently hardcoded default 5
    ) -> None:
        if len(daily_returns) < self.MIN_DATA_POINTS:
            raise ValueError(...)
        self._returns = np.array(daily_returns, dtype=np.float64)
        self._block_size = max(1, min(block_size, len(daily_returns)))
        ...
```

From agents/models.py (existing — 62 lines; current dataclass):
```python
@dataclass
class AgentInput:
    ticker: str
    asset_type: str
    portfolio: Portfolio | None = None
    regime: Regime | None = None
    learned_weights: dict[str, Any] = field(default_factory=dict)
    approved_rules: list[str] = field(default_factory=list)
    # ADD: backtest_mode: bool = False
```

From agents/fundamental.py (current — top of analyze around lines 43-62):
```python
async def analyze(self, agent_input: AgentInput) -> AgentOutput:
    self._validate_asset_type(agent_input)
    self._logger.info("Analyzing %s", agent_input.ticker)
    warnings: list[str] = [NON_PIT_WARNING]
    try:
        key_stats = await self._provider.get_key_stats(agent_input.ticker)
        financials = await self._provider.get_financials(agent_input.ticker)
    except Exception as exc:
        ...
```

From engine/aggregator.py (existing renormalization block — lines 110-129):
```python
raw_weights = self._weights.get(asset_type, self._weights["stock"])
warnings: list[str] = []

present = {o.agent_name for o in agent_outputs}
completeness_map = {
    o.agent_name: getattr(o, "data_completeness", 1.0)
    for o in agent_outputs
}
used_raw = {
    k: v * completeness_map.get(k, 1.0)
    for k, v in raw_weights.items()
    if k in present and v > 0
}
total_raw = sum(used_raw.values())
weights = {k: v / total_raw for k, v in used_raw.items()} if total_raw > 0 else raw_weights
```

DEFAULT_WEIGHTS (lines 54-69) — the complete reference we must respect in tests:
```python
DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
    "stock": {
        "TechnicalAgent": 0.25,
        "FundamentalAgent": 0.40,
        "MacroAgent": 0.20,
        "SentimentAgent": 0.15,
    },
    "btc": {
        "CryptoAgent": 0.80,
        "TechnicalAgent": 0.20,
    },
    "eth": {
        "CryptoAgent": 0.80,
        "TechnicalAgent": 0.20,
    },
}
```

From backtesting/engine.py (existing AgentInput construction — line 274):
```python
agent_input = AgentInput(ticker=cfg.ticker, asset_type=cfg.asset_type)
# Need to change to:
agent_input = AgentInput(ticker=cfg.ticker, asset_type=cfg.asset_type, backtest_mode=True)
```

From arch docs (authoritative reference for optimal_block_length):
```python
# arch>=6.0
from arch.bootstrap import optimal_block_length
import pandas as pd

# Input: pandas Series or numpy array of returns
ret = pd.Series(returns_array)  # 1-D
# Returns: DataFrame with columns ['stationary', 'circular'] and one row per input series
res = optimal_block_length(ret)
# Extract the stationary bootstrap block length (our use case):
block = int(round(float(res['stationary'].iloc[0])))
# Fallback guard: block can occasionally be 0 or 1 on very short series.
block = max(3, min(block, len(ret) - 1))
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Replace hardcoded block_size with arch.optimal_block_length (FOUND-03)</name>
  <read_first>
    - engine/monte_carlo.py (whole file — 140 lines)
    - tests/test_041_risk_analytics.py (existing Monte Carlo test patterns — if any)
    - pyproject.toml (verify `arch>=6` is already in dependencies — added by Plan 01 Task 1)
    - .planning/research/STACK.md lines 310-340 (recommendation: `arch.optimal_block_length`)
    - .planning/codebase/CONCERNS.md lines 66-73 (hard-coded block_size residual risk)
  </read_first>
  <behavior>
    - Test A: `MonteCarloSimulator(returns, block_size=7)` sets `self._block_size == 7` (explicit override preserved).
    - Test B: `MonteCarloSimulator(returns)` (no block_size) sets `self._block_size` to a value in `[3, len(returns)-1]` and invokes `arch.bootstrap.optimal_block_length` exactly once.
    - Test C: Given a deterministic returns series of length 250 with known autocorrelation (e.g., AR(1) with phi=0.3, fixed seed), `MonteCarloSimulator(returns)._block_size` is a specific value (assert `3 <= block <= 30` as a generous sanity band).
    - Test D: When arch raises (e.g., patched to raise `ValueError`), simulator falls back to `block_size=5` and logs a warning (NOT crashing).
    - Test E: `simulate(...)` produces the same `percentiles` keys (`p5/p25/p50/p75/p95`) and the same shape as before — regression-safe.
    - Test F: The returned dict includes `"block_size"` key (existed already; verify still correct after auto-selection).
    - Test G: `optimal_block_length` is called with the full returns array, not a slice.
  </behavior>
  <action>
    Edit `engine/monte_carlo.py`:

    1. Add imports at the top:
       ```python
       import logging

       logger = logging.getLogger(__name__)
       ```

    2. Change the `__init__` signature default from `block_size: int = 5` to `block_size: int | None = None`:
       ```python
       def __init__(
           self,
           daily_returns: list[float],
           block_size: int | None = None,
       ) -> None:
           if len(daily_returns) < self.MIN_DATA_POINTS:
               raise ValueError(
                   f"Need at least {self.MIN_DATA_POINTS} daily returns, "
                   f"got {len(daily_returns)}"
               )
           self._returns = np.array(daily_returns, dtype=np.float64)

           # Guard against degenerate data (all zeros → flat projection)
           if np.all(self._returns == 0):
               self._returns = np.zeros_like(self._returns)

           # FOUND-03: auto-select block size via Patton-Politis-White
           # if caller did not explicitly set one.
           if block_size is None:
               self._block_size = self._auto_select_block_size(self._returns)
           else:
               self._block_size = max(1, min(block_size, len(daily_returns)))

       @staticmethod
       def _auto_select_block_size(returns: np.ndarray, fallback: int = 5) -> int:
           """Return the stationary-bootstrap optimal block length per Politis-White (2004).

           Uses arch.bootstrap.optimal_block_length. On any exception (arch not
           installed, degenerate input, numerical error), returns `fallback`
           and logs a warning.
           """
           try:
               import pandas as pd
               from arch.bootstrap import optimal_block_length
               series = pd.Series(returns)
               res = optimal_block_length(series)
               # Result is a DataFrame with columns ('stationary', 'circular') in arch>=6.
               raw = float(res["stationary"].iloc[0])
               if not np.isfinite(raw) or raw < 1:
                   raise ValueError(f"non-finite or <1 block length: {raw}")
               block = int(round(raw))
           except Exception as exc:
               logger.warning(
                   "optimal_block_length failed (%s); falling back to block_size=%d",
                   exc, fallback,
               )
               return max(1, min(fallback, len(returns)))
           return max(3, min(block, len(returns) - 1))
       ```

    3. Do NOT change `simulate()` logic. It continues to use `self._block_size` as before. The returned dict already contains `"block_size": bs` — keep that.

    4. Create `tests/test_foundation_03_block_length.py` with the seven behaviors. For Test C, use:
       ```python
       import numpy as np
       rng = np.random.default_rng(42)
       phi = 0.3
       noise = rng.normal(0, 0.01, 250)
       returns = [noise[0]]
       for i in range(1, 250):
           returns.append(phi * returns[-1] + noise[i])
       sim = MonteCarloSimulator(returns)
       assert 3 <= sim._block_size <= 30, f"auto block_size out of sanity band: {sim._block_size}"
       ```
       For Test D, patch `arch.bootstrap.optimal_block_length` to raise and assert `sim._block_size == 5`:
       ```python
       with patch("engine.monte_carlo.MonteCarloSimulator._auto_select_block_size",
                  wraps=MonteCarloSimulator._auto_select_block_size) as wrapped:
           ...
       ```
       Or simpler: `mocker.patch("arch.bootstrap.optimal_block_length", side_effect=ValueError("boom"))` then assert `sim._block_size == 5` (the fallback).
  </action>
  <verify>
    <automated>
      pytest tests/test_foundation_03_block_length.py -x -v
      pytest tests/test_041_risk_analytics.py -x 2>/dev/null || true
      python -c "
      from engine.monte_carlo import MonteCarloSimulator
      import numpy as np
      rng = np.random.default_rng(42)
      r = (rng.normal(0, 0.01, 250)).tolist()
      sim = MonteCarloSimulator(r)
      assert 3 <= sim._block_size <= sim._returns.shape[0] - 1, f'block={sim._block_size}'
      sim2 = MonteCarloSimulator(r, block_size=7)
      assert sim2._block_size == 7
      print('OK', sim._block_size, sim2._block_size)
      "
      grep -q "from arch.bootstrap import optimal_block_length" engine/monte_carlo.py
      grep -q "_auto_select_block_size" engine/monte_carlo.py
      python -c "import arch; from arch.bootstrap import optimal_block_length; print('arch version:', arch.__version__)"
    </automated>
  </verify>
  <acceptance_criteria>
    - `engine/monte_carlo.py` contains the literal string `from arch.bootstrap import optimal_block_length`.
    - `engine/monte_carlo.py` contains the literal string `_auto_select_block_size`.
    - `engine/monte_carlo.py` default for `block_size` parameter is `None` (verified via `inspect.signature(MonteCarloSimulator.__init__).parameters['block_size'].default is None`).
    - `python -c "import arch"` succeeds (arch >=6 is installed per Plan 01 Task 1's `pyproject.toml` edit).
    - `MonteCarloSimulator(returns)._block_size` is in `[3, len(returns)-1]` for a random 250-point returns series.
    - `MonteCarloSimulator(returns, block_size=7)._block_size == 7` (explicit override preserved).
    - When `arch.bootstrap.optimal_block_length` is patched to raise, the fallback path sets `_block_size == 5` and logs a warning.
    - `pytest tests/test_foundation_03_block_length.py -x` → exit 0 with at least 7 tests.
    - `pytest tests/test_041_risk_analytics.py -x` → exit 0 (regression: existing Monte Carlo tests still pass).
  </acceptance_criteria>
  <done>
    MonteCarloSimulator auto-selects block_size via `arch.bootstrap.optimal_block_length` when the caller does not explicitly specify one. Explicit override is preserved. A graceful fallback logs a warning and uses block_size=5 if arch is unavailable or errors.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add backtest_mode flag to AgentInput and wire it through FundamentalAgent + Backtester (FOUND-04)</name>
  <read_first>
    - agents/models.py (whole file — 62 lines)
    - agents/fundamental.py (focus on lines 35-142 — the analyze method and its early guards)
    - backtesting/engine.py (focus on line 274 — the single AgentInput construction site inside the rebalance loop)
    - tests/test_006_fundamental_agent.py (existing FundamentalAgent test pattern — MockProvider, asyncio.run)
    - .planning/research/PITFALLS.md lines 137-161 (look-ahead bias discussion + recommended fix)
    - .planning/codebase/CONCERNS.md lines 273-278 (point-in-time fundamental data flagged HIGH priority)
  </read_first>
  <behavior>
    - Test A: `AgentInput(ticker="AAPL", asset_type="stock")` has `.backtest_mode == False` by default.
    - Test B: `AgentInput(ticker="AAPL", asset_type="stock", backtest_mode=True).backtest_mode is True`.
    - Test C: Constructing `AgentInput(backtest_mode="yes")` (non-bool) — document the expected behavior. For this plan we accept truthy values (Python doesn't enforce bool); the agent uses `if agent_input.backtest_mode:` which is truthiness-based. Test asserts `if agent_input.backtest_mode:` behaves correctly for `True`, `False`, `0`, `1`.
    - Test D: `FundamentalAgent(mock_provider).analyze(AgentInput(ticker="AAPL", asset_type="stock", backtest_mode=True))` returns an `AgentOutput` with:
        * `signal == Signal.HOLD`
        * `confidence <= 40.0`
        * `warnings` list contains a string matching the pattern `backtest_mode.*skipping.*restated.*fundamentals|look-ahead bias` (case-insensitive)
        * `mock_provider.get_key_stats` was called ZERO times (verified via counter on mock)
        * `mock_provider.get_financials` was called ZERO times
    - Test E: `FundamentalAgent(mock_provider).analyze(AgentInput(ticker="AAPL", asset_type="stock"))` (backtest_mode=False, default) still calls `get_key_stats` and `get_financials` exactly once each (unchanged behavior).
    - Test F: `Backtester.run` builds AgentInput with `backtest_mode=True`. Verified via grep of the source AND via a fake provider that tracks calls: when backtesting with `agents=["FundamentalAgent"]`, the fundamental provider paths are NOT hit.
    - Test G: The existing `tests/test_006_fundamental_agent.py` suite still passes in full (regression).
  </behavior>
  <action>
    1. Edit `agents/models.py`. Add a field to `AgentInput`:
       ```python
       @dataclass
       class AgentInput:
           ticker: str
           asset_type: str
           portfolio: Portfolio | None = None
           regime: Regime | None = None
           learned_weights: dict[str, Any] = field(default_factory=dict)
           approved_rules: list[str] = field(default_factory=list)
           backtest_mode: bool = False
       ```
       Place it at the end of the field list to preserve positional-arg compatibility for any existing call sites that construct `AgentInput` positionally (none currently should — all existing callers use kwargs — but defensive ordering is cheap).

    2. Edit `agents/fundamental.py`. At the very top of `analyze()`, BEFORE `self._logger.info("Analyzing %s", agent_input.ticker)`, add the backtest_mode gate:
       ```python
       async def analyze(self, agent_input: AgentInput) -> AgentOutput:
           self._validate_asset_type(agent_input)

           if agent_input.backtest_mode:
               self._logger.info(
                   "Analyzing %s in backtest_mode: returning HOLD (no provider calls)",
                   agent_input.ticker,
               )
               return AgentOutput(
                   agent_name=self.name,
                   ticker=agent_input.ticker,
                   signal=Signal.HOLD,
                   confidence=30.0,
                   reasoning=(
                       "FundamentalAgent is disabled in backtest_mode because yfinance "
                       "returns current/restated financials, which would inject look-ahead "
                       "bias into historical backtests. Defaulting to HOLD."
                   ),
                   metrics=self._empty_metrics(),
                   warnings=[
                       "backtest_mode: skipping restated fundamentals to prevent "
                       "look-ahead bias."
                   ],
                   data_completeness=0.0,
               )

           self._logger.info("Analyzing %s", agent_input.ticker)
           warnings: list[str] = [NON_PIT_WARNING]
           # ... existing body unchanged ...
       ```
       Do NOT change ANY other logic in `analyze()`. The existing try/except around provider calls stays.

    3. Edit `backtesting/engine.py`. Find the `AgentInput` construction (currently line 274):
       ```python
       agent_input = AgentInput(ticker=cfg.ticker, asset_type=cfg.asset_type)
       ```
       Change to:
       ```python
       agent_input = AgentInput(
           ticker=cfg.ticker,
           asset_type=cfg.asset_type,
           backtest_mode=True,
       )
       ```
       Do NOT change any other line. Do NOT remove the existing non-PIT warning (lines 166-172) — it still applies if the user explicitly opts in FundamentalAgent via `cfg.agents=["FundamentalAgent"]`. The warning text AND the backtest_mode HOLD output are complementary: the warning tells the user, the agent's backtest_mode output proves it's honored.

    4. Create `tests/test_foundation_04_backtest_mode.py`. Pattern:
       ```python
       from __future__ import annotations
       import asyncio
       from unittest.mock import AsyncMock
       import pandas as pd
       import pytest

       from agents.fundamental import FundamentalAgent
       from agents.models import AgentInput, Signal
       from data_providers.base import DataProvider


       class CountingProvider(DataProvider):
           def __init__(self):
               self.key_stats_calls = 0
               self.financials_calls = 0
               self.price_calls = 0

           async def get_price_history(self, ticker, period="1y", interval="1d"):
               self.price_calls += 1
               return pd.DataFrame()

           async def get_current_price(self, ticker):
               return 100.0

           async def get_key_stats(self, ticker):
               self.key_stats_calls += 1
               return {"market_cap": 1e12, "pe_ratio": 25.0, "sector": "Technology"}

           async def get_financials(self, ticker, period="annual"):
               self.financials_calls += 1
               return {"income_statement": None, "balance_sheet": None, "cash_flow": None}

           def is_point_in_time(self):
               return False

           def supported_asset_types(self):
               return ["stock"]


       def test_agent_input_default_backtest_mode_false():
           i = AgentInput(ticker="AAPL", asset_type="stock")
           assert i.backtest_mode is False

       def test_agent_input_backtest_mode_true():
           i = AgentInput(ticker="AAPL", asset_type="stock", backtest_mode=True)
           assert i.backtest_mode is True

       def test_fundamental_backtest_mode_returns_hold_without_calls():
           async def _run():
               provider = CountingProvider()
               agent = FundamentalAgent(provider)
               out = await agent.analyze(AgentInput(
                   ticker="AAPL", asset_type="stock", backtest_mode=True,
               ))
               assert out.signal == Signal.HOLD
               assert out.confidence <= 40.0
               assert any("backtest_mode" in w.lower() for w in out.warnings)
               assert provider.key_stats_calls == 0, "get_key_stats should NOT be called"
               assert provider.financials_calls == 0, "get_financials should NOT be called"
           asyncio.run(_run())

       def test_fundamental_backtest_mode_false_still_calls_provider():
           async def _run():
               provider = CountingProvider()
               agent = FundamentalAgent(provider)
               out = await agent.analyze(AgentInput(
                   ticker="AAPL", asset_type="stock",
               ))
               assert provider.key_stats_calls == 1
               assert provider.financials_calls == 1
           asyncio.run(_run())

       def test_backtester_threads_backtest_mode_true():
           # Grep-level check as a final safety net (complements behavior tests)
           src = open("backtesting/engine.py").read()
           assert "backtest_mode=True" in src, "Backtester must set backtest_mode=True"
       ```
  </action>
  <verify>
    <automated>
      pytest tests/test_foundation_04_backtest_mode.py -x -v
      pytest tests/test_006_fundamental_agent.py -x
      pytest tests/test_013_backtesting.py -x
      grep -q "backtest_mode: bool = False" agents/models.py
      grep -q "agent_input.backtest_mode" agents/fundamental.py
      grep -q "backtest_mode=True" backtesting/engine.py
      grep -q "skipping restated fundamentals" agents/fundamental.py
      python -c "from agents.models import AgentInput; i = AgentInput('AAPL','stock'); assert i.backtest_mode is False; j = AgentInput('AAPL','stock',backtest_mode=True); assert j.backtest_mode is True; print('OK')"
    </automated>
  </verify>
  <acceptance_criteria>
    - `agents/models.py` contains the literal line `backtest_mode: bool = False`.
    - `agents/fundamental.py` contains the literal `agent_input.backtest_mode`.
    - `agents/fundamental.py` contains the warning substring `skipping restated fundamentals`.
    - `backtesting/engine.py` contains the literal substring `backtest_mode=True`.
    - `pytest tests/test_foundation_04_backtest_mode.py -x` → exit 0 with at least 5 tests (behaviors A,B,D,E,F), all passing.
    - `pytest tests/test_006_fundamental_agent.py -x` → exit 0 (regression: existing FundamentalAgent tests still pass).
    - `pytest tests/test_013_backtesting.py -x` → exit 0 (regression: existing backtesting tests still pass).
    - `AgentInput("AAPL", "stock").backtest_mode is False` and `AgentInput("AAPL", "stock", backtest_mode=True).backtest_mode is True` at runtime.
    - In backtest_mode=True, `CountingProvider.key_stats_calls == 0` after `FundamentalAgent.analyze()` — proving no provider call was made.
  </acceptance_criteria>
  <done>
    `AgentInput` has a `backtest_mode` boolean field defaulting to False. When True, `FundamentalAgent.analyze` returns HOLD immediately with a clear warning and makes zero provider calls, eliminating the possibility of silent look-ahead bias via restated yfinance financials. `Backtester.run` sets `backtest_mode=True` in every `AgentInput` it constructs.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Parametrized test proving SignalAggregator renormalizes to sum=1.0 for every single-agent-disabled scenario (FOUND-05)</name>
  <read_first>
    - engine/aggregator.py (whole file — 317 lines; focus on lines 110-145 for the renormalization block)
    - tests/test_008_signal_aggregator.py (existing aggregator tests — pattern + helpers)
    - agents/models.py (AgentOutput, Signal enums)
    - .planning/codebase/CONCERNS.md lines 185-192 ("signal aggregator weight normalization" fragile area)
  </read_first>
  <behavior>
    - Test A (parametrized, stock asset type, 4 scenarios): For each agent in `["TechnicalAgent", "FundamentalAgent", "MacroAgent", "SentimentAgent"]`, construct agent outputs for the OTHER three, aggregate, assert `sum(result.metrics["weights_used"].values())` is within `1e-6` of `1.0`.
    - Test B (parametrized, btc asset type, 2 scenarios): For each agent in `["CryptoAgent", "TechnicalAgent"]`, build agent outputs with that one missing (i.e., only the other one present), aggregate, assert `sum == 1.0`.
    - Test C (parametrized, eth asset type, 2 scenarios): Same as btc.
    - Test D (no agents at all): `aggregate([], "stock")` returns `metrics["weights_used"] == {}` AND `final_signal == Signal.HOLD` with a `"No agent produced a signal."` warning (existing degenerate path — verify unchanged).
    - Test E (confidence scaling regression): Disabling SentimentAgent (which has default weight 0.15) and running the remaining three at 100% confidence should NOT produce a `final_confidence` less than the case where all four ran at 100% confidence with SentimentAgent set to HOLD. (This is the "systematically deflated confidence" pitfall from PITFALLS.md #8.) Specifically: with 3 agents all BUY @ 100%, `final_confidence > 60`.
    - Test F (data_completeness interaction): Pass `data_completeness=0.5` on one agent; assert that agent's effective weight in `metrics["weights_used"]` is HALF what it would have been at completeness=1.0, and the total still sums to 1.0. This proves the completeness-scaling branch also renormalizes.
    - Test G (custom weights override preserved): If user passes `weights={"stock": {"TechnicalAgent": 0.5, "FundamentalAgent": 0.5}}` and supplies only TechnicalAgent, `metrics["weights_used"]["TechnicalAgent"] == pytest.approx(1.0)` (single agent gets the full weight via renormalization).
  </behavior>
  <action>
    Create `tests/test_foundation_05_agent_renorm.py`. The existing aggregator code at `engine/aggregator.py:110-129` ALREADY renormalizes (`total_raw = sum(used_raw.values())` then `weights = {k: v / total_raw for k, v in used_raw.items()}`). This task's job is to EXHAUSTIVELY verify every single-agent-disabled scenario per the ROADMAP success criterion.

    If any parametrized case FAILS the `sum ≈ 1.0` assertion, fix the underlying code (do not skip the failing test). The expected fix site is `engine/aggregator.py` lines 110-145.

    Test scaffolding:
    ```python
    from __future__ import annotations
    import pytest

    from agents.models import AgentOutput, Signal
    from engine.aggregator import SignalAggregator


    def _mk(name: str, signal: Signal = Signal.BUY, confidence: float = 60.0,
            data_completeness: float = 1.0) -> AgentOutput:
        return AgentOutput(
            agent_name=name,
            ticker="TEST",
            signal=signal,
            confidence=confidence,
            reasoning=f"{name} says {signal.value}",
            data_completeness=data_completeness,
        )


    STOCK_AGENTS = ["TechnicalAgent", "FundamentalAgent", "MacroAgent", "SentimentAgent"]
    BTC_AGENTS = ["CryptoAgent", "TechnicalAgent"]


    @pytest.mark.parametrize("missing", STOCK_AGENTS)
    def test_stock_renormalizes_with_one_agent_missing(missing):
        agg = SignalAggregator()
        outputs = [_mk(a) for a in STOCK_AGENTS if a != missing]
        result = agg.aggregate(outputs, "AAPL", "stock")
        weights = result.metrics["weights_used"]
        total = sum(weights.values())
        assert total == pytest.approx(1.0, abs=1e-6), (
            f"stock missing={missing}: weights sum to {total} != 1.0 (weights={weights})"
        )
        # Regression: confidence should not be crushed to 30 just because one agent is missing
        assert result.final_confidence >= 50.0, (
            f"stock missing={missing}: final_confidence={result.final_confidence} "
            f"(expected >=50 with 3 BUY agents at 60%)"
        )


    @pytest.mark.parametrize("missing", BTC_AGENTS)
    def test_btc_renormalizes_with_one_agent_missing(missing):
        agg = SignalAggregator()
        outputs = [_mk(a) for a in BTC_AGENTS if a != missing]
        result = agg.aggregate(outputs, "BTC-USD", "btc")
        weights = result.metrics["weights_used"]
        total = sum(weights.values())
        assert total == pytest.approx(1.0, abs=1e-6), (
            f"btc missing={missing}: weights sum to {total} (weights={weights})"
        )


    @pytest.mark.parametrize("missing", BTC_AGENTS)
    def test_eth_renormalizes_with_one_agent_missing(missing):
        agg = SignalAggregator()
        outputs = [_mk(a) for a in BTC_AGENTS if a != missing]
        result = agg.aggregate(outputs, "ETH-USD", "eth")
        weights = result.metrics["weights_used"]
        total = sum(weights.values())
        assert total == pytest.approx(1.0, abs=1e-6), (
            f"eth missing={missing}: weights sum to {total} (weights={weights})"
        )


    def test_empty_agent_outputs_produce_hold():
        agg = SignalAggregator()
        result = agg.aggregate([], "AAPL", "stock")
        assert result.final_signal == Signal.HOLD
        assert "No agent produced a signal." in result.warnings
        assert result.metrics["weights_used"] == {}


    def test_confidence_not_deflated_by_missing_agent():
        agg = SignalAggregator()
        # 3 BUY agents at 100% confidence, SentimentAgent missing
        outputs = [_mk(a, Signal.BUY, confidence=100.0) for a in
                   ("TechnicalAgent", "FundamentalAgent", "MacroAgent")]
        result = agg.aggregate(outputs, "AAPL", "stock")
        assert result.final_confidence >= 60.0, (
            f"confidence deflated to {result.final_confidence} when SentimentAgent missing"
        )


    def test_data_completeness_scales_weight_but_sum_stays_one():
        agg = SignalAggregator()
        full = [_mk(a, data_completeness=1.0) for a in STOCK_AGENTS]
        half = [
            _mk("TechnicalAgent", data_completeness=0.5),
            _mk("FundamentalAgent", data_completeness=1.0),
            _mk("MacroAgent", data_completeness=1.0),
            _mk("SentimentAgent", data_completeness=1.0),
        ]
        r_full = agg.aggregate(full, "AAPL", "stock")
        r_half = agg.aggregate(half, "AAPL", "stock")
        # Both should still sum to 1.0
        assert sum(r_full.metrics["weights_used"].values()) == pytest.approx(1.0, abs=1e-6)
        assert sum(r_half.metrics["weights_used"].values()) == pytest.approx(1.0, abs=1e-6)
        # Half-completeness Technical should have less weight than full-completeness Technical
        assert (
            r_half.metrics["weights_used"]["TechnicalAgent"]
            < r_full.metrics["weights_used"]["TechnicalAgent"]
        )


    def test_custom_weights_renormalize_on_missing_agent():
        custom = {"stock": {"TechnicalAgent": 0.5, "FundamentalAgent": 0.5}}
        agg = SignalAggregator(weights=custom)
        outputs = [_mk("TechnicalAgent", Signal.BUY, confidence=80.0)]
        result = agg.aggregate(outputs, "AAPL", "stock")
        assert result.metrics["weights_used"]["TechnicalAgent"] == pytest.approx(1.0, abs=1e-6)
    ```

    Also, as a minor documentation-only enhancement in `engine/aggregator.py`, add a comment above lines 115-129 explaining the invariant. Do NOT alter the renormalization logic unless the tests fail:
    ```python
    # --- Weight renormalization (FOUND-05) ---
    # When fewer agents than expected are present (e.g., SentimentAgent offline),
    # scale remaining weights so they sum to exactly 1.0. Each weight is also
    # scaled by the agent's data_completeness before renormalization so agents
    # with partial data contribute proportionally less. Invariant validated by
    # tests/test_foundation_05_agent_renorm.py (parametrized across every
    # single-agent-disabled scenario for stock/btc/eth).
    ```

    If any test fails due to genuine math error (unlikely — the existing code looks correct), fix the aggregator block accordingly and re-run. Document the fix in the plan SUMMARY.
  </action>
  <verify>
    <automated>
      pytest tests/test_foundation_05_agent_renorm.py -x -v
      pytest tests/test_008_signal_aggregator.py -x
      grep -q "Weight renormalization (FOUND-05)" engine/aggregator.py
      python -c "
      from engine.aggregator import SignalAggregator
      from agents.models import AgentOutput, Signal
      o = [AgentOutput(agent_name='TechnicalAgent', ticker='T', signal=Signal.BUY, confidence=60.0, reasoning='x'),
           AgentOutput(agent_name='FundamentalAgent', ticker='T', signal=Signal.BUY, confidence=60.0, reasoning='x'),
           AgentOutput(agent_name='MacroAgent', ticker='T', signal=Signal.BUY, confidence=60.0, reasoning='x')]
      r = SignalAggregator().aggregate(o, 'T', 'stock')
      s = sum(r.metrics['weights_used'].values())
      assert abs(s - 1.0) < 1e-6, s
      print('weights sum to', s)
      "
    </automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_foundation_05_agent_renorm.py` exists and contains at least 8 test functions (4 parametrized stock + 2 parametrized btc + 2 parametrized eth + 4 regression tests).
    - `engine/aggregator.py` contains the literal comment substring `Weight renormalization (FOUND-05)` (documenting the invariant).
    - `pytest tests/test_foundation_05_agent_renorm.py -x` → exit 0 (all scenarios pass).
    - `pytest tests/test_008_signal_aggregator.py -x` → exit 0 (regression: existing aggregator tests still pass).
    - For every asset type × missing-agent combination (8 cases for stock with 4 agents taken 3 at a time = 4 "missing one"; btc = 2; eth = 2 = 8 total parametrized cases), the sum of `metrics["weights_used"].values()` equals 1.0 within 1e-6.
    - `test_confidence_not_deflated_by_missing_agent`: `final_confidence >= 60` when 3 BUY agents @ 100% confidence are aggregated with SentimentAgent missing.
  </acceptance_criteria>
  <done>
    The ROADMAP Phase 1 success criterion 4 ("Disabling any agent renormalizes remaining weights to sum to 1.0 — verifiable via parametrized test") is met by a dedicated parametrized test suite covering every single-agent-disabled scenario for stock/btc/eth. The existing aggregator code passes every scenario; a documentation comment references the tests. If any scenario had failed, the aggregator math would have been corrected in this task.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Backtest runner → agent pipeline | The backtester constructs AgentInput; if `backtest_mode` were omitted, FundamentalAgent would silently use restated data (look-ahead bias). |
| External library (arch) → Monte Carlo simulator | arch returns a block-length estimate; an attacker who poisoned the arch install could distort risk calculations. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-01 | Tampering | Malicious actor modifies backtesting/engine.py to drop `backtest_mode=True` | mitigate | Task 2 acceptance criteria include a grep check that `backtest_mode=True` is literally present in the source. Ongoing regression protection via `test_foundation_04_backtest_mode.py::test_backtester_threads_backtest_mode_true`. |
| T-03-02 | Information disclosure | Non-PIT warning strings could leak ticker names to logs | accept | Ticker names are public market symbols; no risk. |
| T-03-03 | Denial of service | `arch.optimal_block_length` on degenerate input (all zeros) could hang | mitigate | `_auto_select_block_size` wraps arch in try/except and falls back to `block_size=5` on any exception, logging a warning. |
| T-03-04 | Tampering | A caller passes `AgentInput(backtest_mode=False)` inside `Backtester.run` to bypass the guard | mitigate | Task 2 hardcodes `backtest_mode=True` in `Backtester.run`. The user-facing `cfg.agents=["FundamentalAgent"]` opt-in triggers a non-PIT warning in results. Both are belt + suspenders. |
| T-03-05 | Repudiation | Backtest results are silently more optimistic if a future code change reverts Task 2 | mitigate | The `warnings` field of the backtest result retains the non-PIT message (existing code at backtesting/engine.py:166-172). |
</threat_model>

<verification>
```bash
pytest tests/test_foundation_03_block_length.py tests/test_foundation_04_backtest_mode.py tests/test_foundation_05_agent_renorm.py -x -v
pytest tests/test_041_risk_analytics.py tests/test_006_fundamental_agent.py tests/test_008_signal_aggregator.py tests/test_013_backtesting.py -x
grep -q "from arch.bootstrap import optimal_block_length" engine/monte_carlo.py
grep -q "_auto_select_block_size" engine/monte_carlo.py
grep -q "backtest_mode: bool = False" agents/models.py
grep -q "agent_input.backtest_mode" agents/fundamental.py
grep -q "backtest_mode=True" backtesting/engine.py
grep -q "Weight renormalization (FOUND-05)" engine/aggregator.py
python -c "from agents.models import AgentInput; assert AgentInput('A','stock').backtest_mode is False; assert AgentInput('A','stock',backtest_mode=True).backtest_mode is True"
python -c "from engine.monte_carlo import MonteCarloSimulator; import numpy as np; r = np.random.default_rng(1).normal(0,0.01,250).tolist(); s = MonteCarloSimulator(r); assert 3 <= s._block_size <= len(r)-1"
```

All 9 checks must exit 0.
</verification>

<success_criteria>
- Monte Carlo auto-selects block_size via `arch.bootstrap.optimal_block_length`. Explicit overrides still honored.
- Arch fallback to `block_size=5` on any exception, with a logged warning.
- `AgentInput.backtest_mode: bool = False` is the new field.
- `FundamentalAgent.analyze` short-circuits to HOLD + warning on `backtest_mode=True` with ZERO provider calls.
- `Backtester.run` always constructs `AgentInput(..., backtest_mode=True)`.
- Parametrized `test_foundation_05_agent_renorm.py` passes for every single-agent-disabled scenario for stock (4 cases), btc (2 cases), eth (2 cases).
- Confidence for 3 BUY agents @ 100% with SentimentAgent missing is >= 60 (not deflated).
- All existing tests in `tests/test_006_fundamental_agent.py`, `tests/test_008_signal_aggregator.py`, `tests/test_013_backtesting.py`, `tests/test_041_risk_analytics.py` continue to pass.
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-hardening/03-PLAN-signal-math-corrections-SUMMARY.md` documenting:
- Before/after behavior of `MonteCarloSimulator`: default block_size old=5, new=auto-selected (include the specific value returned for a representative returns series)
- Before/after behavior of `FundamentalAgent`: provider call counts in backtest_mode=True (expected: 0) vs backtest_mode=False (expected: 1 key_stats + 1 financials)
- Parametrized renormalization test coverage matrix (asset type × missing agent → pass/fail)
- Any aggregator math fixes if Task 3 uncovered an edge case (expected: none; document "no changes needed, existing renormalization math is correct" if so)
</output>
</content>
</invoke>