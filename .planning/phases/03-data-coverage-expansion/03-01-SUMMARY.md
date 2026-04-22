---
phase: 03-data-coverage-expansion
plan: "01"
subsystem: data_providers + agents
tags: [finnhub, sector-pe, fundamental-agent, rate-limiter, data-quality]
dependency_graph:
  requires:
    - 01-03-PLAN (backtest_mode FOUND-04 gate in agents/fundamental.py)
    - 02-01-PLAN (FredProvider pattern used as template)
  provides:
    - FinnhubProvider: live sector P/E via peer-basket median
    - sector_pe_cache.get_sector_pe_source(): source provenance for reasoning strings
    - FundamentalAgent live-mode reasoning now distinguishes data source
  affects:
    - agents/fundamental.py (reasoning string extended)
    - data_providers/sector_pe_cache.py (Finnhub priority layer added)
tech_stack:
  added:
    - httpx.AsyncClient (already a dep — no pyproject.toml change)
    - statistics.median (stdlib)
  patterns:
    - Peer-basket sector P/E derivation (5 proxy tickers per sector, median)
    - Sibling-function source provenance (_source_cache + get_sector_pe_source)
    - Priority-layered cache (Finnhub > yfinance ETF > static table)
key_files:
  created:
    - data_providers/finnhub_provider.py
    - tests/test_data_coverage_01_finnhub.py
  modified:
    - data_providers/sector_pe_cache.py
    - agents/fundamental.py
decisions:
  - "Peer basket of 5 proxy tickers per sector (not ETF) — Finnhub free tier does not expose sector aggregates directly; median of N=5 peers resists a single poisoned value (T-03-01-02)"
  - "Sibling get_sector_pe_source() function (not modified return type) — keeps float|None return of get_sector_pe_median backward-compatible with all existing callers"
  - "Priority-1 Finnhub inside sector_pe_cache.py (not in fundamental.py directly) — single integration point; yfinance ETF path still works as priority-2 fallback"
  - "Sanity filter: drop PE <= 0 or > 1000 — eliminates negative-earnings artifacts and extreme outliers before median computation"
  - "TTL unchanged at 86400s (24h) — satisfies plan requirement of TTL >= 1h; no churn needed"
  - "RuntimeError propagated from get_sector_pe when _client is None — callers (sector_pe_cache) catch and fall back to static cleanly"
metrics:
  duration_seconds: 395
  completed_date: "2026-04-21"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 2
  tests_added: 15
  tests_regression: 30
---

# Phase 3 Plan 01: Finnhub Sector P/E Integration Summary

**One-liner:** Live sector P/E via Finnhub peer-basket median (5 proxy tickers/sector) wired into FundamentalAgent with graceful fallback to static SECTOR_PE_MEDIANS and source-tagged reasoning strings.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| T-01-01 | Implement FinnhubProvider with rate-limited httpx client | 27d03a9 | data_providers/finnhub_provider.py, tests/test_data_coverage_01_finnhub.py |
| T-01-02 | Wire FinnhubProvider into FundamentalAgent sector P/E flow | f4cf2e7 | data_providers/sector_pe_cache.py, agents/fundamental.py |

## Test Results

- **15 new tests** in `tests/test_data_coverage_01_finnhub.py`: all pass
  - 10 unit tests (T1-T10): FinnhubProvider class behavior
  - 5 integration tests (I1-I5): FundamentalAgent reasoning strings + FOUND-04 contract
- **Regression**: `test_006_fundamental_agent.py` (13 tests), `test_foundation_04_backtest_mode.py` (7 tests), `test_004_data_providers.py` (6 tests): all pass
- **Total run**: 45 passed, 1 skipped (network-gated), 0 failed

## Must-Have Truth Verification

