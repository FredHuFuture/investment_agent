---
phase: 07-digest-analytics-completeness
reviewed: 2026-04-24T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - api/app.py
  - api/routes/digest.py
  - api/routes/drift.py
  - daemon/jobs.py
  - daemon/scheduler.py
  - data_providers/dividend_cache.py
  - data_providers/yfinance_provider.py
  - db/database.py
  - engine/analytics.py
  - engine/digest.py
  - engine/drift_detector.py
  - engine/pipeline.py
  - notifications/email_dispatcher.py
  - frontend/src/api/endpoints.ts
  - frontend/src/api/types.ts
  - frontend/src/components/calibration/AgentCalibrationRow.tsx
  - frontend/src/components/calibration/CalibrationTable.tsx
  - frontend/src/components/calibration/DriftBadge.tsx
  - frontend/src/pages/CalibrationPage.tsx
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-04-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Phase 7 delivers AN-01 (dividend-aware IRR), AN-02 (IC-IR drift detector + auto-scale + DriftBadge UI), and LIVE-04 (weekly Markdown digest + email/Telegram dispatch). Overall the phase is well-structured and the FOUND-07 two-connection pattern, never-zero-all guard, and preliminary_threshold flag are all correctly implemented. Three warnings require attention before the phase is closed as verified: a `threshold_type` string mismatch between the backend and TypeScript types that breaks DriftBadge tooltip semantics; a renormalization correctness issue when manual-override rows coexist with drifting agents; and an over-aggressive PII clamp regex that redacts the word "position" from alert messages. Four info items cover a deprecated event-loop API call, a missing `run_once` CLI entry for the drift job, a `DriftLogEntry` type missing the `id` field returned by the API, and a minor redundant no-op in `_evaluate_one`.

---

## Warnings

### WR-01: `threshold_type` literal mismatch — DriftBadge tooltip always shows wrong string

**File:** `frontend/src/components/calibration/DriftBadge.tsx:59`

**Issue:** `DriftBadge` branches on `entry.threshold_type === "absolute_floor"` to choose tooltip text. However `engine/drift_detector.py:137` writes `threshold_type = "absolute_low"` and the `drift_log` DDL in `db/database.py:740` constrains the column to `('drop_pct', 'absolute_low', 'preliminary', 'none')`. The value `"absolute_floor"` is never written to the database. The TypeScript type `DriftLogEntry.threshold_type` in `frontend/src/api/types.ts:905` compounds this by declaring `"absolute_floor"` instead of `"absolute_low"`.

Consequence: whenever an absolute-floor drift is detected (IC-IR < 0.5 for 2 consecutive weeks), the badge tooltip always shows the `drop_pct` fallback branch `"IC-IR dropped X% below 60-day avg …"` instead of the dedicated `"IC-IR floor (<0.5) breached for 2 consecutive weeks"` message, giving the operator misleading context about why the drift triggered.

**Fix:**

In `frontend/src/components/calibration/DriftBadge.tsx`, line 59:
```tsx
// Before (wrong literal)
entry.threshold_type === "absolute_floor"

// After (matches backend)
entry.threshold_type === "absolute_low"
```

In `frontend/src/api/types.ts`, line 905:
```ts
// Before
threshold_type: "pct_drop" | "absolute_floor" | "none" | null;

// After (must also add "preliminary" to match the four stored values)
threshold_type: "drop_pct" | "absolute_low" | "preliminary" | "none" | null;
```

Note: the `types.ts` declaration also uses `"pct_drop"` where the backend writes `"drop_pct"`. Both the `absolute_floor`/`absolute_low` mismatch and the `pct_drop`/`drop_pct` mismatch need fixing together.

---

### WR-02: `_apply_drift_scale` renorm denominator includes manual-override rows but UPSERT skips them — post-write weights do not sum to 1.0

**File:** `engine/drift_detector.py:239-298`

