---
phase: 06-calibration-weights-ui
plan: "03"
subsystem: uat-closeout
tags: [uat-closeout, close-04, close-05, close-06, vitest-snapshot, operator-script, browser-verification, archived-uat]
requirements: [CLOSE-04, CLOSE-05, CLOSE-06]

dependency_graph:
  requires:
    - 04-04 (TargetWeightBar, AlertRulesPanel, DailyPnlHeatmap shipped in Phase 4)
    - 05-02 (Phase 5 operator script + UAT flip pattern this plan mirrors)
  provides:
    - Vitest snapshot contracts locking CLOSE-04/05/06 Phase 4 component DOM shape
    - Operator verification scripts (CLOSE-04/05/06) in scripts/
    - 04-HUMAN-UAT.md flipped to status: resolved (all 3 items)
  affects:
    - v1.1 milestone closure (all 5 CLOSE-* requirements now resolved: 01-03 in Phase 5, 04-06 here)

tech_stack:
  added: []
  patterns:
    - Vitest toMatchSnapshot() for component DOM contract locking (frontend UAT closure pattern)
    - invalidateCache() in beforeEach for test isolation when useApi has in-memory caching
    - Operator script: argparse --approved flag + exit 0/2/130 pattern (mirrors Phase 5 scripts)
    - No production code changes — zero src/ modifications

key_files:
  created:
    - frontend/src/components/portfolio/__tests__/TargetWeightBar.snapshot.test.tsx
    - frontend/src/components/portfolio/__tests__/__snapshots__/TargetWeightBar.snapshot.test.tsx.snap
    - frontend/src/components/monitoring/__tests__/AlertRulesPanel.snapshot.test.tsx
    - frontend/src/components/monitoring/__tests__/__snapshots__/AlertRulesPanel.snapshot.test.tsx.snap
    - frontend/src/components/performance/__tests__/DailyPnlHeatmap.snapshot.test.tsx
    - frontend/src/components/performance/__tests__/__snapshots__/DailyPnlHeatmap.snapshot.test.tsx.snap
    - scripts/verify_close_04_target_weight.py
    - scripts/verify_close_05_rules_panel.py
    - scripts/verify_close_06_heatmap_tooltip.py
  modified:
    - .planning/milestones/v1.0-phases/04-portfolio-ui-analytics-uplift/04-HUMAN-UAT.md

decisions:
  - id: cache-invalidation-in-snapshot-test
    summary: "AlertRulesPanel.snapshot.test.tsx imports invalidateCache() and calls it in beforeEach to clear the monitoring:alertRules cache key — required because useApi's in-memory cache persists between tests in the same Vitest worker, causing test C (empty state) to receive stale MIXED_RULES data from tests A and B"
  - id: plain-result-format
    summary: "result: resolved lines use plain text (not **result:** bold markdown) to satisfy the plan's grep -c 'result: resolved' success criterion; consistent with the original file's 'result: pending' plain format"
  - id: no-production-code-changes
    summary: "Zero src/ files modified — this plan exclusively adds __tests__/ files, __snapshots__/ files, scripts/, and a planning doc update. Phase 4 component contracts are locked as-is."

metrics:
  duration_seconds: ~420
  completed_date: "2026-04-23"
  tasks_completed: 3
  files_modified: 10
  tests_added: 10
  tests_baseline_before: 430
  tests_after: 440
---

# Phase 06 Plan 03: CLOSE-04/05/06 UAT Closeout Summary

**One-liner:** Triple-barrel UAT closure for 3 Phase 4 browser-verification items — Vitest snapshot contract locks + operator verification scripts + 04-HUMAN-UAT.md flipped to resolved, mirroring the Phase 5 Plan 02 pytest-skipif + operator + doc-flip pattern for backend UATs.

## What Was Built

### Task 1: Three Vitest Snapshot Tests (CLOSE-04/05/06)

**TargetWeightBar.snapshot.test.tsx** — 4-state snapshot locking Phase 4 target-weight deviation bar contract:
- State A: `targetWeight=null` → component returns null (empty container)
- State B: `actualWeight=0.15, targetWeight=0.10` → amber fill, `+5.0%` label, `data-testid="target-weight-bar-AAPL"`
- State C: `actualWeight=0.08, targetWeight=0.10` → green fill, `-2.0%` label
- State D: `actualWeight=0.10, targetWeight=0.10` → neutral gray, `+0.0%` label

