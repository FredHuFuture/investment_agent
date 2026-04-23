---
phase: 03-data-coverage-expansion
plan: "03"
subsystem: data_providers + agents
tags: [edgar, insider-transactions, form-4, fundamental-agent, rate-limiter, data-quality]
dependency_graph:
  requires:
    - 03-01-PLAN (sector_pe_source variable + Finnhub reasoning string in agents/fundamental.py)
    - 01-03-PLAN (backtest_mode FOUND-04 gate in AgentInput — unchanged)
  provides:
    - EdgarProvider: Form 4 insider transaction aggregation via edgartools
    - FundamentalAgent insider_score component (+0.10 / -0.10 / 0.0 composite tilt)
    - insider_info dict in AgentOutput.metrics for downstream consumers
  affects:
    - agents/fundamental.py (insider block + _build_reasoning extension)
    - data_providers/edgar_provider.py (new file)
    - pyproject.toml (edgartools>=3.0 added to core deps)
tech_stack:
  added:
    - edgartools>=3.0 (Apache 2.0, pure-Python, core dep)
  patterns:
    - Lazy import guard (try/except ImportError at EdgarProvider.__init__)
    - asyncio.to_thread() wrapping synchronous edgartools API
    - Class-level AsyncRateLimiter(10/s) for SEC courtesy limit
    - Defensive backtest_mode double-guard (early-return at line 50 + inline if-not-backtest_mode)
    - Additive composite tilt: _clamp(composite + insider_score * 100.0) applied after weighted average
key_files:
  created:
    - data_providers/edgar_provider.py
    - tests/test_data_coverage_03_edgar.py
  modified:
    - agents/fundamental.py
    - pyproject.toml
decisions:
  - "edgartools added to core [project.dependencies] (not optional) — pure-Python, no C extensions, Apache 2.0; insider data is v1 differentiator, not opt-in"
  - "Insider tilt applied AFTER value/quality/growth weighted average — orthogonal lever; prevents insider data from distorting the valuation/quality/growth ratios"
  - "_MIN_TRANSACTIONS_FOR_REASONING=3 defined locally in fundamental.py — avoids import-time dependency on edgar_provider; mirrors _MIN_TRANSACTIONS_FOR_SIGNAL in edgar_provider.py"
  - "transaction_count counts ALL Form 4 transaction rows (any code); buys_shares/sells_shares count only P/S codes — distinction lets callers audit total filing activity vs open-market activity"
  - "net_buy_ratio thresholds: >0.70 bullish (+0.10), <0.30 bearish (-0.10), 0.30-0.70 neutral (0.0) — 70/30 split consistent with plan spec; 3-tx minimum prevents single-filing noise"
metrics:
  duration_seconds: 376
  completed_date: "2026-04-22"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 2
  tests_added: 17
  tests_regression: 37
---

# Phase 3 Plan 03: SEC EDGAR Insider Transaction Integration Summary

**One-liner:** SEC EDGAR Form 4 insider-transaction signal wired into FundamentalAgent via EdgarProvider (edgartools, 10 req/s rate limit) — net-buy ratio >70% adds +10 composite tilt, <30% adds -10, coexisting with Plan 03-01 Finnhub sector P/E and yfinance fundamentals.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| T-03-01 | EdgarProvider + edgartools dep + 17-test scaffold | 1f4d30d | data_providers/edgar_provider.py, pyproject.toml, tests/test_data_coverage_03_edgar.py |
| T-03-02 | Integrate insider signal into FundamentalAgent (additive to Plan 03-01) | 5d2942c | agents/fundamental.py |

## Test Results

- **17 new tests** in `tests/test_data_coverage_03_edgar.py`: all pass
  - 9 provider unit tests (T1–T9): aggregation math, edge cases, graceful degradation
  - 8 FundamentalAgent integration tests (T10–T17): insider tilt, coexistence, FOUND-04 regression
- **Regression**: `test_006_fundamental_agent.py` (12 tests), `test_foundation_04_backtest_mode.py` (10 tests), `test_data_coverage_01_finnhub.py` (15 tests): all pass
- **Total run**: 54 passed, 1 warning, 0 failed

## Must-Have Truth Verification

