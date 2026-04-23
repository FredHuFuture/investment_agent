---
phase: 04-portfolio-ui-analytics-uplift
plan: "02"
subsystem: portfolio/models + portfolio/manager + db/database + monitoring/checker + monitoring/monitor + engine/llm_synthesis + engine/aggregator + engine/pipeline + api/routes/portfolio
tags: [fsm, target-weight, alert-rules, daemon-wiring, llm-synthesis, backtest-guard, pii-safe]
dependency_graph:
  requires:
    - 04-01 (analytics endpoints — wave peer, independent)
  provides:
    - PositionStatus FSM (validate_status_transition)
    - VALID_TRANSITIONS dict-of-frozenset
    - active_positions.target_weight column
    - PATCH /portfolio/positions/{ticker}/target-weight
    - _seed_default_alert_rules (idempotent init_db seeding)
    - alert_rules.enabled honored by monitoring/checker.py
    - _load_enabled_rules in monitoring/monitor.py
    - LlmSynthesis dataclass + run_llm_synthesis()
    - AggregatedSignal.llm_synthesis field
    - ENABLE_LLM_SYNTHESIS flag (default false)
  affects:
    - engine/aggregator.py (new llm_synthesis field in AggregatedSignal)
    - engine/pipeline.py (llm_synthesis step + backtest_mode param)
    - monitoring/checker.py (enabled_rule_types param)
    - monitoring/monitor.py (_load_enabled_rules + pass-through)
    - db/database.py (target_weight column + alert_rules seeding)
tech_stack:
  added: []
  patterns:
    - PositionStatus(str, Enum) — raw string values for 100% DB back-compat
    - VALID_TRANSITIONS: dict[str, frozenset[str]] — extensible FSM table
    - _ensure_column() additive migration pattern (FOUND-06)
    - _seed_default_alert_rules() idempotent INSERT with name+metric guard
    - enabled_rule_types: set[str] | None — None=all-enabled backward-compat
    - FOUND-04 backtest_mode short-circuit as FIRST check in run_llm_synthesis
    - 4h TTL in-memory cache keyed (ticker, signal, regime, confidence_bucket)
    - PII-safe prompt: confidence bucketed to 10%, no dollar amounts, no thesis_text
key_files:
  created:
    - engine/llm_synthesis.py
    - tests/test_ui_03_alert_rules_daemon.py
    - tests/test_ui_04_target_weight.py
    - tests/test_ui_06_position_status_fsm.py
    - tests/test_ui_07_llm_synthesis_flag.py
  modified:
    - portfolio/models.py
    - portfolio/manager.py
    - db/database.py
    - monitoring/checker.py
    - monitoring/monitor.py
    - engine/aggregator.py
    - engine/pipeline.py
    - api/routes/portfolio.py
    - .env.example
decisions:
  - "PositionStatus uses open+closed only (no 'reopened' state) per research Open Q#3 — re-entry reuses 'open'"
  - "VALID_TRANSITIONS is dict-of-frozenset not if-chains — extensible without restructuring"
  - "closed→open allowed in FSM (re-entry), closed→closed and open→open are explicit errors"
  - "backtest_mode short-circuit is the FIRST check in run_llm_synthesis — never reorder (FOUND-04)"
  - "LLM cache key is (ticker, signal, regime, confidence_bucket) — 4h TTL"
  - "LLM prompt deliberately omits thesis_text (T-04-06 prompt injection) and dollar amounts (T-04-07 PII)"
  - "confidence bucketed to round(c/10)*10 in both prompt and cache key"
  - "enabled_rule_types=None is the backward-compat sentinel — all rules fire when table missing"
metrics:
  duration_seconds: 1882
  completed: "2026-04-22"
  tasks_completed: 3
  files_modified: 9
---

# Phase 04 Plan 02: Backend FSM + LLM Synthesis + Daemon Wiring + Target Weight Summary

PositionStatus FSM formalized with frozenset transition guard, active_positions.target_weight column added via _ensure_column, alert_rules seeded idempotently and daemon now respects enabled toggles, and opt-in LLM Bull/Bear synthesis with hard FOUND-04 backtest short-circuit.

## What Was Built

### Task 1 — PositionStatus FSM + target_weight + alert_rules seeding (commit `51b4b9b`)

**portfolio/models.py:**
- `PositionStatus(str, Enum)` with `OPEN="open"`, `CLOSED="closed"` — raw strings for 100% DB back-compat
- `VALID_TRANSITIONS: dict[str, frozenset[str]]` — `{"open": frozenset({"closed"}), "closed": frozenset({"open"})}`; closed→open (re-entry) allowed; closed→closed and open→open raise ValueError
- `validate_status_transition(current, next_status) -> None` — raises `ValueError("Invalid PositionStatus transition: ...")` on denied transitions
- `target_weight: float | None = None` field added to `Position` dataclass; included in `from_db_row` (index 18) and `to_dict()`

