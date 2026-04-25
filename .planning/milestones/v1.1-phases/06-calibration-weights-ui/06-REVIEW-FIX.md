---
phase: 06-calibration-weights-ui
fixed_at: 2026-04-24T00:05:00Z
review_path: .planning/phases/06-calibration-weights-ui/06-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 6: Code Review Fix Report

**Fixed at:** 2026-04-24T00:05:00Z
**Source review:** .planning/phases/06-calibration-weights-ui/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2 (WR-01, WR-02 — Info findings IN-01/IN-02 excluded per fix_scope=critical_warning)
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: SummaryAgent accepted by KNOWN_AGENTS allowlist but has no seeded weight row

**Files modified:** `api/routes/weights.py`, `tests/test_live_03_weights_api.py`
**Commit:** `fe5d7b7`
**Applied fix:** Removed `"SummaryAgent"` from `KNOWN_AGENTS` in `api/routes/weights.py` with an
explanatory comment. `SummaryAgent` is a narrative generator, not a signal producer, so it has no
row in `DEFAULT_WEIGHTS` / `agent_weights`. Accepting it via `PATCH /weights/override` would UPSERT
a `weight=0.0` row that surfaces as a misleading "Active 0%" agent in `WeightsEditor`. The
`calibration.py` `KNOWN_AGENTS` list was intentionally left untouched (it returns null metrics
with an explanatory note, which is benign).

Added `test_summary_agent_rejected_from_weights_override` (Test 26) which PATCHes with
`agent="SummaryAgent"` and asserts 400 `UNKNOWN_AGENT`, and additionally verifies no row is
inserted into `agent_weights`. All 26 tests in `tests/test_live_03_weights_api.py` pass.

### WR-02: `setRebuilding(false)` deferred via setTimeout — not cancelled on component unmount

**Files modified:** `frontend/src/pages/CalibrationPage.tsx`, `frontend/src/pages/__tests__/CalibrationPage.test.tsx`
**Commit:** `f36b4c3`
**Applied fix:** Added `mountedRef = useRef(true)` and `rebuildTimeoutRef = useRef<number | null>(null)`
to `CalibrationPage`. A `useEffect` with empty deps sets `mountedRef.current = true` on mount and
in its cleanup function: sets `mountedRef.current = false` and calls `clearTimeout(rebuildTimeoutRef.current)`
if a timeout is pending. In `handleRebuildCorpus`, replaced bare `setTimeout` with
`rebuildTimeoutRef.current = window.setTimeout(...)` and added an early-return guard
`if (!mountedRef.current) return` inside the callback. This prevents both the network refetch and
state update from executing against an unmounted component.

Added `test` "does not call refetch or setRebuilding after unmount during pending rebuild (WR-02)"
which: renders with fake rebuild data, clicks the rebuild button (real timers), then switches to
`vi.useFakeTimers()`, unmounts the component, advances time 5s past the 3s delay, and asserts
`getCalibrationAnalytics` call count did not increase. All 9 tests in `CalibrationPage.test.tsx` pass.

---

_Fixed: 2026-04-24T00:05:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
