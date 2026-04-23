---
phase: 04-portfolio-ui-analytics-uplift
reviewed: 2026-04-21T00:00:00Z
depth: standard
files_reviewed: 33
files_reviewed_list:
  - .env.example
  - api/routes/analytics.py
  - api/routes/portfolio.py
  - db/database.py
  - engine/aggregator.py
  - engine/analytics.py
  - engine/llm_synthesis.py
  - engine/pipeline.py
  - monitoring/checker.py
  - monitoring/monitor.py
  - portfolio/manager.py
  - portfolio/models.py
  - tests/test_ui_01_ttwror.py
  - tests/test_ui_02_benchmark_allowlist.py
  - tests/test_ui_03_alert_rules_daemon.py
  - tests/test_ui_04_target_weight.py
  - tests/test_ui_05_daily_pnl.py
  - tests/test_ui_06_position_status_fsm.py
  - tests/test_ui_07_llm_synthesis_flag.py
  - frontend/src/api/endpoints.ts
  - frontend/src/api/types.ts
  - frontend/src/components/monitoring/AlertRulesPanel.tsx
  - frontend/src/components/monitoring/__tests__/AlertRulesPanel.test.tsx
  - frontend/src/components/performance/BenchmarkSelector.tsx
  - frontend/src/components/performance/DailyPnlHeatmap.tsx
  - frontend/src/components/performance/TtwrorMetricCard.tsx
  - frontend/src/components/performance/__tests__/BenchmarkSelector.test.tsx
  - frontend/src/components/performance/__tests__/DailyPnlHeatmap.test.tsx
  - frontend/src/components/performance/__tests__/TtwrorMetricCard.test.tsx
  - frontend/src/components/portfolio/PositionsTable.tsx
  - frontend/src/components/portfolio/TargetWeightBar.tsx
  - frontend/src/components/portfolio/__tests__/TargetWeightBar.test.tsx
  - frontend/src/pages/PerformancePage.tsx
  - frontend/src/pages/PortfolioPage.tsx
  - frontend/src/pages/__tests__/PerformancePage.test.tsx
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-04-21
**Depth:** standard
**Files Reviewed:** 33
**Status:** issues_found

## Summary

Phase 4 lands the seven UI uplift stories (UI-01 through UI-07) covering TTWROR/IRR metrics, benchmark allowlist, alert-rules daemon wiring, target_weight column, daily P&L heatmap, PositionStatus FSM, and opt-in LLM synthesis. The implementation is well-structured and the critical safety checks (FOUND-04 backtest short-circuit, benchmark allowlist, FSM guard in close_position) are all correctly placed and covered by tests.

Four warnings and three informational findings are raised. No critical security vulnerabilities were found. The most important warning is a gap in `load_portfolio` and related queries that do not yet SELECT the new `target_weight` column — meaning the column is correctly migrated but its value is never returned to the frontend via the main portfolio load path.

## Warnings

### WR-01: `target_weight` not selected in `load_portfolio` / `get_all_positions` queries

**File:** `portfolio/manager.py:741-772` (load_portfolio), `611-644` (get_all_positions)

**Issue:** `_ensure_column` correctly adds the `target_weight` column at startup (db/database.py:643), and `Position.from_db_row` handles it at index 18 (portfolio/models.py:124-125). However, neither `load_portfolio` nor `get_all_positions` SELECT that column. Both queries end at `ap.realized_pnl` (18 columns, index 17) — so `len(row) > 18` is always False and `pos.target_weight` is always `None` even after a successful PATCH.

The only path that correctly returns `target_weight` would require the SELECT to include `ap.target_weight` as a 19th column. The `set_target_weight` method writes correctly, but the portfolio GET response never reflects it.

**Fix:** Add `ap.target_weight` to the SELECT in both `load_portfolio` (line 750) and `get_all_positions` (line 618) queries:

```python
# In load_portfolio and get_all_positions, extend SELECT to:
SELECT
    ap.ticker,
    ap.asset_type,
    ap.quantity,
    ap.avg_cost,
    ap.sector,
    ap.industry,
    ap.entry_date,
    ap.original_analysis_id,
    ap.expected_return_pct,
    ap.expected_hold_days,
    pt.thesis_text,
    pt.expected_target_price,
    pt.expected_stop_loss,
    ap.status,
    ap.exit_price,
    ap.exit_date,
    ap.exit_reason,
    ap.realized_pnl,
    ap.target_weight       -- ← add this (index 18)
FROM active_positions ap
LEFT JOIN positions_thesis pt ON ap.original_analysis_id = pt.id
```

