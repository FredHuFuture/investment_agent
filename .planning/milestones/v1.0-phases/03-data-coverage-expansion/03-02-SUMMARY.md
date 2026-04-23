---
phase: 03-data-coverage-expansion
plan: "02"
subsystem: agents + scripts + pyproject
tags: [finbert, sentiment, local-inference, transformers, lazy-import, optional-deps]
dependency_graph:
  requires:
    - 01-03-PLAN (backtest_mode FOUND-04 gate in AgentInput — unchanged)
  provides:
    - SentimentAgent with FinBERT local inference branch when ANTHROPIC_API_KEY absent
    - [llm-local] optional dependency group (transformers>=4.30, torch>=2.0)
    - scripts/fetch_finbert.py pre-download helper
    - Module-level lazy-import guard (_FINBERT_IMPORT_ATTEMPTED / _FINBERT_AVAILABLE)
  affects:
    - agents/sentiment.py (3-branch analyze flow)
    - pyproject.toml ([llm-local] extra + [all] updated)
tech_stack:
  added:
    - transformers>=4.30 (optional, [llm-local] extra)
    - torch>=2.0 (optional, [llm-local] extra)
  patterns:
    - Module-level lazy-import guard (attempt-once, cache result in global flag)
    - Instance-level pipeline singleton (_finbert_pipeline on SentimentAgent)
    - asyncio.to_thread() wrapping sync HuggingFace pipeline for event-loop safety
    - Signed-score aggregation (positive=+score, negative=-score, neutral=0)
key_files:
  created:
    - scripts/fetch_finbert.py
    - scripts/__init__.py
    - tests/test_data_coverage_02_finbert.py
  modified:
    - agents/sentiment.py
    - pyproject.toml
decisions:
  - "[llm-local] added to [all] extra — 'give me everything' intent includes local LLM; size noted in comment (~400 MB)"
  - "HOLD confidence fixed at 40.0 when below threshold (not formula) — matches plan spec and aligns with existing HOLD@40 convention for 'insufficient data'"
  - "asyncio.to_thread() for FinBERT inference — prevents event-loop stall; 10 headlines ~200ms CPU, acceptable"
  - "_FINBERT_IMPORT_ATTEMPTED global (not instance) — import check happens once per process regardless of how many SentimentAgent instances exist"
  - "_finbert_pipeline instance attribute — pipeline object cached per agent; test isolation resets it via fresh SentimentAgent instances"
  - "Minimum 3 headlines for non-HOLD — local inference on 1-2 headlines too noisy; HOLD@40 with explicit warning"
  - "Text truncation at 512 chars per headline — FinBERT tokeniser truncates at 512 tokens; cutting chars avoids slow tokenisation of very long snippets"
metrics:
  duration_seconds: 420
  completed_date: "2026-04-22"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 2
  tests_added: 13
  tests_regression: 24
---

# Phase 3 Plan 02: FinBERT Local Sentiment Fallback Summary

**One-liner:** FinBERT (ProsusAI/finbert, Apache 2.0) wired into SentimentAgent as a lazy-loaded local-inference fallback when ANTHROPIC_API_KEY is absent — zero-cost offline operation with signed-score aggregation (BUY>=0.25, SELL<=-0.25, HOLD=40 confidence, BUY/SELL confidence=min(90,50+|score|*100)).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| T-02-01 | Add [llm-local] optional dependency group + fetch_finbert.py | 5086633 | pyproject.toml, scripts/fetch_finbert.py, scripts/__init__.py |
| T-02-02 | FinBERT fallback branch in SentimentAgent + 13 tests | e99d907 | agents/sentiment.py, tests/test_data_coverage_02_finbert.py |

## Test Results

- **13 new tests** in `tests/test_data_coverage_02_finbert.py`: all pass
  - 1 subprocess guard: `test_import_does_not_pull_transformers`
  - 4 FinBERT branch coverage: BUY, SELL, mixed-HOLD, unavailable-HOLD
  - 3 edge cases: both-unavailable, requires-3-headlines, pipeline-cached
  - 2 boundary/math: threshold (0.26->BUY, 0.24->HOLD), aggregation (0.42->BUY@90)
  - 2 regressions: no-headlines HOLD@40, Anthropic success path unchanged
  - 1 `test_sentiment_finbert_aggregation_math` (bonus, from plan spec)
- **Regression**: `test_027_sentiment_agent.py` (11 tests): all pass
- **Full suite**: 699 passed, 4 deselected (network), 0 failed

## Must-Have Truth Verification

