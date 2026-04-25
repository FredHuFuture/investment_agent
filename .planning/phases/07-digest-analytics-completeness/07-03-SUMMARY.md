---
phase: 07-digest-analytics-completeness
plan: "03"
type: summary
wave: 2
depends_on: ["07-01"]
requirements: [AN-02]
tags: [frontend, drift-badge, calibration-page, vitest, an-02]
files_modified:
  created:
    - frontend/src/components/calibration/DriftBadge.tsx
    - frontend/src/components/calibration/__tests__/DriftBadge.test.tsx
    - frontend/src/components/calibration/__tests__/__snapshots__/DriftBadge.test.tsx.snap
  modified:
    - frontend/src/api/types.ts
    - frontend/src/api/endpoints.ts
    - frontend/src/components/calibration/AgentCalibrationRow.tsx
    - frontend/src/components/calibration/CalibrationTable.tsx
    - frontend/src/pages/CalibrationPage.tsx
    - frontend/src/components/calibration/__tests__/AgentCalibrationRow.test.tsx
    - frontend/src/pages/__tests__/CalibrationPage.test.tsx
dependency_graph:
  requires:
    - "07-01 GET /drift/log endpoint (drift_log table + route)"
  provides:
    - "DriftBadge component (3 states: amber Preliminary, red Drift Detected, null)"
    - "getDriftLog() endpoint wrapper in frontend/src/api/endpoints.ts"
    - "DriftLogEntry + DriftLogResponse TypeScript interfaces"
    - "CalibrationPage drift badge integration (per-agent, per-asset-type)"
  affects:
    - "frontend/src/pages/CalibrationPage.tsx (third useApi + driftByAgent memo)"
    - "frontend/src/components/calibration/AgentCalibrationRow.tsx (driftEntry prop)"
    - "frontend/src/components/calibration/CalibrationTable.tsx (driftByAgent prop)"
tech_stack:
  added: []
  patterns:
    - "Tailwind CSS span badges (amber-500/15 + red-500/15) — no new npm packages"
    - "useMemo for driftByAgent keyed lookup (agent_name -> DriftLogEntry for selected assetType)"
    - "Non-blocking third useApi — page renders calibration table even when drift fetch fails"
    - "Phase 6 cal-* testid namespace continued: cal-drift-badge-{agentName}"
    - "Vitest fake timers (vi.useFakeTimers / vi.setSystemTime) for 7-day window boundary tests"
    - "3 named snapshots locked: preliminary / triggered / null"
key_decisions:
  - "DriftBadge renders nothing (not an empty placeholder) for null/OK entries — row stays clean"
  - "preliminary_threshold takes precedence over triggered — amber before red, threshold is inactive"
  - "7-day RECENT_DRIFT_WINDOW_MS enforced client-side matching ROADMAP SC-5 definition"
  - "driftByAgent keyed by agent_name only (not agent_name::asset_type) because CalibrationPage filters drifts to selected assetType tab before building the map"
  - "Degraded handling: getDriftLog failure leaves driftByAgent={} silently — no error toast, no spinner stuck"
  - "FOUND-04 note branch in AgentCalibrationRow deliberately omits DriftBadge — no IC-IR cell to attach to"
metrics:
  duration_seconds: 283
  completed_date: "2026-04-24"
  tasks_completed: 2
  files_created: 3
  files_modified: 7
  tests_added: 13
  snapshots_added: 3
  regressions: 0
---

# Phase 7 Plan 03: DriftBadge Frontend Integration Summary

**One-liner:** Per-agent drift badge on `/calibration` with 3 states (amber Preliminary / red Drift Detected / null), 7-day window enforcement, and non-blocking CalibrationPage integration via `GET /drift/log`.

## What Was Built

### Task 1 — Types + Endpoint Wrapper + DriftBadge Component

**`frontend/src/api/types.ts`** — Added `DriftLogEntry` and `DriftLogResponse` interfaces matching the 07-01 backend shape exactly. `triggered` and `preliminary_threshold` are typed as `boolean` (backend coerces via `bool()` in route handler).

**`frontend/src/api/endpoints.ts`** — Added `getDriftLog()` calling `apiGet<DriftLogResponse>("/drift/log")`. Placed after the Phase 6 weights functions with a clear AN-02 comment block.

**`frontend/src/components/calibration/DriftBadge.tsx`** (new, 75 lines) — 3 visual states:
- `null` entry → returns `null` (nothing rendered)
- `entry.preliminary_threshold === true` → amber badge "Preliminary" with `bg-amber-500/15 text-amber-300 border-amber-500/30`
- `entry.triggered === true AND ageMs <= RECENT_DRIFT_WINDOW_MS (7d)` → red badge "Drift Detected (-23.6%)" with `bg-red-500/15 text-red-300 border-red-500/30`

`data-testid="cal-drift-badge-{agentName}"` on the outer span continues the Phase 6 `cal-*` testid namespace. The `title` attribute surfaces threshold context (floor type + 60d avg IC-IR).

