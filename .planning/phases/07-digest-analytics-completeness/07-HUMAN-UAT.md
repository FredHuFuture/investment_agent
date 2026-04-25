---
status: partial
phase: 07-digest-analytics-completeness
source: [07-VERIFICATION.md]
started: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
---

## Current Test

[awaiting operator action — 3 items requiring live runtime / browser / corpus]

## Tests

### 1. Email delivery end-to-end (LIVE-04 SC-2)
**expected:** With `SMTP_HOST` + `SMTP_PORT` + `SMTP_USERNAME` + `SMTP_PASSWORD` + `ALERT_TO_EMAILS` env vars set, calling `POST /api/v1/digest/weekly` with `deliver_email=true` causes the digest Markdown body (HTML-escaped + wrapped in `<pre>`) to land in the operator's inbox. Subject: "Weekly Investment Digest — YYYY-MM-DD". Body contains all 5 H2 sections.
**result:** pending
**how to run:**
```
export SMTP_HOST=smtp.gmail.com SMTP_PORT=587 SMTP_USERNAME=... SMTP_PASSWORD=... ALERT_TO_EMAILS=user@example.com
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000 &
curl -s -X POST -H "Content-Type: application/json" -d '{"deliver_email": true}' \
  http://127.0.0.1:8000/api/v1/digest/weekly | jq .delivered
# check inbox for "Weekly Investment Digest"
```

### 2. Non-preliminary drift detection (AN-02 SC-4)
**expected:** With a populated `backtest_signal_history` (60+ weekly IC samples per agent — requires multi-month operation OR rebuilding corpus over 1+ years), running `daemon/jobs.py::run_drift_detector` with a synthetic IC drop > 20% triggers `triggered=True` AND `preliminary_threshold=False` in `drift_log`. Auto-scale persists the new weight to `agent_weights` with `source='ic_ir'`. Notification fires via existing channel.
**result:** pending
**how to run:**
```
# After Phase 5 corpus rebuild + 60+ weeks of weekly drift_detector runs OR synthetic backfill:
python -c "
import asyncio
from daemon.jobs import run_drift_detector
asyncio.run(run_drift_detector('data/investment_agent.db'))
"
sqlite3 data/investment_agent.db "SELECT agent_name, asset_type, triggered, preliminary_threshold, weight_before, weight_after FROM drift_log ORDER BY evaluated_at DESC LIMIT 5"
```
**why human:** The `<60 samples → preliminary` flag is the correct behavior today. Promoting to non-preliminary requires real data that operator must accumulate or generate.

### 3. CalibrationPage drift badge in browser (AN-02 SC-5)
**expected:** Visit `/calibration` after a real drift event. AgentCalibrationRow renders a red drift badge with delta_pct (e.g., "drift -23%") next to the affected agent's IC-IR cell. Hover shows native tooltip with `evaluated_at` + IC values. Amber preliminary badge shows when corpus thin.
**result:** pending
**how to run:** Phase 5 corpus rebuild + populated drift_log → frontend dev server → hover badge

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

(none — all implementation verified; operator runtime sign-off pending for live email/corpus/browser)
