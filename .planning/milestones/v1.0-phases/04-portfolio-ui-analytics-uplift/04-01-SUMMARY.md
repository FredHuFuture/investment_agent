---
phase: 04-portfolio-ui-analytics-uplift
plan: "01"
subsystem: engine/analytics + api/routes/analytics
tags: [analytics, ttwror, irr, benchmark, allowlist, daily-pnl, ssrf-mitigation]
dependency_graph:
  requires: []
  provides:
    - compute_ttwror
    - compute_irr_closed_form
    - compute_irr_multi
    - VALID_BENCHMARKS
    - PortfolioAnalytics.get_ttwror_irr
    - PortfolioAnalytics.get_daily_pnl_heatmap
    - GET /analytics/returns
    - GET /analytics/daily-pnl
    - GET /analytics/benchmark (hardened with allowlist)
  affects:
    - api/routes/analytics.py (GET /analytics/benchmark now enforces allowlist)
    - engine/analytics.py (3 new pure functions + 2 new async methods + VALID_BENCHMARKS)
tech_stack:
  added: []
  patterns:
    - scipy.optimize.brentq for multi-cashflow IRR root-finding
    - Geometric linking of portfolio_snapshots.total_value for TTWROR
    - frozenset allowlist + uppercased strip for SSRF mitigation (T-04-03)
    - Last-of-day semantics for daily P&L (dict[date_str] = float, last write wins)
key_files:
  created:
    - tests/test_ui_01_ttwror.py
    - tests/test_ui_02_benchmark_allowlist.py
    - tests/test_ui_05_daily_pnl.py
  modified:
    - engine/analytics.py
    - api/routes/analytics.py
decisions:
  - TTWROR returns decimal (raw) from compute_ttwror(); get_ttwror_irr() multiplies by 100 for percentage display
  - Aggregate IRR uses closed-form (single-window start→end); multi-cashflow aggregate IRR deferred to UI-v2 per research Open Question #2
  - Per-position TTWROR computed only for closed positions (open positions lack current market price in portfolio_snapshots)
  - VALID_BENCHMARKS type-annotated as frozenset[str] following project strict-mode conventions
  - Daily P&L uses last-of-day semantics (dict keyed on YYYY-MM-DD, last timestamp wins)
metrics:
  duration_seconds: 2475
  completed: "2026-04-22"
  tasks_completed: 2
  files_modified: 5
---

# Phase 04 Plan 01: Backend Analytics (TTWROR + IRR + Benchmark Allowlist + Daily P&L) Summary

TTWROR/IRR backend math via geometric linking and scipy.optimize.brentq, benchmark SSRF protection via frozenset allowlist, and daily P&L heatmap data source — all three UI-01/02/05 backend contracts locked in.

## What Was Built

### Task 1 — TTWROR + IRR math (commit `697e2d7`)

**engine/analytics.py additions:**

- `VALID_BENCHMARKS: frozenset[str]` — allowlist of 5 approved benchmark tickers (SSRF mitigation T-04-03)
- `compute_ttwror(values: list[float]) -> float` — geometric sub-period linking; skips None/zero prev values safely
- `compute_irr_closed_form(cost_basis, final_value, hold_days) -> float | None` — closed-form `(final/cost)^(365/days) - 1`; returns None on degenerate inputs
- `compute_irr_multi(cash_flows) -> float | None` — scipy.optimize.brentq bracketed root-finder for multi-cashflow IRR in [-0.99, 10.0]
- `PortfolioAnalytics.get_ttwror_irr(days=365) -> dict` — aggregate + per-position breakdown from portfolio_snapshots

**tests/test_ui_01_ttwror.py:** 16 tests covering:
- Empty/single value → 0.0
- Simple uptrend (100→110 = +10%)
- Downtrend (100→50 = -50%)
- None/zero prev-value safe skip
- Closed-form IRR canonical examples (100→121/365d ≈ 21%, 100→121/730d ≈ 10%)
- Degenerate IRR inputs return None (zero cost, zero days, negative days)
- brentq 2-CF matches closed-form within 1e-4
- Integration: seeded DB with 3 snapshots yields positive aggregate.ttwror
- Empty DB yields ttwror=None, snapshot_count=0

### Task 2 — Daily P&L heatmap + allowlist enforcement (commit `bbbd31e`)

**engine/analytics.py addition:**

- `PortfolioAnalytics.get_daily_pnl_heatmap(days=365) -> list[dict]` — returns `[{date, pnl}]` using last-of-day snapshot semantics; empty list when <2 distinct days

**api/routes/analytics.py changes:**

