---
phase: 05-corpus-population-live-data-closeout
verified: 2026-04-23T00:00:00Z
status: human_needed
score: 4/5 must-haves verified (SC-1 requires live portfolio corpus — operator action)
overrides_applied: 0
human_verification:
  - test: "Run POST /api/v1/calibration/rebuild-corpus with tickers=null against a portfolio containing 5+ open US equity positions"
    expected: "GET /api/v1/analytics/calibration returns non-zero sample_size for all non-Fundamental agents across all rebuilt tickers; corpus date_range spans 3+ years prior to today"
    why_human: "SC-1 requires an actual populated corpus in the live SQLite DB. The endpoint and delegation chain are fully implemented and tested against stub data, but sample_size will be 0 until rebuild_signal_corpus has run against real YFinance OHLCV data for the user's portfolio tickers. No in-process test can assert on live DB corpus rows without triggering a real multi-minute network fetch."
---

# Phase 5: Corpus Population + Live Data Closeout Verification Report

**Phase Goal:** The calibration corpus exists for all user-configured tickers with 3+ years of signal history, and all three live-environment v1.0 UAT items are documented as resolved — so Phase 6 UI has real data to display and no "partial" verification debts hang over live data infrastructure.
**Verified:** 2026-04-23T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `GET /api/v1/analytics/calibration` returns non-zero `sample_size` for all non-Fundamental agents across 5+ user-configured tickers after corpus is populated | ? HUMAN NEEDED | Implementation fully wired: `_run_batch_rebuild` → `rebuild_signal_corpus` → `backtest_signal_history` → `corpus_metadata.total_observations`; `sample_size` sourced from live DB read (not hardcoded); non-zero requires operator to run rebuild against real portfolio |
| 2 | `POST /api/v1/calibration/rebuild-corpus` triggers `rebuild_signal_corpus` per ticker, returns progress, completes without error | ✓ VERIFIED | 15 tests pass in `test_live_01_corpus_rebuild.py` (including FOUND-07 delegation, per-ticker isolation, WR-01/WR-02 outer guard, error_message population); all key links wired |
| 3 | FinBERT live test documented in `03-HUMAN-UAT.md` with status resolved | ✓ VERIFIED | `**result:** resolved` at line 18; `closed_by: Phase 5 Plan 05-02 Task 1` at line 19; automated test + operator script both exist |
| 4 | Finnhub live test documented in `03-HUMAN-UAT.md` with status resolved | ✓ VERIFIED | `**result:** resolved` at line 41; `closed_by: Phase 5 Plan 05-02 Task 2` at line 42; automated test + operator script both exist |
| 5 | Daemon PID test documented in `03-HUMAN-UAT.md` with status resolved | ✓ VERIFIED | `**result:** resolved` at line 63; `closed_by: Phase 5 Plan 05-02 Task 3` at line 64; all 4 tests pass unconditionally |

