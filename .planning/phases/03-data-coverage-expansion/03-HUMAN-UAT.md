---
status: partial
phase: 03-data-coverage-expansion
source: [03-VERIFICATION.md]
started: 2026-04-21T04:00:00Z
updated: 2026-04-21T04:00:00Z
---

## Current Test

[awaiting human testing — 3 items below require external-API / daemon-launch verification]

## Tests

### 1. FinBERT non-HOLD on real news-rich ticker
**expected:** With `ANTHROPIC_API_KEY` unset AND `pip install -e ".[llm-local]"` completed AND `python scripts/fetch_finbert.py` run, invoking `SentimentAgent.analyze(...)` on a ticker with ≥3 news headlines (e.g., NVDA, AAPL during an earnings week) produces a non-HOLD signal with confidence > 40.
**result:** pending
**how to run:** `python -c "import os; os.environ.pop('ANTHROPIC_API_KEY', None); import asyncio; from agents.sentiment import SentimentAgent; from data_providers.yfinance_provider import YFinanceProvider; asyncio.run(SentimentAgent(YFinanceProvider()).analyze(...))"`

### 2. Live Finnhub API round-trip
**expected:** With `FINNHUB_API_KEY` set to a valid free-tier key, `FinnhubProvider.get_sector_pe("technology")` returns a float (peer-basket median P/E) without 429 rate-limit errors. FundamentalAgent reasoning contains `"Finnhub sector P/E"` string.
**result:** pending
**how to run:** `export FINNHUB_API_KEY=<key> && python -c "import asyncio; from data_providers.finnhub_provider import FinnhubProvider; print(asyncio.run(FinnhubProvider().get_sector_pe('technology')))"`

### 3. Daemon PID file + netstat localhost binding
**expected:** Running `python -m daemon.scheduler` creates `data/daemon.pid` containing a numeric PID matching the live process. Running `uvicorn api.app:app --host 127.0.0.1 --port 8000` shows `netstat -an | grep 8000` reporting `127.0.0.1:8000 LISTEN` (not `0.0.0.0:8000`). Killing the daemon removes the PID file via atexit.
**result:** pending
**how to run:** Launch daemon, check `data/daemon.pid`, run `netstat -an` on port 8000, kill daemon, verify PID file cleanup.

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

(none — all 3 items are standard external-integration validations deferred to operator)
