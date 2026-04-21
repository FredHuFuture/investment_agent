---
phase: 02-signal-quality-upgrade
verified: 2026-04-21T00:00:00Z
status: passed
score: 4/4 success criteria verified
must_haves_verified: 4/4
overrides_applied: 0
requirement_coverage:
  - id: SIG-01
    status: satisfied
  - id: SIG-02
    status: satisfied
  - id: SIG-03
    status: satisfied
  - id: SIG-04
    status: satisfied
  - id: SIG-05
    status: satisfied
  - id: SIG-06
    status: satisfied
success_criteria:
  - criterion: "GET /api/v1/analytics/risk returns cvar_95 (QuantStats CVaR) and portfolio_var (historical simulation, correlation-aware)"
    status: verified
    evidence: "engine/analytics.py:544-554 uses qs_stats.cvar() at 0.95 and 0.99 confidence; portfolio_var aliased to var_95 (Tier 1 identity); response dict line 585-588 surfaces cvar_95, cvar_99, portfolio_var, portfolio_var_method; 11/11 tests pass (6 in test_signal_quality_01_cvar.py, 5 in test_signal_quality_06_portfolio_var.py)"
  - criterion: "GET /api/v1/analytics/calibration returns per-agent Brier score and IC; negative-IC agents lose weight"
    status: verified
    evidence: "api/routes/calibration.py returns ic_5d + ic_horizon + brier_score per agent; engine/weight_adapter.py:475 applies max(0.0, icir/scale_divisor) — zero-floors negative IC; 19/19 tests pass across test_signal_quality_02_brier.py, test_signal_quality_03_ic_icir.py, test_signal_quality_03b_weight_adapter_ic.py including end-to-end HTTP test"
  - criterion: "Backtest with non-zero cost_per_trade produces strictly lower P&L than cost_per_trade=0"
    status: verified
    evidence: "backtesting/engine.py:387,401,427 applies entry+exit tx costs; test_cost_reduces_total_return asserts delta > 0.0001 (strict inequality); COST_PER_TRADE_EQUITY=0.001 COST_PER_TRADE_CRYPTO=0.0025 confirmed in backtesting/models.py:12-13; 3/3 tests pass"
  - criterion: "Walk-forward scaffold produces per-window out-of-sample Sharpe ratios in BacktestResult.walk_forward_windows"
    status: verified
    evidence: "backtesting/walk_forward.py: generate_walk_forward_windows(purge_days=1 default) + run_walk_forward(purge_days=5 default); BacktestResult.walk_forward_windows field confirmed; test_run_walk_forward_returns_per_window_sharpe asserts keys {window_idx, oos_start, oos_end, sharpe, total_return, n_trades}; 15/15 tests pass (test_signal_quality_05_walk_forward.py + test_signal_quality_05b_signal_corpus.py)"
regressions_found: []
---

# Phase 2: Signal Quality Upgrade Verification Report

**Phase Goal:** Every agent's predictive contribution is measurable, the backtester prices in transaction reality, and tail risk is visible at the portfolio level.
**Verified:** 2026-04-21
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /analytics/risk returns cvar_95, cvar_99, portfolio_var via QuantStats historical simulation | VERIFIED | engine/analytics.py:544-554; qs_stats.cvar(0.95) and qs_stats.cvar(0.99); N<10 guard returns None; 11/11 SC-1/SC-6 tests pass |
| 2 | GET /analytics/calibration returns per-agent Brier, ic_5d, ic_horizon, ic_ir; negative-IC agents get zero weight | VERIFIED | api/routes/calibration.py; tracker.py compute_brier_score + compute_rolling_ic + compute_icir; weight_adapter.py max(0, icir/2.0); 19/19 tests pass |
| 3 | Backtest with cost_per_trade=0.001 has strictly lower total_return than cost_per_trade=0 | VERIFIED | engine.py applies entry+exit tx costs; test_cost_reduces_total_return asserts delta > 0.0001; 3/3 tests pass |
| 4 | walk_forward_windows is a list of per-OOS-window dicts with sharpe, total_return, etc. | VERIFIED | BacktestResult.walk_forward_windows field; purge_days defaults correct (1 for generator, 5 for run_walk_forward); 15/15 tests pass |

**Score:** 4/4 truths verified

---

## Required Artifacts

