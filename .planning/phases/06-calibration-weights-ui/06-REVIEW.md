---
phase: 06-calibration-weights-ui
reviewed: 2026-04-23T00:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - api/models.py
  - api/routes/calibration.py
  - api/routes/weights.py
  - db/database.py
  - engine/aggregator.py
  - frontend/src/App.tsx
  - frontend/src/api/endpoints.ts
  - frontend/src/api/types.ts
  - frontend/src/components/calibration/AgentCalibrationRow.tsx
  - frontend/src/components/calibration/AssetTypeTabs.tsx
  - frontend/src/components/calibration/CalibrationTable.tsx
  - frontend/src/components/calibration/ICSparkline.tsx
  - frontend/src/components/calibration/WeightsEditor.tsx
  - frontend/src/pages/CalibrationPage.tsx
  - frontend/src/pages/WeightsPage.tsx
  - frontend/src/components/layout/Sidebar.tsx
  - tests/test_live_03_weights_api.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-04-23T00:00:00Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Phase 6 lands the `agent_weights` table (LIVE-03), three new weight endpoints, the
`CalibrationPage` with five calibration components, and a `WeightsPage` redirect. The
overall implementation is sound: the UPSERT manual_override guard is correctly implemented
(SQLite's `excluded` alias on line 272 does reference the proposed insert row, not the
persisted row), the FOUND-05 renormalization is correct in both `load_weights_from_db` and
`_read_current_weights`, and the empty-corpus graceful degradation path works as specified.

Two warnings and two info findings are identified. Neither warning is a blocker, but WR-01
(SummaryAgent in KNOWN_AGENTS without a seeded weight) is a correctness hole that will
surface the first time an operator tries to exclude-then-reenable SummaryAgent via the UI.

---

## Warnings

### WR-01: SummaryAgent accepted by KNOWN_AGENTS allowlist but has no seeded weight row

**File:** `api/routes/weights.py:39-46`, `api/routes/calibration.py:39-47`
**Issue:**
`KNOWN_AGENTS` in both files includes `"SummaryAgent"`. The `PATCH /weights/override`
endpoint passes the allowlist check and executes an UPSERT that inserts a new row with
`weight=0.0` when no pre-existing row for `SummaryAgent` exists. `DEFAULT_WEIGHTS` in
`engine/aggregator.py` does not include `SummaryAgent` for any asset type, so the DB seed
in `init_db` never creates a `SummaryAgent` row.

The concrete failure path:
1. Operator PATCHes `SummaryAgent/stock excluded=True` — UPSERT inserts `(SummaryAgent, stock, 0.0, 1, 1, 'manual', ...)`. OK so far.
2. Operator PATCHes `SummaryAgent/stock excluded=False` — UPSERT updates `excluded=0, manual_override=1, weight` remains `0.0`.
3. `_read_current_weights` includes `SummaryAgent` in `raw[stock]` with `weight=0.0`.
4. Renormalization: `0.0 / sum(all_weights)` = `0.0` — SummaryAgent appears in `current` with weight `0.0` and in `renormalized_weights` returned from `OverrideResponse`.
5. The WeightsEditor shows SummaryAgent as "Active" with weight `0.00%`, which is misleading.

The underlying issue: `SummaryAgent` is a narrative generator, not a signal producer.
It does not appear in `DEFAULT_WEIGHTS` because it does not emit `BUY/HOLD/SELL` signals;
adding it to the KNOWN_AGENTS allowlist for the weights system is a category error.

**Fix (recommended — remove SummaryAgent from weight-system KNOWN_AGENTS):**
```python
# api/routes/weights.py
KNOWN_AGENTS = {
    "TechnicalAgent",
    "FundamentalAgent",
    "MacroAgent",
    "SentimentAgent",
    "CryptoAgent",
    # SummaryAgent omitted: it is a narrative generator, not a signal producer,
    # and has no row in DEFAULT_WEIGHTS / agent_weights.
}
```

The calibration.py list can keep `SummaryAgent` since it just produces null metrics
with a note — that is benign. Only the weight-system KNOWN_AGENTS needs the removal.

---

### WR-02: `setRebuilding(false)` deferred via setTimeout — not cancelled on component unmount

**File:** `frontend/src/pages/CalibrationPage.tsx:86-89`
**Issue:**
```tsx
setTimeout(() => {
  calApi.refetch();
  setRebuilding(false);
}, 3_000);
```
If the user navigates away from `/calibration` within 3 seconds of triggering a corpus
rebuild, the `setTimeout` callback fires against an unmounted component, calling
`setRebuilding(false)` on dead state. React 18 suppresses the "setState on unmounted
component" warning (it was removed in React 18), but the `calApi.refetch()` call will
still execute, performing a network request for a component that is no longer mounted
and whose result will be silently dropped.

This is a resource leak (a dangling network request), not a crash. However in strict
mode (development) the double-mount/unmount cycle will reproduce this predictably.

