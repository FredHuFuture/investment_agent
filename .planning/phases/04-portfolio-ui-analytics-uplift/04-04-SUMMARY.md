---
phase: 04-portfolio-ui-analytics-uplift
plan: "04"
subsystem: frontend/src/components/portfolio + frontend/src/components/monitoring + frontend/src/api
tags: [frontend, target-weight, alert-rules, deviation-bar, built-in-badge, react, vitest, ui-03, ui-04]
dependency_graph:
  requires:
    - 04-02 (PATCH /portfolio/positions/{ticker}/target-weight, alert_rules seeded with metric=hardcoded)
  provides:
    - TargetWeightBar component (data-testid=target-weight-bar-{ticker})
    - setTargetWeight() PATCH endpoint client
    - target_weight field on Position interface
    - AlertRulesPanel Built-in badge (data-testid=alert-rule-builtin-badge-{id})
    - AlertRulesPanel toggle testid (data-testid=alert-rule-toggle-{id})
  affects:
    - frontend/src/api/types.ts (+1 field on Position)
    - frontend/src/api/endpoints.ts (+1 function setTargetWeight)
    - frontend/src/components/portfolio/PositionsTable.tsx (new Target Wt column)
    - frontend/src/pages/PortfolioPage.tsx (totalValue + onPositionUpdated wired)
    - frontend/src/components/monitoring/AlertRulesPanel.tsx (Built-in badge + sort + hide delete)
tech_stack:
  added: []
  patterns:
    - Deviation bar: center-tick bar with directional fill (amber=overweight, green=underweight), 4x scale so 25pp fills bar
    - window.prompt for inline target-weight edit — acceptable per research "ship fast" philosophy
    - metric === "hardcoded" guard: hides delete, replaces metric/condition/threshold cells with dashes, adds Built-in badge
    - data-testid scoping: target-weight-bar-{ticker}, alert-rule-toggle-{id}, alert-rule-builtin-badge-{id}
key_files:
  created:
    - frontend/src/components/portfolio/TargetWeightBar.tsx
    - frontend/src/components/portfolio/__tests__/TargetWeightBar.test.tsx
    - frontend/src/components/monitoring/__tests__/AlertRulesPanel.test.tsx
  modified:
    - frontend/src/api/types.ts (target_weight?: number | null on Position)
    - frontend/src/api/endpoints.ts (setTargetWeight export)
    - frontend/src/components/portfolio/PositionsTable.tsx (Target Wt column + onPositionUpdated + totalValue props)
    - frontend/src/components/monitoring/AlertRulesPanel.tsx (Built-in badge, sort, hide delete, data-testid toggles)
    - frontend/src/pages/PortfolioPage.tsx (totalValue + onPositionUpdated passed to PositionsTable)
decisions:
  - window.prompt used for target-weight inline edit — research explicitly permits for v1 "ship fast"; proper modal deferred to UI-v2-03 candidate
  - deviation sign convention: positive = overweight (amber), negative = underweight (green) — matches financial convention
  - fillWidth = abs(deviation * 100) * 4, clamped to 100% — 25pp deviation saturates the bar fully
  - deviation >= 0 threshold for "+" prefix (not isOver) so near-zero rounds to "+0.0%" correctly
  - Built-in rules sorted first in AlertRulesPanel table via stable JS sort on metric === "hardcoded"
  - Delete button hidden for hardcoded rules; backend re-seeds them on init_db so deleting via UI would be misleading
metrics:
  duration_seconds: 339
  completed: "2026-04-21"
  tasks_completed: 2
  files_modified: 8
---

# Phase 04 Plan 04: UI-03 AlertRulesPanel Polish + UI-04 TargetWeightBar Summary

TargetWeightBar deviation component (amber=overweight, green=underweight) wired into PositionsTable with inline window.prompt editor; AlertRulesPanel polished with Built-in badge and delete suppression for daemon-seeded hardcoded rules.

## What Was Built

### Task 1 — TargetWeightBar + setTargetWeight API + PositionsTable (commit `3fc5977`)