| Truth | Status |
|-------|--------|
| Reasoning contains "Finnhub sector P/E" when key set | VERIFIED (test_fundamental_agent_uses_finnhub_when_key_set) |
| Reasoning contains "static sector median" when key unset | VERIFIED (test_fundamental_agent_falls_back_to_static_when_key_unset) |
| Rate limiter queues 61st call | VERIFIED (test_finnhub_rate_limiter_queues_61st_call) |
| TTL cache reuses within 1h | VERIFIED (test_sector_pe_cache_reuses_within_ttl) |
| FOUND-04 backtest_mode gate preserved | VERIFIED (test_fundamental_agent_backtest_mode_unchanged_by_finnhub + foundation_04 regression) |

## Design Decisions

### Peer basket size: 5 tickers per sector
Finnhub free tier exposes `/stock/metric` per ticker but no sector-aggregate endpoint. Five well-known large-caps per sector gives enough consensus to apply `statistics.median()` while keeping request count manageable (5 req/sector P/E refresh). The `len(pes) < 2` guard ensures at least 2 valid responses are required before returning a median — a single poisoned or missing value cannot corrupt the result (T-03-01-02 mitigation).

### Sanity filter thresholds: drop PE ≤ 0 or > 1000
Negative P/E indicates negative earnings (valid business state, not a valid comparator). Values > 1000 are statistical anomalies (e.g., companies with near-zero earnings). Dropping these before median computation prevents outliers from skewing the sector benchmark.

### Sibling function approach for source provenance
`get_sector_pe_source()` reads from a module-level `_source_cache` dict populated as a side-effect of `get_sector_pe_median()`. This keeps the return type of `get_sector_pe_median()` as `float | None` — backward-compatible with all existing callers — while allowing `agents/fundamental.py` to query the source in a separate await call.

### Cache TTL: 86400s (24h) unchanged
The plan advisory noted "TTL >= 1 hour is fine". The existing 24h TTL satisfies this without churn. A single cache dict serves all three sources (Finnhub result overwrites any stale yfinance entry on next refresh).

### Priority ordering in sector_pe_cache
Finnhub is inserted as priority 1 inside `sector_pe_cache.get_sector_pe_median()` — before the yfinance ETF path. This means the integration point is a single module rather than spreading Finnhub awareness into `agents/fundamental.py`. The yfinance ETF fallback (priority 2) and static table (priority 3) remain intact.

## Security Mitigations Applied

| Threat ID | Mitigation |
|-----------|-----------|
| T-03-01-01 | API token in httpx default_params only; log lines use path string, never full URL |
| T-03-01-02 | Defensive float coercion + sanity filter (<=0, >1000) + median(N>=2) consensus |
| T-03-01-03 | 429 returns `{}` instead of raising; static fallback keeps agent functional |
| T-03-01-04 | Exception catch in sector_pe_cache falls back to static; httpx timeout=10s |
| T-03-01-06 | `_api_key` private attribute; never logged; no test assertion captures it |

## Deviations from Plan

None — plan executed exactly as written.

- `sector_pe_cache.py` was extended with the sibling-function pattern (preferred option from plan Step A).
- `_build_reasoning` signature gained `sector_pe_source: str = "static"` default — backward-compatible.
- `data_providers/factory.py` left unchanged (plan Step D: "LEAVE UNCHANGED — sector_pe_cache.py handles Finnhub wiring transparently").
- `pyproject.toml` not touched (httpx already present).

## Known Stubs

None. The Finnhub integration is fully wired. When `FINNHUB_API_KEY` is unset the static fallback path is active (not a stub — it's a designed degradation mode).

## Open Follow-ups for Plan 03-03

- **Insider signal batching:** Plan 03-03 adds another Finnhub call site (`/stock/insider-transactions`). Consider batching sector P/E + insider calls into a single provider pass per ticker to stay within the 60 req/min budget.
- **`_finnhub_provider` singleton reset:** The module-level `_finnhub_provider` in `sector_pe_cache.py` is never reset if `FINNHUB_API_KEY` changes at runtime. This is fine for the solo-operator use case but should be noted for any future test isolation that sets/unsets the env var without calling `sector_pe_cache._finnhub_provider = None` explicitly (as the integration tests already do).

## Self-Check: PASSED
