---
phase: 06-calibration-weights-ui
plan: "02"
subsystem: calibration-ui
tags: [frontend, calibration-page, weights-ui, recharts, react, vitest, sparkline, live-02, live-03]
requirements: [LIVE-02, LIVE-03]

dependency_graph:
  requires:
    - 06-01 (agent_weights table + GET /weights + POST /weights/apply-ic-ir + PATCH /weights/override)
    - 05-01 (LIVE-01 rebuild corpus endpoint + corpus_rebuild_jobs table)
    - 02-03 (GET /analytics/calibration endpoint + compute_rolling_ic tracker method)
  provides:
    - /calibration route (CalibrationPage: calibration table + weights editor, weekly review surface)
    - rolling_ic field added to GET /analytics/calibration response (sparkline data)
    - /weights redirect to /calibration (backward compat)
    - Calibration nav item in Sidebar (Tools group)
  affects:
    - 06-03 (if planned: any further calibration UI extensions consume these components)
    - 07 AN-02 (drift detector may surface warnings in CalibrationPage)

tech_stack:
  added:
    - 5 new React components: ICSparkline, AgentCalibrationRow, CalibrationTable, AssetTypeTabs, WeightsEditor
    - 1 new page: CalibrationPage (replaces donut WeightsPage)
    - Recharts LineChart used for 60x20px sparklines (already installed at 2.15.4 — no new dep)
  patterns:
    - data-testid="cal-*" namespace for all Phase 06 calibration components
    - TDD: RED test (module not found) → GREEN component → typecheck (tsc --noEmit)
    - useApi with cacheKey pattern (matching PerformancePage)
    - Card without CardHeader subtitle for JSX content (inline div instead)
    - data-stroke attribute on sparkline wrapper for testable color assertions in jsdom

key_files:
  created:
    - frontend/src/components/calibration/ICSparkline.tsx
    - frontend/src/components/calibration/AgentCalibrationRow.tsx
    - frontend/src/components/calibration/CalibrationTable.tsx
    - frontend/src/components/calibration/AssetTypeTabs.tsx
    - frontend/src/components/calibration/WeightsEditor.tsx
    - frontend/src/components/calibration/__tests__/ICSparkline.test.tsx
    - frontend/src/components/calibration/__tests__/AgentCalibrationRow.test.tsx
    - frontend/src/components/calibration/__tests__/CalibrationTable.test.tsx
    - frontend/src/components/calibration/__tests__/AssetTypeTabs.test.tsx
    - frontend/src/components/calibration/__tests__/WeightsEditor.test.tsx
    - frontend/src/pages/__tests__/CalibrationPage.test.tsx
  modified:
    - api/routes/calibration.py (rolling_ic field added to both normal + NULL_EXPECTED branches)
    - tests/test_signal_quality_03_ic_icir.py (test_calibration_exposes_rolling_ic_field added)
    - frontend/src/api/types.ts (AgentCalibrationEntry, CalibrationResponse, WeightsOverviewResponse, etc.)
    - frontend/src/api/endpoints.ts (getCalibrationAnalytics, getWeightsV2, applyIcIrWeights, overrideAgentWeight, rebuildCalibrationCorpus, getCalibrationRebuildJob)
    - frontend/src/App.tsx (CalibrationPage lazy import + /calibration Route)
    - frontend/src/components/layout/Sidebar.tsx (Calibration nav item + icon in Tools group)
    - frontend/src/pages/CalibrationPage.tsx (full implementation, replacing Task 1 placeholder)
    - frontend/src/pages/WeightsPage.tsx (rewritten as Navigate redirect)
    - frontend/src/pages/__tests__/WeightsPage.test.tsx (rewritten for redirect contract)

