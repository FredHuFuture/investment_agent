---
phase: 06-calibration-weights-ui
plan: "01"
subsystem: weights-persistence
tags: [backend, weights, agent-weights-table, fastapi, ic-ir, aggregator, pydantic, live-03]
requirements: [LIVE-03]

dependency_graph:
  requires:
    - 05-01 (corpus_rebuild_jobs table + LIVE-01 rebuild endpoint)
    - 02-03 (compute_ic_weights SIG-03 API surface)
    - 01-02 (FOUND-05 renormalization contract, FOUND-06 idempotent DDL pattern)
  provides:
    - agent_weights table (UNIQUE(agent_name, asset_type), seed-on-empty)
    - load_weights_from_db helper (engine/aggregator.py)
    - GET /weights (new shape: current + suggested_ic_ir + overrides)
    - POST /weights/apply-ic-ir
    - PATCH /weights/override
  affects:
    - 06-02 (frontend WeightsPage consumes these 3 endpoints)
    - 07 AN-02 (drift detector will call load_weights_from_db to wire pipeline)

tech_stack:
  added:
    - agent_weights SQLite table (per-(agent, asset_type) rows)
  patterns:
    - FOUND-06 idempotent CREATE TABLE IF NOT EXISTS + seed-only-on-empty
    - FOUND-05 renormalization preserved in load_weights_from_db and _read_current_weights
    - SIG-03 compute_ic_weights reused (not reimplemented)
    - Deferred imports (aiosqlite in aggregator, weight_adapter in route) prevent circular imports
    - UPSERT ON CONFLICT for concurrent-write safety (T-06-01-03)

key_files:
  created:
    - tests/test_live_03_weights_api.py (25 tests covering DDL, 3 endpoints, aggregator wiring, threat model)
  modified:
    - db/database.py (agent_weights DDL + seeding after corpus_rebuild_jobs block)
    - engine/aggregator.py (load_weights_from_db module-level async helper)
    - api/models.py (WeightsOverviewResponse, ApplyIcIrResponse, OverrideRequest, OverrideResponse)
    - api/routes/weights.py (full rewrite: GET /weights + POST /apply-ic-ir + PATCH /override)

decisions:
  - id: DDL-booleans-as-integer
    summary: "manual_override and excluded stored as INTEGER 0/1 (not BOOLEAN) — SQLite has no native boolean type; INTEGER is idiomatic and avoids driver inconsistencies"
  - id: seed-only-on-empty
    summary: "Seeding runs only when COUNT(*)=0: preserves user overrides across restarts; mirrors corpus_rebuild_jobs idempotent pattern (FOUND-06)"
  - id: upsert-preserves-manual-override
    summary: "POST /weights/apply-ic-ir uses ON CONFLICT DO UPDATE WHERE agent_weights.manual_override=0 so machine-suggested weights never overwrite explicit user decisions (T-06-01-04)"
  - id: pipeline-wiring-deferred
    summary: "load_weights_from_db helper is tested and ready but pipeline.py and daemon call sites remain on DEFAULT_WEIGHTS. Wiring deferred to Phase 7 AN-02 drift detector. See Open Follow-ups."
  - id: legacy-weights-contract-superseded
    summary: "Old GET /weights returned {weights, crypto_factor_weights, buy_threshold, sell_threshold, source, sample_size}. New shape returns {current, suggested_ic_ir, overrides, source, computed_at, sample_size}. Frontend WeightsPage.tsx donut breaks until 06-02 ships."

metrics:
  duration_seconds: ~600
  completed_date: "2026-04-23"
  tasks_completed: 3
  files_modified: 5
  tests_added: 25
  tests_baseline_before: 900
  tests_after: 925
---

# Phase 06 Plan 01: agent_weights Table + Weights API (LIVE-03) Summary

**One-liner:** Persisted per-(agent, asset_type) weights table with UPSERT-safe HTTP endpoints (GET/POST/PATCH) and IC-IR integration via existing compute_ic_weights — enabling the Phase 6 WeightsPage UI.

## What Was Built

### Task 1: agent_weights DDL + seeding + load helper
- Added `agent_weights` table to `db/database.py` immediately after `corpus_rebuild_jobs` (FOUND-06 grouping). Schema: 8 columns including `UNIQUE(agent_name, asset_type)`, `CHECK(source IN ('default','ic_ir','manual'))`, and `CHECK(asset_type IN ('stock','btc','eth'))`.
- Seed behavior: `COUNT(*) == 0` guard prevents reseed on subsequent startups — preserves user overrides across restarts.
- `load_weights_from_db(db_path)` added at module level in `engine/aggregator.py`. Deferred `import aiosqlite` keeps aggregator importable in offline/test contexts. Skips `excluded=1` rows; renormalizes per FOUND-05; returns `None` on empty/missing table.