The same omission exists in `get_closed_positions` (line 252) and `get_position` (line 322) but those paths do not need `target_weight` for the current UI feature.

---

### WR-02: `validate_status_transition` is called with hardcoded string literals, bypassing the enum

**File:** `portfolio/manager.py:165`

**Issue:** The call is `validate_status_transition(PositionStatus.OPEN.value, PositionStatus.CLOSED.value)` — both arguments are resolved to string literals `"open"` and `"closed"` at call time. This is correct and safe _for the current two-state FSM_, but it also means the FSM guard is fully exercised and meaningful only while the SELECT filter `WHERE ticker = ? AND status = 'open'` (line 155) is in effect. If that filter is ever removed or the query returns a closed row, `validate_status_transition` would raise on the hardcoded pair `("open", "closed")` — which is the _valid_ transition — not on the actual current status.

More concretely: the guard does not read the `current_status` from `row["status"]`; it always validates `open→closed`. This means that if a data inconsistency placed a non-'open' row through the filter (e.g., via direct DB write), the guard would still pass (because `open→closed` is valid) rather than catching the real invalid transition. The guard is therefore redundant rather than defensive.

**Fix:** Read the actual current status from the row and validate against it:

```python
current_status = str(row[_STATUS_COL_INDEX])  # or row["status"] with row_factory
validate_status_transition(current_status, PositionStatus.CLOSED.value)
```

This makes the FSM guard genuinely defensive against data inconsistency, not just documentation.

---

### WR-03: Cache key in `run_llm_synthesis` does not include `asset_type`, risking cross-asset cache collisions

**File:** `engine/llm_synthesis.py:99-102`

**Issue:** `_cache_key` returns `(ticker, final_signal.value, regime, confidence_bucket)`. Two assets with the same ticker symbol but different asset types (e.g., a stock "ETH" and crypto "ETH-USD" both normalised to "ETH" at the aggregator level) would share the same cache key and one synthesis could be served for the other's context. While rare in practice with the current ticker normalisation, it violates the invariant that the cache key should uniquely identify the synthesis context.

```python
def _cache_key(aggregated: AggregatedSignal) -> tuple:
    regime = aggregated.regime.value if aggregated.regime else "NEUTRAL"
    bucket = int(round(aggregated.final_confidence / 10.0) * 10)
    return (aggregated.ticker, aggregated.final_signal.value, regime, bucket)
    # ↑ missing aggregated.asset_type
```

**Fix:**

```python
def _cache_key(aggregated: AggregatedSignal) -> tuple:
    regime = aggregated.regime.value if aggregated.regime else "NEUTRAL"
    bucket = int(round(aggregated.final_confidence / 10.0) * 10)
    return (aggregated.ticker, aggregated.asset_type, aggregated.final_signal.value, regime, bucket)
```

---

### WR-04: `AlertRulesPanel` silently swallows `handleCreate` errors — user gets no feedback

**File:** `frontend/src/components/monitoring/AlertRulesPanel.tsx:72-86`

**Issue:** The `handleCreate` form submission wraps `createAlertRule` in a `try/catch` that does nothing in the `catch` branch (comment "silently handle — user can retry"). The form loading spinner resets and the form disappears with no toast/error message. If the backend rejects the rule (e.g., a duplicate name, 422 from Pydantic), the user has no indication the create failed. The same silent swallow applies to `handleToggle` (line 91-95) and `handleDelete` (line 98-104), though those are lower-risk.

**Fix:** Surface the error with at minimum a `window.alert` (consistent with the `TargetWeightBar` pattern already used in this phase), or better, a toast notification:

```typescript
async function handleCreate(e: React.FormEvent) {
  e.preventDefault();
  if (!name.trim() || !threshold) return;
  setFormLoading(true);
  try {
    await createAlertRule({ name: name.trim(), metric, condition, threshold: Number(threshold), severity });
    resetForm();
    setShowForm(false);
    refetch();
  } catch (e) {
    window.alert(`Failed to create rule: ${String(e)}`);
  } finally {
    setFormLoading(false);
  }
}
```

