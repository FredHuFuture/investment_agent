---
status: partial
phase: 06-calibration-weights-ui
source: [06-VERIFICATION.md]
started: 2026-04-23T00:00:00Z
updated: 2026-04-23T00:00:00Z
---

## Current Test

[awaiting operator browser-based verification of 4 flows]

## Tests

### 1. Apply IC-IR weights round-trip (LIVE-03 SC-2)
**expected:** With a populated corpus (run Phase 5 LIVE-01 rebuild first), visit `/calibration`. The WeightsEditor shows current weights alongside suggested IC-IR values. Click "Apply IC-IR weights". Toast confirms success. Refetch renders updated "Current" column matching the suggested values. `agent_weights` table shows `source='ic_ir'` for each row. The next daemon `signal_aggregator` run will NOT yet use these weights — Phase 7 AN-02 wires `load_weights_from_db` into `pipeline.py`. That's documented.
**result:** pending
**how to run:**
```
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload &
cd frontend && npm run dev &
# Populate corpus first if not done (Phase 5 LIVE-01)
curl -s -X POST -H "Content-Type: application/json" -d '{"tickers": null}' \
  http://127.0.0.1:8000/analytics/calibration/rebuild-corpus
# Wait for completion...
# Open http://localhost:3000/calibration
# Click "Apply IC-IR weights" on the Stock tab
sqlite3 data/investment_agent.db "SELECT agent_name, weight, source FROM agent_weights WHERE asset_type='stock'"
```

### 2. Manual override toggle persistence (LIVE-03 SC-3)
**expected:** On `/calibration`, toggle "Exclude" on TechnicalAgent (Stock tab). `PATCH /api/v1/weights/override` fires. Row now shows `excluded=1, manual_override=1` in `agent_weights`. Page reload — toggle stays OFF. Re-enable — row updates accordingly. `GET /weights` shows remaining agents' weights re-normalized to sum to 1.0.
**result:** pending

### 3. CLOSE-04 Target-weight browser flow (redundant with 04-HUMAN-UAT.md Test #1 — verify once)
**expected:** `/portfolio`, click "set target" on a position, enter `0.10`, bar renders with correct color. Reload — target persists. Enter `1.5` — alert "between 0.0 and 1.0".
**result:** pending (snapshot test + operator script already confirm rendering contract; this is the final operator sign-off)

### 4. CLOSE-06 Heatmap tooltip (redundant with 04-HUMAN-UAT.md Test #3 — verify once)
**expected:** `/performance` with populated portfolio_snapshots. Hover colored cell. Native browser tooltip shows `"YYYY-MM-DD: +$X.XX"` with correct sign/color.
**result:** pending

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps

(none — implementation verified; operator sign-off pending for live UI flows; SC-2 daemon-wiring explicitly deferred to Phase 7 AN-02 per 06-01 SUMMARY)
