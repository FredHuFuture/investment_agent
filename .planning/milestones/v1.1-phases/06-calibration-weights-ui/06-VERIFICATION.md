---
phase: 06-calibration-weights-ui
verified: 2026-04-24T00:30:00Z
status: gaps_found
score: 4/5 success criteria verified (1 gap, 1 partial-deferred)
overrides_applied: 0
gaps:
  - truth: "tsc --noEmit exits 0 (all TypeScript type errors resolved)"
    status: failed
    reason: "Unused 'afterEach' import in frontend/src/pages/__tests__/CalibrationPage.test.tsx (line 1) causes TS6133 noUnusedLocals error — tsc --noEmit exits non-zero. One-line fix: remove 'afterEach' from the vitest import."
    artifacts:
      - path: "frontend/src/pages/__tests__/CalibrationPage.test.tsx"
        issue: "Line 1 imports 'afterEach' from vitest but afterEach is never used in the file (added during WR-02 fix, cleanup was missed)"
    missing:
      - "Remove 'afterEach' from import on line 1 of CalibrationPage.test.tsx"
deferred:
  - truth: "The next daemon signal_aggregator run uses the updated agent_weights (SC-2 partial)"
    addressed_in: "Phase 7"
    evidence: "Phase 7 goal: 'a drift detector automatically flags and down-weights agents whose IC-IR has degraded'; Phase 7 SC-4: 'writes a scaled-down weight to the agent_weights table via WeightAdapter'; 06-01-SUMMARY explicitly: 'Pipeline wiring deferred to Phase 7 AN-02 drift detector — load_weights_from_db helper is tested and ready but pipeline.py remains on DEFAULT_WEIGHTS'"
human_verification:
  - test: "Apply IC-IR weights live round-trip"
    expected: "Visiting /calibration, clicking 'Apply IC-IR weights' (when corpus populated) should change source badge from Default to IC-IR, update current weights column to show IC-IR-derived values, and persist across page reload"
    why_human: "Requires live servers with populated corpus; automated tests mock the API responses"
  - test: "CLOSE-04 target-weight browser persistence on reload"
    expected: "Setting a target weight, reloading the page, and verifying the TargetWeightBar still renders with correct color/deviation (tests the backend PATCH write-then-GET round-trip)"
    why_human: "Snapshot test locks DOM contract; live persistence requires a real browser + running backend"
  - test: "CLOSE-05 rules panel daemon wiring"
    expected: "Disabling STOP_LOSS_HIT via toggle, triggering POST /monitor/check, and verifying backend log shows STOP_LOSS_HIT absent from enabled types"
    why_human: "Snapshot test locks UI contract; daemon log verification requires running backend"
  - test: "CLOSE-06 DailyPnlHeatmap tooltip on hover"
    expected: "Hovering over a positive heatmap cell shows native browser tooltip with format 'YYYY-MM-DD: +$XXX.XX'"
    why_human: "Snapshot test locks title attributes; native browser tooltip appearance requires a real browser"
---

# Phase 6: Calibration & Weights UI Verification Report