### Plan 02-01 (SIG-01, SIG-06): CVaR + Portfolio VaR

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `engine/analytics.py` | QuantStats CVaR + portfolio VaR in get_portfolio_risk() | VERIFIED | 32 091 bytes; `import quantstats.stats as qs_stats` at line 26 (after matplotlib stubs); qs_stats.cvar called at lines 544-545; portfolio_var at line 554; N<10 guard at line 542 |
| `api/routes/analytics.py` | /risk endpoint surfaces cvar_95, cvar_99, portfolio_var | VERIFIED | Route unchanged; forwards dict from get_portfolio_risk() which now contains all new fields |
| `pyproject.toml` | quantstats>=0.0.81 dependency | VERIFIED | Line 23: `"quantstats>=0.0.81"` |
| `tests/test_signal_quality_01_cvar.py` | 6 CVaR tests + matplotlib-leak subprocess test | VERIFIED | 9 553 bytes, 6 test functions: reference match, fat-tail divergence, 99>95 monotonicity, insufficient-data None, matplotlib-leak subprocess, portfolio_var_method field |
| `tests/test_signal_quality_06_portfolio_var.py` | 5 portfolio VaR tests including FastAPI TestClient | VERIFIED | 9 798 bytes, 5 test functions including HTTP end-to-end |

