---
phase: "07"
plan: "02"
subsystem: digest-engine
tags: [digest, weekly, markdown, email, telegram, apscheduler, live-04, pii-clamp]
dependency_graph:
  requires:
    - 07-01  # drift_log table built by AN-02 — digest section (c) reads it
    - 04-01  # PortfolioAnalytics.get_benchmark_comparison — section (a)
    - 03-04  # EmailDispatcher + TelegramDispatcher — delivery channels
  provides:
    - weekly-digest-markdown   # render_weekly_digest() returns PII-clamped Markdown
    - digest-endpoint          # POST /digest/weekly exposes on-demand preview
    - digest-email-method      # EmailDispatcher.send_markdown_email (additive)
    - digest-cron              # Sunday 18:00 APScheduler job (after 17:30 drift detector)
  affects:
    - 07-03  # CalibrationPage drift badge reads drift_log (same source as section c)
tech_stack:
  added: []
  patterns:
    - "FOUND-07 two-connection pattern in run_weekly_digest"
    - "PII clamp: _clamp_pii() strips dollar amounts + thesis markers (T-07-02-02)"
    - "html.escape() in send_markdown_email <pre> wrap (T-07-02-01)"
    - "APScheduler misfire_grace_time=3600 on Sunday 18:00 cron"
    - "Telegram 3900-char truncation with marker (T-07-02-04)"
key_files:
  created:
    - engine/digest.py
    - api/routes/digest.py
    - tests/test_live_04_digest.py
    - tests/test_live_04_digest_email.py
    - tests/test_live_04_digest_scheduler.py
  modified:
    - notifications/email_dispatcher.py
    - daemon/jobs.py
    - daemon/scheduler.py
    - api/app.py
decisions:
  - "PII clamp uses _clamp_pii() which strips both dollar-amount patterns ($NNN,NNN) and thesis-marker keywords (thesis/secret/position) — the monitoring_alerts message field can contain these from portfolio notes"
  - "threshold_type in drift_log uses 'drop_pct' and 'absolute_low' (actual schema) not 'pct_drop'/'absolute_floor' (plan sample SQL) — auto-fixed in test fixture"
  - "send_markdown_email uses html.escape() + <pre> wrap (not full Markdown-to-HTML conversion) — sufficient since digest body is machine-generated with no user-supplied text"
metrics:
  duration_seconds: 1680
  completed_date: "2026-04-25"
  tasks: 3
  files_created: 5
  files_modified: 4
  tests_added: 16
  tests_passing: 16
---

# Phase 7 Plan 02: LIVE-04 Weekly Digest Summary

Weekly portfolio digest rendered as PII-clamped Markdown, exposed via `POST /digest/weekly`, dispatched Sunday 18:00 US/Eastern via email (`<pre>` wrap + `html.escape()`) and Telegram (3900-char truncation), with all five sections reading from live DB tables.

## What Was Built

### T-02-01: engine/digest.py — 5-section Markdown renderer

`render_weekly_digest(db_path)` is the single canonical source of the weekly Markdown body. Returns a string containing all 5 H2 sections in order:

- **(a) Portfolio Performance vs Benchmark** — calls `PortfolioAnalytics.get_benchmark_comparison(provider, "SPY", days=7)`; gracefully shows "No portfolio snapshots" when `data_points < 2`.
- **(b) Top 5 Signal Flips This Week** — Python-side flip detection from `signal_history` (no `signal_changed` column per RESEARCH Q2); groups by ticker, compares last 2 `final_signal` values within past 7 days.
- **(c) IC-IR Movers (>20% from 60-day avg)** — reads `drift_log` (built in 07-01) for `triggered=1` or `preliminary_threshold=1` rows within the past 7 days; shows "No IC-IR movers this week — corpus may need more data" when empty.
- **(d) Open Thesis Drift Alerts** — `AlertStore.get_recent_alerts(acknowledged=0, limit=20)` filtered to past 30 days; only unacknowledged alerts appear.
- **(e) Action Items** — heuristic synthesis from sections (b)-(d): drift triggers → CalibrationPage review suggestion; signal flips → thesis review; HIGH/CRITICAL alerts → acknowledge or act.

