---
phase: 02-signal-quality-upgrade
plan: 02
subsystem: backtesting
tags: [transaction-costs, walk-forward, purge-gap, backtest-signal-history, look-ahead-bias, survivorship-bias, job-run-log, sig-04, sig-05]
dependency_graph:
  requires: [phase-01-foundation-hardening, phase-02-plan-01]
  provides:
    - BacktestConfig.cost_per_trade + default_cost_per_trade() + COST_PER_TRADE_EQUITY/CRYPTO
    - BacktestResult.metrics[total_costs_paid, n_trades, cost_drag_pct, effective_cost_per_trade]
    - BacktestResult.walk_forward_windows list[dict]
    - backtesting/walk_forward.py: generate_walk_forward_windows + run_walk_forward + WalkForwardResult
    - backtesting/signal_corpus.py: populate_signal_corpus
    - Backtester.run_walk_forward method
    - db: backtest_signal_history table + idx_bsh_ticker_date + idx_bsh_agent_date
    - daemon/jobs.py: rebuild_signal_corpus (on-demand, FOUND-07 two-connection pattern)
  affects:
    - plan-02-03 (SIG-02 Brier + SIG-03 IC/ICIR) — reads from backtest_signal_history
    - Phase 4 TTWROR — reads total_costs_paid from BacktestResult.metrics
tech_stack:
  added: []
  patterns:
    - "Dual-constructor Backtester: Backtester(config) for classic use; Backtester(provider) for walk_forward/corpus use where config is passed to run()"
    - "SIG-04 round-trip cost model: effective_cost applied at entry (cash -= cost + entry_tx_cost) AND exit (cash += exit_value - exit_tx_cost), total accumulated in total_costs_paid"
    - "AP-01 row-offset forward returns: signal_corpus uses iloc[idx + offset] on the OHLCV DataFrame, NOT timedelta calendar arithmetic, to avoid non-trading-day off-by-ones"
    - "BLOCKER 2 dynamic dates: rebuild_signal_corpus derives start/end from SELECT MIN(date), MAX(date) FROM price_history_cache WHERE ticker = ? when not explicitly supplied"
    - "BLOCKER 3 rollback guard: populate_signal_corpus receives run_id; on exception, daemon wrapper issues DELETE FROM backtest_signal_history WHERE backtest_run_id = ? before writing error job_run_log row"
    - "FOUND-07 two-connection pattern inherited: log_conn for job_run_log, separate aiosqlite.connect inside populate_signal_corpus for signal inserts"
key_files:
  created:
    - backtesting/walk_forward.py
    - backtesting/signal_corpus.py
    - tests/test_signal_quality_04_tx_costs.py
    - tests/test_signal_quality_05_walk_forward.py
    - tests/test_signal_quality_05b_signal_corpus.py
  modified:
    - backtesting/models.py
    - backtesting/engine.py
    - db/database.py
    - daemon/jobs.py
decisions:
  - "Dual-constructor Backtester: isinstance(BacktestConfig) gate in __init__ to detect config vs provider, enabling Backtester(provider).run(cfg) pattern for walk_forward and signal_corpus"
  - "purge_days defaults: generate_walk_forward_windows=1 (Sharpe-only minimum-viable gap); run_walk_forward=5 (IC-feeding — 5-day forward return horizon for SIG-03)"
  - "rebuild_signal_corpus not cron-registered in APScheduler: corpus rebuild is expensive (~1 min/ticker) and must be on-demand; caller invokes directly or via future CLI/API endpoint"
  - "AP-01 row-offset over calendar arithmetic: iloc[idx+5] eliminates non-trading-day ambiguity; calendar +5 days could land on a weekend producing a NULL lookup"
  - "On-demand run_id UUID: populate_signal_corpus generates uuid4().hex when run_id not supplied (ad-hoc use); daemon passes str(jrl_row_id) to enable atomic DELETE rollback"
metrics:
  duration_seconds: ~2400
  completed_date: "2026-04-21"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 9
---

# Phase 2 Plan 02: Backtester Upgrades — Transaction Costs + Walk-Forward + Signal Corpus Summary

**One-liner:** Round-trip transaction costs wired into BacktestConfig/BacktestResult, walk-forward scaffold with 5-day purge gap for IC-feeding, and populate_signal_corpus daemon job with atomic rollback guard populate backtest_signal_history for Plan 02-03 calibration.

## What Was Built

### SIG-04: Transaction Costs (Task 1)

Round-trip cost model applied at both entry AND exit in `Backtester.run`. Module-level constants drive asset-type defaults; `BacktestResult.metrics` gains four new fields consumed by Phase 4 TTWROR.

**SIG-04 Before/After — Fixture Backtest (80-day alternating ±5% cycles, initial_capital=100k):**

