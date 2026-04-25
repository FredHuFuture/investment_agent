---
phase: 07-digest-analytics-completeness
fixed_at: 2026-04-24T23:07:00Z
review_path: .planning/phases/07-digest-analytics-completeness/07-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 7: Code Review Fix Report

**Fixed at:** 2026-04-24T23:07:00Z
**Source review:** `.planning/phases/07-digest-analytics-completeness/07-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (WR-01, WR-02, WR-03 — Info findings IN-01 through IN-04 deferred per fix_scope=critical_warning)
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: `threshold_type` literal mismatch — DriftBadge tooltip always shows wrong string

**Files modified:** `frontend/src/api/types.ts`, `frontend/src/components/calibration/DriftBadge.tsx`, `frontend/src/components/calibration/__tests__/DriftBadge.test.tsx`
**Commit:** `269bb66`
**Applied fix:**
- `types.ts` line 905: changed `"pct_drop" | "absolute_floor" | "none" | null` to `"drop_pct" | "absolute_low" | "preliminary" | "none" | null` — matching the four values the backend writes and the DB CHECK constraint allows.
- `DriftBadge.tsx` line 59: changed branch condition from `entry.threshold_type === "absolute_floor"` to `entry.threshold_type === "absolute_low"` so the dedicated floor-breach tooltip text is now reachable.
- `DriftBadge.test.tsx`: updated the existing `"absolute_floor"` test case to use `"absolute_low"`, updated the default `makeEntry` fixture from `"pct_drop"` to `"drop_pct"`, and added a new explicit test `"tooltip text for threshold_type=absolute_low matches backend canonical string"` asserting exact tooltip text.
- All 10 DriftBadge tests pass.

---

### WR-02: `_apply_drift_scale` renorm denominator includes manual-override rows but UPSERT skips them

**Files modified:** `engine/drift_detector.py`, `tests/test_an02_drift_detector.py`
**Commit:** `c6b8a48`
**Applied fix:**
- `engine/drift_detector.py` lines 239-251: added `AND manual_override = 0` to the SELECT query that loads agent weights for the renorm denominator. Previously the SELECT fetched all `excluded=0` rows (including `manual_override=1`), causing the denominator to over-count agents that the UPSERT's `WHERE manual_override = 0` clause would then skip — leaving non-manual weights summing to less than 1.0 in the DB.
- `tests/test_an02_drift_detector.py`: added `test_renorm_denominator_excludes_manual_override_rows` which seeds a 3-agent scenario (TechnicalAgent manual_override=1, FundamentalAgent auto, MacroAgent auto drifting), calls `_apply_drift_scale`, and asserts the written non-manual weights sum to exactly 1.0 (within 1e-6) and the manual_override row is untouched.
- All 12 drift detector tests pass.

---

### WR-03: `_THESIS_RE` matches the word "position" — SIGNAL_REVERSAL messages fully redacted

**Files modified:** `engine/digest.py`, `tests/test_live_04_digest.py`
**Commit:** `fbc55c1`
**Applied fix:**
- `engine/digest.py` line 57: changed `_THESIS_RE = re.compile(r"(thesis|secret|position).*", re.IGNORECASE)` to `_THESIS_RE = re.compile(r"\b(thesis|secret)\b.*", re.IGNORECASE)`. Removed `position` from the alternation (it is not PII) and added word-boundary anchors `\b` to prevent partial-word matches. Daemon-generated messages like "Review position -- original signal was BUY..." now pass through the PII clamp intact.
- `tests/test_live_04_digest.py`: added `test_digest_pii_clamp_position_word_not_redacted` (Test 8) that seeds a SIGNAL_REVERSAL alert containing "position", "BUY", and "SELL" and asserts those words survive in the digest body; also seeds a THESIS_DRIFT alert containing "thesis" and asserts "long-term growth" (the thesis narrative) is still redacted.
- All 8 digest tests pass.

## Skipped Issues

None.

## Deferred Info Findings (outside fix_scope)

The following Info findings were out of scope per `fix_scope: critical_warning` and are recorded here for follow-up:

- **IN-01** (`notifications/email_dispatcher.py:278`): `asyncio.get_event_loop()` deprecated — replace with `asyncio.get_running_loop()`. Low risk on Python 3.12 but will emit DeprecationWarnings.
- **IN-02** (`daemon/scheduler.py:328-344`): `run_once("drift")` not wired in `MonitoringDaemon.run_once`; `daemonRunOnce` TS type union missing `"digest"` and `"drift"`. Operator ergonomics gap, no runtime error.
- **IN-03** (`frontend/src/api/types.ts:898-910`): `DriftLogEntry` interface missing `id: number` field returned by `GET /drift/log`. No current consumer reads `id`, but incomplete type coverage.
- **IN-04** (`engine/drift_detector.py:138-139`): Dead `if delta_pct is None: delta_pct = None` assignment in `_evaluate_one`. Cosmetic noise, no behavioral impact.

---

_Fixed: 2026-04-24T23:07:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