**Score:** 4/5 truths fully verified (SC-1 implementation verified but live corpus data requires operator action)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/routes/calibration.py` | POST + GET rebuild-corpus endpoints + BackgroundTasks runner | ✓ VERIFIED | `rebuild_corpus_endpoint` at line 143, `rebuild_corpus_progress_endpoint` at line 228, `_run_batch_rebuild` at line 265, `BackgroundTasks` imported at line 24 |
| `db/database.py` | `corpus_rebuild_jobs` DDL + `idx_crj_job_id` + `idx_crj_status` | ✓ VERIFIED | `CREATE TABLE IF NOT EXISTS corpus_rebuild_jobs` at line 656; `idx_crj_job_id` at line 672; `idx_crj_status` at line 678 |
| `api/models.py` | `RebuildCorpusRequest` + `RebuildCorpusResponse` + `RebuildCorpusProgressResponse` | ✓ VERIFIED | `class RebuildCorpusRequest` at line 167; `class RebuildCorpusResponse` at line 197; `class RebuildCorpusProgressResponse` at line 205 |
| `tests/test_live_01_corpus_rebuild.py` | 13+ endpoint/model/DDL tests | ✓ VERIFIED | 15 tests (13 original + 2 WR-01/WR-02 additions); all pass |
| `tests/test_close_01_finbert_live.py` | FinBERT live test + skipif guards + meta-test | ✓ VERIFIED | 3 tests; skipif at lines 37-39, 80-82; meta-test `test_finbert_live_tests_skip_cleanly_when_unavailable` runs unconditionally |
| `tests/test_close_02_finnhub_live.py` | Finnhub live test + network marker + meta-test | ✓ VERIFIED | 4 tests; `@pytest.mark.skipif(not finnhub_key, ...)` + `@pytest.mark.network` on all 3 live tests; meta-test passes |
| `tests/test_close_03_daemon_pid_live.py` | Subprocess PID lifecycle tests (no preconditions) | ✓ VERIFIED | 4 tests; all pass without any env vars or API keys; subprocess uses natural exit for cross-platform atexit |
| `scripts/verify_close_01_finbert.py` | Operator CLI with `if __name__` guard | ✓ VERIFIED | Exists; `if __name__ == "__main__"` at line 64 |
| `scripts/verify_close_02_finnhub.py` | Operator CLI with `if __name__` guard | ✓ VERIFIED | Exists; `if __name__ == "__main__"` at line 52 |
| `scripts/verify_close_03_daemon_pid.py` | Operator CLI with `if __name__` guard | ✓ VERIFIED | Exists; `if __name__ == "__main__"` at line 106 |
| `.planning/milestones/v1.0-phases/03-data-coverage-expansion/03-HUMAN-UAT.md` | `status: resolved`; all 3 items resolved | ✓ VERIFIED | Frontmatter `status: resolved` at line 2; `**result:** resolved` at lines 18, 41, 63; `resolved_by: phase-05-plan-02` in frontmatter |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `api/routes/calibration.py::rebuild_corpus_endpoint` | `PortfolioManager.get_all_positions()` | `positions = await pm.get_all_positions()` when tickers is None | ✓ WIRED | Line 169 in calibration.py |
| `api/routes/calibration.py::_run_batch_rebuild` | `daemon.jobs.rebuild_signal_corpus` | `await rebuild_signal_corpus(db_path=db_path, tickers=[(ticker, asset_type)])` | ✓ WIRED | Line 312-315; single-element list preserves FOUND-07 |
| `api/routes/calibration.py::_run_batch_rebuild` | `corpus_rebuild_jobs` table | `INSERT` on start; `UPDATE` on per-ticker progress; `UPDATE` on batch completion | ✓ WIRED | `UPDATE corpus_rebuild_jobs SET` at lines 367, 400, 437, 447 |
| `tests/test_live_01_corpus_rebuild.py` | `api/routes/calibration.py` | FastAPI `TestClient(create_app(...))` | ✓ WIRED | Pattern used across all endpoint tests |
| `tests/test_close_01_finbert_live.py` | `agents.sentiment.SentimentAgent` | Import inside test function body (not at module top) | ✓ WIRED | Lazy-import contract preserved; `importlib.util.find_spec` at module top only |
| `tests/test_close_02_finnhub_live.py` | `data_providers.finnhub_provider.FinnhubProvider` | `FinnhubProvider()` inside test body when key set | ✓ WIRED | Pattern at lines 26-46 in test file |
| `tests/test_close_03_daemon_pid_live.py` | `scripts.ensure_pid` | `from scripts.ensure_pid import ensure_pid_file, remove_pid_file` in inline subprocess script | ✓ WIRED | Lines 54-57 in `_subprocess_launcher_script` |
| WR-01 outer guard | `corpus_rebuild_jobs.error_message` | `UPDATE corpus_rebuild_jobs SET status='error', error_message=?` in outer except | ✓ WIRED | Lines 396-414 in calibration.py; commit 707e740 |
| WR-02 error_message | `corpus_rebuild_jobs.error_message` | Final-status UPDATE sets `error_message = error_summary` for partial/error states | ✓ WIRED | Lines 363-380 in calibration.py; `error_summary` populated for error and partial states |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `api/routes/calibration.py::get_calibration` | `corpus_metadata.total_observations` | `store.get_backtest_corpus_metadata()` reads from `backtest_signal_history` table | DB query; real after rebuild | ✓ FLOWING (post-rebuild) / awaits operator run |
| `api/routes/calibration.py::rebuild_corpus_progress_endpoint` | `ticker_progress`, `tickers_completed`, `status` | `corpus_rebuild_jobs` table SELECT `WHERE job_id = ?` | DB query; live job state | ✓ FLOWING |
| `api/routes/calibration.py::_run_batch_rebuild` | `progress[ticker]["rows_inserted"]` | `result.get("rows_inserted", 0)` from `rebuild_signal_corpus` return | Real corpus rows written by daemon job | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| POST endpoint exists and returns 200 | `pytest tests/test_live_01_corpus_rebuild.py::test_rebuild_corpus_endpoint_returns_job_id_and_runs_in_background -q` | 1 passed | ✓ PASS |
| FOUND-07 single-element delegation | `pytest tests/test_live_01_corpus_rebuild.py::test_rebuild_corpus_delegates_per_ticker -q` | 1 passed | ✓ PASS |
| Outer exception guard (WR-01) | `pytest tests/test_live_01_corpus_rebuild.py::test_batch_rebuild_outer_exception_marks_error -q` | 1 passed | ✓ PASS |
| error_message population (WR-02) | `pytest tests/test_live_01_corpus_rebuild.py::test_batch_rebuild_partial_writes_error_message -q` | 1 passed | ✓ PASS |
| CLOSE-03 all tests pass unconditionally | `pytest tests/test_close_03_daemon_pid_live.py -q` | 4 passed | ✓ PASS |
| Phase 3 regression | `pytest tests/test_data_coverage_01_finnhub.py tests/test_data_coverage_02_finbert.py tests/test_data_coverage_05_pid_bind.py -q` | 40 passed | ✓ PASS |
| Core contract regression | `pytest tests/test_signal_quality_05b_signal_corpus.py tests/test_foundation_07_job_run_log.py tests/test_001_db.py tests/test_022_api.py -q` | 33 passed | ✓ PASS |
| Live corpus data in GET /analytics/calibration | Requires running POST /analytics/calibration/rebuild-corpus against real portfolio | Cannot verify without operator action | ? SKIP (human_needed) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| LIVE-01 | 05-01-PLAN.md | POST rebuild-corpus endpoint + background job + progress API | ✓ SATISFIED | `rebuild_corpus_endpoint`, `_run_batch_rebuild`, `corpus_rebuild_jobs` table all implemented and tested; REQUIREMENTS.md line 21 marked `[x]` |
| CLOSE-01 | 05-02-PLAN.md | FinBERT live test documented as resolved in 03-HUMAN-UAT.md | ✓ SATISFIED | `**result:** resolved` line 18 in 03-HUMAN-UAT.md; REQUIREMENTS.md line 28 marked `[x]` |
| CLOSE-02 | 05-02-PLAN.md | Finnhub live test documented as resolved in 03-HUMAN-UAT.md | ✓ SATISFIED | `**result:** resolved` line 41 in 03-HUMAN-UAT.md; REQUIREMENTS.md line 29 marked `[x]` |
| CLOSE-03 | 05-02-PLAN.md | Daemon PID test documented as resolved in 03-HUMAN-UAT.md | ✓ SATISFIED | `**result:** resolved` line 63 in 03-HUMAN-UAT.md; REQUIREMENTS.md line 30 marked `[x]` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `db/database.py` | 672 | `CREATE INDEX idx_crj_job_id` is redundant (UNIQUE constraint creates implicit index) | ℹ️ Info | No functional impact; noted in 05-REVIEW.md as IN-03; excluded from fix scope |
| `scripts/verify_close_03_daemon_pid.py` | 80 | `pid_content == str(daemon_proc.pid)` can show False on Windows multi-step launch | ℹ️ Info | Operator cosmetic only; automated tests are correct; noted in 05-REVIEW.md as IN-02 |
| (none) | - | No TODO/FIXME/placeholder/return null stubs in any Phase 5 modified file | - | - |

No blocker or warning anti-patterns. Both info items were triaged in the code review (05-REVIEW.md IN-02, IN-03) and explicitly excluded from fix scope as non-functional.

### Human Verification Required

#### 1. Live Corpus Population — SC-1

**Test:** With a portfolio containing 5+ open US equity positions, start the API server (`uvicorn api.app:app --host 127.0.0.1 --port 8000`) and run:
```
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"tickers": null}' \
  http://127.0.0.1:8000/analytics/calibration/rebuild-corpus