**frontend/src/api/types.ts:**
- Added `target_weight?: number | null` to `Position` interface

**frontend/src/api/endpoints.ts:**
- Added `setTargetWeight(ticker, targetWeight)` → `apiPatch<{ticker, target_weight}>("/portfolio/positions/{ticker}/target-weight", {target_weight})`
- `apiPatch` already existed in `client.ts` — no new helper needed

**frontend/src/components/portfolio/TargetWeightBar.tsx (NEW):**
- Props: `{actualWeight: number, targetWeight: number | null, ticker?: string}`
- Returns null when `targetWeight` is null
- Renders: actual% label | center-tick bar with directional fill | deviation label | "(target X%)" hint
- Overweight (actual > target+0.0001): amber fill extends right from center
- Underweight (actual < target-0.0001): green fill extends left from center
- Fill width = `min(abs(deviation * 100) * 4, 100)%` — 25pp deviation saturates bar
- `data-testid="target-weight-bar-{ticker}"` (or `"target-weight-bar"` when no ticker)

**frontend/src/components/portfolio/PositionsTable.tsx:**
- Added `onPositionUpdated?: () => void` and `totalValue?: number` props
- New "Target Wt" column: renders `<TargetWeightBar>` + "set target" / "edit target" inline button
- Button fires `window.prompt` → validates 0.0-1.0 range → calls `setTargetWeight` → calls `onPositionUpdated()`

**frontend/src/pages/PortfolioPage.tsx:**
- Passes `totalValue={data.total_value}` and `onPositionUpdated={() => { invalidateCache("portfolio"); refetch(); }}` to PositionsTable

**Tests: 5 Vitest tests — all pass**

### Task 2 — AlertRulesPanel polish + MonitoringPage verification (commit `2766851`)

**frontend/src/components/monitoring/AlertRulesPanel.tsx:**
- Detect `rule.metric === "hardcoded"` per row
- Add "Built-in" name badge: `data-testid="alert-rule-builtin-badge-{id}"`
- Replace metric/condition/threshold cells with `—` dashes for hardcoded rules
- Hide delete button for hardcoded rules (backend re-seeds on init_db)
- Add `data-testid="alert-rule-toggle-{id}"` to toggle button for all rules
- Sort: hardcoded rules appear first (stable JS sort)

**frontend/src/pages/MonitoringPage.tsx:**
- Already imports and renders `<AlertRulesPanel />` — no change needed

**Tests: 3 Vitest tests — all pass**

## Test Count Delta

| File | Before | After | Delta |
|------|--------|-------|-------|
| TargetWeightBar.test.tsx | 0 | 5 | +5 |
| AlertRulesPanel.test.tsx | 0 | 3 | +3 |
| **Total frontend tests** | 392 | 400 | **+8** |

## data-testid Inventory (for future e2e harness)

| Selector | Component | Description |
|----------|-----------|-------------|
| `data-testid="target-weight-bar-{ticker}"` | TargetWeightBar | Deviation bar root div |
| `data-testid="alert-rule-builtin-badge-{id}"` | AlertRulesPanel | "Built-in" pill on hardcoded rules |
| `data-testid="alert-rule-toggle-{id}"` | AlertRulesPanel | Toggle switch button for any rule |

## Human Verification

**Task 3 is a `checkpoint:human-verify` — manual steps required.**

The automated portions (Tasks 1 and 2) are complete and committed. Please verify the following in a running browser session:

### 1. Target-weight flow (UI-04)

```bash
# Terminal 1 — backend
python -m uvicorn api.app:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

- Visit `http://localhost:3000/portfolio`
- For any open position, click **"set target"** below the weight column
- Enter `0.10` at the prompt → the `TargetWeightBar` appears with correct deviation colour (amber if actual > 10%, green if actual < 10%)
- Reload the page → the target persists (confirms PATCH + backend storage working)
- Click **"edit target"** → clear the field and submit → bar disappears (cleared to null)
- Enter `1.5` → expect browser alert "Target weight must be between 0.0 and 1.0"

### 2. Rules panel + daemon wiring (UI-03)