**Phase Goal:** The user can open a browser, see which agents are performing well or poorly this week (Brier, IC, IC-IR, sparkline), apply IC-IR-suggested weights with one click, manually disable a noisy agent, and confirm the three deferred v1.0 browser-side UAT flows work as intended — so the dashboard is genuinely usable as a weekly review surface.
**Verified:** 2026-04-24T00:30:00Z
**Status:** gaps_found (1 gap: unused import causing tsc failure; 1 deferred to Phase 7; 4 human verification items for live browser flows)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | /calibration renders per-agent Brier/IC/IC-IR/sparkline table + FOUND-04 note | VERIFIED | CalibrationPage.tsx + CalibrationTable + AgentCalibrationRow all exist and are wired; 26 component tests pass; route in App.tsx confirmed |
| 2 | Apply IC-IR persists to agent_weights; Apply button disabled when corpus empty | VERIFIED (partial) | POST /weights/apply-ic-ir found in weights.py; WeightsEditor apply button gated on `suggested === null`; daemon wiring deferred to Phase 7 |
| 3 | Per-agent override persists exclusion; remaining weights renormalize to 1.0 | VERIFIED | PATCH /weights/override with UPSERT confirmed; FOUND-05 renormalization in _read_current_weights and load_weights_from_db; SummaryAgent removed from KNOWN_AGENTS (WR-01 fix); Test 26 confirms rejection |
| 4 | CLOSE-04 target-weight browser flow documented as resolved in 04-HUMAN-UAT.md | VERIFIED | 4-state TargetWeightBar snapshot test passes; 04-HUMAN-UAT.md status: resolved; result: resolved on item 1 |
| 5 | CLOSE-05 rules panel + CLOSE-06 heatmap tooltip documented as resolved in 04-HUMAN-UAT.md | VERIFIED | AlertRulesPanel and DailyPnlHeatmap snapshot tests all 10 pass; 04-HUMAN-UAT.md items 2+3 both result: resolved |