## Info

### IN-01: `get_daily_pnl_heatmap` does not protect against `val` being non-numeric after `float()` conversion

**File:** `engine/analytics.py:1017-1024`

**Issue:** The inner loop does `float(val)` without a guard for non-finite results (`NaN`, `Inf`). SQLite REAL columns can store `NULL` (handled by `if ts is None or val is None: continue`) but an upstream bug could write a Python `float('nan')` to `total_value`. If that happened, `by_day[date_str] = float('nan')` would silently propagate NaN into the pnl result (`curr_val - prev_val = NaN`) and the frontend would receive `{"pnl": null}` after JSON serialisation — which the heatmap handles as a neutral cell. This is not currently reachable but is worth a `math.isfinite` guard:

```python
val_f = float(val)
if not math.isfinite(val_f):
    continue
by_day[date_str] = val_f
```

---

### IN-02: `PortfolioPage.tsx` imports `setTargetWeight` but `onPositionUpdated` callback may be absent

**File:** `frontend/src/components/portfolio/PositionsTable.tsx:152`

**Issue:** `onPositionUpdated?.()` uses optional chaining, which is correct. However the `onPositionUpdated` prop is typed as `(() => void) | undefined` — callers that omit it get no data refresh after a successful target_weight PATCH. `PortfolioPage` passes `onPositionUpdated` (confirmed by the prop chain) but the `PositionsTable` is also used on the Position Detail page. If the prop is missing on any usage, the UI silently shows a stale target weight until the next manual refresh. This is not a bug in the current code but is a footgun for future callers.

**Fix:** Document in the JSDoc or PropTypes comment that `onPositionUpdated` is required if the target weight edit button is visible, or conditionally hide the edit button when `onPositionUpdated` is undefined.

---

### IN-03: `AlertRulesPanel.test.tsx` test coverage gap — Delete button hidden for built-in rules is not asserted

**File:** `frontend/src/components/monitoring/__tests__/AlertRulesPanel.test.tsx`

**Issue:** The test suite asserts that the "Built-in" badge appears and that toggling fires `toggleAlertRule`, but does not assert the key security invariant: the Delete button (`×`) must NOT appear for `metric === "hardcoded"` rows. Without this assertion, a regression that accidentally renders the delete button for built-in rules would go undetected.

**Fix:** Add a test:

```typescript
it("does not render delete button for built-in rules", async () => {
  render(<AlertRulesPanel />);
  await waitFor(() => screen.getByText("STOP_LOSS_HIT"));
  // The only delete button should be for the user-defined rule (id=3)
  const deleteButtons = screen.queryAllByRole("button", { name: /×/ });
  expect(deleteButtons).toHaveLength(1); // only the non-hardcoded rule
});
```

---

## Test Coverage Notes

- **FOUND-04 compliance** (llm_synthesis.py): Verified. `backtest_mode` check is the first statement in `run_llm_synthesis` (line 145-150), before `_is_enabled()`, before `AsyncAnthropic` check, before any `os.getenv`. `test_synthesis_skipped_in_backtest_mode` passes a mock client and asserts `create.call_count == 0`. The cache path cannot bypass backtest_mode because the cache is only populated _after_ the guard (lines 163-165 come after line 145 guard). FOUND-04 is correctly implemented.

- **Benchmark allowlist** (api/routes/analytics.py:88-98): Verified. `ticker.upper().strip()` normalisation happens before the `VALID_BENCHMARKS` check. All five valid tickers and all injection variants are covered by `test_ui_02_benchmark_allowlist.py`. HTTP 400 is correctly returned (not 500 or 200).

- **PositionStatus FSM** (portfolio/models.py:22-39): `VALID_TRANSITIONS` is a `dict[str, frozenset[str]]`. `open→open` and `closed→closed` both raise `ValueError`. `open→closed` and `closed→open` pass. All four are covered by `test_ui_06_position_status_fsm.py`. Note: `closed→open` being valid per the FSM design is intentional (re-entry); this is documented.

- **target_weight migration** (db/database.py:643): `_ensure_column` is idempotent — it checks PRAGMA before ALTER. No mass-update of existing rows. Pydantic `Field(ge=0.0, le=1.0)` correctly returns 422 on out-of-range values (covered by `test_patch_endpoint_clamps_out_of_range`).