**portfolio/manager.py:**
- Import `PositionStatus`, `validate_status_transition`
- `close_position._op`: calls `validate_status_transition(OPEN, CLOSED)` after SELECT, before UPDATE — explicit FSM guard
- New `set_target_weight(ticker, target_weight) -> bool`: UPDATE active_positions SET target_weight = ? WHERE ticker = ? AND status = 'open'; returns True if rowcount > 0

**db/database.py:**
- `_ensure_column(conn, "active_positions", "target_weight", "REAL")` called in `init_db()` after `_migrate_add_portfolios`
- New `_seed_default_alert_rules(conn)` — idempotent CREATE TABLE IF NOT EXISTS + INSERT of 5 rows (STOP_LOSS_HIT/TARGET_HIT/TIME_OVERRUN/SIGNIFICANT_LOSS/SIGNIFICANT_GAIN) with `metric='hardcoded'`, `condition='eq'`, `threshold=0.0`, `enabled=1`; only inserts when `(name, metric='hardcoded')` not already present

**api/routes/portfolio.py:**
- `SetTargetWeightBody(BaseModel)`: `target_weight: float | None = Field(default=None, ge=0.0, le=1.0)`
- `PATCH /positions/{ticker}/target-weight`: 404 on missing ticker, 422 on out-of-range (Pydantic), returns `{data: {ticker, target_weight}}`

**Tests:** 14 tests — 7 FSM (transition matrix, ValueError on denied, enum round-trip, close_position guard) + 7 target_weight (column existence, persistence, clear with None, 422, 404, 200 success)

### Task 2 — Daemon respects alert_rules.enabled (commit `09d5edd`)

**monitoring/checker.py:**
- New param `enabled_rule_types: set[str] | None = None`
- Inner `_enabled(name) -> bool` helper: `enabled_rule_types is None or name in enabled_rule_types`
- All 5 rule checks wrapped: `if _enabled("STOP_LOSS_HIT") and ...`, etc.
- Backward-compat: `None` = all rules fire (existing callers unaffected)

**monitoring/monitor.py:**
- New module-level `_logger`
- New `_load_enabled_rules(conn) -> set[str] | None` — queries `SELECT name FROM alert_rules WHERE metric = 'hardcoded' AND enabled = 1`; catches `aiosqlite.OperationalError` and returns `None` (backward-compat for fresh DBs without `init_db`)
- `run_check`: calls `_load_enabled_rules(conn)` before the position loop; logs enabled set; passes `enabled_rule_types=enabled_rule_types` to every `check_position()` call

**Tests:** 8 tests — disabled rule suppression, backward-compat all-enabled, empty set suppresses all, graceful None on missing table, 5 rules seeded by init_db, idempotent seeding, full enabled set from seeded DB, disabled flag respected by _load_enabled_rules

### Task 3 — LLM Bull/Bear synthesis with FOUND-04 guard (commit `ae86212`)

**engine/llm_synthesis.py (new):**
- `LlmSynthesis` dataclass: ticker, bull_case, bear_case, synthesis, model, cached + to_dict()
- `run_llm_synthesis(aggregated, agent_input, client=None) -> LlmSynthesis | None`
- **FOUND-04 order (critical — must not reorder):**
  1. `if agent_input.backtest_mode: return None` — FIRST CHECK
  2. `if not _is_enabled(): return None` — reads ENABLE_LLM_SYNTHESIS env, default false
  3. `if AsyncAnthropic is None: return None` — SDK not installed
  4. `if not api_key: return None` — no ANTHROPIC_API_KEY
- Cache: `_CACHE: dict[tuple, tuple[float, LlmSynthesis]]` with 4h TTL; key = `(ticker, signal.value, regime.value, round(confidence/10)*10)`
- PII-safe `_build_prompt()`: confidence bucketed to 10% increments, no dollar amounts, no thesis_text
- Exception handling: JSON parse errors and network/auth failures → return None + append to aggregated.warnings; never raises

**engine/aggregator.py:**
- `AggregatedSignal` gains `llm_synthesis: "LlmSynthesis | None" = None` field (TYPE_CHECKING import guard)
- `to_dict()` serializes `llm_synthesis.to_dict()` when non-None

**engine/pipeline.py:**
- `_run_pipeline` gains `backtest_mode: bool = False` param; passed to `AgentInput` construction
- Post-sector-modifier, pre-return: `try: synthesis = await run_llm_synthesis(signal, agent_input); if synthesis: signal.llm_synthesis = synthesis except Exception: log + warn`

**.env.example:**
- Added `ENABLE_LLM_SYNTHESIS=false` with cost-per-call comment and FOUND-04 reference

**Tests:** 9 tests — off by default, FOUND-04 (zero API calls in backtest), fires when enabled, PII exclusion (no "$", no "thesis", bucketed confidence), cache hit second call, missing SDK, missing API key, API exception → None + warning, AggregatedSignal field default

## FSM Transition Matrix Shipped

```
            → open   → closed
from open   | DENIED | ALLOWED (close)
from closed | ALLOWED (re-entry) | DENIED
```