**Fix:**
```tsx
import { useEffect, useRef } from "react";

// Inside the component:
const mountedRef = useRef(true);
useEffect(() => {
  return () => { mountedRef.current = false; };
}, []);

// In handleRebuildCorpus:
const timeoutId = setTimeout(() => {
  if (mountedRef.current) {
    calApi.refetch();
    setRebuilding(false);
  }
}, 3_000);

// Optionally store timeoutId in a ref and clearTimeout in cleanup.
```

---

## Info

### IN-01: Sidebar shows both "Calibration" and "Weights" nav entries — "Weights" immediately redirects

**File:** `frontend/src/components/layout/Sidebar.tsx:211-214`
**Issue:**
The sidebar's Tools group contains both `{ to: "/calibration", label: "Calibration" }` and
`{ to: "/weights", label: "Weights" }`. Clicking "Weights" triggers a client-side redirect
via `WeightsPage → <Navigate to="/calibration" replace />`. This causes a visible route
flash and briefly highlights both nav entries. It also adds dead nav real estate that could
confuse users. The plan documents this as a design decision (legacy bookmarks preserved),
but the sidebar entry for /weights is actively misleading since the user sees it active for
a split second before the redirect.

**Fix (optional — acceptable deferral if /weights entry is intentional):**
Remove the `/weights` entry from the sidebar `navGroups` now that the redirect is in place,
or rename the entry to "Calibration" and keep a single entry pointing to `/calibration`.

---

### IN-02: Test 3 name says "8 rows" but count is derived dynamically — name will mislead after DEFAULT_WEIGHTS changes

**File:** `tests/test_live_03_weights_api.py:137`
**Issue:**
```python
async def test_seed_on_empty_db_has_8_rows(tmp_path: Path) -> None:
    """Test 3 (seed on empty): fresh DB has exactly 8 rows across 3 asset_types."""
```
The test itself correctly computes `expected_count = sum(len(v) for v in SignalAggregator.DEFAULT_WEIGHTS.values())`.
The hardcoded "8" in the function name and docstring is accurate today (4 stock + 2 btc + 2 eth),
but if an agent is added to `DEFAULT_WEIGHTS` in a future phase, the test will still pass
but the name will mislead maintainers.

**Fix:**
```python
async def test_seed_on_empty_db_matches_default_weights(tmp_path: Path) -> None:
    """Test 3 (seed on empty): fresh DB has exactly as many rows as DEFAULT_WEIGHTS defines."""
```

---

## Test Coverage Notes

- **LIVE-03 unit tests** (25 tests in `test_live_03_weights_api.py`): comprehensive coverage of DDL,
  seed idempotence, UPSERT, FOUND-05 renormalization, threat model (T-06-01-01 through T-06-01-05),
  and empty-corpus graceful degradation. All critical backend invariants are exercised.
- **Frontend component tests**: new `__tests__/` files exist for all 5 calibration components
  (confirmed by git diff). Not read as part of this review (not in `files_to_read`) but their
  presence is confirmed.
- **Snapshot tests** (06-03): `TargetWeightBar`, `AlertRulesPanel`, `DailyPnlHeatmap` are locked.
- **Gap**: No test covers the PATCH of `SummaryAgent` specifically (WR-01 failure path).

---

## Clean Files

The following files reviewed are free of findings:

- `api/models.py` — Pydantic models are well-typed, all Phase 6 models present
- `api/routes/calibration.py` — `rolling_ic` addition is additive; FOUND-04 note pattern correct
- `db/database.py` — FOUND-06 seed-on-empty pattern verified correct; UNIQUE constraint DDL matches spec
- `engine/aggregator.py` — `load_weights_from_db` renormalization math correct; deferred aiosqlite import correct
- `frontend/src/App.tsx` — Routes correctly registered for `/calibration` and `/weights`
- `frontend/src/api/endpoints.ts` — All new endpoints correctly typed; legacy `getWeights` and `getCalibration` preserved
- `frontend/src/api/types.ts` — All new Phase 6 types correctly defined; `WeightsOverviewResponse.source` typed as union
- `frontend/src/components/calibration/AgentCalibrationRow.tsx` — FOUND-04 note branch correct; data-testid coverage complete
- `frontend/src/components/calibration/AssetTypeTabs.tsx` — Pure presentation component; ARIA roles correct
- `frontend/src/components/calibration/CalibrationTable.tsx` — Empty-corpus CTA correctly gated on `total_observations === 0`
- `frontend/src/components/calibration/ICSparkline.tsx` — Null IC values replaced with `0` for rendering (documented); no user-controlled strings rendered
- `frontend/src/components/calibration/WeightsEditor.tsx` — Apply button disabled on `suggested === null`; pending set prevents double-submit
- `frontend/src/pages/WeightsPage.tsx` — Clean redirect implementation

---

_Reviewed: 2026-04-23T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