decisions:
  - id: unified-page
    summary: "Combined LIVE-02 (calibration table) and LIVE-03 (weights editor) into single CalibrationPage — both surfaces are consulted together in weekly review; halves route count; legacy /weights redirects via Navigate"
  - id: data-stroke-for-sparkline-color-testing
    summary: "ICSparkline wrapper div exposes data-stroke attribute so Vitest/jsdom tests can assert stroke color without querying Recharts SVG internals (which are mocked away)"
  - id: card-inline-header-for-jsx-subtitle
    summary: "WeightsEditor uses inline div header instead of CardHeader because CardHeader.subtitle is typed string-only; source badge requires JSX ReactNode"
  - id: cal-weights-editor-wrapper-div
    summary: "data-testid='cal-weights-editor' placed on a wrapper <div> around Card because Card component does not forward arbitrary props to its DOM element"
  - id: weights-page-redirect-not-delete
    summary: "WeightsPage.tsx kept as Navigate redirect (not deleted) to preserve backward compat with bookmarked /weights URLs and sidebar shortcut until nav is cleaned up in a later plan"
  - id: no-new-npm-packages
    summary: "Recharts 2.15.4 already installed from Phase 4; no new dependencies added — confirmed via git diff HEAD~3 frontend/package.json (empty)"

metrics:
  duration_seconds: 1446
  completed_date: "2026-04-23"
  tasks_completed: 3
  files_modified: 19
  tests_added: 36
  backend_tests_added: 1
  tests_baseline_before: 925
  tests_after: 430
  frontend_tests_after: 430
---

# Phase 06 Plan 02: Calibration & Weights UI (LIVE-02 + LIVE-03) Summary

**One-liner:** Full-stack calibration surface: rolling_ic sparklines per agent via Recharts + per-asset-type weights editor with IC-IR apply + per-agent exclude toggle, wired to the 06-01 endpoints.

## What Was Built

### Task 1: Backend extension + types + endpoints + routing

- `api/routes/calibration.py`: Added `rolling_ic: list[float | None]` field to both normal agent branch and `NULL_EXPECTED` branch (FundamentalAgent gets `[]`). Additive change — no existing fields modified.
- `frontend/src/api/types.ts`: Added 7 new Phase 06 types: `AgentCalibrationEntry`, `CorpusMetadata`, `CalibrationResponse`, `WeightsOverrideFlags`, `WeightsOverviewResponse`, `ApplyIcIrResponse`, `OverrideResponse`.
- `frontend/src/api/endpoints.ts`: Added 6 new endpoint wrappers: `getCalibrationAnalytics`, `getWeightsV2`, `applyIcIrWeights`, `overrideAgentWeight`, `rebuildCalibrationCorpus`, `getCalibrationRebuildJob`. Legacy `getCalibration` + `getWeights` untouched for existing consumers.
- `frontend/src/App.tsx`: Lazy-loaded `CalibrationPage` + `<Route path="/calibration">` added before `/weights`.
- `frontend/src/components/layout/Sidebar.tsx`: Calibration nav item (with inline SVG icon) added to Tools group.
- `tests/test_signal_quality_03_ic_icir.py`: `test_calibration_exposes_rolling_ic_field` verifies the field via FastAPI TestClient (end-to-end response shape check).

### Task 2: CalibrationTable + AgentCalibrationRow + ICSparkline

- `ICSparkline`: 60×20px Recharts `<LineChart>` with no axes, color-coded stroke from IC-IR (`#10B981` green >1.0, `#F59E0B` amber 0.5–1.0, `#EF4444` red <0.5, `#6B7280` gray null). Exposes `data-stroke` on wrapper div for testable color assertions. Empty-state span when `rollingIc.length === 0`.
- `AgentCalibrationRow`: table `<tr>` with 5 cells (Agent, Brier, IC, IC-IR, Sparkline). Null metrics render "Insufficient data" text with `title` attribute explaining N threshold (N<20 for Brier, N<30 for IC/IC-IR). FOUND-04 note branch for FundamentalAgent replaces metric cells with full-width note `<td colSpan={4}>`.
- `CalibrationTable`: Composes 6 rows in `AGENT_ORDER` order. Empty-corpus CTA (`cal-empty-corpus-cta`) rendered when `total_observations === 0` instead of table. Survivorship bias warning shown as amber footnote.

### Task 3: AssetTypeTabs + WeightsEditor + CalibrationPage + WeightsPage redirect

