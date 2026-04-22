---
phase: 04-portfolio-ui-analytics-uplift
fixed_at: 2026-04-21T00:53:30Z
review_path: .planning/phases/04-portfolio-ui-analytics-uplift/04-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 4: Code Review Fix Report

**Fixed at:** 2026-04-21T00:53:30Z
**Source review:** .planning/phases/04-portfolio-ui-analytics-uplift/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4
- Fixed: 4
- Skipped: 0

## Fixed Issues

### WR-01: `target_weight` not selected in `load_portfolio` / `get_all_positions` queries

**Files modified:** `portfolio/manager.py`, `tests/test_ui_04_target_weight.py`
**Commit:** 7e8d67b
**Applied fix:** Added `ap.target_weight` as the 19th column (index 18) to both the `get_all_positions` SELECT (line 635) and the `load_portfolio` SELECT (line 767). `Position.from_db_row` already handled index 18 correctly with `if len(row) > 18` — the guard now evaluates True and `target_weight` is populated on every portfolio load. Added regression test `test_load_portfolio_returns_target_weight` that sets a target weight via `set_target_weight`, then asserts both `load_portfolio` and `get_all_positions` return the correct non-None value.

---

### WR-02: `validate_status_transition` called with hardcoded constants instead of actual row status

**Files modified:** `portfolio/manager.py`
**Commit:** 7fe1a9d
**Applied fix:** Extended the `close_position` SELECT to also return the `status` column (`SELECT ticker, asset_type, quantity, avg_cost, original_analysis_id, entry_date, status`). The FSM guard now reads `current_status = str(row[6])` from the fetched row and calls `validate_status_transition(current_status, PositionStatus.CLOSED.value)`. This makes the guard genuinely defensive: if a data inconsistency causes a non-'open' row to reach this code path, the transition validator will catch it rather than silently passing the hardcoded `open→closed` pair.

---

### WR-03: Cache key in `run_llm_synthesis` missing `asset_type`

**Files modified:** `engine/llm_synthesis.py`
**Commit:** 436c672
**Applied fix:** Added `aggregated.asset_type` as the second element of the `_cache_key` return tuple: `(aggregated.ticker, aggregated.asset_type, aggregated.final_signal.value, regime, bucket)`. Two tickers with the same symbol but different asset types (e.g., stock "ETH" vs crypto "ETH") will now produce distinct cache keys, preventing cross-asset synthesis collisions.

---

### WR-04: `AlertRulesPanel` silently swallows errors in `handleCreate`, `handleToggle`, `handleDelete`

**Files modified:** `frontend/src/components/monitoring/AlertRulesPanel.tsx`
**Commit:** d21dcb7
**Applied fix:** Replaced the three empty `catch { }` blocks with `catch (err) { window.alert(...) }` calls, consistent with the `TargetWeightBar` pattern used elsewhere in Phase 4. `handleCreate` alerts `"Failed to create rule: {err}"`, `handleToggle` alerts `"Failed to toggle rule: {err}"`, `handleDelete` alerts `"Failed to delete rule: {err}"`. The `finally` block in `handleCreate` (which resets `formLoading`) was preserved unchanged.

---

_Fixed: 2026-04-21T00:53:30Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