```
Capture the `job_id` from the response, then poll:
```
curl http://127.0.0.1:8000/analytics/calibration/rebuild-corpus/<job_id>
```
Wait for `status` to become `success` or `partial` (may take several minutes per ticker). Then:
```
curl "http://127.0.0.1:8000/analytics/calibration?horizon=5d"
```

**Expected:** `data.corpus_metadata.total_observations > 0`; per-agent `sample_size > 0` for Technical, Macro, Crypto, and Sentiment agents across the rebuilt tickers.

**Why human:** SC-1 requires the actual `backtest_signal_history` table to be populated by `rebuild_signal_corpus` running against real YFinance OHLCV data (3+ years per ticker). This is a multi-minute network operation. No automated test can assert live DB corpus rows without triggering real market data fetches. The code path is fully verified by automated tests with stub data; the live data result requires operator execution.

### Gaps Summary

No actionable gaps. SC-1 is not a gap — the implementation is complete and all code paths are tested. SC-1's "non-zero sample_size" clause is an observable outcome that depends on the operator having run the corpus rebuild against their live portfolio. This is the explicit design of the phase: the endpoint is the deliverable, the data population is an operator action.

All code review warnings (WR-01, WR-02) were fixed in commit 707e740 and verified by two new tests. All three info items from code review are cosmetic/non-functional and explicitly out of fix scope.

---

## Test Run Summary

```
Phase 5 suite:      21 passed, 5 skipped (expected — CLOSE-01 live x2, CLOSE-02 live x3)
Phase 3 regression: 40 passed
Core contracts:     33 passed
Total:              94 passed, 5 skipped, 0 failures
```

5 skips are all CI-expected: CLOSE-01 live tests skip without `[llm-local]` + unset `ANTHROPIC_API_KEY`; CLOSE-02 live tests skip without `FINNHUB_API_KEY`. Meta-tests (which verify the skipif guards exist) pass unconditionally.

## Commit Verification

All Phase 5 commits verified present in git history:

| Commit | Description |
|--------|-------------|
| `769fc17` | feat(05-01): add corpus_rebuild_jobs DDL + Pydantic models (Task 1) |
| `466c194` | feat(05-01): implement rebuild-corpus endpoints + background task runner (Task 2) |
| `ee2521a` | test(05-02): CLOSE-01 FinBERT live pytest + operator script |
| `ced0ff3` | test(05-02): CLOSE-02 Finnhub live pytest + operator script |
| `5fc7d7d` | feat(05-02): CLOSE-03 daemon PID subprocess test + UAT doc resolved |
| `707e740` | fix(05): outer exception guard + error_message population in _run_batch_rebuild (WR-01, WR-02) |
| `83f6b8a` | docs(05): add code review fix report |

---

_Verified: 2026-04-23T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