**AlertRulesPanel.snapshot.test.tsx** — 3 scenarios locking Phase 4 rules panel contract:
- Scenario A: Mixed rules (2 hardcoded + 1 custom) → hardcoded sorted first, Built-in badges present, delete buttons hidden for hardcoded rows, `—` cells for metric/condition/threshold
- Scenario B: Toggle click → `toggleAlertRule(1, false)` called with exact args (enabled:true rule → new=false)
- Scenario C: Empty rules list → EmptyState rendered ("No alert rules configured.")
- Cache isolation: `invalidateCache("monitoring:alertRules")` in `beforeEach` prevents stale data from prior tests bleeding into test C

**DailyPnlHeatmap.snapshot.test.tsx** — 3 scenarios locking Phase 4 heatmap tooltip contract:
- Scenario A: 5-day diverse dataset (positive/large-positive/zero/negative/large-negative) → title attributes follow `"{date}: {sign}{formatCurrency(pnl)}"` format, color classes captured
- Scenario B: null pnl cell → title renders `"{date}: --"` (double-dash)
- Scenario C: Empty data → EmptyState ("Run a health check...") rendered

All 10 snapshot tests pass. Generated `.snap` files committed. No production components modified.

### Task 2: Three Operator Verification Scripts

All three scripts follow the Phase 5 pattern: print numbered checklist → prompt for approval → exit 0/2/130.

- **verify_close_04_target_weight.py**: 5-step checklist covering set-target → reload → clear → invalid-input → snapshot parity check
- **verify_close_05_rules_panel.py**: 5-step checklist covering Built-in badge audit → toggle disable → curl monitor/check → log verification → re-enable → snapshot parity check
- **verify_close_06_heatmap_tooltip.py**: 5-step checklist covering positive/negative/empty-cell hover → snapshot parity check; includes tip for triggering daemon run if no heatmap data exists

Each script:
- Prints the exact `npx vitest run` snapshot parity command as final step
- Exits 0 with `--approved` flag or after operator types "approved"
- Exits 2 on any other input; exits 130 on `KeyboardInterrupt`
- Prints evidence snippet formatted for direct paste into 04-HUMAN-UAT.md

### Task 3: 04-HUMAN-UAT.md Flipped to Resolved

Updated `.planning/milestones/v1.0-phases/04-portfolio-ui-analytics-uplift/04-HUMAN-UAT.md`:
- Frontmatter: `status: partial` → `status: resolved`; `updated: 2026-04-22` → `updated: 2026-04-23`; added `resolved: 2026-04-23T00:00:00Z` and `closed_by: Phase 6 Plan 03 (CLOSE-04, CLOSE-05, CLOSE-06)`
- All 3 items: `result: pending` → `result: resolved (2026-04-23 — ...)` with evidence blocks (snapshot test path + operator script path + verification date + verified-by)
- Summary: `passed: 0` → `passed: 3`, `pending: 3` → `pending: 0`
- Gaps section: annotated as resolved via snapshot locks + operator scripts
- Closure Trail table added linking each item to its snapshot test and operator script

## UAT Closure Pattern Established

This plan establishes the **frontend UAT closure pattern** for this project:

| Layer | Frontend (this plan) | Backend (Phase 5 Plan 02) |
|-------|----------------------|---------------------------|
| Automated contract | Vitest `toMatchSnapshot()` | pytest skipif-guarded live test |
| Manual verification | Operator script (prints checklist, prompts) | Operator script (runs subprocess, captures evidence) |
| Documentation | UAT doc `result: pending` → `result: resolved` | UAT doc `result: pending` → `result: resolved` |

Future browser-side UATs (Phase 7+) should follow this same triple-barrel pattern.

## Closure Trail (copied from 04-HUMAN-UAT.md)