**Score:** 4/5 truths fully verified (SC-2 partially deferred to Phase 7; 1 tsc gap found)

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | "next daemon signal_aggregator run uses updated agent_weights" (SC-2 partial) | Phase 7 | Phase 7 SC-4: 'writes a scaled-down weight to the agent_weights table via WeightAdapter'; 06-01-SUMMARY: 'Pipeline wiring deferred to Phase 7 AN-02 drift detector'; pipeline.py currently uses legacy WeightAdapter.load_weights() not load_weights_from_db |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `db/database.py` | agent_weights DDL + seed-on-empty | VERIFIED | CREATE TABLE IF NOT EXISTS agent_weights found; UNIQUE(agent_name, asset_type); 8-column schema |
| `engine/aggregator.py` | load_weights_from_db helper | VERIFIED | async def load_weights_from_db confirmed importable; SELECT query, excluded filter, renormalization present |
| `api/routes/weights.py` | 3 endpoints + KNOWN_AGENTS (no SummaryAgent) | VERIFIED | apply-ic-ir, KNOWN_AGENTS, UPSERT ON CONFLICT all present; SummaryAgent confirmed absent from KNOWN_AGENTS |
| `api/models.py` | WeightsOverviewResponse, OverrideRequest, ApplyIcIrResponse | VERIFIED | All three Pydantic models found |
| `frontend/src/pages/CalibrationPage.tsx` | Main calibration page with table + weights editor | VERIFIED | File exists; mountedRef + rebuildTimeoutRef (WR-02 fix) confirmed; imports getCalibrationAnalytics + getWeightsV2 |
| `frontend/src/components/calibration/AgentCalibrationRow.tsx` | data-testid="cal-agent-row-{name}" + FOUND-04 note | VERIFIED | data-testid template literals confirmed; entry.note branch renders cal-agent-note-{name} |
| `frontend/src/components/calibration/ICSparkline.tsx` | data-testid="cal-ic-sparkline-{name}" | VERIFIED | Both sparkline and empty-state testids confirmed |
| `frontend/src/components/calibration/WeightsEditor.tsx` | Apply IC-IR button + exclude toggle | VERIFIED | cal-apply-ic-ir-button and cal-exclude-toggle-{assetType}-{agent} testids confirmed |
| `frontend/src/components/calibration/CalibrationTable.tsx` | Empty corpus CTA | VERIFIED | cal-empty-corpus-cta on total_observations === 0 branch confirmed |
| `frontend/src/App.tsx` | /calibration route registered | VERIFIED | Lazy CalibrationPage import + Route path="/calibration" found |
| `frontend/src/pages/WeightsPage.tsx` | Navigate redirect to /calibration | VERIFIED | Navigate + calibration both found in file |
| `frontend/src/components/portfolio/__tests__/TargetWeightBar.snapshot.test.tsx` | CLOSE-04 snapshot | VERIFIED | File exists with CLOSE-04 marker; 4 tests pass |
| `frontend/src/components/monitoring/__tests__/AlertRulesPanel.snapshot.test.tsx` | CLOSE-05 snapshot | VERIFIED | File exists with CLOSE-05 marker; 3 tests pass |
| `frontend/src/components/performance/__tests__/DailyPnlHeatmap.snapshot.test.tsx` | CLOSE-06 snapshot | VERIFIED | File exists with CLOSE-06 marker; 3 tests pass |
| `scripts/verify_close_04_target_weight.py` | Operator script, exits 0 with --approved | VERIFIED | File exists; exit 0 confirmed |
| `scripts/verify_close_05_rules_panel.py` | Operator script, exits 0 with --approved | VERIFIED | File exists; exit 0 confirmed |
| `scripts/verify_close_06_heatmap_tooltip.py` | Operator script, exits 0 with --approved | VERIFIED | File exists; exit 0 confirmed |
| `.planning/milestones/v1.0-phases/04-portfolio-ui-analytics-uplift/04-HUMAN-UAT.md` | status: resolved, 3x result: resolved | VERIFIED | status: resolved in frontmatter; grep -c "result: resolved" returns 3 |
| `tests/test_live_03_weights_api.py` | 26 tests covering DDL/endpoints/threat model | VERIFIED | 26 tests collected; test_summary_agent_rejected_from_weights_override (Test 26) present |
| `frontend/src/pages/__tests__/CalibrationPage.test.tsx` | 9 page tests pass including WR-02 | VERIFIED (with gap) | 9 tests pass; but unused 'afterEach' import causes tsc --noEmit to exit non-zero |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| api/routes/weights.py::POST /weights/apply-ic-ir | engine/weight_adapter.py::compute_ic_weights | deferred import of WeightAdapter inside endpoint | WIRED | adapter.compute_ic_weights call confirmed at line 135 of weights.py |
| api/routes/weights.py::PATCH /weights/override | agent_weights row UPSERT | ON CONFLICT(agent_name, asset_type) DO UPDATE | WIRED | UPSERT ON CONFLICT pattern confirmed; KNOWN_AGENTS guard at line 246 |
| engine/aggregator.py::load_weights_from_db | SELECT agent_name, asset_type from agent_weights | aiosqlite query + excluded filter + renormalize | WIRED | SELECT query confirmed at line 346; deferred aiosqlite import confirmed |
| frontend/src/pages/CalibrationPage.tsx | GET /api/v1/analytics/calibration | useApi(() => getCalibrationAnalytics()) | WIRED | getCalibrationAnalytics import + useApi call confirmed |
| frontend/src/pages/CalibrationPage.tsx | GET /api/v1/weights | useApi(() => getWeightsV2()) | WIRED | getWeightsV2 import + useApi call confirmed |
| frontend/src/components/calibration/WeightsEditor.tsx | POST /api/v1/weights/apply-ic-ir | onApplyIcIr callback → CalibrationPage::handleApplyIcIr → applyIcIrWeights() | WIRED | onApplyIcIr prop wired to handleApplyIcIr which calls applyIcIrWeights at line 69 |
| frontend/src/components/calibration/WeightsEditor.tsx | PATCH /api/v1/weights/override | onOverride callback → CalibrationPage::handleOverride → overrideAgentWeight() | WIRED | onOverride prop wired to handleOverride which calls overrideAgentWeight at line 82 |
| CalibrationPage.tsx CLOSE-04 snapshot | TargetWeightBar DOM contract | toMatchSnapshot() 4 states | WIRED | 4 snapshot tests pass; .snap file committed |
| CalibrationPage.tsx CLOSE-05 snapshot | AlertRulesPanel toggle contract | toMatchSnapshot() + toggleAlertRule exact args | WIRED | 3 snapshot tests pass including toggle-args behavioral check |
| CalibrationPage.tsx CLOSE-06 snapshot | DailyPnlHeatmap title attribute | toMatchSnapshot() title format | WIRED | 3 snapshot tests pass; title format locked |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| CalibrationTable.tsx | data.agents (calibration entries) | GET /analytics/calibration → api/routes/calibration.py → tracker.compute_rolling_ic + compute_icir | Yes — queries backtest_signal_history table | FLOWING |
| WeightsEditor.tsx | data.current / data.suggested_ic_ir | GET /weights → api/routes/weights.py → SELECT FROM agent_weights + compute_ic_weights | Yes — queries agent_weights table + backtest_signal_history for IC-IR | FLOWING |
| WeightsEditor.tsx (apply) | POST /weights/apply-ic-ir response | api/routes/weights.py → compute_ic_weights → UPSERT into agent_weights | Yes — writes to agent_weights, refetch confirms persistence | FLOWING |
| WeightsEditor.tsx (override) | PATCH /weights/override response.renormalized_weights | api/routes/weights.py → UPDATE agent_weights + _read_current_weights | Yes — DB write + read-back with renormalization | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| load_weights_from_db importable | python -c "from engine.aggregator import load_weights_from_db; print('ok')" | ok | PASS |
| KNOWN_AGENTS excludes SummaryAgent | python -c "from api.routes.weights import KNOWN_AGENTS; print(sorted(KNOWN_AGENTS))" | ['CryptoAgent', 'FundamentalAgent', 'MacroAgent', 'SentimentAgent', 'TechnicalAgent'] | PASS |
| CalibrationPage 9 tests pass | npx vitest run src/pages/__tests__/CalibrationPage.test.tsx | 9/9 pass | PASS |
| Snapshot tests 10/10 pass | npx vitest run ...TargetWeightBar...AlertRulesPanel...DailyPnlHeatmap snapshot tests | 10/10 pass | PASS |
| Calibration component tests | npx vitest run src/components/calibration/__tests__/ | 26/26 pass | PASS |
| tsc --noEmit exits 0 | cd frontend && npx tsc --noEmit | TS6133: 'afterEach' declared but never read in CalibrationPage.test.tsx:1 | FAIL |
| Operator scripts exit 0 with --approved | python scripts/verify_close_0{4,5,6}*.py --approved | Exit 0 each | PASS |
| 04-HUMAN-UAT.md status resolved | grep "^status:" 04-HUMAN-UAT.md | status: resolved | PASS |
| 3x result: resolved in UAT doc | grep -c "result: resolved" 04-HUMAN-UAT.md | 3 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| LIVE-02 | 06-02 | CalibrationPage at /calibration with per-agent Brier/IC/IC-IR/sparkline | SATISFIED | CalibrationPage, AgentCalibrationRow, ICSparkline, CalibrationTable all exist and wired; 26 component tests pass |
| LIVE-03 | 06-01, 06-02 | Agent weight management UI — agent_weights table + endpoints + Apply IC-IR + override toggle | SATISFIED | agent_weights DDL, 3 endpoints, WeightsEditor component, override toggle all verified |
| CLOSE-04 | 06-03 | Target-weight browser flow verified in 04-HUMAN-UAT.md | SATISFIED | TargetWeightBar.snapshot.test.tsx 4 states pass; 04-HUMAN-UAT.md item 1 result: resolved |
| CLOSE-05 | 06-03 | Rules panel daemon wiring verified in 04-HUMAN-UAT.md | SATISFIED | AlertRulesPanel.snapshot.test.tsx 3 scenarios pass; 04-HUMAN-UAT.md item 2 result: resolved |
| CLOSE-06 | 06-03 | DailyPnlHeatmap tooltip verified in 04-HUMAN-UAT.md | SATISFIED | DailyPnlHeatmap.snapshot.test.tsx 3 scenarios pass; 04-HUMAN-UAT.md item 3 result: resolved |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| frontend/src/pages/__tests__/CalibrationPage.test.tsx | 1 | Unused 'afterEach' import (TS6133 noUnusedLocals) | Warning | tsc --noEmit exits non-zero; violates plan success criterion; 1-line fix: remove from import |

