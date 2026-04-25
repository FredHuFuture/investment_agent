---
phase: 07-digest-analytics-completeness
verified: 2026-04-24T23:30:00Z
status: gaps_found
score: 4/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "TypeScript strict compile (tsc --noEmit) passes clean on all frontend source and test files"
    status: failed
    reason: "WR-01 fix (threshold_type literals) was applied to DriftBadge.test.tsx but NOT to AgentCalibrationRow.test.tsx (lines 112, 147) or CalibrationPage.test.tsx (line 248) — all three still use the old literal \"pct_drop\" which is now an invalid value per the updated DriftLogEntry.threshold_type union type (\"drop_pct\" | \"absolute_low\" | \"preliminary\" | \"none\" | null). npx tsc --noEmit exits non-zero with 3 TS2322 errors."
    artifacts:
      - path: "frontend/src/components/calibration/__tests__/AgentCalibrationRow.test.tsx"
        issue: "line 112 and 147: threshold_type: \"pct_drop\" — should be \"drop_pct\""
      - path: "frontend/src/pages/__tests__/CalibrationPage.test.tsx"
        issue: "line 248: threshold_type: \"pct_drop\" — should be \"drop_pct\""
    missing:
      - "Change threshold_type: \"pct_drop\" to \"drop_pct\" at AgentCalibrationRow.test.tsx lines 112 and 147"
      - "Change threshold_type: \"pct_drop\" to \"drop_pct\" at CalibrationPage.test.tsx line 248"
human_verification:
  - test: "Email delivery end-to-end"
    expected: "Sunday digest arrives in inbox with all 5 sections visible, <pre>-formatted Markdown, correct date header"
    why_human: "Requires live SMTP credentials, real email relay, and calendar day (Sunday) or manual run_once trigger — cannot automate without external service"
  - test: "Live corpus drift detection (non-preliminary threshold)"
    expected: "After running evaluate_drift against a populated corpus (60+ weekly IC samples), at least one agent shows a real drift_log row with preliminary_threshold=0 and triggered=1 or triggered=0 based on actual IC-IR values"
    why_human: "Production corpus required; test suite uses synthetic fixtures that trigger preliminary_threshold=1 by design. The automated path is correct but the non-preliminary production path needs a real corpus to validate end-to-end."
  - test: "CalibrationPage badge visible in browser"
    expected: "After triggering a drift condition (e.g., via run_once drift CLI), navigating to /calibration shows an amber or red badge on the affected agent row within the 7-day window"
    why_human: "Browser rendering verification — automated Vitest tests confirm the component logic but visual rendering and end-to-end API wiring need live browser confirmation"
---

# Phase 7: Digest + Analytics Completeness Verification Report

**Phase Goal:** The user receives (or can trigger on demand) a weekly Markdown digest that surfaces the week's key portfolio signals in one artifact; dividend-paying positions report accurately higher IRR; and a drift detector automatically flags and down-weights agents whose IC-IR has degraded — so the weekly review workflow is self-contained and signal trust is maintained without manual intervention.

