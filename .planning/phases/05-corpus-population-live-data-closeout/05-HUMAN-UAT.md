---
status: partial
phase: 05-corpus-population-live-data-closeout
source: [05-VERIFICATION.md]
started: 2026-04-23T00:00:00Z
updated: 2026-04-23T00:00:00Z
---

## Current Test

[awaiting operator action — single item, runs against live YFinance OHLCV]

## Tests

### 1. Live Corpus Population (LIVE-01 end-to-end, SC-1)
**expected:** With 5+ open portfolio positions, running `POST /analytics/calibration/rebuild-corpus` with `tickers: null` and polling the returned `job_id` completes with `status: success` (or `partial` if some tickers failed, `error` only if all failed). After completion, `GET /analytics/calibration?horizon=5d` returns `data.corpus_metadata.total_observations > 0` and per-agent `sample_size > 0` for Technical, Macro, Crypto, and Sentiment agents across the rebuilt tickers. FundamentalAgent correctly shows the FOUND-04 HOLD-only corpus note.
**result:** pending
**how to run:**
```
# 1. Start backend
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload &

# 2. Trigger rebuild (uses all open positions if tickers=null)
JOB=$(curl -s -X POST -H "Content-Type: application/json" -d '{"tickers": null}' \
  http://127.0.0.1:8000/analytics/calibration/rebuild-corpus | jq -r .job_id)
echo "job_id=$JOB"

# 3. Poll until done (rebuild fetches 3 years OHLCV per ticker — may take several minutes)
until curl -s "http://127.0.0.1:8000/analytics/calibration/rebuild-corpus/$JOB" | jq -r .status | grep -qE "success|partial|error"; do
  sleep 10
  curl -s "http://127.0.0.1:8000/analytics/calibration/rebuild-corpus/$JOB" | jq '{status, tickers_completed, tickers_total}'
done

# 4. Verify corpus populated
curl -s "http://127.0.0.1:8000/analytics/calibration?horizon=5d" | jq '.data | {corpus_metadata, agents: .agents | map({agent_name, sample_size})}'
```
**why human:** The endpoint + data-flow chain is fully implemented and tested with stubs. Asserting non-zero `sample_size` requires `rebuild_signal_corpus` to run against real YFinance OHLCV (3+ years × 5-10 tickers, multi-minute network operation). This is the intended operator action Phase 5 was built to enable. Phase 6 UI needs this populated corpus to render non-null calibration cells.

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps

(none — all implementation verified; only operator-driven live data population remains)