- Visit `http://localhost:3000/monitoring`
- Observe 5 hardcoded rules listed with "Built-in" badge: `STOP_LOSS_HIT`, `TARGET_HIT`, `TIME_OVERRUN`, `SIGNIFICANT_LOSS`, `SIGNIFICANT_GAIN`
- Disable `STOP_LOSS_HIT` via the toggle
- Run a monitor check:
  ```bash
  curl -X POST http://localhost:8000/api/v1/monitor/check
  ```
- Confirm backend log: `"Enabled hardcoded alert types: ['SIGNIFICANT_GAIN', 'SIGNIFICANT_LOSS', 'TARGET_HIT', 'TIME_OVERRUN']"` (STOP_LOSS_HIT absent)
- Re-enable `STOP_LOSS_HIT` → confirm it reappears in next monitor check log

### 3. No regressions

```bash
pytest -q                        # backend suite
cd frontend && npm run test      # 400 frontend tests
cd frontend && npx tsc --noEmit  # TypeScript clean
```

**Resume signal:** Type "approved" when both flows verify, or describe any unexpected behavior.

## Deviations from Plan

### Auto-fix [Rule 1 - Bug] Fixed "+0.0%" sign for near-zero deviation

- **Found during:** Task 1 GREEN phase (test run)
- **Issue:** Test `shows near-zero deviation as neutral` expected "+0.0%" but component used `isOver ? "+" : ""` — with `deviation = 0.0001`, `isOver` is false (not > 0.0001), so "+" was omitted
- **Fix:** Changed prefix condition to `deviation >= 0 ? "+" : ""` — applies "+" whenever deviation is non-negative, matching mathematical convention
- **Files modified:** `frontend/src/components/portfolio/TargetWeightBar.tsx`
- **Commit:** `3fc5977` (included in same commit)

## Known Stubs

None — both components wire to real API endpoints:
- `TargetWeightBar` reads `position.target_weight` from backend via `getPortfolio()` response and writes via `setTargetWeight()` PATCH
- `AlertRulesPanel` reads from `GET /alerts/rules` (includes seeded hardcoded rules after `init_db`) and writes via `toggleAlertRule()` PATCH

## Threat Flags

None — T-04-18 (target_weight range validation) is mitigated: client-side `parseFloat` + `0.0-1.0` range check in `window.prompt` handler gives immediate UX feedback; backend Pydantic `Field(ge=0.0, le=1.0)` provides defense-in-depth. T-04-19 (delete hardcoded rule) is mitigated: delete button is hidden in the UI for `metric === "hardcoded"` rules. T-04-21 (XSS via rule name) is mitigated: `{rule.name}` is a JSX text node — React auto-escapes.

## UX v2 Candidates

- **UI-v2-03**: Replace `window.prompt` target-weight editor with a proper inline popover or modal field — especially relevant once multiple positions have targets and users want to bulk-edit allocations.

## Self-Check: PASSED

- [x] `frontend/src/components/portfolio/TargetWeightBar.tsx` exists with `data-testid="target-weight-bar-{ticker}"`
- [x] `frontend/src/api/types.ts` contains `target_weight`
- [x] `frontend/src/api/endpoints.ts` contains `setTargetWeight`
- [x] `frontend/src/components/portfolio/PositionsTable.tsx` contains `TargetWeightBar`
- [x] `frontend/src/pages/PortfolioPage.tsx` passes `onPositionUpdated` and `totalValue`
- [x] `frontend/src/components/monitoring/AlertRulesPanel.tsx` contains `metric === "hardcoded"` and "Built-in"
- [x] `frontend/src/components/monitoring/__tests__/AlertRulesPanel.test.tsx` exists with 3 tests
- [x] `frontend/src/components/portfolio/__tests__/TargetWeightBar.test.tsx` exists with 5 tests
- [x] Commit `3fc5977` (Task 1) exists in git log
- [x] Commit `2766851` (Task 2) exists in git log
- [x] 400 frontend tests pass (up from 392); 0 regressions
- [x] `npx tsc --noEmit` exits 0