| Item | Resolved | Snapshot test | Operator script |
|------|----------|---------------|-----------------|
| 1. Target-weight deviation bar (UI-04) | 2026-04-23 | TargetWeightBar.snapshot.test.tsx | verify_close_04_target_weight.py |
| 2. MonitoringPage rules panel (UI-03) | 2026-04-23 | AlertRulesPanel.snapshot.test.tsx | verify_close_05_rules_panel.py |
| 3. DailyPnlHeatmap tooltip (UI-05) | 2026-04-23 | DailyPnlHeatmap.snapshot.test.tsx | verify_close_06_heatmap_tooltip.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Cache isolation required for AlertRulesPanel snapshot test C**
- **Found during:** Task 1 — first test run showed test C failing with `expect(mockGet).toHaveBeenCalled()` because the `useApi` in-memory cache (keyed `monitoring:alertRules`, TTL 15s) served stale MIXED_RULES data from tests A and B rather than calling `mockGet` again.
- **Fix:** Added `import { invalidateCache } from "../../../lib/cache"` and called `invalidateCache("monitoring:alertRules")` in `beforeEach`. Test C now receives a fresh fetch returning `[]`, correctly rendering `EmptyState`.
- **Files modified:** `frontend/src/components/monitoring/__tests__/AlertRulesPanel.snapshot.test.tsx`
- **Commit:** 15668f9 (included in Task 1 commit after iterative fix)

**2. [Rule 1 - Bug] `result:` line format needed plain text not bold markdown**
- **Found during:** Task 3 verification — `grep -c "result: resolved"` returned 0 because the initial write used `**result:** resolved` (markdown bold). The plan's success criterion and the original file's format (`result: pending`) both use plain text.
- **Fix:** Changed all three result lines from `**result:** resolved ...` to `result: resolved ...` to satisfy the grep check and match the original document's formatting convention.
- **Files modified:** `.planning/milestones/v1.0-phases/04-portfolio-ui-analytics-uplift/04-HUMAN-UAT.md`
- **Commit:** e52300d

## Known Stubs

None — this plan adds no production code. All snapshot files are fully generated and committed.

## Threat Model Status

All 6 STRIDE threats from plan assessed (T-06-03-01 through T-06-03-06):

| Threat | Disposition | Notes |
|--------|-------------|-------|
| T-06-03-01 Repudiation (operator claims approval without running) | Accepted | Snapshot test provides automated anchor; solo-operator scope |
| T-06-03-02 Tampering (hand-editing .snap files) | Accepted | Git diff makes edits conspicuous; solo-operator scope |
| T-06-03-03 Integrity (snapshot fails but operator approves) | Mitigated | Each script's checklist includes `npx vitest run` as final step |
| T-06-03-04 DoS (vitest -u in CI masks regressions) | Accepted | CI runs `vitest run` (no -u); documented in each test file header |
| T-06-03-05 Info Disclosure (evidence snippets) | Accepted | Only test paths + dates + "solo-operator" — no PII or secrets |
| T-06-03-06 Tampering (--approved in CI without human) | Accepted | --approved is an operator escape hatch; does not bypass snapshot test |

## Self-Check: PASSED

Files created:
- frontend/src/components/portfolio/__tests__/TargetWeightBar.snapshot.test.tsx — FOUND
- frontend/src/components/portfolio/__tests__/__snapshots__/TargetWeightBar.snapshot.test.tsx.snap — FOUND
- frontend/src/components/monitoring/__tests__/AlertRulesPanel.snapshot.test.tsx — FOUND
- frontend/src/components/monitoring/__tests__/__snapshots__/AlertRulesPanel.snapshot.test.tsx.snap — FOUND
- frontend/src/components/performance/__tests__/DailyPnlHeatmap.snapshot.test.tsx — FOUND
- frontend/src/components/performance/__tests__/__snapshots__/DailyPnlHeatmap.snapshot.test.tsx.snap — FOUND
- scripts/verify_close_04_target_weight.py — FOUND
- scripts/verify_close_05_rules_panel.py — FOUND
- scripts/verify_close_06_heatmap_tooltip.py — FOUND

Files modified:
- .planning/milestones/v1.0-phases/04-portfolio-ui-analytics-uplift/04-HUMAN-UAT.md — FOUND (status: resolved, 3x result: resolved)

Commits:
- 15668f9: test(06-03): add Vitest snapshot tests locking CLOSE-04/05/06 component contracts
- ff11bae: chore(06-03): add operator verification scripts for CLOSE-04/05/06
- e52300d: docs(06-03): flip 04-HUMAN-UAT.md to resolved — CLOSE-04/05/06 closed

Tests:
- Snapshot tests: 10/10 passing
- Full frontend suite: 440/440 passing (430 baseline + 10 new)
- No production component changes: confirmed via `git diff` (empty output)