### Task 2: Pydantic models + 3 endpoints
- `api/models.py`: Added `WeightsOverviewResponse`, `ApplyIcIrResponse`, `OverrideRequest` (Pydantic pattern validator on `asset_type`), `OverrideResponse`.
- `api/routes/weights.py`: Complete rewrite with:
  - `GET /weights`: reads `agent_weights` via `_read_current_weights`, computes suggested via `_compute_suggested_ic_ir` (deferred import of WeightAdapter/SignalTracker/SignalStore). `suggested_ic_ir[at]` is `null` when corpus empty.
  - `POST /weights/apply-ic-ir`: calls `compute_ic_weights`; returns 409 `NO_IC_IR_DATA` when corpus insufficient; otherwise UPSERTs with `WHERE agent_weights.manual_override=0` guard.
  - `PATCH /weights/override`: validates agent via `KNOWN_AGENTS` allowlist (T-06-01-01); UPSERTs `excluded` + `manual_override=1` + `source='manual'`; returns renormalized weights for that asset_type.

### Task 3: Regression + threat model tests
Tests 18-25 cover all 8 STRIDE threats: unknown agent (400), invalid asset_type (422), concurrent PATCHes (sequential, both commit), apply-ic-ir respects manual_override=1, XSS agent_name rejected, FOUND-05 renorm contract preserved, aggregator wiring via load_weights_from_db, empty corpus graceful degradation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_weights_default for superseded GET /weights contract**
- **Found during:** Task 2 (endpoint rewrite)
- **Issue:** `tests/test_022_api.py::test_weights_default` asserted legacy response keys (`buy_threshold`, `sell_threshold`, `weights`) that no longer exist in the new LIVE-03 shape. This caused 1 test failure in the full suite.
- **Fix:** Updated assertions to validate the new shape (`current`, `suggested_ic_ir`, `overrides`, `source`). The plan explicitly documents that the old contract is superseded; the test just needed updating to match.
- **Files modified:** `tests/test_022_api.py`
- **Commit:** 51affcd

## Open Follow-ups (Deferred to Phase 7 AN-02)

**CRITICAL: Pipeline wiring is NOT in this plan.**

`load_weights_from_db` is tested and ready, but `pipeline.py`, daemon job call sites, and any other `SignalAggregator` construction points remain on `DEFAULT_WEIGHTS`. The Phase 7 AN-02 drift detector plan must wire these call sites:

1. `engine/pipeline.py` — wherever `SignalAggregator()` is constructed, replace with:
   ```python
   from engine.aggregator import load_weights_from_db
   db_weights = await load_weights_from_db(db_path)
   aggregator = SignalAggregator(weights=db_weights)  # falls back to defaults if None
   ```
2. `daemon/scheduler.py` or equivalent — any daemon job that runs analysis must pass `db_path` to `load_weights_from_db` before constructing the aggregator.

Until this wiring lands, the production signal aggregation uses `DEFAULT_WEIGHTS` even if the user has applied IC-IR weights or manual overrides via the UI. The `agent_weights` table is the source of truth for the UI; the pipeline connection is what makes it affect live signals.

**Phase 7 AN-02 planner: pick up this deferred wiring as the first task in that plan.**

## Threat Model Status

8 STRIDE threats assessed; 4 mitigated, 4 accepted:

| Threat ID | Category | Disposition | Implementation |
|-----------|----------|-------------|----------------|
| T-06-01-01 | Tampering (agent_name) | Mitigated | KNOWN_AGENTS allowlist in route, 400 UNKNOWN_AGENT |
| T-06-01-02 | Tampering (asset_type) | Mitigated | Pydantic pattern + DB CHECK constraint |
| T-06-01-03 | DoS (concurrent PATCHes) | Mitigated | UPSERT ON CONFLICT; SQLite WAL serializes |
| T-06-01-04 | Tampering (apply-ic-ir overwrite) | Mitigated | WHERE manual_override=0 in UPSERT |
| T-06-01-05 | XSS (agent_name in response) | Accepted | Rejected at input (T-01); React escapes text nodes |
| T-06-01-06 | Info Disclosure (agent list) | Accepted | Not sensitive; already in docs |
| T-06-01-07 | Spoofing (no auth) | Accepted | DATA-05: localhost-only, solo-operator v1 |
| T-06-01-08 | DoS (IC compute in GET) | Accepted | O(N*A) at v1.1 scope, ~1-2s max |

## Known Stubs

None — all weights data is read from the live `agent_weights` table. The `suggested_ic_ir` values are `null` (not stubs) when the corpus is empty; this is correct behavior documented in the response.

## Self-Check: PASSED

Files created/modified:
- db/database.py — FOUND (agent_weights DDL present)
- engine/aggregator.py — FOUND (load_weights_from_db present)
- api/models.py — FOUND (WeightsOverviewResponse, ApplyIcIrResponse, OverrideRequest present)
- api/routes/weights.py — FOUND (apply-ic-ir, KNOWN_AGENTS, UPSERT pattern present)
- tests/test_live_03_weights_api.py — FOUND (25 tests, all passing)

Commits:
- 41f38b9: feat(06-01): add agent_weights DDL + seed + load_weights_from_db helper
- 6804493: feat(06-01): add Pydantic models + 3 weights endpoints (LIVE-03)