**Verified:** 2026-04-24T23:30:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /api/v1/digest/weekly returns Markdown with all 5 H2 sections | ✓ VERIFIED | `engine/digest.py` exports 5 HEADER_* constants; `api/routes/digest.py` router registered in `api/app.py` under `/digest` prefix; render_weekly_digest spot-check returns all 5 headers |
| 2 | APScheduler Sunday 18:00 digest_weekly + opt-in email | ✓ VERIFIED | `daemon/scheduler.py` registers `digest_weekly` at `hour=18, minute=0, day_of_week=sun, misfire_grace_time=3600`; `EmailDispatcher.send_markdown_email` exists with `html.escape()` + `<pre>` wrap; graceful skip when `is_configured=False` |
| 3 | compute_irr_multi(dividends=[...]) strictly > same call with dividends=[] | ✓ VERIFIED | `engine/analytics.py` line 72-73 accepts `dividends` + `entry_date` kwargs; spot-check: IRR without dividends=0.0997, with dividends=0.1210 (strictly greater); 13 test_an01_dividend_irr.py tests pass |
| 4 | Drift detector writes scaled weight to agent_weights when IC-IR degrades; CalibrationPage shows drift badge | ✓ VERIFIED | `engine/drift_detector.py` has `evaluate_drift`, `MIN_SAMPLES_FOR_REAL_THRESHOLD=60`, `ICIR_FLOOR=0.5`; `_apply_drift_scale` SELECT filters `manual_override=0` (WR-02 fix); never-zero-all guard at `total_new <= 0`; `engine/pipeline.py` calls `load_weights_from_db(self._db_path)` (Phase 6 deferral closed) |
| 5 | TypeScript strict compile passes (tsc --noEmit exit 0) | ✗ FAILED | `npx tsc --noEmit` exits non-zero with 3 TS2322 errors: `"pct_drop"` literal in `AgentCalibrationRow.test.tsx` (lines 112, 147) and `CalibrationPage.test.tsx` (line 248) is not assignable to the corrected `DriftLogEntry.threshold_type` union after WR-01 fix |

**Score:** 4/5 truths verified (1 TypeScript compile gap)

---

## Deferred Items