Implemented as `VALID_TRANSITIONS: dict[str, frozenset[str]]` — extensible for future states.

## alert_rules Seeding — Idempotency Confirmation

`_seed_default_alert_rules()` is safe to call on every `init_db()`:
- Uses `CREATE TABLE IF NOT EXISTS` — no-op if table exists
- Checks `SELECT 1 FROM alert_rules WHERE name = ? AND metric = 'hardcoded' LIMIT 1` before each INSERT
- Double `init_db()` call verified by `test_seed_is_idempotent` — produces exactly 5 rows

## LLM Cost Estimate

- Model: claude-sonnet-4-20250514 (~$3/M input, ~$15/M output tokens)
- Typical call: ~500 token prompt + ~150 token response ≈ **$0.004 per synthesis call**
- Daily daemon (10 positions, all cache misses): ~$0.04/day
- Cache hit rate: same (ticker, signal, regime, confidence_bucket) within 4h → 0 cost
- **Backtest 3yr/ticker (prevented by FOUND-04):** ~$2.78/ticker — verified zero calls by `test_synthesis_skipped_in_backtest_mode`

## SQL Migrations — No Existing Data Modified

| Migration | Type | Data affected |
|-----------|------|---------------|
| `_ensure_column(active_positions, target_weight, REAL)` | ADD COLUMN only | Existing rows get NULL (no touch) |
| `_seed_default_alert_rules` 5 INSERT rows | INSERT only | Only when name+metric not present |

No existing rows rewritten. No indexes dropped/recreated for this plan. No schema-breaking changes.

## Deviations from Plan

### Auto-noted: Deviation from VALID_TRANSITIONS spec in task description vs plan body

The plan task description says `"closed": frozenset({"open"})` (closed→open allowed for re-entry), which matches the plan's `<behavior>` block: "closed → open ok (reopen)". This is the correct behavior. The research doc's Pattern 4 showed a different 3-state model with 'reopened', but research Open Q#3 resolved to reuse 'open'. Implementation matches the plan spec.

### Auto-noted: `agent_outputs` renamed `agent_signals` in AggregatedSignal

The plan refers to `aggregated.agent_outputs` in the prompt builder, but `AggregatedSignal` uses `agent_signals` (confirmed in the actual dataclass). `_build_prompt()` correctly uses `aggregated.agent_signals`. Tests pass.

## Known Stubs

None — all 4 requirements ship real behavior. No placeholder data in any response path.

## Threat Flags

None — all threats from the plan's threat model are mitigated:
- T-04-06 (prompt injection via thesis_text): `_build_prompt` deliberately omits thesis_text; verified by `test_prompt_excludes_pii`
- T-04-07 (dollar amounts to Anthropic): prompt uses percentage/enum fields only; verified by `test_prompt_excludes_pii` asserting `"$" not in prompt`
- T-04-08 (backtest cost DoS): FOUND-04 guard is first check; verified by `test_synthesis_skipped_in_backtest_mode` asserting `call_count == 0`
- T-04-09 (FSM bypass): `validate_status_transition` raises ValueError before UPDATE; SQL WHERE clause is defense-in-depth
- T-04-10 (target_weight out of range): Pydantic `Field(ge=0.0, le=1.0)` at API layer

## Self-Check: PASSED

- [x] `portfolio/models.py` contains `class PositionStatus(str, Enum)`, `VALID_TRANSITIONS`, `validate_status_transition`, `target_weight` field
- [x] `portfolio/manager.py` contains `validate_status_transition` import and call in `close_position`, `set_target_weight` method
- [x] `db/database.py` contains `_ensure_column(conn, "active_positions", "target_weight", "REAL")` and `_seed_default_alert_rules`
- [x] `monitoring/checker.py` contains `enabled_rule_types` param and `_enabled()` helper
- [x] `monitoring/monitor.py` contains `_load_enabled_rules` and `SELECT name FROM alert_rules WHERE metric = 'hardcoded' AND enabled = 1`
- [x] `engine/llm_synthesis.py` exists with `run_llm_synthesis`, `ENABLE_LLM_SYNTHESIS`, `agent_input.backtest_mode` first check
- [x] `engine/aggregator.py` contains `llm_synthesis: "LlmSynthesis | None" = None`
- [x] `engine/pipeline.py` contains `run_llm_synthesis` call and `backtest_mode` param
- [x] `api/routes/portfolio.py` contains `target-weight` PATCH endpoint
- [x] `.env.example` contains `ENABLE_LLM_SYNTHESIS=false`
- [x] Commit `51b4b9b` (Task 1) exists
- [x] Commit `09d5edd` (Task 2) exists
- [x] Commit `ae86212` (Task 3) exists
- [x] 31 new tests pass; 249 regression tests pass; 800 total tests pass (excluding network marker)
- [x] CRITICAL: `test_synthesis_skipped_in_backtest_mode` asserts `mock_client.messages.create.call_count == 0`