- `AssetTypeTabs`: Three-tab `role="tablist"` switcher with `aria-selected`, `data-testid="cal-asset-type-tab-{value}"`, green underline on active tab.
- `WeightsEditor`: Four-column table (Agent | Current | Suggested IC-IR | Delta | Exclude). Apply button (`cal-apply-ic-ir-button`) disabled when `suggested_ic_ir[assetType] === null` with tooltip. Per-agent exclude checkbox (`cal-exclude-toggle-{assetType}-{agent}`) with pending state guard. Source badge (`cal-weights-source-badge`) with color coding. `cal-weights-editor` testid on wrapper div.
- `CalibrationPage`: Dual `useApi` (calibration + weights) with `refetchAll`. Handlers for `handleApplyIcIr`, `handleOverride`, `handleRebuildCorpus` each with toast feedback. `AssetTypeTabs` state defaults to `"stock"`.
- `WeightsPage`: Rewritten as `<Navigate to="/calibration" replace />` — old 329-line donut page gone.

## data-testid Inventory (for future Playwright harness)

| testid | Component | Description |
|--------|-----------|-------------|
| `cal-calibration-table` | CalibrationTable | Main table element |
| `cal-agent-row-{agentName}` | AgentCalibrationRow | One per agent row |
| `cal-agent-note-{agentName}` | AgentCalibrationRow | FOUND-04 note cell (FundamentalAgent) |
| `cal-ic-sparkline-{agentName}` | ICSparkline | Sparkline wrapper (has `data-stroke`) |
| `cal-ic-sparkline-empty-{agentName}` | ICSparkline | Empty-state span |
| `cal-empty-corpus-cta` | CalibrationTable | Empty corpus message container |
| `cal-rebuild-corpus-button` | CalibrationTable | Rebuild corpus trigger button |
| `cal-asset-type-tabs` | AssetTypeTabs | Tab list container |
| `cal-asset-type-tab-stock` | AssetTypeTabs | Stock tab button |
| `cal-asset-type-tab-btc` | AssetTypeTabs | BTC tab button |
| `cal-asset-type-tab-eth` | AssetTypeTabs | ETH tab button |
| `cal-weights-editor` | WeightsEditor | Outer wrapper div |
| `cal-weights-source-badge` | WeightsEditor | Source label badge |
| `cal-apply-ic-ir-button` | WeightsEditor | Apply IC-IR weights button |
| `cal-weights-row-{assetType}-{agent}` | WeightsEditor | One per agent/asset-type row |
| `cal-current-{assetType}-{agent}` | WeightsEditor | Current weight cell |
| `cal-exclude-toggle-{assetType}-{agent}` | WeightsEditor | Exclude checkbox |

## Recharts LineChart Notes

- Sparklines are 60×20px with `margin={{ top: 2, bottom: 2, left: 0, right: 0 }}`.
- `<YAxis hide domain={["auto", "auto"]} />` present to prevent Recharts warning about missing axis.
- `isAnimationActive={false}` prevents test-environment animation timer issues.
- In tests, Recharts is fully mocked via `vi.mock("recharts", ...)` — tests assert on the `data-stroke` attribute of the wrapper div, not on SVG `stroke` properties inside the mocked component tree.

## Legacy WeightsPage Removal

The v1.0 donut-based WeightsPage (329 lines of SVG donut + palette constants) is superseded. The new CalibrationPage is richer: it shows per-agent IC/Brier/IC-IR alongside the weights editor, replacing the static donut visualization. The `/weights` URL continues to work via a `<Navigate replace />` redirect — no 404s for bookmarks.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] data-stroke attribute on ICSparkline for testable color assertion**
- **Found during:** Task 2 implementation
- **Issue:** Recharts `<Line stroke={...}>` renders into SVG in production but is fully mocked in jsdom. Asserting `stroke` on mocked elements is brittle. The plan said "check `data-stroke` attribute" — this required the wrapper `<div>` to explicitly carry `data-stroke={stroke}`.
- **Fix:** Added `data-stroke={stroke}` to the ICSparkline wrapper div. Tests assert on wrapper attribute, not SVG internals.
- **Files modified:** `frontend/src/components/calibration/ICSparkline.tsx`

**2. [Rule 1 - Bug] CardHeader subtitle typed as string, not ReactNode**
- **Found during:** Task 3 WeightsEditor implementation
- **Issue:** Plan specified passing JSX (the source badge span) as CardHeader `subtitle`. CardHeader interface has `subtitle?: string` — TypeScript rejects JSX. Cast `as unknown as string` would fail strict mode.
- **Fix:** WeightsEditor uses an inline div header instead of `CardHeader`, fully implementing the header pattern directly. Functionality identical; CardHeader component not modified.
- **Files modified:** `frontend/src/components/calibration/WeightsEditor.tsx`