**PII clamp (`_clamp_pii`):** strips dollar-amount patterns (`$NNN,NNN.NN → $—`) and thesis-marker keywords (`thesis`, `secret`, `position` → `[redacted]`). Applied to all alert message fields. No thesis_text field is ever queried.

7 tests: all 5 sections, empty-data paths, PII clamp regex sweep (`\$[0-9,]+\.?[0-9]*` returns 0 matches).

### T-02-02: POST /digest/weekly + EmailDispatcher.send_markdown_email

`api/routes/digest.py`: `POST /weekly` returns `PlainTextResponse` with `media_type="text/markdown"`. Registered in `api/app.py` under `/digest` prefix.

`notifications/email_dispatcher.py`: new `send_markdown_email(subject, markdown_body)` method (additive — does NOT modify `send_alert` or `send_alert_digest`). Wraps Markdown body with `html.escape()` + `<pre>` inside the existing dark-theme HTML template. Returns `False` (not raises) when `is_configured` is False.

5 tests: 200 + text/markdown content-type, all 5 H2 headers, PII regression, `<pre>` wrap, unconfigured skip, XSS escape (`&lt;script&gt;`).

### T-02-03: APScheduler Sunday 18:00 + run_weekly_digest daemon job

`daemon/jobs.py::run_weekly_digest` follows the FOUND-07 two-connection pattern exactly:
1. `async with aiosqlite.connect(db_path) as log_conn: row_id = await _begin_job_run_log(log_conn, "digest_weekly", started_at)`
2. `render_weekly_digest(db_path)` — separate connection opened internally
3. Email dispatch via `EmailDispatcher.send_markdown_email` (graceful no-op if SMTP unset)
4. Telegram dispatch with 3900-char truncation + `...(truncated — full digest in email)` marker
5. `_record_daemon_run(...)` + `_end_job_run_log(log_conn, row_id, "success")`

`daemon/scheduler.py`: `CronTrigger(day_of_week="sun", hour=18, minute=0, timezone=self._config.timezone)` with `id="digest_weekly"` and `misfire_grace_time=3600`. Fires 30 minutes after the 17:30 drift detector. Added `_job_digest_weekly` wrapper, `run_once("digest")` branch, and `"digest_weekly"` in `get_status` job_names list.

4 tests: job_run_log `digest_weekly` success row, APScheduler cron field inspection (day_of_week=sun, hour=18, minute=0, misfire_grace_time=3600), SMTP-unconfigured graceful skip, Telegram truncation length ≤ 4000 with marker.

## PII Clamp

Mirrors Phase 4 LLM prompt precedent (T-04-04). Three layers:

1. **Renderer-layer (`_clamp_pii`):** strips `$NNN,NNN.NN` patterns and thesis-marker keywords from alert message fields before they enter the Markdown body.
2. **Transport-layer (`send_markdown_email`):** `html.escape()` applied to entire Markdown body before `<pre>` wrap — prevents any residual HTML-special characters from injecting into email HTML.
3. **Scope boundary:** `thesis_text` from `positions_thesis` is NEVER queried by `render_weekly_digest` — only `ticker`, `alert_type`, `severity`, `message` (clamped), `created_at` are surfaced from alerts.

Test `test_digest_pii_clamp_strips_dollar_and_thesis` asserts: `$1,234,567` not in body, `secret thesis` not in body, regex `\$[0-9,]+\.?[0-9]*` returns 0 matches.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] drift_log threshold_type CHECK constraint values differ from plan sample SQL**
- **Found during:** T-02-01 test execution (test 4 — `test_digest_icir_movers_from_drift_log`)
- **Issue:** Plan sample SQL used `'pct_drop'` and `'absolute_floor'` but actual `db/database.py` schema uses `'drop_pct'` and `'absolute_low'` per the CHECK constraint. SQLite raised `IntegrityError: CHECK constraint failed`
- **Fix:** Updated test fixture to use `'drop_pct'` (correct value from live schema)
- **Files modified:** `tests/test_live_04_digest.py`
- **Commit:** 0ff72ab