### Plan 02-02 (SIG-04, SIG-05): Transaction Costs + Walk-Forward + Signal Corpus

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backtesting/models.py` | cost_per_trade field + COST_PER_TRADE_EQUITY/CRYPTO constants | VERIFIED | COST_PER_TRADE_EQUITY=0.001 at line 12; COST_PER_TRADE_CRYPTO=0.0025 at line 13; BacktestConfig.cost_per_trade at line 43; walk_forward_windows at line 73 |
| `backtesting/engine.py` | cost applied at entry+exit; total_costs_paid accumulated | VERIFIED | Lines 387, 401, 427 accumulate total_costs_paid; metrics["total_costs_paid"] at line 438 |
| `backtesting/walk_forward.py` | generate_walk_forward_windows(purge_days=1) + run_walk_forward(purge_days=5) | VERIFIED | 7 203 bytes; generate_walk_forward_windows default purge_days=1 confirmed; run_walk_forward default purge_days=5 confirmed; BLOCKER 4 resolution documented |
| `backtesting/signal_corpus.py` | populate_signal_corpus uses agg_raw_score (WR-01 fix) | VERIFIED | 6 864 bytes; line 129: `agg_raw_score = entry.get("raw_score", 0.0)`; used in INSERT tuple at line 137 |
| `db/database.py` | backtest_signal_history table DDL + idx_bsh_ticker_date + idx_bsh_agent_date | VERIFIED | CREATE TABLE IF NOT EXISTS backtest_signal_history with 13 columns; both indexes confirmed |
| `daemon/jobs.py` | rebuild_signal_corpus uses async with for log_conn (WR-02 fix) | VERIFIED | WR-02 committed at 238ccab; async with pattern replaces bare aiosqlite.connect |
| `tests/test_signal_quality_04_tx_costs.py` | 3 tx cost tests | VERIFIED | 8 886 bytes, 3 test functions; test_cost_reduces_total_return asserts strict delta > 0.0001 |
| `tests/test_signal_quality_05_walk_forward.py` | 10 walk-forward tests | VERIFIED | 16 845 bytes, 10 test functions |
| `tests/test_signal_quality_05b_signal_corpus.py` | 5 corpus tests including WR-01 raw_score guard | VERIFIED | 9 739 bytes, 5 test functions; test_populate_signal_corpus_stores_raw_score_not_null asserts COUNT(raw_score IS NULL) = 0 |

### Plan 02-03 (SIG-02, SIG-03): Brier + IC/IC-IR + Calibration API

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tracking/store.py` | get_backtest_signals_by_agent + get_backtest_corpus_metadata | VERIFIED | Both methods present; get_backtest_signals_by_agent delegates to module-level _get_backtest_signals_by_agent; get_backtest_corpus_metadata reads COUNT(DISTINCT ticker) for survivorship_bias_warning (WR-03 fix: n_tickers <= 3) |
| `tracking/tracker.py` | compute_brier_score + compute_rolling_ic + compute_icir | VERIFIED | 17 980 bytes; all three methods at lines 320, 356, 427; HOLD excluded in brier; raw_score used in IC (AP-02); NaN guard via `ic_val == ic_val`; std=0 guard in compute_icir |
| `engine/weight_adapter.py` | compute_ic_weights returning AdaptiveWeights source="ic_ir" or None | VERIFIED | 22 824 bytes; method at line 433; max(0.0, icir/scale_divisor) at line 475; all-zero → equal-weight fallback; no agents valid → returns None |
| `api/routes/calibration.py` | GET /calibration endpoint with ic_5d + ic_horizon stable keys | VERIFIED | 4 481 bytes; WARNING 11 fix: ic_5d stable key + ic_horizon sibling; FundamentalAgent null with FOUND-04 note; preliminary_calibration=True; survivorship_bias_warning in corpus_metadata |
| `api/app.py` | calibration_router registered under /analytics prefix | VERIFIED | Line 119-120: `from api.routes.calibration import router as calibration_router` + `app.include_router(calibration_router, prefix="/analytics", ...)` |
| `tests/test_signal_quality_02_brier.py` | 6 Brier tests | VERIFIED | 7 384 bytes, 6 test functions |
| `tests/test_signal_quality_03_ic_icir.py` | 6 IC/IC-IR tests | VERIFIED | 7 730 bytes, 6 test functions |
| `tests/test_signal_quality_03b_weight_adapter_ic.py` | 7 weight-adapter + calibration API tests | VERIFIED | 13 047 bytes, 7 test functions including end-to-end HTTP calibration test |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `engine/analytics.py::get_portfolio_risk` | `quantstats.stats.cvar` | qs_stats.cvar(_returns_series, confidence=0.95/0.99) | WIRED | Lines 544-545 confirmed; preceded by matplotlib stub pre-emption lines 18-24 |
| `engine/analytics.py::get_portfolio_risk` | `quantstats.stats.value_at_risk` | qs_stats.value_at_risk(_returns_series, confidence=0.95/0.99) | WIRED | Lines 546-547 confirmed |
| `api/routes/analytics.py::portfolio_risk` | `engine.analytics.PortfolioAnalytics.get_portfolio_risk` | Forwards entire returned dict | WIRED | Route passes dict through; cvar_95, cvar_99, portfolio_var now present in dict |
| `api/routes/calibration.py::get_calibration` | `tracking.tracker.SignalTracker.compute_brier_score` | Per-agent iteration at line 83 | WIRED | Pattern `compute_brier_score` confirmed |
| `api/routes/calibration.py::get_calibration` | `tracking.tracker.SignalTracker.compute_rolling_ic` | Per-agent iteration at line 84 | WIRED | Pattern `compute_rolling_ic` confirmed |
| `engine/weight_adapter.py::compute_ic_weights` | `tracking.tracker.SignalTracker.compute_icir` | IC-IR-based weight scaling at line 473 | WIRED | Pattern `compute_icir` confirmed |
| `tracking/store.py::get_backtest_signals_by_agent` | `backtest_signal_history` table | SELECT WHERE agent_name = ? | WIRED | Pattern `FROM backtest_signal_history` confirmed in _get_backtest_signals_by_agent |
| `backtesting/signal_corpus.py::populate_signal_corpus` | top-level `entry["raw_score"]` | agg_raw_score = entry.get("raw_score", 0.0) | WIRED | WR-01 fix confirmed at line 129 |
| `backtesting/walk_forward.py::run_walk_forward` | `Backtester.run` with backtest_mode=True | Delegation — no direct AgentInput construction | WIRED | FOUND-04 honored: walk_forward.py module docstring confirms delegation |

---

## Data-Flow Trace (Level 4)

All Phase 2 artifacts are computation/API modules, not UI rendering components. Data flow is verified through test suites rather than visual rendering paths. The critical flow is:

- `backtest_signal_history` <- `populate_signal_corpus` <- `Backtester.run` (with backtest_mode=True, FOUND-04)
- `backtest_signal_history.raw_score` is the top-level aggregated score (WR-01 fix confirmed at signal_corpus.py:129)
- `compute_rolling_ic` reads `r["raw_score"]` from rows (tracker.py:374) — confirmed AP-02 guard
- `compute_ic_weights` flows IC-IR into `max(0.0, icir/2.0)` weight factors — confirmed

All data flows are test-covered with substantive assertions (not just existence checks).

---

## Behavioral Spot-Checks