**3. [Rule 1 - Bug] Card component does not forward data-testid**
- **Found during:** Task 3 test runs (cal-weights-editor not found)
- **Issue:** `<Card data-testid="cal-weights-editor">` — the `Card` component spreads no `...rest` props, so the testid is silently dropped.
- **Fix:** Wrapped `<Card>` with an outer `<div data-testid="cal-weights-editor">`. Tests pass; no Card component modification needed.
- **Files modified:** `frontend/src/components/calibration/WeightsEditor.tsx`

**4. [Rule 1 - Bug] unused `waitFor` import in WeightsEditor.test.tsx caused tsc error**
- **Found during:** TypeScript check after Task 3 (noUnusedLocals strict mode)
- **Fix:** Removed `waitFor` from the import line.
- **Files modified:** `frontend/src/components/calibration/__tests__/WeightsEditor.test.tsx`

## Known Stubs

None — all data flows from live backend endpoints:
- Calibration metrics: GET /analytics/calibration (Phase 2 SIG-03 + this plan's rolling_ic extension)
- Weights: GET /weights, POST /weights/apply-ic-ir, PATCH /weights/override (Phase 6 Plan 01)
- Corpus rebuild: POST /analytics/calibration/rebuild-corpus (Phase 5 LIVE-01)

The `suggested_ic_ir` values are `null` (not stubs) when corpus is empty — correct behavior, results in disabled Apply button.

## Threat Model Status

All 7 STRIDE threats from plan's threat_model assessed:

| Threat ID | Disposition | Implementation |
|-----------|-------------|----------------|
| T-06-02-01 Tampering (override body) | Mitigated | TypeScript union compile-time; backend KNOWN_AGENTS allowlist (T-06-01-01) is authoritative |
| T-06-02-02 Info Disclosure (rolling IC) | Accepted | IC is internal analytics, not sensitive |
| T-06-02-03 XSS (FundamentalAgent note) | Mitigated | `{entry.note}` text node; React auto-escapes; no dangerouslySetInnerHTML |
| T-06-02-04 DoS (long rolling_ic array) | Accepted | Backend caps window at 252; 252-pt Recharts line renders in <50ms |
| T-06-02-05 Spoofing (no CSRF) | Accepted | localhost-only, solo-operator; SameSite=Lax default |
| T-06-02-06 Error Info Disclosure | Mitigated | Toast shows err.message only; ApiError.message is user-facing |
| T-06-02-07 Tampering (rebuild DoS) | Accepted | Button disabled during rebuild; no rate-limit needed at v1.1 scope |

## Self-Check: PASSED

Files verified:

- api/routes/calibration.py — FOUND (rolling_ic in both branches)
- frontend/src/api/types.ts — FOUND (AgentCalibrationEntry, CalibrationResponse present)
- frontend/src/api/endpoints.ts — FOUND (getCalibrationAnalytics, applyIcIrWeights present)
- frontend/src/App.tsx — FOUND (CalibrationPage route present)
- frontend/src/components/layout/Sidebar.tsx — FOUND (Calibration nav item present)
- frontend/src/pages/CalibrationPage.tsx — FOUND (full implementation)
- frontend/src/pages/WeightsPage.tsx — FOUND (Navigate redirect present)
- All 5 component files — FOUND
- All 7 test files — FOUND

Commits:
- 532d5ed: feat(06-02): extend calibration API with rolling_ic + add Phase 06 types/endpoints/routing
- ef7b82f: feat(06-02): add CalibrationTable + AgentCalibrationRow + ICSparkline components (LIVE-02)
- 58ecafa: feat(06-02): add AssetTypeTabs + WeightsEditor + CalibrationPage + WeightsPage redirect (LIVE-02, LIVE-03)

Test counts:
- Backend: 7 tests in test_signal_quality_03_ic_icir.py (7 passed, includes 1 new)
- Frontend: 430 tests total (up from ~394 pre-plan; 36 new tests added; 0 regressions)
- tsc --noEmit: exit 0