**2. [Rule 2 - Missing critical functionality] _clamp_pii needed to strip thesis-marker keywords, not just dollar amounts**
- **Found during:** T-02-01 test 7 (PII clamp) — `monitoring_alerts.message` field contained `"thesis: My secret thesis"` which passed through the initial `_DOLLAR_RE`-only clamp
- **Fix:** Added `_THESIS_RE = re.compile(r"(thesis|secret|position).*", re.IGNORECASE)` applied before dollar-amount stripping; matches from the first keyword occurrence to end-of-line and replaces with `[redacted]`
- **Files modified:** `engine/digest.py`
- **Commit:** 0ff72ab

## Threat Model Status

| Threat ID | Status | Evidence |
|-----------|--------|---------|
| T-07-02-01 | Mitigated | `html.escape()` in `send_markdown_email`; `test_send_markdown_email_html_escapes_script_tags` asserts `&lt;script&gt;` |
| T-07-02-02 | Mitigated | `_clamp_pii()` strips dollar amounts + thesis markers; `test_digest_pii_clamp_strips_dollar_and_thesis` passes |
| T-07-02-03 | Mitigated | `_send_sync` exception caught by `_send_async`; password not logged |
| T-07-02-04 | Mitigated | `if len(tg_text) > 3900: tg_text[:3900] + "...(truncated)"` in `run_weekly_digest`; `test_telegram_truncates_long_digest` passes |
| T-07-02-05 | Mitigated | `misfire_grace_time=3600` on digest_weekly cron; verified by `test_apscheduler_registers_digest_weekly_sunday_1800` |
| T-07-02-06 | Accepted | signal_history is daemon-write-only; localhost-bound per DATA-05 |
| T-07-02-07 | Accepted | Solo operator, localhost-bind; same posture as all v1.x endpoints |
| T-07-02-08 | Accepted | drift_log is daemon-write-only via run_drift_detector |
| T-07-02-09 | Accepted | At v1.1 scope (~350 rows max), O(N) flip detection is well within budget |

## Test Coverage

16 new tests across 3 files:

- `test_live_04_digest.py` (7): all 5 H2 headers, perf empty, signal flips AAPL HOLD→BUY, IC-IR DRIFT DETECTED, IC-IR empty message, open alerts unacknowledged-only, PII clamp dollar+thesis strip
- `test_live_04_digest_email.py` (5): POST /weekly 200+text/markdown+5 headers, no-dollar-amounts regression, `<pre>` wrap, unconfigured returns False, XSS escaping
- `test_live_04_digest_scheduler.py` (4): job_run_log success row, APScheduler cron fields (sun/18/0/misfire=3600), SMTP-unconfigured graceful, Telegram truncation ≤4000 chars

## Regression Results

- `test_an01_dividend_irr.py` (13 tests): 13 passed
- `test_an02_drift_detector.py` (14 tests): 14 passed
- `test_an02_drift_api.py` (9 tests): 9 passed
- `test_014_daemon.py` (8 tests): 8 passed

44 regression tests: 44 passed, 0 failed.

## Known Stubs

None. All five digest sections are wired to live data:
- Section (a): `PortfolioAnalytics.get_benchmark_comparison` queries real `portfolio_snapshots`
- Section (b): queries real `signal_history`
- Section (c): queries real `drift_log` (built by 07-01 drift detector)
- Section (d): queries real `monitoring_alerts` via `AlertStore`
- Section (e): derived heuristically from sections (b)-(d)

## Self-Check

- [x] `engine/digest.py` — `render_weekly_digest` + 5 `HEADER_*` constants + `_clamp_pii`
- [x] `api/routes/digest.py` — `POST /weekly` with `PlainTextResponse(media_type="text/markdown")`
- [x] `api/app.py` — `digest_router` registered under `/digest` prefix
- [x] `notifications/email_dispatcher.py` — `send_markdown_email` with `html.escape()` + `<pre>`
- [x] `daemon/jobs.py` — `run_weekly_digest` FOUND-07 pattern + email + Telegram truncation
- [x] `daemon/scheduler.py` — Sunday 18:00 `digest_weekly` cron + `misfire_grace_time=3600`
- [x] 16 new tests: 16 passed
- [x] 44 regression tests: 44 passed

## Self-Check: PASSED