| Behavior | Check | Result | Status |
|----------|-------|--------|--------|
| matplotlib excluded from sys.modules on analytics import | `python -c "import sys; from engine import analytics; banned=[m for m in sys.modules if m.startswith('matplotlib') or m.startswith('seaborn')]; assert not banned; print('OK')"` | OK no plot imports | PASS |
| COST_PER_TRADE_EQUITY = 0.001 | `python -c "from backtesting.models import COST_PER_TRADE_EQUITY; assert COST_PER_TRADE_EQUITY == 0.001; print('OK')"` | OK | PASS |
| COST_PER_TRADE_CRYPTO = 0.0025 | `python -c "from backtesting.models import COST_PER_TRADE_CRYPTO; assert COST_PER_TRADE_CRYPTO == 0.0025; print('OK')"` | OK | PASS |
| generate_walk_forward_windows default purge_days=1 | inspect.signature output | purge_days: 1 | PASS |
| run_walk_forward default purge_days=5 | inspect.signature output | purge_days: 5 | PASS |
| walk_forward_windows in BacktestResult | `python -c "from backtesting.models import BacktestResult; ..."` | True | PASS |
| calibration_router registered under /analytics | `grep "calibration_router" api/app.py` | lines 119-120 confirmed | PASS |
| KNOWN_AGENTS == 6, FundamentalAgent in NULL_EXPECTED | `python -c "from api.routes.calibration import KNOWN_AGENTS, NULL_EXPECTED; ..."` | OK | PASS |
| max(0, icir/scale_divisor) in weight_adapter | grep pattern | max(0.0, icir / scale_divisor) found | PASS |
| quantstats>=0.0.81 in pyproject.toml | grep output | Line 23: "quantstats>=0.0.81" | PASS |

---

## Full Test Suite Results

```
tests/test_signal_quality_01_cvar.py            6/6  passed   (SC-1: CVaR historical simulation)
tests/test_signal_quality_06_portfolio_var.py   5/5  passed   (SC-1: portfolio VaR, HTTP end-to-end)
tests/test_signal_quality_02_brier.py           6/6  passed   (SC-2: Brier score)
tests/test_signal_quality_03_ic_icir.py         6/6  passed   (SC-2: IC/IC-IR)
tests/test_signal_quality_03b_weight_adapter_ic.py 7/7 passed (SC-2: weight adapter + calibration API)
tests/test_signal_quality_04_tx_costs.py        3/3  passed   (SC-3: transaction costs)
tests/test_signal_quality_05_walk_forward.py   10/10 passed   (SC-4: walk-forward windows)
tests/test_signal_quality_05b_signal_corpus.py  5/5  passed   (SC-4: signal corpus + WR-01 guard)
tests/test_041_risk_analytics.py               10/10 passed   (regression: existing risk analytics)
```

New signal-quality tests: 48 (6+5+6+6+7+3+10+5)

### Phase 1 Regression Tests

```
tests/test_foundation_01_yfinance_batch.py   — PASS
tests/test_foundation_04_backtest_mode.py    — PASS
tests/test_foundation_05_agent_renorm.py     — PASS
tests/test_001_db.py                         — PASS
tests/test_013_backtesting.py                — PASS
tests/test_014_daemon.py                     — PASS
tests/test_011_signal_tracker.py             — PASS
tests/test_020_weight_adapter.py             — PASS
Total: 70 passed, 0 failed
```

