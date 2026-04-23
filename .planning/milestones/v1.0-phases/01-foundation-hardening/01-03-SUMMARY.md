---
phase: 01-foundation-hardening
plan: 03
subsystem: signal-quality
tags: [monte-carlo, arch, block-bootstrap, backtesting, look-ahead-bias, aggregator, renormalization, FOUND-03, FOUND-04, FOUND-05]

dependency_graph:
  requires:
    - phase: 01-foundation-hardening/01-01
      provides: arch>=6.0 installed in pyproject.toml (required for optimal_block_length)
    - phase: 01-foundation-hardening/01-02
      provides: db/daemon durability (unrelated but in same phase chain)
  provides:
    - engine.monte_carlo.MonteCarloSimulator._auto_select_block_size (Patton-Politis-White block size)
    - agents.models.AgentInput.backtest_mode field
    - agents.fundamental.FundamentalAgent.analyze backtest_mode short-circuit (no provider calls)
    - backtesting.engine.Backtester backtest_mode=True threading
    - tests/test_foundation_03_block_length.py (10 tests)
    - tests/test_foundation_04_backtest_mode.py (10 tests)
    - tests/test_foundation_05_agent_renorm.py (12 parametrized test items)
  affects:
    - Phase 2 backtesting (all future Backtester.run() calls now set backtest_mode=True)
    - Any caller of MonteCarloSimulator that relied on default block_size=5 (now auto-selected)

tech-stack:
  added: []
  patterns:
    - "arch.bootstrap.optimal_block_length in try/except fallback: import locally inside method, wrap in broad except, log WARNING and return default on failure"
    - "backtest_mode short-circuit: at the very top of analyze(), before any provider call, check the flag and return HOLD with data_completeness=0.0 so aggregator renormalization excludes the agent"
    - "Parametrized test coverage: use @pytest.mark.parametrize over all asset-type x missing-agent combinations to exhaustively validate a mathematical invariant"

key-files:
  created:
    - tests/test_foundation_03_block_length.py (10 tests: override, auto-range, AR1 sanity, fallback, simulate shape, block_size key, full-array call, default=None)
    - tests/test_foundation_04_backtest_mode.py (10 tests: default False, explicit True, truthy, HOLD+no-calls, provider still called, grep check, smoke)
    - tests/test_foundation_05_agent_renorm.py (12 test items: 4 stock parametrized, 2 btc, 2 eth, empty outputs, confidence, completeness scaling, custom weights)
  modified:
    - engine/monte_carlo.py (block_size: int | None = None, _auto_select_block_size static method, logger)
    - agents/models.py (backtest_mode: bool = False added to AgentInput)
    - agents/fundamental.py (backtest_mode short-circuit at top of analyze())
    - backtesting/engine.py (AgentInput construction gains backtest_mode=True)
    - engine/aggregator.py (FOUND-05 invariant comment above renormalization block)

key-decisions:
  - "Import arch locally inside _auto_select_block_size (not at module top) so arch absence does not break the entire module at import time — defensive even though arch is always present per Plan 01-01"
  - "data_completeness=0.0 for backtest_mode HOLD: ensures the aggregator weight renormalization excludes FundamentalAgent from the weighted sum entirely when backtest_mode=True, preventing even a 0-weight contribution"
  - "Test E (provider-call regression) uses >= 1 for key_stats_calls: sector_pe_cache also calls get_key_stats internally, so == 1 would be a flaky assertion; >= 1 is correct and still proves the call is made"
  - "Existing aggregator math correct: no SignalAggregator code changes needed — FOUND-05 task added the comment and 12-test validation only"

patterns-established:
  - "All backtest-specific behavior gated via AgentInput.backtest_mode; Backtester is the single source of truth for setting it True"
  - "Monte Carlo block-size selection: auto via arch PPW, fallback to 5, explicit override always wins"

requirements-completed: [FOUND-03, FOUND-04, FOUND-05]

duration: 19min
completed: "2026-04-21"
---

# Phase 1 Plan 03: Foundation Hardening — Signal Math Corrections Summary

**Arch PPW auto-selects Monte Carlo block size, `backtest_mode=True` gates FundamentalAgent from restated yfinance data in backtests, and 12 parametrized tests exhaustively validate SignalAggregator weight renormalization to sum=1.0 for every single-agent-disabled scenario across stock/btc/eth.**

## Performance

- **Duration:** ~19 min
- **Started:** 2026-04-21T09:47:12Z
- **Completed:** 2026-04-21T10:06:07Z
- **Tasks:** 3
- **Files modified:** 5 source files modified, 3 new test files created

## Accomplishments

- `MonteCarloSimulator` now auto-selects block_size via `arch.bootstrap.optimal_block_length` (Patton-Politis-White 2004). For a 250-point returns series with seed=1, the auto-selected block_size is `3` (clamped from the PPW estimate). Explicit `block_size=7` override still returns 7. Fallback to `block_size=5` on any arch exception with WARNING log confirmed by test.
- `FundamentalAgent.analyze()` short-circuits to HOLD with `confidence=30`, `data_completeness=0.0`, and a `backtest_mode: skipping restated fundamentals` warning when `agent_input.backtest_mode is True` — zero provider calls confirmed. `Backtester.run()` now threads `backtest_mode=True` into every `AgentInput` it constructs, eliminating the look-ahead bias vector.
- 12-item parametrized test suite exhaustively validates `sum(weights_used.values()) ≈ 1.0` for all single-agent-disabled combinations: stock ×4, btc ×2, eth ×2, plus 4 regression tests. Existing aggregator math is confirmed correct — no code changes needed.

## Before/After Behavior

### MonteCarloSimulator block_size

