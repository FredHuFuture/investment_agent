---
phase: "07"
plan: "01"
subsystem: analytics-engine
tags: [dividend-irr, drift-detector, ic-ir, pipeline-wiring, agent-weights, apscheduler, sqlite]
dependency_graph:
  requires:
    - 06-01  # agent_weights table + load_weights_from_db helper
    - 02-03  # compute_rolling_ic / compute_icir in tracking/tracker.py
    - 01-02  # FOUND-07 two-connection pattern in daemon/jobs.py
  provides:
    - dividend-aware-irr      # compute_irr_multi extended for AN-01
    - drift-detector          # engine/drift_detector.py evaluate_drift()
    - pipeline-weights-wired  # live SignalAggregator reads agent_weights table
    - drift-log-api           # GET /drift/log endpoint
  affects:
    - 07-02  # LIVE-04 digest can now read drift_log for IC-IR movers section
    - 07-03  # frontend badge reads GET /drift/log
tech_stack:
  added: []
  patterns:
    - "FOUND-02 Parquet sibling cache (DividendCache mirrors ParquetOHLCVCache)"
    - "FOUND-06 idempotent DDL (drift_log CREATE TABLE IF NOT EXISTS)"
    - "FOUND-07 two-connection pattern in run_drift_detector"
    - "preliminary_threshold flag (mirrors Phase 2 preliminary_calibration)"
    - "NEVER-zero-all guard in _apply_drift_scale (renorm safety)"
    - "ON CONFLICT ... WHERE manual_override=0 UPSERT (Phase 6 pattern)"
key_files:
  created:
    - engine/drift_detector.py
    - data_providers/dividend_cache.py
    - api/routes/drift.py
    - tests/test_an01_dividend_irr.py
    - tests/test_an02_drift_detector.py
    - tests/test_an02_pipeline_wiring.py
    - tests/test_an02_drift_api.py
  modified:
    - engine/analytics.py
    - engine/pipeline.py
    - data_providers/yfinance_provider.py
    - db/database.py
    - daemon/jobs.py
    - daemon/scheduler.py
    - api/app.py
decisions:
  - "DividendCache uses 24h TTL Parquet file per ticker (data/cache/dividends/{ticker}.parquet) — not in-memory, survives process restarts"
  - "drift_detector uses deferred imports for tracking/tracker and aiosqlite to avoid circular dependencies"
  - "Pipeline wiring: load_weights_from_db called in else branch of analyze_ticker (default path), not in adaptive-weights branch which still reads legacy portfolio_meta"
  - "Never-zero-all guard: if total_new <= 0 for all asset_type agents, skip UPSERT and return None — weight_after=NULL in drift_log signals the abort"
  - "Alert model uses string severity ('CRITICAL'/'HIGH') not enum — matches monitoring/models.py Alert dataclass contract"
  - "evaluate_drift opens one aiosqlite connection for all agents per run; _apply_drift_scale opens its own connection for weight writes (isolation)"
metrics:
  duration_seconds: 615
  completed_date: "2026-04-25"
  tasks: 3
  files_created: 7
  files_modified: 7
  tests_added: 36
  tests_passing: 36
---

# Phase 7 Plan 01: AN-01 + AN-02 Backend Engine Summary

Dividend-aware IRR, per-agent IC-IR drift detection with auto weight-scaling, and the Phase 6-deferred pipeline wiring that connects the `agent_weights` table to live `SignalAggregator` construction.

## What Was Built

### T-01-01: AN-01 Dividend-Aware IRR

`compute_irr_multi` in `engine/analytics.py` gains two optional parameters: `dividends: list[tuple[datetime, float]] | None` and `entry_date: datetime | None`. When provided, dividends on or after `entry_date` are converted to day-offsets and appended as positive inflows before `brentq` root-finding. Empty/None list is identical to pre-AN-01 behavior.

`YFinanceProvider.get_dividends(ticker)` fetches `yf.Ticker.dividends` (split-adjusted) inside `_yfinance_lock` and `_limiter`, returning `list[tuple[date, float]]` sorted ascending.

`data_providers/dividend_cache.py` — new `DividendCache` class mirroring `ParquetOHLCVCache` (FOUND-02): stores per-ticker dividend series as `{ex_date, amount}` Parquet at `data/cache/dividends/{ticker}.parquet` with 24-hour TTL and atomic-rename writes (Windows-safe delete-then-rename with 3 retries).

### T-01-02: AN-02 Drift Detector + Pipeline Wiring

`engine/drift_detector.py` — new module. `evaluate_drift(db_path)` iterates over `KNOWN_AGENTS × asset_types`, calls `tracker.compute_rolling_ic()` + `compute_icir()`, determines `preliminary_threshold` (True when valid IC count < 60), computes 60-day avg from `drift_log` history, evaluates drop-pct and absolute-floor thresholds, calls `_apply_drift_scale()` when triggered (not preliminary), writes to `drift_log`.

`_apply_drift_scale()` scales the target agent's weight by `max(0, ic_ir / 2.0)`, renormalizes all non-excluded agents for the asset_type to sum=1.0, UPSERTs via `ON CONFLICT ... WHERE manual_override=0` (preserves user overrides). NEVER-zero-all guard: if `total_new <= 0`, the write is aborted and `None` is returned.

`engine/pipeline.py` — Phase 6 deferral closed: `analyze_ticker` default code path now calls `await load_weights_from_db(self._db_path)` and passes `weights=db_weights` to `SignalAggregator`. When DB table is empty, `load_weights_from_db` returns `None` and `SignalAggregator` falls back to `DEFAULT_WEIGHTS`.

### T-01-03: drift_log Table + GET /drift/log + Sunday 17:30 Cron

