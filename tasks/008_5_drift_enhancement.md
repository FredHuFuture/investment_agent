# Task 008.5: Drift Analyzer Enhancement

## 🎯 Goal

Enhance `engine/drift_analyzer.py` with **batch drift summary**, **hold drift**, and **closed-position filtering** so that Task 009 (CLI Report) can display portfolio-level drift statistics. This is a focused incremental enhancement to the existing `DriftAnalyzer` class.

**Phase 1 scope: LONG positions only.** Direction-aware drift (SHORT support) deferred to Phase 2.

## 📥 Context

- `engine/drift_analyzer.py` (Task 002) — currently supports single-thesis drift via `compute_position_drift(thesis_id)`.
- `db/database.py` — SQLite schema with `positions_thesis` and `trade_executions` tables.
- Architecture review: `project/investment_agent_v4_review.md` — identifies open-trade contamination and hold drift ambiguity as issues.

## 🛠️ Requirements

### 1. Enhance `compute_position_drift` return dict

Add two new fields to the dict returned by `compute_position_drift`:

```python
{
    # ... existing fields ...
    "hold_drift_days": int | None,    # actual_hold_days - expected_hold_days
    "actual_hold_days": int | None,   # calendar days from first BUY to last SELL (closed) or to today (open)
}
```

**Calculation:**
```python
from datetime import date

# actual_hold_days: calendar days between first BUY executed_at and:
#   - last SELL executed_at (if position_status == "closed")
#   - today (if position_status == "open")
# None if no executions.

# hold_drift_days:
#   - None if expected_hold_days is not set on the thesis (NULL)
#   - actual_hold_days - expected_hold_days otherwise
```

To compute this, the method needs `executed_at` from trade_executions. Modify the SQL query:

```python
# Change from:
SELECT action, quantity, executed_price
# To:
SELECT action, quantity, executed_price, executed_at
FROM trade_executions WHERE thesis_id = ? ORDER BY id ASC
```

Also fetch `expected_hold_days` from `positions_thesis`:

```python
# Change from:
SELECT expected_entry_price, expected_target_price, expected_return_pct
# To:
SELECT expected_entry_price, expected_target_price, expected_return_pct, expected_hold_days
FROM positions_thesis WHERE id = ?
```

**Date parsing:** `executed_at` is stored as ISO text (e.g. `"2026-03-10T10:00:00"`). Use `date.fromisoformat(executed_at[:10])` to extract the date portion.

### 2. New: `compute_drift_summary` batch method

```python
async def compute_drift_summary(
    self,
    lookback: int = 50,
    include_open: bool = False,
) -> dict[str, Any]:
    """Compute aggregate drift statistics across recent theses.

    Args:
        lookback: Maximum number of recent theses to include (by created_at DESC).
        include_open: If False (default), entry_drift and hold_drift stats only
                      include closed positions. return_drift always excludes open
                      positions (no realized return to measure).
                      If True, entry_drift and hold_drift include open positions too.

    Returns dict with:
        total_theses: int           — number of theses in lookback window
        closed_count: int           — number with position_status == "closed"
        open_count: int             — number with position_status == "open"
        no_exec_count: int          — number with position_status == "no_executions"
        avg_entry_drift_pct: float | None  — mean entry drift (filtered per include_open)
        avg_return_drift_pct: float | None — mean return drift (closed only, always)
        avg_actual_return_pct: float | None — mean actual return (closed only)
        win_rate: float | None      — fraction of closed positions with actual_return_pct > 0
        avg_hold_drift_days: float | None — mean hold drift (closed with expected_hold_days set)
        individual_drifts: list[dict]  — per-thesis drift dicts from compute_position_drift
    """
```

**Implementation strategy:**
1. Query recent thesis IDs: `SELECT id FROM positions_thesis ORDER BY created_at DESC LIMIT ?` with `lookback`.
2. Call `compute_position_drift(thesis_id)` for each.
3. Partition results by `position_status`.
4. Compute aggregate statistics from the partitioned results.

```python
# Pseudocode for aggregation:
closed = [d for d in drifts if d["position_status"] == "closed"]
open_pos = [d for d in drifts if d["position_status"] == "open"]
no_exec = [d for d in drifts if d["position_status"] == "no_executions"]

# entry_drift: from closed (+ open if include_open)
entry_pool = closed if not include_open else closed + open_pos
entry_drifts = [d["entry_drift_pct"] for d in entry_pool if d["entry_drift_pct"] is not None]
avg_entry_drift_pct = mean(entry_drifts) if entry_drifts else None

# return_drift: always closed only (open has no realized return)
return_drifts = [d["return_drift_pct"] for d in closed if d["return_drift_pct"] is not None]
avg_return_drift_pct = mean(return_drifts) if return_drifts else None

# actual return: closed only
actual_returns = [d["actual_return_pct"] for d in closed if d["actual_return_pct"] is not None]
avg_actual_return_pct = mean(actual_returns) if actual_returns else None

# win rate: fraction of closed with actual_return_pct > 0
if actual_returns:
    win_rate = sum(1 for r in actual_returns if r > 0) / len(actual_returns)
else:
    win_rate = None

# hold drift: closed with hold_drift_days not None
hold_drifts = [d["hold_drift_days"] for d in closed if d["hold_drift_days"] is not None]
avg_hold_drift_days = mean(hold_drifts) if hold_drifts else None
```