| Truth | Status |
|-------|--------|
| Reasoning contains "Insider" when >=3 Form 4 txs in 90d | VERIFIED (test_fundamental_agent_includes_insider_in_reasoning) |
| net_buy_ratio > 0.70 → +0.10 tilt | VERIFIED (test_fundamental_agent_insider_bullish_tilts_composite_up) |
| net_buy_ratio < 0.30 → -0.10 tilt | VERIFIED (test_fundamental_agent_insider_bearish_tilts_composite_down) |
| edgartools unavailable → no crash | VERIFIED (test_fundamental_agent_edgar_none_graceful_degradation) |
| AsyncRateLimiter(10, 1.0) in EdgarProvider | VERIFIED (test_edgar_rate_limiter_defaults_10_per_second) |
| Finnhub sector P/E from Plan 03-01 still in reasoning alongside insider | VERIFIED (test_fundamental_agent_both_sources_coexist) |
| backtest_mode=True → EdgarProvider NOT called (FOUND-04) | VERIFIED (test_fundamental_agent_backtest_mode_skips_edgar) |
| Non-P/S transaction codes excluded from ratio | VERIFIED (test_edgar_ignores_non_P_S_codes) |

## Three Active Data Sources in FundamentalAgent

After Plan 03-03, `FundamentalAgent.analyze()` draws on three independent data sources:

| Source | Plan | Signal type | When active |
|--------|------|-------------|-------------|
| yfinance fundamentals | Pre-existing | Value / Quality / Growth scores (weighted avg) | Always (live mode) |
| Finnhub sector P/E | 03-01 | Relative PE valuation benchmark | When FINNHUB_API_KEY set |
| SEC EDGAR Form 4 | 03-03 | Insider accumulation/distribution overlay | When edgartools installed and >= 3 txs |

## Insider Scoring Specification

| Variable | Value |
|----------|-------|
| Bullish threshold | net_buy_ratio > 0.70 |
| Bearish threshold | net_buy_ratio < 0.30 |
| Bullish tilt | +0.10 (applied as composite += 0.10 * 100 = +10) |
| Bearish tilt | -0.10 (applied as composite += -0.10 * 100 = -10) |
| Neutral | 0.0 (no composite change) |
| Minimum transactions | 3 (fewer → no tilt) |
| Lookback window | 90 days (since_days parameter) |
| Codes counted | P (open-market purchase) and S (open-market sale) only |
| Codes excluded | A (award), M (exercise), G (gift), D (return-to-issuer), F (tax withholding), etc. |

## Security Mitigations Applied

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-03-03-01 | AsyncRateLimiter(10/s) class-level; Edgar exceptions caught at INFO level; agent continues without insider signal if throttled |
| T-03-03-02 | Defensive getattr(tx, 'transaction_code', None) or '' and int(float(shares)) with try/except; malformed filings skipped with debug log |
| T-03-03-06 | asyncio.to_thread(_fetch) wraps all edgartools calls; async rate limiter prevents thread-pool exhaustion |

## Deviations from Plan

### Auto-fixed Issues

None. Plan executed exactly as written.

Minor implementation notes (not deviations):
- `_MIN_TRANSACTIONS_FOR_REASONING = 3` defined in `agents/fundamental.py` (not imported from `edgar_provider.py`) — avoids an import-time dependency and keeps `_build_reasoning` self-contained. The value is identical to `_MIN_TRANSACTIONS_FOR_SIGNAL` in `edgar_provider.py`.
- `transaction_count` in the returned dict counts ALL transaction rows (any code), not just P/S — this gives callers full visibility into total insider filing activity while `buys_shares`/`sells_shares` isolate the open-market signal. Plan spec implied transaction_count = total; confirmed by test_edgar_ignores_non_P_S_codes.

## Known Stubs

None. The EDGAR integration is fully wired. When edgartools is not installed (ImportError) or returns no filings, the agent returns the standard fundamental signal with no insider component — this is a designed degradation mode, not a stub.

## Open Follow-ups

- **Live EDGAR smoke-test:** Deferred — requires network; not CI-runnable. `EdgarProvider().get_insider_transactions("AAPL")` against live SEC EDGAR to verify edgartools API compatibility with the production `>=3.0` release.
- **Transaction count field clarification:** The `transaction_count` field counts all Form 4 transaction rows (any code). If a future consumer needs "open-market-only count", add `open_market_count = buys + sells_count` to the returned dict.
- **Insider signal batching note from 03-01 SUMMARY:** Plan 03-01 flagged that 03-03 adds a new Finnhub call site. Actually 03-03 uses EDGAR (not Finnhub), so the Finnhub 60-req/min budget is unaffected. The batching concern applies only if additional Finnhub calls are added in Phase 4.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced beyond those documented in the plan's threat model. edgartools communicates exclusively via HTTPS to SEC EDGAR public servers (no new trust boundaries at the API layer).

## Self-Check: PASSED

- `data_providers/edgar_provider.py`: FOUND
- `tests/test_data_coverage_03_edgar.py`: FOUND
- `agents/fundamental.py`: FOUND (modified)
- `pyproject.toml`: FOUND (modified)
- Commit `1f4d30d`: FOUND
- Commit `5d2942c`: FOUND
- 54 tests pass, 0 failures