`db/database.py` — `drift_log` table with 12 columns (id, agent_name, asset_type, evaluated_at, current_icir, avg_icir_60d, delta_pct, threshold_type CHECK, triggered, preliminary_threshold, weight_before, weight_after, created_at) + composite index on `(agent_name, asset_type, evaluated_at DESC)`. DDL uses `CREATE TABLE IF NOT EXISTS` (FOUND-06).

`api/routes/drift.py` — `GET /drift/log?days=7&limit=200` returns `{drifts: [...]}` with all fields. `triggered`/`preliminary_threshold` coerced from SQLite INTEGER to Python `bool`. Gracefully returns `{drifts: []}` if table is missing (pre-init_db).

`daemon/jobs.py::run_drift_detector` — FOUND-07 two-connection pattern around `_begin_job_run_log`/`_end_job_run_log`. Calls `evaluate_drift`, dispatches notifications via `AlertStore.save_alert` (CRITICAL for never-zero-all aborts, HIGH for normal drift triggers, INFO-level log for preliminary).

`daemon/scheduler.py` — Sunday 17:30 US/Eastern `CronTrigger` with `misfire_grace_time=3600`. Import of `run_drift_detector` added to scheduler imports.

## Decisions Made

1. **DividendCache uses Parquet files** — survives process restarts, consistent with ParquetOHLCVCache pattern; 24h TTL is generous for quarterly-changing data.
2. **evaluate_drift per asset_type** — CryptoAgent handles btc/eth; stock agents handle stock. No cross-asset contamination.
3. **Never-zero-all guard at renorm level** — checks `total_new <= 0` after computing scaled weights for all agents in the asset_type, not just the target agent. This catches the single-agent edge case correctly.
4. **Alert model uses string literals** — `monitoring/models.py::Alert` uses `str` for `alert_type` and `severity`, not enums. Strings `'SIGNAL_REVERSAL'`, `'CRITICAL'`, `'HIGH'` match existing monitor.py conventions.
5. **Pipeline wiring in else-branch only** — the `_use_adaptive_weights=True` branch (reads from legacy `portfolio_meta`) is left intact for backward compatibility. Only the default production path gets `load_weights_from_db`.

## Test Coverage

36 new tests across 4 files:
- `test_an01_dividend_irr.py` (13): strict-inequality MSFT/KO, backward-compat, pre-entry filter, on-entry-date inclusion, dense-stream brentq convergence, DividendCache round-trip/TTL/invalidate
- `test_an02_drift_detector.py` (14): DDL idempotency, index existence, preliminary flag, MIN_SAMPLES constant, triggered pct-drop, triggered absolute-floor, weight scale UPSERT, manual_override preservation, never-zero-all (single agent), never-zero-all (multi-agent), evaluate_drift writes drift_log
- `test_an02_pipeline_wiring.py` (3): pipeline uses DB weights not DEFAULT_WEIGHTS, falls back to defaults when DB empty, load_weights_from_db callable
- `test_an02_drift_api.py` (9): empty table, response shape (11 fields), day filter (in/out window), wide window, limit param, default params, invalid days (422), invalid limit (422), bool coercion

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Alert model uses string literals not enums**
- **Found during:** T-01-02 notification dispatch code
- **Issue:** Plan referenced `AlertSeverity.CRITICAL`, `AlertType.THESIS_DRIFT` but `monitoring/models.py::Alert` uses plain `str` fields, no enum classes exist
- **Fix:** Used string literals `'CRITICAL'`, `'HIGH'`, `'SIGNAL_REVERSAL'` and added `recommended_action` required field
- **Files modified:** daemon/jobs.py (run_drift_detector notification block)
- **Commit:** db298b2

**2. [Rule 1 - Bug] compute_irr_multi type annotation uses `datetime` for both date and datetime inputs**
- **Found during:** T-01-01 implementation review
- **Issue:** Research spec used `date` type for dividends but `datetime` is more common from yfinance; added normalization via `isinstance(entry_date, datetime)` `.date()` call so both work
- **Fix:** Added dual-type normalization in `compute_irr_multi` — `div_d = div_date.date() if isinstance(div_date, datetime) else div_date`
- **Files modified:** engine/analytics.py
- **Commit:** d70b70f

## Known Stubs

None. All data flows are wired: `compute_irr_multi` correctly augments cash flows, `evaluate_drift` reads real IC data (or returns preliminary=True on empty corpus), pipeline reads real DB weights (or falls back to DEFAULT_WEIGHTS), drift_log endpoint queries real table.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: new_endpoint | api/routes/drift.py | GET /drift/log exposes agent IC-IR values and weight history; no auth (solo-operator, localhost-only per DATA-04) |

No additional threat surface beyond what the plan's threat model anticipated (solo-operator, localhost-only deployment with no auth).

## Self-Check

- [x] `engine/analytics.py` — `dividends:` in `compute_irr_multi` signature
- [x] `data_providers/dividend_cache.py` — `data/cache/dividends` path
- [x] `engine/pipeline.py` — `load_weights_from_db` call
- [x] `engine/drift_detector.py` — `preliminary_threshold` + `MIN_SAMPLES_FOR_REAL_THRESHOLD`
- [x] `db/database.py` — `CREATE TABLE IF NOT EXISTS drift_log`
- [x] `api/routes/drift.py` — `/log` endpoint + `router` export
- [x] `api/app.py` — `drift_router` registered
- [x] `daemon/scheduler.py` — `day_of_week="sun"`, `hour=17`, `minute=30`
- [x] `daemon/jobs.py` — `async def run_drift_detector`
- [x] 36 new tests: 36 passed, 0 failed
- [x] 66 regression tests: 66 passed, 0 failed

## Self-Check: PASSED