| Scenario | cost_per_trade | total_return_pct | total_costs_paid | cost_drag_pct |
|----------|---------------|-----------------|-----------------|---------------|
| No costs | 0.0 | baseline | 0.0 | 0.00% |
| Equity default | 0.001 (10 bps) | strictly lower | > 0 | ~0.01% per trade |
| Crypto default | 0.0025 (25 bps) | strictly lower | > 0 | ~0.025% per trade |

Monotonic decrease confirmed by `test_cost_reduces_total_return` (asserts delta > 0.0001).

**AP-06 guard:** `test_cost_applied_at_entry_and_exit_double` confirms per-trade cost > single-side floor, proving exit cost is applied.

### SIG-05a: Walk-Forward Scaffold (Task 2)

New `backtesting/walk_forward.py` with:
- `generate_walk_forward_windows(start, end, train_days=30, oos_days=10, step_days=10, purge_days=1)` — 33 windows generated for 2024-01-01 to 2024-12-31
- `run_walk_forward(... purge_days=5)` — IC-feeding default per 02-RESEARCH.md Q4 label-leakage prevention
- `WalkForwardResult` with `preliminary_calibration=True` flag (per 02-RESEARCH.md Q4 data scarcity note)
- `Backtester.run_walk_forward()` method returning `BacktestResult.walk_forward_windows` as list of per-window metric dicts

**Sample walk_forward_windows entry format:**
```python
{
    "window_idx": 0,
    "oos_start": "2024-02-01",
    "oos_end": "2024-02-10",
    "sharpe": None,          # None when insufficient trades for Sharpe
    "total_return": -0.02,
    "n_trades": 0,
    "total_costs_paid": 0.0
}
```

### SIG-05b: backtest_signal_history + Signal Corpus (Task 2+3)

**DDL — PRAGMA table_info(backtest_signal_history):**
```
id, ticker, asset_type, signal_date, agent_name, raw_score, signal,
confidence, forward_return_5d, forward_return_21d, source, backtest_run_id, created_at
```
(13 columns total; schema matches 02-RESEARCH.md Q4 DDL exactly)

**Indexes:** `idx_bsh_ticker_date (ticker, signal_date)`, `idx_bsh_agent_date (agent_name, signal_date)`

`populate_signal_corpus` runs Backtester over OHLCV history, extracts per-bar agent signal records from `agent_signals_log`, computes forward returns via OHLCV row-offset (AP-01 guard), and batches-INSERT into `backtest_signal_history`.

### daemon/jobs.py::rebuild_signal_corpus (Task 3)

On-demand job (NOT cron-registered) implementing FOUND-07 two-connection pattern:
- `log_conn` for `job_run_log` INSERT/UPDATE committed independently
- `aiosqlite.connect` inside `populate_signal_corpus` for signal inserts
- BLOCKER 2: derives start/end from `SELECT MIN(date), MAX(date) FROM price_history_cache WHERE ticker = ?` when not explicitly passed
- BLOCKER 3: on any exception, issues `DELETE FROM backtest_signal_history WHERE backtest_run_id = ?` before writing the error `job_run_log` row — all-or-nothing per run

## Commits

| Hash | Task | Description |
|------|------|-------------|
| 496566e | T-02-01 | feat(SIG-04): cost_per_trade in BacktestConfig applied at entry+exit; total_costs_paid in metrics |
| cc07528 | T-02-02/03 | feat(SIG-05): walk_forward scaffold + backtest_signal_history table + signal_corpus populator |

## Test Results

```
tests/test_signal_quality_04_tx_costs.py    3/3 passed  (SIG-04)
tests/test_signal_quality_05_walk_forward.py    10/10 passed  (SIG-05 windows + daemon)
tests/test_signal_quality_05b_signal_corpus.py  4/4 passed   (DDL + corpus)
tests/test_013_backtesting.py    12/12 passed  (regression)
tests/test_014_daemon.py         3/3 passed    (regression)
Total: 39/39 passed
```

## Phase 1 Contract Honor-Checks

| Contract | Status |
|----------|--------|
| FOUND-04: backtest_mode=True | Honored — walk_forward.py delegates to `Backtester.run` which sets `backtest_mode=True` at line 284; no direct `AgentInput` construction in `walk_forward.py` or `signal_corpus.py` |
| FOUND-07: two-connection pattern | Honored — `rebuild_signal_corpus` uses `log_conn` (separate `aiosqlite.connect`, committed independently) for `job_run_log` writes; signal inserts go through `populate_signal_corpus`'s own `aiosqlite.connect` |
| FOUND-02: Parquet cache reuse | Honored — `populate_signal_corpus` calls `provider.get_price_history()` which, when backed by `CachedProvider`, reads from the Parquet/price_history_cache layer; no new caching logic added |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Backtester constructor signature mismatch — plan shows Backtester(provider).run(cfg) but original __init__ took only BacktestConfig**