No anti-patterns found in production source files. No TODOs, stubs, or hardcoded empty returns in CalibrationPage.tsx, WeightsEditor.tsx, CalibrationTable.tsx, AgentCalibrationRow.tsx, ICSparkline.tsx, or api/routes/weights.py.

### Human Verification Required

#### 1. Apply IC-IR Weights Live Round-Trip

**Test:** Visit /calibration with a populated corpus (run POST /analytics/calibration/rebuild-corpus first if needed). Check that "Apply IC-IR weights" button is enabled. Click it. Verify source badge changes from "Default" to "IC-IR" and the current weights column updates to show the IC-IR-derived values. Reload the page and verify the IC-IR weights persist.
**Expected:** Source badge shows "IC-IR" (green) after apply; current weight column values match the suggested column; persists on reload.
**Why human:** Requires live servers with a populated backtest_signal_history corpus. Automated tests mock the API response.

#### 2. CLOSE-04 Target-Weight Browser Persistence on Reload

**Test:** Run `python scripts/verify_close_04_target_weight.py` with live servers running (see script's step-by-step instructions).
**Expected:** Set target weight 0.10, TargetWeightBar renders with amber/green fill, persists on Ctrl+R reload, clears on blank input, shows alert on 1.5.
**Why human:** Snapshot test locks the DOM contract; live browser persistence (PATCH write + GET read-back) requires running backend.

#### 3. CLOSE-05 Rules Panel Daemon Log Verification

**Test:** Run `python scripts/verify_close_05_rules_panel.py` with live servers. Disable STOP_LOSS_HIT, run `curl -X POST http://127.0.0.1:8000/api/v1/monitor/check`, inspect backend log.
**Expected:** Backend log shows `Enabled hardcoded alert types: [...]` with STOP_LOSS_HIT absent.
**Why human:** Snapshot test locks UI contract; daemon log verification requires running backend + log inspection.

#### 4. CLOSE-06 DailyPnlHeatmap Tooltip on Hover

**Test:** Run `python scripts/verify_close_06_heatmap_tooltip.py` with live servers + populated portfolio_snapshots. Hover over a green cell and a red cell.
**Expected:** Native browser tooltip shows "YYYY-MM-DD: +$XXX.XX" for positive, "YYYY-MM-DD: -$XXX.XX" for negative cells.
**Why human:** Snapshot test locks title attributes in jsdom; native browser tooltip rendering requires a real browser.

### Gaps Summary

**1 gap blocks the "no TypeScript errors" success criterion:**

`frontend/src/pages/__tests__/CalibrationPage.test.tsx` imports `afterEach` from vitest (line 1) but never uses it. TypeScript's `noUnusedLocals` strict setting causes `tsc --noEmit` to exit non-zero. This was introduced during the WR-02 fix (02-REVIEW-FIX) when the import was expanded but not subsequently cleaned up. The fix is trivial: remove `afterEach` from the import line.

**Root cause:** The WR-02 fix added a test that uses `vi.useFakeTimers()` and fake timer advancement, which required expanding the test scaffolding. The `afterEach` import was added provisionally and left when the final test didn't need it.

**1 deferred item (not a gap):** SC-2's requirement that "the next daemon run uses updated weights" is explicitly deferred to Phase 7 AN-02. The `load_weights_from_db` helper is fully tested and ready; only the pipeline.py call-site wiring is missing. Phase 7 AN-02 (drift detector) is the designated owner.

---

_Verified: 2026-04-24T00:30:00Z_
_Verifier: Claude (gsd-verifier)_
