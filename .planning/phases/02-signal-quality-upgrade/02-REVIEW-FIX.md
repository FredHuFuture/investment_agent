---
phase: 02-signal-quality-upgrade
fixed_at: 2026-04-21T00:00:00Z
review_path: .planning/phases/02-signal-quality-upgrade/02-REVIEW.md
iteration: 1
fix_scope: critical_warning
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 02 Code Review Fix Report

**Fixed at:** 2026-04-21
**Source review:** `.planning/phases/02-signal-quality-upgrade/02-REVIEW.md`
**Iteration:** 1

## Summary

All 4 Warning findings fixed. WR-01 was the most critical — a silent data-corruption bug where every `raw_score` column in `backtest_signal_history` was `NULL`, making IC/IC-IR computation silently return `(None, [])` for the production corpus path while appearing to work. The fix reads the top-level aggregated `raw_score` from the backtester's `agent_signals_log` entry (one score per bar, shared across all agents for that bar), which is semantically sound: IC measures each agent's timing correlation with the consensus aggregate score. WR-02 through WR-04 were structural fragilities and compatibility bugs with no silent data impact.

All 5 Info findings (IN-01 through IN-05) were skipped per `fix_scope: critical_warning`.

Full test suite after fixes: **81 passed, 0 failures** (`pytest tests/test_signal_quality_*.py tests/test_041_risk_analytics.py tests/test_013_backtesting.py tests/test_014_daemon.py tests/test_001_db.py -q`).

---

## Fixed Issues

### WR-01: `populate_signal_corpus` silently reads `raw_score` from wrong dict level

**Files modified:** `backtesting/signal_corpus.py`, `tracking/tracker.py`, `tests/test_signal_quality_05b_signal_corpus.py`
**Commit:** `28be823`
**What changed:**
- `signal_corpus.py` lines 117-145: Added `agg_raw_score = entry.get("raw_score", 0.0)` before the inner loop and used `agg_raw_score` in the INSERT tuple instead of `agent_sig.get("raw_score")`. The per-agent sub-dicts from the backtester engine only carry `"agent"`, `"signal"`, and `"confidence"` — `"raw_score"` lives at the top-level entry. Every row previously stored `NULL`; now every row stores the aggregated bar-level float.
- `tracker.py` `compute_rolling_ic` docstring updated to document the semantic: `raw_score` in `backtest_signal_history` is the aggregated bar-level score, not a per-agent proprietary score, and IC therefore measures agent-timing-correlation with the aggregate signal.
**Tests added:** `test_populate_signal_corpus_stores_raw_score_not_null` in `tests/test_signal_quality_05b_signal_corpus.py` — asserts `SELECT COUNT(*) FROM backtest_signal_history WHERE raw_score IS NULL = 0` after `populate_signal_corpus` runs.

---

### WR-02: `rebuild_signal_corpus` log connection left open outside `async with`

**Files modified:** `daemon/jobs.py`
**Commit:** `238ccab`
**What changed:**
- Replaced `log_conn = await aiosqlite.connect(db_path)` (bare open, closed manually in `finally`) with `async with aiosqlite.connect(db_path) as log_conn:` for the `_begin_job_run_log` call — connection closes immediately after the begin-log commit, matching the `prune_signal_history` pattern.
- Both `_end_job_run_log` calls (success path and error path) now each open their own short-lived `async with aiosqlite.connect(db_path) as log_conn:` block, so no long-lived bare connection handle is kept across the job body.
- Removed the `finally: await log_conn.close()` block (no longer needed — context managers handle lifetime).

---

### WR-03: `survivorship_bias_warning` unconditionally `True`

**Files modified:** `tracking/store.py`
**Commit:** `1ddfa6c`
**What changed:**
- `get_backtest_corpus_metadata` now reads `n_tickers = (meta_row["n_tickers"] or 0) if meta_row else 0` (already computed by the existing `COUNT(DISTINCT ticker)` in the metadata query — no extra DB round-trip).
- `survivorship_bias_warning` is now `n_tickers <= 3` instead of hardcoded `True`. Warning fires when corpus covers 0 tickers (empty — no data is not safe), 1 ticker (single-stock survivorship bias risk), 2, or 3 tickers. With 4+ tickers the flag is `False`, giving API consumers an accurate signal about actual corpus breadth.

---

### WR-04: `asyncio.run()` inside sync tests conflicts with pytest-asyncio auto mode

**Files modified:** `tests/test_signal_quality_03b_weight_adapter_ic.py`, `tests/test_signal_quality_04_tx_costs.py`, `tests/test_signal_quality_06_portfolio_var.py`
**Commit:** `0434260`
**What changed:**
- `test_signal_quality_03b_weight_adapter_ic.py`: `test_calibration_endpoint_http_end_to_end` converted from `def` + `asyncio.run(_setup())` to `async def` with direct `await _seed_multi_agent_corpus(...)`. Removed local `import asyncio`.
- `test_signal_quality_04_tx_costs.py`: Both `test_cost_reduces_total_return` and `test_cost_applied_at_entry_and_exit_double` converted from `def` + `asyncio.run(...)` to `async def` with direct `await`. Top-level `import asyncio` removed (no longer used anywhere in the file).
- `test_signal_quality_06_portfolio_var.py`: Both `test_risk_endpoint_http_via_fastapi_testclient` (Test D) and `test_risk_endpoint_insufficient_data_returns_nulls` (Test E) converted from `def` + inner `async def _prepare()` + `asyncio.run(_prepare())` to flat `async def` with direct `await` calls. Removed local `import asyncio` from each.

---

## Skipped Issues

None — all 4 in-scope findings were fixed.

---

_Fixed: 2026-04-21_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