None — all identified issues are either verified or classified as gaps/human-verification.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `engine/digest.py` | render_weekly_digest + 5 section renderers | ✓ VERIFIED | Exists, 388+ lines, 5 HEADER_* constants, _clamp_pii regex narrowed (WR-03 fix: `\b(thesis|secret)\b.*`) |
| `engine/drift_detector.py` | evaluate_drift + _apply_drift_scale | ✓ VERIFIED | Exists, 200+ lines, MIN_SAMPLES_FOR_REAL_THRESHOLD=60, ICIR_FLOOR=0.5, FOUND-07 pattern |
| `engine/analytics.py` | compute_irr_multi with dividends kwarg | ✓ VERIFIED | Backward-compat dividends=None/[] path preserved |
| `data_providers/dividend_cache.py` | DividendCache Parquet sibling cache | ✓ VERIFIED | data/cache/dividends/{ticker}.parquet, 24h TTL, atomic rename |
| `data_providers/yfinance_provider.py` | get_dividends async method | ✓ VERIFIED | `async def get_dividends` at line 224 |
| `engine/pipeline.py` | load_weights_from_db wired into analyze_ticker | ✓ VERIFIED | Lines 280-283 call `load_weights_from_db(self._db_path)`, pass `weights=db_weights` to SignalAggregator |
| `db/database.py` | drift_log DDL (CREATE TABLE IF NOT EXISTS) | ✓ VERIFIED | Line 731: `CREATE TABLE IF NOT EXISTS drift_log` with 13 columns; CHECK constraint includes `'drop_pct', 'absolute_low', 'preliminary', 'none'` |
| `api/routes/drift.py` | GET /drift/log router | ✓ VERIFIED | router exported, registered in api/app.py under `/drift` prefix |
| `api/routes/digest.py` | POST /digest/weekly router | ✓ VERIFIED | PlainTextResponse with media_type="text/markdown", registered under `/digest` |
| `daemon/jobs.py` | run_drift_detector + run_weekly_digest | ✓ VERIFIED | Both async functions exist and are importable |
| `daemon/scheduler.py` | Sunday 17:30 drift + Sunday 18:00 digest crons | ✓ VERIFIED | Both CronTrigger entries with misfire_grace_time=3600; drift at 17:30, digest at 18:00 |
| `notifications/email_dispatcher.py` | send_markdown_email additive method | ✓ VERIFIED | Method exists, uses html.escape() + `<pre>` wrap, returns False when not configured |
| `frontend/src/components/calibration/DriftBadge.tsx` | 3-state badge component | ✓ VERIFIED | Exists, 3 states (null/amber preliminary/red triggered), data-testid="cal-drift-badge-{agentName}" |
| `frontend/src/api/types.ts` | DriftLogEntry + DriftLogResponse interfaces | ✓ VERIFIED | threshold_type corrected to `"drop_pct" \| "absolute_low" \| "preliminary" \| "none" \| null` (WR-01 fix) |
| `frontend/src/api/endpoints.ts` | getDriftLog wrapper | ✓ VERIFIED | Line 586: `apiGet<DriftLogResponse>("/drift/log")` |
| `frontend/src/pages/CalibrationPage.tsx` | Third useApi for /drift/log + driftByAgent memo | ✓ VERIFIED | getDriftLog imported, useApi at line 62, useMemo at line 69, driftByAgent threaded to CalibrationTable at line 163 |
| `frontend/src/components/calibration/AgentCalibrationRow.tsx` | driftEntry prop + DriftBadge inline | ✓ VERIFIED | optional `driftEntry` prop at line 8, DriftBadge rendered at line 84 |
| `frontend/src/components/calibration/CalibrationTable.tsx` | driftByAgent prop passthrough | ✓ VERIFIED | optional prop at line 9, threaded to AgentCalibrationRow at line 89 |
| `frontend/src/components/calibration/__tests__/AgentCalibrationRow.test.tsx` | Contains stale "pct_drop" literal | ✗ STUB (type error) | Lines 112, 147 use `threshold_type: "pct_drop"` — invalid after WR-01 types.ts fix |
| `frontend/src/pages/__tests__/CalibrationPage.test.tsx` | Contains stale "pct_drop" literal | ✗ STUB (type error) | Line 248 uses `threshold_type: "pct_drop"` — invalid after WR-01 types.ts fix |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| engine/pipeline.py::analyze_ticker | engine/aggregator.py::load_weights_from_db | `await load_weights_from_db(self._db_path)` | ✓ WIRED | Lines 280-283; closes Phase 6 deferral |
| engine/drift_detector.py::_apply_drift_scale | agent_weights table | `ON CONFLICT ... WHERE manual_override=0` (SELECT also filters) | ✓ WIRED | SELECT at line 247 filters `manual_override = 0`; UPSERT at line 294 guards same |
| daemon/scheduler.py::_setup_scheduler | daemon/jobs.py::run_drift_detector | CronTrigger sun 17:30 | ✓ WIRED | Lines 155-164 register drift_detector cron |
| daemon/scheduler.py::_setup_scheduler | daemon/jobs.py::run_weekly_digest | CronTrigger sun 18:00 | ✓ WIRED | Lines 169-180 register digest_weekly cron |
| api/app.py | api/routes/drift.py::router | include_router prefix='/drift' | ✓ WIRED | Lines 138-140 |
| api/app.py | api/routes/digest.py::router | include_router prefix='/digest' | ✓ WIRED | Lines 142-144 |
| engine/digest.py::render_weekly_digest | drift_log table | `FROM drift_log WHERE evaluated_at >= ?` | ✓ WIRED | Line 243 in _get_icir_movers |
| engine/digest.py::render_weekly_digest | monitoring_alerts via AlertStore | `get_recent_alerts(acknowledged=0)` | ✓ WIRED | Lines 295-308 in _get_open_alerts |
| notifications/email_dispatcher.py::send_markdown_email | EmailDispatcher._send_async | wraps Markdown in `<pre>`, calls _send_async | ✓ WIRED | Lines 264-270 |
| frontend/src/api/endpoints.ts::getDriftLog | GET /drift/log | `apiGet<DriftLogResponse>("/drift/log")` | ✓ WIRED | Line 586-587 |
| frontend/src/pages/CalibrationPage.tsx | frontend AgentCalibrationRow via CalibrationTable | `driftByAgent={driftByAgent}` prop | ✓ WIRED | Line 163 |
| frontend/src/components/calibration/DriftBadge.tsx | frontend/src/api/types.ts::DriftLogEntry | imports DriftLogEntry as prop type | ✓ WIRED | Line 1: `import type { DriftLogEntry }` |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| engine/digest.py | movers list | `drift_log` table query | Yes — real aiosqlite SELECT | ✓ FLOWING |
| engine/digest.py | bench dict | `PortfolioAnalytics.get_benchmark_comparison` | Yes — real portfolio_snapshots | ✓ FLOWING |
| engine/digest.py | flips list | `signal_history` query | Yes — real aiosqlite SELECT with 7d cutoff | ✓ FLOWING |
| engine/digest.py | alerts list | `AlertStore.get_recent_alerts(acknowledged=0)` | Yes — real monitoring_alerts | ✓ FLOWING |
| CalibrationPage.tsx | driftData | `getDriftLog()` via useApi | Yes — GET /drift/log queries drift_log table | ✓ FLOWING |
| DriftBadge.tsx | entry prop | driftByAgent[name] from CalibrationPage | Derives from driftData | ✓ FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command/Check | Result | Status |
|----------|--------------|--------|--------|
| Dividend IRR strictly greater for MSFT/KO fixtures | `compute_irr_multi` with dividends=[(date,2.0)] vs [] | 0.1210 > 0.0997 | ✓ PASS |
| All 5 H2 headers in HEADER_* constants | Python import check | All 5 present with correct H2 text | ✓ PASS |
| APScheduler digest_weekly cron fields | `MonitoringDaemon._setup_scheduler()` introspection | sun/18:00/misfire_grace_time=3600 | ✓ PASS |
| APScheduler drift_detector cron fields | Same introspection | sun/17:30/registered | ✓ PASS |
| WR-02: SELECT filters manual_override=0 | grep engine/drift_detector.py | `WHERE asset_type = ? AND excluded = 0 AND manual_override = 0` at line 247 | ✓ PASS |
| WR-03: "position" word survives _clamp_pii | `_clamp_pii("Review position -- original thesis...")` | "Review position -- original [redacted]" — position survives | ✓ PASS |
| WR-01: DriftBadge uses "absolute_low" literal | grep DriftBadge.tsx | `entry.threshold_type === "absolute_low"` | ✓ PASS |
| WR-01: types.ts threshold_type corrected | grep types.ts | `"drop_pct" \| "absolute_low" \| "preliminary" \| "none" \| null` | ✓ PASS |
| tsc --noEmit frontend compile | `cd frontend && npx tsc --noEmit` | **FAIL**: 3 TS2322 errors in test files using stale `"pct_drop"` | ✗ FAIL |
| Vitest DriftBadge + AgentCalibrationRow + CalibrationPage | npx vitest run 3 test files | 27 tests pass | ✓ PASS |
| run_drift_detector + run_weekly_digest importable | Python import check | Both OK | ✓ PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| LIVE-04 | 07-02 | Weekly digest POST endpoint + APScheduler + email | ✓ SATISFIED | `engine/digest.py`, `api/routes/digest.py`, `daemon/scheduler.py` Sunday 18:00, `send_markdown_email` |
| AN-01 | 07-01 | Dividend-aware IRR via compute_irr_multi(dividends=...) | ✓ SATISFIED | `engine/analytics.py` lines 72-73 backward-compat kwargs; 13 tests pass; strict-greater IRR verified |
| AN-02 | 07-01, 07-03 | IC-IR drift detector + auto-scale + DriftBadge UI | ✓ SATISFIED | `engine/drift_detector.py` evaluate_drift; `_apply_drift_scale` writes agent_weights; CalibrationPage DriftBadge wired; Phase 6 pipeline deferral closed |