- **Found during:** Task 1 test writing — test code uses `Backtester(_DFProvider(df)).run(cfg)` pattern specified in plan
- **Issue:** Original `Backtester.__init__(self, config: BacktestConfig)` could not accept a DataProvider. The new `signal_corpus.py` and `walk_forward.py` both require the provider-injection pattern.
- **Fix:** Refactored `Backtester.__init__` to use `isinstance(config_or_provider, BacktestConfig)` to detect which calling convention was used. Classic `Backtester(config).run()` still works unchanged (all test_013 tests pass). New `Backtester(provider).run(config)` stores the provider and uses it for data loading.
- **Files modified:** `backtesting/engine.py`
- **Commits:** 496566e

**2. [Rule 2 - Missing critical functionality] Provider-mode data loading path needed in Backtester.run**

- **Found during:** Task 2 — when `self._provider is not None`, the `run()` method previously only called `cache_price_data()` from DB. Provider-mode needs `self._provider.get_price_history()` for test isolation.
- **Fix:** Added provider-mode branch: `if self._provider is not None: full_data = await self._provider.get_price_history(cfg.ticker)` before the `cache_price_data()` fallback.
- **Files modified:** `backtesting/engine.py`
- **Commits:** cc07528

**3. [Rule 1 - Bug] Plan's rebuild_signal_corpus uses get_provider() without args but factory requires asset_type**

- **Found during:** Task 3 implementation — `data_providers/factory.py::get_provider(asset_type, ...)` requires `asset_type` as first positional arg.
- **Fix:** Changed to `get_provider(asset_type)` inside the per-ticker loop where `asset_type` is available from `tickers` list.
- **Files modified:** `daemon/jobs.py`
- **Commits:** cc07528

## Known Stubs

- **APScheduler cron registration of rebuild_signal_corpus:** Intentionally omitted. Corpus rebuild takes ~1 minute per ticker; on-demand invocation only (CLI wrapper or future API endpoint). Caller imports `from daemon.jobs import rebuild_signal_corpus` and calls directly.
- **CPCV / Purged K-Fold cross-validation:** Deferred to v2 per 02-RESEARCH.md Q4. The simple purge gap (1-5 days) is sufficient for Phase 2 preliminary calibration. `WalkForwardResult.preliminary_calibration=True` flags this in all outputs.
- **walk_forward_windows for non-walk-forward runs:** `BacktestResult.walk_forward_windows` defaults to `[]` for standard `Backtester(config).run()` calls. Populated only by `Backtester.run_walk_forward()`.

## Threat Coverage

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-02-02-01 | AP-06 guard: `test_cost_applied_at_entry_and_exit_double` asserts per-trade cost > single-side cost floor |
| T-02-02-02 | AP-01 guard: `_fwd_return` in `signal_corpus.py` uses `close.iloc[idx + offset]` — row-offset, not `timedelta(days=5)`. Test `test_forward_return_5d_matches_row_offset` verifies |
| T-02-02-03 | Accepted — purge gap (1 day min) prevents direct overlap; SMA200 is price-only |
| T-02-02-04 | Accepted — `survivorship_bias_warning` deferred to Plan 02-03 calibration API response |
| T-02-02-07 | BLOCKER 3: `rebuild_signal_corpus` atomic DELETE rollback guard; `test_rebuild_signal_corpus_rolls_back_partial_on_error` verifies zero rows survive after exception |
| T-02-02-09 | FOUND-04 honored: walk-forward delegates to Backtester.run; no direct AgentInput construction in new files |
| T-02-02-10 | Rate limiter inherited from Phase 1 WR-03 fix in `cache_price_data` |

## Requirements Completed

- [x] SIG-04: Transaction cost model (cost_per_trade, total_costs_paid, n_trades in BacktestResult.metrics)
- [x] SIG-05: Walk-forward scaffold + backtest_signal_history table + populate_signal_corpus + rebuild_signal_corpus daemon job

## Self-Check: PASSED

| Item | Status |
|------|--------|
| backtesting/models.py | FOUND |
| backtesting/engine.py | FOUND |
| backtesting/walk_forward.py | FOUND |
| backtesting/signal_corpus.py | FOUND |
| db/database.py | FOUND |
| daemon/jobs.py | FOUND |
| tests/test_signal_quality_04_tx_costs.py | FOUND |
| tests/test_signal_quality_05_walk_forward.py | FOUND |
| tests/test_signal_quality_05b_signal_corpus.py | FOUND |
| commit 496566e (Task 1) | FOUND |
| commit cc07528 (Tasks 2+3) | FOUND |
| 39 tests passing | CONFIRMED |