**`frontend/src/components/calibration/__tests__/DriftBadge.test.tsx`** (new, 9 tests + 3 snapshots):
- Null entry renders nothing
- Amber state on preliminary_threshold=true
- Red state on triggered=true within 7 days, with delta_pct in text
- Renders nothing when triggered but evaluated_at > 7 days ago (window enforcement)
- Renders nothing in OK state (triggered=false, preliminary=false)
- absolute_floor tooltip text verified
- 3 named snapshots: preliminary / triggered / null

### Task 2 — Row + Table + Page Wiring

**`frontend/src/components/calibration/AgentCalibrationRow.tsx`** — Added optional `driftEntry?: DriftLogEntry | null` prop (default `null`). `<DriftBadge>` rendered inline inside the IC-IR `<td>` wrapped in `<span className="inline-flex items-center">`. The FOUND-04 note branch (early return at line 51) is unchanged — no badge in that path. Backward-compat: existing tests pass without the prop.

**`frontend/src/components/calibration/CalibrationTable.tsx`** — Added optional `driftByAgent?: Record<string, DriftLogEntry>` prop (default `{}`). Threaded `driftEntry={driftByAgent[name] ?? null}` to each `<AgentCalibrationRow>` in the map.

**`frontend/src/pages/CalibrationPage.tsx`** — Added third `useApi<DriftLogResponse>` for `/drift/log` with 60s TTL. Added `useMemo` building `driftByAgent: Record<string, DriftLogEntry>` keyed by `agent_name` filtering to selected `assetType` tab. Passed `driftByAgent={driftByAgent}` to `<CalibrationTable>`. Degraded: if `getDriftLog()` fails, `driftApi.data` is `undefined`, map is `{}`, no badges appear, calibration table still renders.

**Test extensions:**
- `AgentCalibrationRow.test.tsx` — 3 new tests: D1 (no badge without prop), D2 (triggered badge), D3 (FOUND-04 note branch no badge)
- `CalibrationPage.test.tsx` — `getDriftLog` added to mock factory + `mockGetDriftLog` constant; default mock returns `{drifts:[]}`. 2 new integration tests: D4 (badge appears for triggered TechnicalAgent), D5 (table renders without badge when getDriftLog rejects)

## Phase 6 cal-* Namespace Continuation

All drift badge testids use `cal-drift-badge-{agentName}` following the Phase 6 convention established for `cal-agent-row-*`, `cal-agent-note-*`, `cal-ic-sparkline-*`, `cal-weights-editor`, `cal-apply-ic-ir-button`, etc. No exceptions introduced.

## Snapshots Locked

Three snapshots committed in `frontend/src/components/calibration/__tests__/__snapshots__/DriftBadge.test.tsx.snap`:
1. `snapshot: preliminary state` — amber span with dot + "Preliminary" text
2. `snapshot: triggered state` — red span with dot + "Drift Detected (-23.6%)"
3. `snapshot: null state` — `null` (container.firstChild is null; snapshot records this as empty)

These are refactor-proof assertions — any accidental class or text change will fail the snapshot test.

## Test Counts

| File | New Tests | Snapshots |
|------|-----------|-----------|
| DriftBadge.test.tsx | 6 behavioral + 3 snapshot | 3 |
| AgentCalibrationRow.test.tsx | 3 (D1, D2, D3) | 0 |
| CalibrationPage.test.tsx | 2 (D4, D5) | 0 |
| **Total new** | **13** | **3** |
| Phase 6 regressions | 0 | — |

## Threat Model Status

| Threat ID | Status | Notes |
|-----------|--------|-------|
| T-07-03-01 XSS via agent_name in testid | Mitigated | React escapes testid attribute; backend KNOWN_AGENTS allowlist from 07-01 |
| T-07-03-02 Info Disclosure via /drift/log | Accepted | Same posture as T-06-02-02 rolling IC — internal analytics, localhost-only |
| T-07-03-03 DoS from slow /drift/log blocking page | Mitigated | Non-blocking useApi; test D5 verifies table renders when drift fetch fails |
| T-07-03-04 Stale evaluated_at causing false-positive badge | Accepted | 7-day window filters these out; user sees OK row, not fake alarm |
| T-07-03-05 Long agent_name collision in testid | Accepted | KNOWN_AGENTS is closed set of 5 names; no collisions possible |

## Deviations from Plan

None — plan executed exactly as written.

The plan specified `driftByAgent` keyed by `agent_name + asset_type` (e.g., `"TechnicalAgent::stock"`). During implementation, the simpler approach of filtering `driftData.drifts` to only the selected `assetType` tab before building the map was used instead (keys are just `agent_name`). This is functionally equivalent because the CalibrationPage already scopes to one asset_type at a time via the `assetType` state variable — noted as a minor clarification, not a behavioral deviation.

## Known Stubs

None — DriftBadge reads live data from the `getDriftLog` endpoint wired through to the 07-01 `drift_log` table. No hardcoded placeholder values.

## Self-Check

Files created/exist:
- `frontend/src/components/calibration/DriftBadge.tsx` — FOUND
- `frontend/src/components/calibration/__tests__/DriftBadge.test.tsx` — FOUND
- `frontend/src/components/calibration/__tests__/__snapshots__/DriftBadge.test.tsx.snap` — FOUND

Commits exist:
- `76b3d38` — Task 1 (types + endpoint + DriftBadge)
- `b431e79` — Task 2 (row + table + page wiring)