---

## Anti-Patterns Found

| File | Location | Pattern | Severity | Impact |
|------|----------|---------|----------|--------|
| `frontend/src/components/calibration/__tests__/AgentCalibrationRow.test.tsx` | Lines 112, 147 | `threshold_type: "pct_drop"` — stale literal, type error | ✗ Blocker | TypeScript compile fails (`tsc --noEmit` exits non-zero); Vitest passes at runtime because it skips type checking |
| `frontend/src/pages/__tests__/CalibrationPage.test.tsx` | Line 248 | `threshold_type: "pct_drop"` — stale literal, type error | ✗ Blocker | Same root cause as above |
| `frontend/src/components/calibration/DriftBadge.tsx` | Line 30 (comment only) | Comment still says `"pct_drop / absolute_floor"` — stale docs | ℹ Info | Documentation mismatch only; no runtime impact |
| `notifications/email_dispatcher.py` | Line ~278 | `asyncio.get_event_loop()` (IN-01, deferred from review) | ℹ Info | DeprecationWarning on Python 3.10+, RuntimeError risk on 3.12 in some thread contexts; deferred by reviewer as out of fix_scope=critical_warning |

---

## Human Verification Required

### 1. Email delivery end-to-end

**Test:** Configure SMTP env vars (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_FROM_EMAIL`, `ALERT_TO_EMAILS`), then either wait for Sunday 18:00 or run `python -m daemon.scheduler run-once digest` (or equivalent CLI), then open inbox.

**Expected:** Email arrives with subject "Investment Agent — Weekly Digest YYYY-MM-DD"; body shows the 5 sections in `<pre>`-formatted dark-theme HTML; no raw dollar amounts; no thesis text; Markdown renders cleanly in email client.

**Why human:** Requires live SMTP credentials, real email relay, and cannot be automated without external mail server.

---

### 2. Live corpus drift detection (non-preliminary path)

**Test:** With a populated corpus (60+ weekly IC samples for at least one agent), run `evaluate_drift(db_path)` and inspect `drift_log` for rows with `preliminary_threshold=0`.

**Expected:** At least one agent × asset_type combination shows `preliminary_threshold=0` and `triggered=0` or `1` depending on actual IC-IR values — confirming the non-preliminary code path executes.

**Why human:** All automated tests use synthetic fixtures that deliberately keep the IC sample count below 60 to trigger `preliminary_threshold=1`. Production corpus is required to validate the non-preliminary branch.

---

### 3. CalibrationPage badge visible in browser

**Test:** Trigger a drift condition by running `evaluate_drift` against a test DB where an agent has IC-IR below threshold, then navigate to `/calibration` in the browser.

**Expected:** The affected agent's row shows an amber "Preliminary" or red "Drift Detected" badge inline next to the IC-IR value, within 7 days of evaluation.

**Why human:** Browser rendering and end-to-end API call chain (frontend → GET /drift/log → drift_log table) require live browser verification despite Vitest tests confirming component logic.

---

## Gaps Summary

**One gap blocking TypeScript compile:**

The WR-01 code review fix (correcting `threshold_type` literals from `"pct_drop"` to `"drop_pct"` and from `"absolute_floor"` to `"absolute_low"`) was correctly applied to `frontend/src/api/types.ts` and `frontend/src/components/calibration/__tests__/DriftBadge.test.tsx`. However, two other test files that also construct `DriftLogEntry` fixtures were missed:

- `frontend/src/components/calibration/__tests__/AgentCalibrationRow.test.tsx`: lines 112 and 147 use `threshold_type: "pct_drop"` — should be `"drop_pct"`
- `frontend/src/pages/__tests__/CalibrationPage.test.tsx`: line 248 uses `threshold_type: "pct_drop"` — should be `"drop_pct"`

These are test-file-only errors. All production source files compile cleanly. Vitest runs pass because Vitest does not perform type checking. The fix is two-line substitutions.

**Root cause:** The review fix scope identified the DriftBadge test fixture as stale but the fix propagation did not cover all test files that construct `DriftLogEntry` objects.

**Impact:** `npx tsc --noEmit` fails (exit 1) with 3 TS2322 errors. CI pipelines that run tsc before Vitest would block.

---

_Verified: 2026-04-24T23:30:00Z_
_Verifier: Claude (gsd-verifier)_