| Before | After |
|--------|-------|
| `block_size: int = 5` (hardcoded default) | `block_size: int \| None = None` (auto-selects via PPW) |
| Always uses 5 blocks regardless of autocorrelation structure | Auto-selects optimal block length for the actual returns series |
| No fallback needed | On any exception: falls back to `block_size=5` + WARNING log |
| Override: `block_size=7` → `_block_size=7` | Override preserved: `block_size=7` → `_block_size=7` |

Representative value: `MonteCarloSimulator(rng(seed=1).normal(0,0.01,250))._block_size == 3`

### FundamentalAgent provider call counts

| Mode | `key_stats_calls` | `financials_calls` | Signal |
|------|-------------------|-------------------|--------|
| `backtest_mode=False` (default) | ≥1 | 1 | BUY/HOLD/SELL |
| `backtest_mode=True` | **0** | **0** | HOLD (confidence=30) |

### Parametrized renormalization test coverage matrix

| Asset | Missing Agent | Weights sum ≈ 1.0 | final_confidence ≥ 50 |
|-------|---------------|-------------------|----------------------|
| stock | TechnicalAgent | PASS | PASS |
| stock | FundamentalAgent | PASS | PASS |
| stock | MacroAgent | PASS | PASS |
| stock | SentimentAgent | PASS | PASS |
| btc | CryptoAgent | PASS | — |
| btc | TechnicalAgent | PASS | — |
| eth | CryptoAgent | PASS | — |
| eth | TechnicalAgent | PASS | — |

## Task Commits

1. **Task 1: Auto block_size via arch.optimal_block_length (FOUND-03)** — `dffb4aa` (feat)
2. **Task 2: backtest_mode flag (FOUND-04)** — `56b6452` (feat)
3. **Task 3: Parametrized renorm tests + FOUND-05 comment (FOUND-05)** — `23be6b3` (feat)

## Files Created/Modified

- `engine/monte_carlo.py` — `block_size: int | None = None` default; `_auto_select_block_size()` static method; module-level `logger`
- `agents/models.py` — `backtest_mode: bool = False` appended to `AgentInput` dataclass
- `agents/fundamental.py` — `backtest_mode` gate at top of `analyze()` (before any provider call)
- `backtesting/engine.py` — `AgentInput(ticker=cfg.ticker, asset_type=cfg.asset_type, backtest_mode=True)`
- `engine/aggregator.py` — `# --- Weight renormalization (FOUND-05) ---` comment block
- `tests/test_foundation_03_block_length.py` — 10 tests (FOUND-03 behaviors A-H)
- `tests/test_foundation_04_backtest_mode.py` — 10 tests (FOUND-04 behaviors A-G + truthy parametrize)
- `tests/test_foundation_05_agent_renorm.py` — 12 test items (FOUND-05 behaviors A-G)

## Decisions Made

- **arch local import inside `_auto_select_block_size`**: defensive — arch is always present (installed in Plan 01-01), but importing locally prevents the entire module from failing at import time if arch is somehow absent in a future environment.
- **`data_completeness=0.0` in backtest HOLD return**: ensures the aggregator renormalization logic fully excludes FundamentalAgent's weight contribution (not just zeroes it) when backtest_mode=True — belt-and-suspenders alongside the HOLD signal.
- **Test E uses `>= 1` for key_stats call count**: `sector_pe_cache.get_sector_pe_median()` also calls `get_key_stats` internally, so `== 1` would be an incorrect and flaky assertion; `>= 1` correctly proves the provider path is reached.
- **No aggregator math changes needed**: FOUND-05 task confirmed existing `total_raw = sum(used_raw.values())` / `weights = {k: v/total_raw ...}` renormalization is correct for all 8 parametrized scenarios.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test E assertion corrected from `== 1` to `>= 1` for `key_stats_calls`**

- **Found during:** Task 2, GREEN phase (test_fundamental_backtest_mode_false_still_calls_provider)
- **Issue:** `CountingProvider.get_key_stats` was called twice (once by `FundamentalAgent.analyze()` directly, once by `sector_pe_cache.get_sector_pe_median()` internally). The test asserted `== 1` but got `2`.
- **Fix:** Changed assertion to `>= 1` with an explanatory comment. The test still proves provider is called (non-backtest path), which is the intent.
- **Files modified:** `tests/test_foundation_04_backtest_mode.py`
- **Commit:** `56b6452`

---

**Total deviations:** 1 auto-fixed (Rule 1 — incorrect test assertion, not a production bug)
**Impact on plan:** Test intent preserved. No production code changes needed.

## Known Stubs

None — all implemented functionality is fully wired. `_auto_select_block_size` is a complete implementation (not a stub); `backtest_mode` gate in `FundamentalAgent` is live code; `Backtester.run()` sets `backtest_mode=True` in the live rebalance loop.

## Threat Flags

No new trust boundary surfaces beyond those declared in the plan's threat model (T-03-01 through T-03-05). The `backtest_mode=True` check in `Backtester.run()` is validated by both a grep-based test and a behavioral test (zero provider calls), satisfying mitigations T-03-01 and T-03-04.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| engine/monte_carlo.py | FOUND |
| agents/models.py | FOUND |
| agents/fundamental.py | FOUND |
| backtesting/engine.py | FOUND |
| engine/aggregator.py | FOUND |
| tests/test_foundation_03_block_length.py | FOUND |
| tests/test_foundation_04_backtest_mode.py | FOUND |
| tests/test_foundation_05_agent_renorm.py | FOUND |
| commit dffb4aa (Task 1) | FOUND |
| commit 56b6452 (Task 2) | FOUND |
| commit 23be6b3 (Task 3) | FOUND |
| 32 new tests passing | CONFIRMED |
| 46 regression tests passing | CONFIRMED |
