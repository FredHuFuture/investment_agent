---
status: partial
phase: 04-portfolio-ui-analytics-uplift
source: [04-VERIFICATION.md, 04-04-SUMMARY.md]
started: 2026-04-22T00:00:00Z
updated: 2026-04-22T00:00:00Z
---

## Current Test

[awaiting human testing — 3 browser-verification flows below]

## Tests

### 1. Target-weight deviation bar (UI-04)
**expected:** Start backend + frontend. Visit `/portfolio`. Click "set target" on any position → enter `0.10` in prompt → bar renders with correct color (amber = overweight, green = underweight). Reload page → target persists. Click "edit target" → blank input → bar disappears. Enter `1.5` → browser alert "Target weight must be between 0.0 and 1.0".
**result:** pending
**how to run:**
```
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload &
cd frontend && npm run dev &
# Open http://localhost:3000/portfolio
```

### 2. MonitoringPage rules panel daemon wiring (UI-03)
**expected:** Visit `/monitoring`. Observe 5 hardcoded rules (STOP_LOSS_HIT, TARGET_HIT, TIME_OVERRUN, SIGNIFICANT_LOSS, SIGNIFICANT_GAIN) each with a "Built-in" badge. Delete button should be hidden for built-in rules. Disable STOP_LOSS_HIT via toggle. Trigger a daemon run: `curl -X POST http://localhost:8000/api/v1/monitor/check`. Confirm the backend log line reads: `Enabled hardcoded alert types: [SIGNIFICANT_GAIN, SIGNIFICANT_LOSS, TARGET_HIT, TIME_OVERRUN]` (STOP_LOSS_HIT absent).
**result:** pending

### 3. DailyPnlHeatmap tooltip (UI-05)
**expected:** Visit `/performance` on an account with at least 7 days of `portfolio_snapshots`. Hover over a colored calendar cell → native browser tooltip appears showing `"YYYY-MM-DD: +$XXX.XX"` with correct sign and color (green positive / gray zero / red negative). Cells without data render as neutral/empty. Heatmap is keyboard-navigable (Tab focuses cells, arrow keys move between).
**result:** pending

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

(none — all 3 items are standard browser-integration validations deferred to operator post-milestone)