- `/analytics/benchmark`: hardened with allowlist check — `ticker = benchmark.upper().strip(); if ticker not in VALID_BENCHMARKS: raise HTTPException(400, ...)`
- NEW `GET /analytics/returns` (UI-01): wraps `get_ttwror_irr()`
- NEW `GET /analytics/daily-pnl` (UI-05): wraps `get_daily_pnl_heatmap()`

**tests/test_ui_02_benchmark_allowlist.py:** 12 tests covering:
- frozenset constant integrity (exactly {"SPY","QQQ","TLT","GLD","BTC-USD"})
- Off-allowlist rejection: FOO, ../etc/passwd, SQL injection, MSFT, http://evil
- Lowercase normalization: spy → SPY (no 400)
- All 5 valid benchmarks parametrized pass without 400

**tests/test_ui_05_daily_pnl.py:** 9 tests covering:
- 3-day shape: 2 entries, correct ±values
- Single snapshot → []
- No snapshots → []
- Last-of-day semantics (09:00=100, 17:00=103 on same day → next day uses 103)
- Negative P&L day
- API /analytics/daily-pnl structure (empty and populated)
- API /analytics/returns structure (aggregate + positions keys)

## Test Count Delta

| Module | Before | After | Delta |
|--------|--------|-------|-------|
| test_ui_01_ttwror.py | 0 | 16 | +16 |
| test_ui_02_benchmark_allowlist.py | 0 | 12 | +12 |
| test_ui_05_daily_pnl.py | 0 | 9 | +9 |
| test_041_risk_analytics.py | 10 | 10 | 0 (all pass, no regression) |
| **Total new tests** | | | **+37** |

## Deviations from Plan

### Auto-noted: Type annotation on VALID_BENCHMARKS

The plan's success criterion grep `"VALID_BENCHMARKS\s*=\s*frozenset"` fails because the code uses the properly-typed `VALID_BENCHMARKS: frozenset[str] = frozenset(...)` following CLAUDE.md's "Type hints required" convention. The constant exists and is correct; the grep pattern was written without accounting for Python type annotations. Both `grep -q "VALID_BENCHMARKS"` checks on `engine/analytics.py` and `api/routes/analytics.py` pass.

### Auto-noted: API prefix is `/analytics/` not `/api/v1/analytics/`

The plan spec refers to `GET /api/v1/analytics/returns` but the FastAPI app mounts the analytics router at `/analytics` (confirmed in `api/app.py` line 105: `app.include_router(analytics_router, prefix="/analytics")`). Tests correctly use `/analytics/returns` and `/analytics/daily-pnl`. No route was changed — this is a plan documentation artifact.

### Per-position TTWROR for open positions returns None

Open positions have no current market price in `portfolio_snapshots` (the table stores aggregate portfolio value, not per-ticker prices). Per-position TTWROR/IRR is computed only for closed positions (entry → exit price). Open positions return `ttwror: null, irr: null` which the frontend should display as "--". This matches the plan's degenerate-input handling spec.

## Known Limitations

- **Dividends not tracked** (A1 per research): `active_positions` has no dividend column. IRR understates true return for dividend stocks. Documented in function docstrings.
- **Aggregate IRR is closed-form (single-window)**: Uses `compute_irr_closed_form(start_value, end_value, hold_days_of_window)` rather than multi-cashflow brentq across all position entry dates. Multi-cashflow aggregate IRR deferred to UI-v2 per research Open Question #2.
- **Per-position TTWROR for open positions**: Returns null (no current price in portfolio_snapshots). Future plan can wire live price fetch.

## Known Stubs

None — all endpoints return real computed data from portfolio_snapshots. No hardcoded/placeholder values in the response path.

## Threat Flags

None — T-04-03 (SSRF via benchmark ticker) is mitigated in this plan. No new network endpoints or trust boundaries introduced beyond what the plan specified.

## Self-Check: PASSED

- [x] `engine/analytics.py` contains `VALID_BENCHMARKS`, `compute_ttwror`, `compute_irr_closed_form`, `compute_irr_multi`, `get_ttwror_irr`, `get_daily_pnl_heatmap`
- [x] `api/routes/analytics.py` contains `VALID_BENCHMARKS` import, `HTTPException(status_code=400`, `@router.get("/returns")`, `@router.get("/daily-pnl")`
- [x] Commit `697e2d7` (Task 1) exists in git log
- [x] Commit `bbbd31e` (Task 2) exists in git log
- [x] 16 + 21 = 37 new tests pass; 31 regression tests pass
- [x] `GET /analytics/benchmark?benchmark=FOO` → HTTP 400 verified via direct httpx call
- [x] `GET /analytics/returns?days=365` → HTTP 200 verified via direct httpx call
