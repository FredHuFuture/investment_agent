---
phase: 02-signal-quality-upgrade
reviewed: 2026-04-21T00:00:00Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - api/app.py
  - api/routes/analytics.py
  - api/routes/calibration.py
  - backtesting/engine.py
  - backtesting/models.py
  - backtesting/signal_corpus.py
  - backtesting/walk_forward.py
  - daemon/jobs.py
  - db/database.py
  - engine/analytics.py
  - engine/weight_adapter.py
  - pyproject.toml
  - tracking/store.py
  - tracking/tracker.py
  - tests/test_signal_quality_01_cvar.py
  - tests/test_signal_quality_02_brier.py
  - tests/test_signal_quality_03_ic_icir.py
  - tests/test_signal_quality_03b_weight_adapter_ic.py
  - tests/test_signal_quality_04_tx_costs.py
  - tests/test_signal_quality_05_walk_forward.py
  - tests/test_signal_quality_05b_signal_corpus.py
  - tests/test_signal_quality_06_portfolio_var.py
findings:
  critical: 0
  warning: 4
  info: 5
  total: 9
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-04-21
**Depth:** standard
**Files Reviewed:** 21
**Status:** issues_found

## Summary

Phase 2 lands SIG-01 through SIG-06 across 11 commits. The implementation is architecturally sound and well-documented. The matplotlib stub pattern is correct, the async test patterns have been properly migrated, the IC computation correctly uses `raw_score`, the weight adapter negative-IC edge case is handled, and the backtest_signal_history schema has appropriate indexes.

Four warnings were found — all logic-level bugs that could produce silent incorrect results under real data conditions. No critical (security/crash) issues were found. Five info items note missing safety wires and minor gaps in test coverage.

---

## Warnings

### WR-01: `populate_signal_corpus` silently reads `agent_sig.get("raw_score")` but the backtester's `agent_signals` list does NOT include `raw_score` per agent

**File:** `backtesting/signal_corpus.py:127-128`

**Issue:** `signal_corpus.py` iterates `entry["agent_signals"]` (line 122) and inserts `agent_sig.get("raw_score")` (line 129). But in `backtesting/engine.py:359-366`, the `agent_signals_log` entries store per-agent records with only three fields:
```python
{
    "agent": o.agent_name,
    "signal": o.signal.value,
    "confidence": o.confidence,
}
```
There is no `raw_score` per agent. The `raw_score` field in `agent_signals_log` is the **aggregated** raw_score, stored at the top-level `entry` (line 358), not inside each `agent_signals` sub-dict. Every row in `backtest_signal_history` will therefore have `raw_score = None`, making `compute_rolling_ic` always return `(None, [])` because the filter at `tracking/tracker.py:376` excludes rows where `raw_score is None`. The Brier score is unaffected (it uses `confidence` not `raw_score`), but IC/ICIR computation is silently broken for the production corpus path.

**Fix:** Either (a) include `raw_score` per agent in the engine's `agent_signals` sub-dict, or (b) store the aggregated `raw_score` from the top-level entry for all agents in that bar:
```python
# In signal_corpus.py, change the inner loop to:
agg_raw_score = entry.get("raw_score", 0.0)
for agent_sig in entry.get("agent_signals", []):
    rows_to_insert.append((
        ticker,
        asset_type,
        signal_date,
        agent_sig["agent"],          # key is "agent" not "agent_name"
        agg_raw_score,               # use aggregated raw_score
        agent_sig["signal"],
        agent_sig.get("confidence"),
        fr5,
        fr21,
        "backtest",
        run_id,
    ))
```
Note also the key name mismatch: engine uses `"agent"` (line 360) but corpus accesses `agent_sig["agent"]` (line 130) which is correct, but also retrieves `agent_sig.get("raw_score")` which doesn't exist in that dict.

---

### WR-02: `rebuild_signal_corpus` log connection left open on `_begin_job_run_log` success, not managed by context manager

**File:** `daemon/jobs.py:1047-1054`