**Issue:** The SQL read on line 244 fetches ALL non-excluded agents (`excluded = 0`) including rows where `manual_override = 1`. These rows are incorporated into `total_new` (denominator, line 268) and `renorm_weights` (line 279). However the UPSERT on line 291 adds `WHERE agent_weights.manual_override = 0` so manual-override rows are silently skipped.

The net effect: suppose stock weights are TechnicalAgent=0.4 (manual, override=1), FundamentalAgent=0.4 (auto), MacroAgent=0.2 (auto), and MacroAgent drifts with scale_factor=0.5. The new_weights map becomes `{Technical: 0.4, Fundamental: 0.4, Macro: 0.1}`, total_new=0.9, renorm produces `{Technical: 0.444, Fundamental: 0.444, Macro: 0.111}`. The UPSERT skips TechnicalAgent (manual_override=1) and writes Fundamental=0.444, Macro=0.111. The actual DB sum for non-manual agents is now 0.555, not 1.0. The `load_weights_from_db` renorm on read will correct this at runtime, but the `drift_log.weight_after` value stored (0.111 for Macro) is inaccurate relative to what the pipeline will actually use, misleading the CalibrationPage audit trail.

**Fix:** Exclude `manual_override = 1` rows from the read so the renorm denominator only covers agents that will actually be written:

```python
# In _apply_drift_scale, replace the SELECT query (line 242-247):
rows = await (
    await conn.execute(
        """
        SELECT agent_name, weight FROM agent_weights
        WHERE asset_type = ? AND excluded = 0 AND manual_override = 0
        """,
        (asset_type,),
    )
).fetchall()
```

This makes `renorm_weights` match the actual post-write DB state and produces accurate `weight_after` audit values.

---

### WR-03: `_THESIS_RE` matches the word "position" — legitimate SIGNAL_REVERSAL messages are entirely redacted in digest section (d)

**File:** `engine/digest.py:57`

**Issue:** `_THESIS_RE = re.compile(r"(thesis|secret|position).*", re.IGNORECASE)` replaces everything from the first occurrence of "position" to the end of the string with `[redacted]`. Alert messages generated by `daemon/jobs.py:267-270` for SIGNAL_REVERSAL events contain phrasing like:

```
"Review position -- original thesis was BUY, re-analysis now signals SELL."
```

`_clamp_pii` applied to this message yields `[redacted]` — the entire alert message is replaced. Section (d) of the weekly digest (`_render_alerts`) applies `_clamp_pii` to the first 120 chars of every alert message, meaning all SIGNAL_REVERSAL and similar position-referencing alerts will display `[redacted]` in the digest table instead of actionable content.

The word "position" is not PII; the legitimate PII targets are dollar amounts (handled by `_DOLLAR_RE`) and thesis narrative text. The regex should target thesis content more precisely.

**Fix:**

```python
# engine/digest.py, replace line 57:

# Before — too broad, catches "position"
_THESIS_RE = re.compile(r"(thesis|secret|position).*", re.IGNORECASE)

# After — targets thesis/secret keywords only, not "position"
_THESIS_RE = re.compile(r"\b(thesis|secret)\b.*", re.IGNORECASE)
```

If stripping at the thesis/secret keyword boundary is intended (i.e., replace the matched portion with `[redacted]`), this narrows it to only match those two markers. If the intent is to fully redact the whole message when it mentions thesis content, the current `.sub("[redacted]", text)` is already correct behavior for those two keywords once "position" is removed from the alternation.

---

## Info

### IN-01: `asyncio.get_event_loop()` deprecated in Python 3.10+; use `asyncio.get_running_loop()`

**File:** `notifications/email_dispatcher.py:278`

**Issue:** `asyncio.get_event_loop()` emits a `DeprecationWarning` in Python 3.10+ when called from a coroutine that is already running inside an event loop (the normal case for an async-called method). Python 3.12 raises a `RuntimeError` in some contexts if no current loop is attached to the thread.

**Fix:**
```python
# Before
loop = asyncio.get_event_loop()
await loop.run_in_executor(None, self._send_sync, subject, html_body)

# After
loop = asyncio.get_running_loop()
await loop.run_in_executor(None, self._send_sync, subject, html_body)
```