| Truth | Status |
|-------|--------|
| FinBERT used when key unset + installed -> non-HOLD on strong sentiment | VERIFIED (test_sentiment_uses_finbert_when_anthropic_key_unset) |
| Anthropic preferred when key set | VERIFIED (test_sentiment_prefers_anthropic_when_key_set) |
| HOLD with warning when both absent | VERIFIED (test_sentiment_holds_when_both_unavailable) |
| [llm-local] is OPTIONAL — default install does NOT pull torch | VERIFIED (pyproject.toml inspection + lazy-import guard) |
| Model download deferred to first-call or explicit fetch (no startup hang) | VERIFIED (subprocess import guard test) |

## FinBERT Aggregation Specification

| Variable | Value |
|----------|-------|
| BUY threshold | mean_score >= 0.25 |
| SELL threshold | mean_score <= -0.25 |
| HOLD confidence | 40.0 (fixed, below-threshold convention) |
| BUY/SELL confidence | min(90, max(30, 50 + abs(mean_score) * 100)) |
| Minimum headlines | 3 (fewer -> HOLD @ 40 with warning) |
| Mean denominator | len(results) — neutrals contribute 0 to numerator, count in denominator |
| Text truncation | 512 chars per headline (FinBERT tokeniser limit) |
| Thread safety | asyncio.to_thread(_infer) wraps sync pipeline call |

## Optional Dependency Decision

`[llm-local]` was **included in `[all]`** extra — rationale: `[all]` is the "give me everything" installer entry point; local sentiment is a core v1 feature. The ~400 MB size is documented in a comment above the `[all]` entry in `pyproject.toml`.

Users who want lean installs use `pip install -e .` (no torch) or `pip install -e .[llm]` (Anthropic only).

## Design Decisions

### HOLD confidence fixed at 40.0 (not formula)
The plan spec states "HOLD, confidence = 40". This aligns with the existing convention throughout the codebase where "no usable data available" HOLDs return 40.0 (see Path 3 "No news provider" and Path 4 "No headlines"). Using the formula `50 + abs(0.0) * 100 = 50` for a below-threshold HOLD would imply the same confidence as a neutral Anthropic result, which is misleading.

### Global _FINBERT_IMPORT_ATTEMPTED vs instance flag
The import check is a process-level fact (transformers is either installed or not). Making it global avoids re-trying a known-failing import for every SentimentAgent instance. Tests reset it via `monkeypatch.setattr(agents.sentiment, "_FINBERT_IMPORT_ATTEMPTED", False)`.

### Pipeline cached on instance, not globally
Unlike the import check, the pipeline object holds GPU/CPU resources and should be tied to the agent instance lifecycle. If the application creates multiple SentimentAgent instances (unusual but valid), each gets its own pipeline. Tests verify the per-instance caching via the `_get_call_count()` spy.

## Security Mitigations Applied (from threat model)

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-03-02-02 | fetch_finbert.py pre-download script created; lazy-first-call logs "may download ~400 MB"; failure falls back to HOLD |
| T-03-02-05 | asyncio.to_thread(_infer) wraps sync pipeline; event loop not blocked |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] HOLD confidence formula returned 50.0 instead of 40.0**
- **Found during:** Task 2 test run (T4 `test_sentiment_finbert_holds_on_mixed_low_score` failed)
- **Issue:** Initial implementation used `confidence = max(30, min(90, 50 + abs(mean_score) * 100))` for all three branches. For HOLD (mean_score near 0), this yields 50.0 — contradicting the plan spec "HOLD, confidence = 40" and the existing codebase convention.
- **Fix:** Split the confidence computation: BUY/SELL use the formula; HOLD uses a fixed 40.0.
- **Files modified:** `agents/sentiment.py` (inline fix before commit)
- **Commit:** e99d907 (incorporated in Task 2 commit)

## Known Stubs

None. The FinBERT integration is fully wired. When neither ANTHROPIC_API_KEY nor transformers is available, the agent returns a designed HOLD @ 35 with an explicit install-hint warning — not a stub.

## Open Follow-ups

- **FinBERT reliability calibration:** FinBERT (2019 vintage) is not recalibrated for modern market language. Brier score comparison (FinBERT vs Anthropic) could be added to the calibration endpoint in a future plan.
- **Model revision pinning:** Currently uses `model="ProsusAI/finbert"` without a `revision=` argument — HuggingFace may update the model weights. Pinning a specific commit hash (e.g., `revision="main"` at a fixed SHA) is a v2 hardening option (T-03-02-01 accepted risk).
- **GPU acceleration:** `asyncio.to_thread` is sufficient for CPU inference. If the user has CUDA, `pipeline(..., device=0)` would be faster but requires torch-cuda; deferred to a future optional enhancement.

## Threat Flags

None. No new network endpoints, auth paths, or trust boundaries introduced beyond those documented in the plan's threat model.

## Self-Check: PASSED