**Issue:** `log_conn` is opened with a bare `await aiosqlite.connect(db_path)` (line 1047) outside any `async with` block. If `_begin_job_run_log` succeeds but then an exception is raised inside the `try` block before `finally: await log_conn.close()` is reached — specifically if the `except` block's cleanup itself raises — the connection may leak. More concretely: if `_end_job_run_log` raises inside the `except` branch (line 1131-1136), execution falls into the outer `except Exception` at line 1133, which swallows `log_end_exc`, and then `finally` always runs. The `finally` block is correct. However the pattern is fragile: `log_conn` is not a context manager here, so any early `return` added in future would leak the connection. The existing `finally` block saves this in the current code, but the code on lines 1050-1054 does `raise` after `await log_conn.close()`, meaning `log_conn` is closed before re-raising, which is correct — but only because the exception handling falls through to the `finally` which also closes it. This double-close is harmless in aiosqlite but indicates a structural fragility.

**Fix:** Wrap the connection management in `async with`:
```python
async with aiosqlite.connect(db_path) as log_conn:
    jrl_row_id = await _begin_job_run_log(log_conn, "rebuild_signal_corpus", started_at)
# After context exit, log_conn is closed; use a separate connection in finally for _end_job_run_log
```
This eliminates the bare `await log_conn.close()` calls and makes the lifetime explicit.

---

### WR-03: `survivorship_bias_warning` in corpus metadata is unconditionally `True` — does not reflect actual ticker count

**File:** `tracking/store.py:363`

**Issue:** The review scope (item 9) asked to verify whether `survivorship_bias_warning` is `True` only when corpus covers 1 ticker. The implementation sets it unconditionally to `True` with a comment `# AP-04: documented limitation`. This is a deliberate choice per AP-04, but the `calibration.py` docstring at line 7-10 implies the warning reflects data scarcity, and the `corpus_metadata` dict already contains `n_tickers` (via `COUNT(DISTINCT ticker)`). Setting the warning unconditionally means it will still be `True` even when 50 tickers are covered, misleading API consumers into thinking survivorship bias is always a concern regardless of corpus breadth. This is a logic/documentation mismatch rather than a crash, but it will cause incorrect frontend alerts.

**Fix:** Tie the warning to actual ticker count:
```python
n_tickers = meta_row["n_tickers"] if meta_row else 0
"survivorship_bias_warning": n_tickers <= 3,  # AP-04: warn when corpus < 4 tickers
```
Or, if the intent is always-true (academic disclaimer), document explicitly in the API response and the calibration endpoint why it is structural, not data-driven.

---

### WR-04: `test_calibration_endpoint_http_end_to_end` uses `asyncio.run()` inside a sync test — will conflict with pytest-asyncio auto mode on some platforms

**File:** `tests/test_signal_quality_03b_weight_adapter_ic.py:308-309`

**Issue:** `test_calibration_endpoint_http_end_to_end` (line 295) is a `def` (sync) test that calls `asyncio.run(_setup())` (line 308). This pattern is explicitly noted in `test_signal_quality_03_ic_icir.py:15-16` as having been replaced because "asyncio.run() fails under asyncio_mode=auto." The same situation applies here: on Python 3.12 with `asyncio_mode=auto`, calling `asyncio.run()` from within a running event loop — which pytest-asyncio's auto mode may establish at the session/module level — raises `RuntimeError: This event loop is already running`. The `test_cost_reduces_total_return` and `test_cost_applied_at_entry_and_exit_double` in `test_signal_quality_04_tx_costs.py` have the same pattern (lines 153-158, 202). The two tests in `test_signal_quality_06_portfolio_var.py` (lines 149, 193) also use `asyncio.run()` inside sync `def` tests. Whether this actually fails depends on the pytest-asyncio session scope configuration. With `asyncio_mode=auto`, it typically does not auto-wrap sync `def` tests, so `asyncio.run()` inside them works. However it is fragile and inconsistent with the fix applied in `test_signal_quality_03_ic_icir.py`.

**Fix:** Convert the affected sync tests to `async def`:
```python
async def test_calibration_endpoint_http_end_to_end(tmp_path: Path) -> None:
    db_file = tmp_path / "cal.db"
    await _seed_multi_agent_corpus(db_file, [...], n=120, seed=42)
    # ... rest of test
```
Or use `pytest.fixture` with a scope to share the seeded DB. Also convert the identical pattern in `test_signal_quality_04_tx_costs.py` and `test_signal_quality_06_portfolio_var.py`.

---

## Info

### IN-01: `backtest_signal_history` lacks a composite unique constraint on `(ticker, agent_name, signal_date)` — duplicate rows possible on re-run

**File:** `db/database.py:467-498`