Phase 1 contracts confirmed intact: FOUND-04 (backtest_mode), FOUND-05 (renormalization), FOUND-07 (two-connection pattern), FOUND-02 (Parquet cache reuse via CachedProvider).

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SIG-01 | 02-01-PLAN.md | Portfolio-level CVaR/Expected Shortfall via QuantStats | SATISFIED | qs_stats.cvar at 95%/99% confidence in engine/analytics.py; cvar_95, cvar_99 in /analytics/risk response; matplotlib-safe via pre-stub pattern |
| SIG-02 | 02-03-PLAN.md | Brier score per-agent for confidence calibration | SATISFIED | compute_brier_score: one-vs-rest binary, HOLD excluded, None at N<20; returns from backtest_signal_history; /analytics/calibration endpoint surfaces brier_score per agent |
| SIG-03 | 02-03-PLAN.md | Rolling IC/IC-IR per agent; IC feeds weight adapter | SATISFIED | compute_rolling_ic: Pearson on raw_score, None at N<30; compute_icir: mean/std with guards; compute_ic_weights: max(0, ic_ir/2.0) zeroes negative IC; BadAgent weight < equal-weight baseline in test |
| SIG-04 | 02-02-PLAN.md | Transaction costs in backtester (cost_per_trade applied in P&L) | SATISFIED | COST_PER_TRADE_EQUITY=0.001, COST_PER_TRADE_CRYPTO=0.0025; cost applied at entry AND exit; total_costs_paid in BacktestResult.metrics; strict delta > 0.0001 verified in test |
| SIG-05 | 02-02-PLAN.md | Walk-forward scaffold producing per-window OOS Sharpe ratios | SATISFIED | generate_walk_forward_windows (purge_days=1) + run_walk_forward (purge_days=5); BacktestResult.walk_forward_windows populated; backtest_signal_history table with DDL; populate_signal_corpus + rebuild_signal_corpus daemon job |
| SIG-06 | 02-01-PLAN.md | Portfolio-level VaR with cross-position correlation awareness | SATISFIED | portfolio_var = var_95 (Tier 1: historical simulation on portfolio return series embeds all position correlations naturally); portfolio_var_method="historical_simulation" surfaced; documented Tier 2 covariance-matrix VaR deferred to v2 |

**Coverage: 6/6 requirements satisfied. No orphaned or unmapped requirements.**

---

## Anti-Patterns Found

All 4 REVIEW warnings (WR-01 through WR-04) were fixed post-review. No blocking anti-patterns remain.

| Finding | Fix Commit | Status |
|---------|-----------|--------|
| WR-01: raw_score=NULL data corruption in populate_signal_corpus | 28be823 | FIXED — `agg_raw_score = entry.get("raw_score", 0.0)` at signal_corpus.py:129; WR-01 regression test confirms COUNT(raw_score IS NULL) = 0 |
| WR-02: log_conn not in async with — potential connection leak | 238ccab | FIXED — two-connection pattern with `async with` blocks in rebuild_signal_corpus |
| WR-03: survivorship_bias_warning unconditionally True | 1ddfa6c | FIXED — now `n_tickers <= 3`; fires only on thin corpus |
| WR-04: asyncio.run() inside running event loop in sync tests | 0434260 | FIXED — affected tests in test_03b, test_04, test_06 converted to async def |

Info-level findings IN-01 through IN-05 are not blockers and were intentionally deferred (scope=critical_warning for fix run).

---

## Commit Verification

All commits documented in SUMMARY files confirmed in git log:

| Commit | Plan | Description |
|--------|------|-------------|
| 1fb365c | 02-01 T1 | feat(SIG-01,SIG-06): replace Gaussian CVaR with QuantStats historical simulation |
| 46a5d81 | 02-01 T2 | test(SIG-01): CVaR historical-simulation + matplotlib-leak regression tests |
| 3b7a16d | 02-01 T3 | feat(SIG-06,api): document /analytics/risk response fields; portfolio_var tests |
| 496566e | 02-02 T1 | feat(SIG-04): cost_per_trade applied at entry+exit; total_costs_paid in metrics |
| cc07528 | 02-02 T2+3 | feat(SIG-05): walk_forward scaffold + backtest_signal_history + signal_corpus |
| 362c44a | 02-03 T1 | feat(SIG-02,SIG-03): Brier + rolling IC + IC-IR in SignalTracker |
| 1560576 | 02-03 T2 | feat(SIG-03): WeightAdapter.compute_ic_weights applies IC-IR/2 scaling |
| 6ed5a45 | 02-03 T3 | feat(SIG-02,SIG-03,api): GET /analytics/calibration endpoint |
| 28be823 | WR-01 fix | fix(02): WR-01 use top-level raw_score in populate_signal_corpus |
| 238ccab | WR-02 fix | fix(02): WR-02 use async with for log_conn in rebuild_signal_corpus |
| 1ddfa6c | WR-03 fix | fix(02): WR-03 tie survivorship_bias_warning to actual ticker count |
| 0434260 | WR-04 fix | fix(02): WR-04 convert asyncio.run() sync tests to async def |

---

## Human Verification Required

None. All four success criteria are verifiable programmatically and have been verified. The BacktestPage.tsx consumption of walk_forward_windows is a data-structure contract (JSON key presence) that is verified by the test suite's key-existence assertions — no visual rendering verification is required for this infrastructure phase.

---

_Verified: 2026-04-21_
_Verifier: Claude (gsd-verifier)_