### 3. New: `get_thesis_ids` helper

```python
async def get_thesis_ids(self, lookback: int = 50) -> list[int]:
    """Get recent thesis IDs ordered by created_at DESC.

    Args:
        lookback: Maximum number of IDs to return.

    Returns:
        List of thesis IDs (most recent first).
    """
```

This is a simple helper used internally by `compute_drift_summary` and also useful for external callers.

### 4. Existing tests must not break

The two existing tests in `test_002_drift.py` must continue to pass. The new fields (`hold_drift_days`, `actual_hold_days`) are additive — existing test assertions on other fields remain valid. You may optionally add assertions for the new fields in existing tests, but do not change existing assertions.

## 📝 Test Cases (`tests/test_008_5_drift_enhancement.py`)

All tests use `tmp_path` with fresh DB, same pattern as `test_002_drift.py`.

### Helper: `_create_thesis_with_executions`

```python
async def _create_thesis_with_executions(
    db_file: Path,
    ticker: str,
    expected_entry_price: float,
    expected_return_pct: float | None,
    expected_hold_days: int | None,
    executions: list[tuple[str, float, float, str]],
    # Each execution: (action, quantity, price, executed_at)
) -> int:
    """Insert a thesis + executions, return thesis_id."""
```

### Test cases (8 tests):

1. **test_hold_drift_closed_position**
   - Create thesis with `expected_hold_days=30`.
   - Add BUY on 2026-01-01, SELL (full qty) on 2026-01-20.
   - `actual_hold_days` should be 19.
   - `hold_drift_days` should be `19 - 30 = -11` (closed early).

2. **test_hold_drift_open_position**
   - Create thesis with `expected_hold_days=60`.
   - Add BUY on 2026-02-01 only (no SELL).
   - `position_status == "open"`.
   - `actual_hold_days` should be `(today - 2026-02-01).days`.
   - `hold_drift_days` should be `actual_hold_days - 60`.

3. **test_hold_drift_no_expected**
   - Create thesis with `expected_hold_days=None`.
   - Add BUY + SELL.
   - `hold_drift_days` should be `None`.
   - `actual_hold_days` should still be computed.

4. **test_drift_summary_closed_only**
   - Create 3 theses: 2 closed (one win, one loss), 1 open.
   - Call `compute_drift_summary(include_open=False)`.
   - `closed_count == 2`, `open_count == 1`.
   - `avg_return_drift_pct` computed from 2 closed only.
   - `win_rate` should be `0.5` (1 win out of 2 closed).
   - Open position's entry_drift excluded from `avg_entry_drift_pct`.

5. **test_drift_summary_include_open**
   - Same setup as test 4.
   - Call `compute_drift_summary(include_open=True)`.
   - `avg_entry_drift_pct` now includes the open position's entry drift.
   - `avg_return_drift_pct` still excludes open (no realized return).

6. **test_drift_summary_empty_db**
   - No theses in DB.
   - `compute_drift_summary()` returns `total_theses=0`, all averages `None`, `individual_drifts=[]`.

7. **test_win_rate_all_winners**
   - Create 3 closed theses, all with positive actual return.
   - `win_rate == 1.0`.

8. **test_drift_summary_lookback_limit**
   - Create 5 theses.
   - Call `compute_drift_summary(lookback=3)`.
   - `total_theses == 3` (only most recent 3).
   - `individual_drifts` has length 3.

## 📂 Files

| Action | File |
|--------|------|
| MODIFY | `engine/drift_analyzer.py` — add hold drift, batch summary, helper |
| CREATE | `tests/test_008_5_drift_enhancement.py` — 8 test cases |
| NO CHANGE | `db/database.py` — no schema changes needed |

## ✅ Acceptance Criteria

1. `pytest tests/test_008_5_drift_enhancement.py -v` — all 8 tests pass.
2. `pytest tests/test_002_drift.py -v` — existing 2 tests still pass (no regression).
3. `pytest tests/ -v` — full suite passes (59 existing + 8 new = 67 total, 2 skipped).
4. `compute_position_drift` returns `hold_drift_days` and `actual_hold_days` fields.
5. `compute_drift_summary` returns correct aggregate stats.
6. Code follows PEP 8, type hints, `from __future__ import annotations`.

## ⚠️ Out of Scope

- SHORT position drift sign inversion → Phase 2
- `direction` column in positions_thesis → Phase 2
- FIFO/LIFO lot matching → Phase 3
- Dividend inclusion in return drift → Phase 3
- Stock split adjustment of expected prices → Phase 3
- Confidence calibration chart → Phase 2

---
**Developer Agent instructions:**
Read `engine/drift_analyzer.py` and `tests/test_002_drift.py` first. Enhance the existing `DriftAnalyzer` class — do NOT create a new class. Ensure backward compatibility: existing `compute_position_drift` callers get the same keys plus new ones. Run `pytest tests/test_002_drift.py -v` after changes to verify no regression, then `pytest tests/ -v`. Report in `docs/AGENT_SYNC.md`.