**Issue:** The `backtest_signal_history` table has no UNIQUE constraint on `(ticker, agent_name, signal_date)`. The daemon's rollback guard (`DELETE WHERE backtest_run_id = ?`) removes rows from a failed run, but a successful re-run of `rebuild_signal_corpus` with the same date range will INSERT duplicate rows without violating any constraint. The `idx_bsh_ticker_date` and `idx_bsh_agent_date` indexes are non-unique. IC computation would then double-count observations, silently inflating the IC sample size and biasing estimates.

**Fix:** Add a unique index (or use `INSERT OR REPLACE`):
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_bsh_unique_signal
ON backtest_signal_history(ticker, agent_name, signal_date);
```
Or, before a full rebuild, truncate the ticker's rows first:
```sql
DELETE FROM backtest_signal_history WHERE ticker = ?;
```

---

### IN-02: `scipy` and `numpy` missing from `pyproject.toml` dependencies

**File:** `pyproject.toml:20-35`

**Issue:** `tracking/tracker.py` uses `from scipy.stats import pearsonr` (line 381) and all IC/ICIR tests use `import numpy as np`. Neither `scipy` nor `numpy` appear in `pyproject.toml`'s `dependencies` or any optional group. They are likely installed transitively (numpy via pandas, scipy possibly via quantstats), but this is not guaranteed. A fresh install in a constrained environment could fail at runtime when IC computation is first triggered.

**Fix:** Add explicit pinned bounds:
```toml
"numpy>=1.24",
"scipy>=1.10",
```

---

### IN-03: The matplotlib stub in `engine/analytics.py` does not stub `quantstats._plotting` submodules that may be imported by quantstats internals

**File:** `engine/analytics.py:22-24`

**Issue:** The stub pre-empts `quantstats.plots`, `quantstats.reports`, and `quantstats._plotting` (the top-level `_plotting` subpackage). However, if `quantstats.stats` internally imports `quantstats._plotting.core` or `quantstats._plotting.wrappers` as sub-submodules, those would not be stubbed. The test `test_matplotlib_not_imported_on_engine_analytics_import` (subprocess check) should catch this in CI, so it is regression-protected. The risk is that a quantstats upgrade adding a new `_plotting.*` submodule would be caught only when the test runs, not at import time. This is a minor fragility rather than a current bug.

**Fix (optional hardening):** Extend the stub to also intercept any `quantstats._plotting.*` child by using an import hook, or add `quantstats._plotting.core`, `quantstats._plotting.wrappers` to the stub list if those are known sub-paths.

---

### IN-04: `agent_sig["agent"]` key in `signal_corpus.py` vs `agent_sig["agent_name"]` in `store.py` — potential future key-name drift

**File:** `backtesting/signal_corpus.py:130`, `tracking/store.py:309`

**Issue:** The `agent_signals` sub-dicts written by the engine (line 360 of `engine.py`) use the key `"agent"`. The corpus insert at `signal_corpus.py:130` correctly reads `agent_sig["agent"]`. However, `tracking/store.py:204` (in `compute_agent_performance`) reads `agent_sig.get("agent_name", "Unknown")` from `signal_history.agent_signals_json` — a different table. These are two separate schemas and currently not confused. But there is no single canonical key name, increasing the maintenance surface. Related: `calibration.py:83` accesses `tracker.compute_brier_score(agent, ...)` using the string name from `KNOWN_AGENTS`, which is then used as the `agent_name` column filter in SQL — these correctly match because the backtester writes `agent_sig["agent"]` (which is `o.agent_name` from the AgentOutput) to the `agent_name` column.

**Fix (info only):** Consider a single constant or dataclass for the per-agent signal dict key to eliminate the dual schema.

---

### IN-05: Test `test_cvar_matches_quantstats_reference` (Test A) has a subtle comparison risk — the analytics engine re-computes daily returns from portfolio values while the test computes reference CVaR directly on the `returns` list

**File:** `tests/test_signal_quality_01_cvar.py:79-91`

**Issue:** The test seeds `portfolio_snapshots` from `returns` via `_seed_snapshots_from_returns`, then calls `get_portfolio_risk()` which re-derives `daily_returns` from the stored `total_value` sequence. The analytical engine computes returns as `(v[i] - v[i-1]) / v[i-1]`, but `_seed_snapshots_from_returns` constructs values as `v[i] = v[i-1] * (1 + r[i-1])`, so the recovered returns are `(v[i]/v[i-1]) - 1 = r[i-1]`. This is algebraically equivalent for small returns, but floating-point rounding through the intermediate portfolio value storage could introduce tiny differences. The test uses a tolerance of `< 0.01` (1 basis point), so this is not a current failure, but it is worth noting that the test is not a pure round-trip because of float storage.

**Fix (info only):** The existing tolerance of `0.01` is adequate. No code change needed.

---

## Test Coverage Notes

- **Matplotlib leak test (Test E, `test_signal_quality_01_cvar.py`)**: The subprocess approach is correct and robust — it catches leaks that in-process state would mask. The test correctly bans both `matplotlib` and `seaborn`.
- **Brier score tests**: All six cases (perfect, random, wrong, HOLD-excluded, insufficient data, integration) produce deterministic outcomes with known expected values. The confidence divisor (`/ 100.0`) is verified by the perfect predictor case: `confidence=95.0 / 100 = 0.95`, `(0.95 - 1)^2 = 0.0025`.
- **IC tests**: The synthetic corpus `_seed_synthetic_corpus` correctly uses a linear model `returns = ic * scores + sqrt(1-ic²) * noise`, which gives the exact Pearson coefficient for large N. The tolerance (`±0.08`) is correctly sized at ~1 standard error for N=100.
- **Walk-forward tests**: Window invariants (purge gap, step, no-extension-past-end) are thoroughly verified. The zero-window edge case is covered.
- **BLOCKER 3 rollback test**: The monkeypatch approach correctly inserts 5 rows then raises, and the assertion verifies `COUNT(*) WHERE backtest_run_id = <jrl_id> = 0`. The `run_id` alignment between `_begin_job_run_log` (which produces the `jrl_row_id`) and `run_id_for_corpus` (which is `str(jrl_row_id)`) is correctly threaded.
- **IC weights tests (Task 2)**: The `test_compute_ic_weights_zero_ic_agent_excluded` test (IN-4) is correctly formulated — it does not assert `weight == 0.0` for ZeroAgent but `PositiveAgent >= ZeroAgent`, acknowledging that true_ic=0 with finite N may yield a non-zero sample IC. This is appropriately conservative.

## Clean Files

The following files were reviewed and found clean with no issues:

- `api/app.py` — calibration router registration is correct (`prefix="/analytics"`, tag `"calibration"`).
- `api/routes/analytics.py` — no Phase 2 changes; existing code is clean.
- `backtesting/models.py` — `default_cost_per_trade`, constants, and `BacktestConfig.cost_per_trade=None` sentinel all correct.
- `backtesting/walk_forward.py` — purge gap invariant (`train_end + purge_days + 1`) is correct; `run_walk_forward` sets `backtest_mode=True` via delegation to `Backtester.run(cfg)` which internally uses `AgentInput(backtest_mode=True)` — FOUND-04 honored.
- `backtesting/engine.py` — `Backtester.run_walk_forward` correctly passes `purge_days=1` (Sharpe-only) to the module-level `run_walk_forward` which defaults to 5; the wrapper explicitly passes through the caller's value, so the inconsistency is user-controlled, not a hidden default conflict. FOUND-04 honored via `AgentInput(backtest_mode=True)` at line 326.
- `engine/weight_adapter.py` — `compute_ic_weights`: when all agents have `icir <= 0`, `factor=0.0` for all, `any_valid` stays `False`, returns `None` — caller falls back to EWMA. Edge case is handled correctly.
- `tracking/tracker.py` — `compute_rolling_ic` uses `r["raw_score"]` (line 374), confirming AP-02 guard. NaN guard `ic_val == ic_val` is correct Python idiom.
- `api/routes/calibration.py` — `ic_5d`/`ic_horizon` stable-key pattern (WARNING 11 fix) is correct. `FundamentalAgent` null-with-note (FOUND-04) is correctly implemented.
- `engine/analytics.py` — historical simulation VaR/CVaR via QuantStats is correct; sign convention (negate QuantStats negative losses to positive percentages) is correct; `portfolio_var` aliased to `var_95` (Tier 1 identity) is consistent with the amended ROADMAP.
- `db/database.py` — `backtest_signal_history` DDL is correct; `idx_bsh_ticker_date` and `idx_bsh_agent_date` indexes support Plan 02-03 query patterns. No PRIMARY KEY on `(ticker, agent, signal_date)` — see IN-01.

---

_Reviewed: 2026-04-21_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