---

### IN-02: `run_once("drift")` not wired in `MonitoringDaemon.run_once`

**File:** `daemon/scheduler.py:328-344`

**Issue:** `run_once` dispatches on `job_name` literals `"daily"`, `"weekly"`, `"regime"`, `"watchlist"`, `"prune"`, and `"digest"`. The new `run_drift_detector` job (AN-02) has no corresponding `"drift"` case, so it cannot be triggered via CLI `run-once drift`. This is an operator ergonomics gap — the drift detector can only fire via the Sunday cron or by calling the Python function directly.

Also, `daemonRunOnce` in `frontend/src/api/endpoints.ts:262` has the type union `"daily" | "weekly" | "regime" | "watchlist"` — neither `"digest"` nor `"drift"` appears, so both new jobs are missing from the frontend type. These are mismatch/dead-code issues rather than runtime errors (the backend endpoint handles unknown values with a `ValueError`).

**Fix:**
```python
# daemon/scheduler.py — add to run_once dispatch:
elif job_name == "drift":
    return await run_drift_detector(self._config.db_path, self._logger)
```

```ts
// frontend/src/api/endpoints.ts line 262 — extend union:
export const daemonRunOnce = (
  job: "daily" | "weekly" | "regime" | "watchlist" | "digest" | "drift"
) => apiPost<Record<string, unknown>>("/daemon/run-once", { job });
```

---

### IN-03: `DriftLogEntry` TypeScript interface missing the `id` field returned by the API

**File:** `frontend/src/api/types.ts:898-910`

**Issue:** `GET /drift/log` returns rows with an `id` field (line 93 of `api/routes/drift.py`). The `DriftLogEntry` interface in `types.ts` does not declare `id`. This means the field is silently dropped at the TypeScript type boundary; if any consumer ever needs to reference a specific drift_log row by id (e.g., for acknowledgement or drill-down), they would need an unsafe cast.

Not a runtime bug today (no consumer reads `id`), but incomplete type coverage that could become a problem if drift acknowledgement is added.

**Fix:**
```ts
export interface DriftLogEntry {
  id: number;         // add this field
  agent_name: string;
  // ... rest unchanged
}
```

---

### IN-04: Redundant `delta_pct = None` assignment in `_evaluate_one`

**File:** `engine/drift_detector.py:138-139`

**Issue:** Lines 138-139 contain `if delta_pct is None: delta_pct = None` — assigning `None` to a variable that is already `None` (the `absolute_low` branch only executes when `avg_icir_60d` is None or zero, so `delta_pct` was never set). This is dead code that adds noise without changing state.

**Fix:** Remove lines 138-139:
```python
# Before
if not triggered and current_icir < ICIR_FLOOR:
    triggered = True
    threshold_type = "absolute_low"
    if delta_pct is None:
        delta_pct = None  # no baseline but floor triggered  <-- remove these 2 lines

# After
if not triggered and current_icir < ICIR_FLOOR:
    triggered = True
    threshold_type = "absolute_low"
```

---

## Test Coverage Notes

The following scrutiny items from the review scope were verified clean:

- **FOUND-07 two-connection pattern**: Both `run_drift_detector` and `run_weekly_digest` use separate `log_conn` connections opened with `async with aiosqlite.connect(db_path)` for start/end job_run_log rows. The pattern is correctly applied.
- **AN-02 never-zero-all guard**: `_apply_drift_scale` line 269 checks `total_new <= 0` and returns `None` with a `logger.critical` call. The job wrapper in `daemon/jobs.py:1223` treats `weight_after is None` as a CRITICAL alert. Guard is correctly implemented.
- **AN-02 preliminary_threshold flag**: When `len(valid_ics) < 60`, `preliminary = True`, `threshold_type = "preliminary"`, and `triggered = False`. DriftBadge renders amber only. This correctly mirrors the Phase 2 pattern.
- **AN-01 dividend cache**: `DividendCache` uses atomic rename (`os.replace` on POSIX, delete-then-rename with 3 retries on Windows), 24h TTL via `mtime`, and falls back cleanly on read error. Matches FOUND-02 pattern.
- **AN-01 backward-compat**: `compute_irr_multi(dividends=None)` and `compute_irr_multi(dividends=[])` both skip dividend injection and return the same result as the pre-AN-01 two-cashflow path.
- **Phase 6 pipeline wiring closed**: `engine/pipeline.py:282-288` calls `load_weights_from_db(self._db_path)` and passes `weights=db_weights` to `SignalAggregator`. `load_weights_from_db` returns `None` when the table is empty and `SignalAggregator.__init__` falls back to `DEFAULT_WEIGHTS`. Wiring is correct.
- **APScheduler misfire_grace_time**: Both new Sunday cron entries (`drift_detector` at 17:30 and `digest_weekly` at 18:00) include `misfire_grace_time=3600`. Order guarantees digest reads fresh drift_log rows.
- **Email PII clamp**: `send_markdown_email` calls `html.escape(markdown_body)` before wrapping in `<pre>`. The digest renderer already enforces PII clamp at content-generation time (no raw dollar amounts or thesis text in sections a-e).
- **Telegram 4096-char truncation**: `run_weekly_digest` in `daemon/jobs.py:1403-1404` truncates at 3900 chars and appends `"...(truncated — full digest in email)"`. Correct.
- **`drift_log` schema**: 13 columns including `weight_before`/`weight_after`, idempotent `CREATE TABLE IF NOT EXISTS`, CHECK constraint on `threshold_type` covers all four valid values. Correct.
- **`source='ic_ir'` on auto-scale**: UPSERT in `_apply_drift_scale` sets `source = 'ic_ir'` and only updates rows where `manual_override = 0`. `source='manual'` rows are preserved.
- **DriftBadge 3 states**: `null` (no badge), amber (preliminary_threshold), red (triggered AND within 7-day window). `data-testid="cal-drift-badge-{agentName}"` present. Graceful degradation: `driftByAgent` map is empty if `driftApi.data` is undefined.
- **No new deps**: No new Python or npm packages introduced in this phase.

## Clean Files

The following reviewed files had no findings:

- `api/app.py` — drift and digest routers correctly registered with appropriate prefixes
- `api/routes/digest.py` — clean render-and-return pattern, no PII leakage
- `api/routes/drift.py` — graceful empty-table fallback, correct bool coercion for SQLite integers
- `data_providers/dividend_cache.py` — correct TTL logic, atomic-rename pattern, empty-list write-through
- `data_providers/yfinance_provider.py` — `get_dividends` correctly returns `[]` on error or empty series
- `engine/analytics.py` — `compute_irr_multi` backward-compatible, scipy brentq bounds reasonable
- `engine/digest.py` — sections (a)-(e) structurally correct; all DB queries wrapped in try/except for graceful degradation (noting WR-03 above on _clamp_pii regex)
- `engine/pipeline.py` — Phase 6 pipeline wiring correctly closed
- `frontend/src/api/endpoints.ts` — `getDriftLog` wired to correct endpoint
- `frontend/src/components/calibration/AgentCalibrationRow.tsx` — DriftBadge integration correct, backward-compat `driftEntry = null` default
- `frontend/src/components/calibration/CalibrationTable.tsx` — correct asset_type-filtered `driftByAgent` prop flow
- `frontend/src/pages/CalibrationPage.tsx` — graceful `driftApi.data` undefined handling, no stuck spinner on drift fetch failure
- `db/database.py` — `drift_log` DDL idempotent, index covers `(agent_name, asset_type, evaluated_at DESC)`, `agent_weights` seeding correct
- `daemon/jobs.py` — both new jobs (`run_drift_detector`, `run_weekly_digest`) follow FOUND-07 two-connection pattern; never-raise contract honored
- `daemon/scheduler.py` — both Sunday cron entries registered with correct `misfire_grace_time=3600`; separate function names; no overlap

---

_Reviewed: 2026-04-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