- **Daemon wiring** (monitoring/monitor.py + checker.py): `_load_enabled_rules` returns `None` on `OperationalError` (backward compat) and a set from a seeded DB. `check_position` wraps each rule in `_enabled(name)` guard. Toggling STOP_LOSS_HIT off is covered by `test_load_enabled_rules_respects_disabled_flag`.

- **PII hygiene in LLM prompt**: `_build_prompt` omits dollar amounts, cost basis, thesis_text, portfolio_id. Confidence is bucketed to 10%. `test_prompt_excludes_pii` asserts `"$" not in prompt`, `"thesis" not in prompt.lower()`, `"72" not in prompt`, and `"70" in prompt`. Correctly implemented.

- **Frontend type safety**: `ReturnsResponse`, `DailyPnlPoint`, `BenchmarkSymbol` types match backend JSON (verified against `engine/analytics.py::get_ttwror_irr` and `get_daily_pnl_heatmap` return shapes). No `any` types introduced in Phase 4 additions. `BenchmarkSelector` uses hardcoded `BENCHMARK_OPTIONS` constant (no free-form input). No `@ts-ignore` or `@ts-expect-error` found in reviewed files.

- **Calendar heatmap accessibility**: `DailyPnlHeatmap.tsx` cells have `tabIndex={cell.date ? 0 : -1}`, `aria-label`, `role="img"`. Null P&L renders as `bg-gray-700/50` (neutral, not error).

## Clean Files

The following files had no issues found during standard-depth review:

- `.env.example` — correctly documents `ENABLE_LLM_SYNTHESIS=false` default and FOUND-04 note
- `engine/llm_synthesis.py` — FOUND-04 guard correctly placed first; PII exclusion correct; graceful degradation complete
- `monitoring/checker.py` — `_enabled()` guard wraps all 5 rule checks; backward-compat `None` default correct
- `monitoring/monitor.py` — `_load_enabled_rules` with `OperationalError` fallback is correct; passes `enabled_rule_types` to `check_position`
- `portfolio/models.py` — FSM, `VALID_TRANSITIONS`, `validate_status_transition` all correct; `from_db_row` index-18 `target_weight` extraction correct when column is selected
- `engine/analytics.py` — `VALID_BENCHMARKS` frozenset; `compute_ttwror`, `compute_irr_closed_form`, `compute_irr_multi` math correct; `get_ttwror_irr` aggregate and per-position logic correct; `get_daily_pnl_heatmap` last-of-day semantics correct
- `api/routes/analytics.py` — allowlist check before yfinance call; parametrised SQL throughout; no injection surface
- `api/routes/portfolio.py` — `SetTargetWeightBody` Pydantic model with `Field(ge=0.0, le=1.0)` correct; 404 on missing ticker; import organisation acceptable
- `db/database.py` — `_ensure_column` idempotent; `_seed_default_alert_rules` idempotent; `target_weight REAL` migration correct; `_migrate_ticker_unique_to_partial` safe
- `frontend/src/api/types.ts` — `ReturnsResponse`, `DailyPnlPoint`, `BenchmarkSymbol` match backend exactly
- `frontend/src/api/endpoints.ts` — `BENCHMARK_OPTIONS` hardcoded (no free-form input); `setTargetWeight`, `getReturns`, `getDailyPnl` correctly typed
- `frontend/src/components/performance/BenchmarkSelector.tsx` — uses `BENCHMARK_OPTIONS` from endpoints (hardcoded list); no free-form input possible
- `frontend/src/components/performance/TtwrorMetricCard.tsx` — null handling correct; `data-testid` selectors present; sparse-data guard correct
- `frontend/src/components/performance/DailyPnlHeatmap.tsx` — accessibility attributes present; null P&L renders as neutral; `getCellColor(null)` returns neutral class
- `frontend/src/components/portfolio/TargetWeightBar.tsx` — null guard returns null; deviation calculation correct; `data-testid` present
- All 7 Python test files (`test_ui_01` through `test_ui_07`) — async patterns correct (no `asyncio.run()` wrappers); fixtures use `tmp_path`; coverage targets the correct invariants; FOUND-04 test asserts `call_count == 0`; PII test asserts specific string exclusions

---

_Reviewed: 2026-04-21_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
