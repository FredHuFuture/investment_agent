# Task 025 -- Thesis Tracking Closed-Loop

## Objective

Wire thesis data through the full stack: API → DB → frontend display → drift alerts. The `positions_thesis` table and `DriftAnalyzer.compute_position_drift()` already exist but are orphaned -- no workflow creates thesis records. This task connects them.

**User story**: "When I add AAPL at $186, I also record *why* -- 'AI growth thesis, target $220 in 60 days'. The dashboard then shows me: 'AAPL held 90 days, 30 days past your plan. Return +40% vs expected +18%. Your thesis is outperforming but your timing assumption was wrong.'"

**This is the product moat.** Without it, we're just another indicator calculator.

---

## Scope

**Files to MODIFY (10):**

| File | Change |
|------|--------|
| `portfolio/manager.py` | `add_position()` accepts thesis fields, inserts into BOTH `active_positions` AND `positions_thesis` |
| `portfolio/models.py` | Add thesis fields to Position dataclass: `thesis_text`, `expected_return_pct`, `expected_hold_days`, `target_price`, `stop_loss` |
| `api/models.py` | Extend `AddPositionRequest` with optional thesis fields. Add `ThesisResponse` model |
| `api/routes/portfolio.py` | `POST /positions` passes thesis fields. New `GET /positions/{ticker}/thesis` endpoint |
| `api/routes/portfolio.py` | `GET /portfolio` response includes thesis fields on each position |
| `frontend/src/api/types.ts` | Extend `Position` interface with thesis fields |
| `frontend/src/components/portfolio/AddPositionForm.tsx` | Add collapsible "Investment Thesis" section: thesis text, expected return %, target price, expected hold days, stop loss |
| `frontend/src/components/portfolio/PositionsTable.tsx` | Add Expected Return and Hold Days columns. Color-code: green if on track, amber if approaching limit, red if overdue |
| `frontend/src/pages/DashboardPage.tsx` | Add "Thesis Drift Alerts" card showing positions where hold time exceeded or return diverged significantly |
| `tests/test_025_thesis_tracking.py` | 8-10 tests |

**Files to READ (reference only):**

| File | Why |
|------|-----|
| `db/database.py` | Understand `positions_thesis` and `active_positions` schema |
| `engine/drift_analyzer.py` | Understand existing drift computation (do NOT modify) |

---

## Detailed Requirements

### 1. Backend: Position + Thesis Creation (portfolio/manager.py)

```python
async def add_position(
    self, ticker, asset_type, quantity, avg_cost, entry_date,
    sector=None, industry=None,
    # NEW thesis fields (all optional)
    thesis_text=None,
    expected_return_pct=None,
    expected_hold_days=None,
    target_price=None,
    stop_loss=None,
):
```

**Logic:**
- Always insert into `active_positions` (existing behavior)
- If ANY thesis field is provided, also INSERT into `positions_thesis`:
  - `expected_signal` = "BUY" (we only support LONG positions in Phase 1)
  - `expected_confidence` = 0.7 (default)
  - `expected_entry_price` = avg_cost
  - `expected_target_price` = target_price
  - `expected_return_pct` = expected_return_pct (or compute from target_price/avg_cost if not given)
  - `expected_hold_days` = expected_hold_days
  - `expected_stop_loss` = stop_loss
- Set `active_positions.original_analysis_id` = the new thesis ID
- Set `active_positions.expected_return_pct` and `active_positions.expected_hold_days`

### 2. Backend: Read Thesis with Position (portfolio/manager.py)

Modify `get_portfolio()` → when loading positions, LEFT JOIN `positions_thesis` to populate thesis fields. Add new method:

```python
async def get_thesis(self, ticker: str) -> dict | None:
    """Get thesis for a position. Returns None if no thesis recorded."""
```

### 3. API Layer (api/models.py + api/routes/portfolio.py)

**AddPositionRequest** -- add optional fields:
```python
thesis_text: str | None = None
expected_return_pct: float | None = None  # e.g. 0.18 for 18%
expected_hold_days: int | None = None
target_price: float | None = None
stop_loss: float | None = None
```

**New endpoint**: `GET /positions/{ticker}/thesis` → returns thesis + drift summary

**Extend GET /portfolio** response: each position in `positions` array should include `thesis_text`, `expected_return_pct`, `expected_hold_days`, `target_price`, `stop_loss` (null if no thesis)

### 4. Frontend: AddPositionForm Enhancement

Add a collapsible section **"Investment Thesis (optional)"** below the existing fields:

| Field | Type | Placeholder |
|-------|------|-------------|
| Thesis | textarea | "Why are you buying? e.g. AI growth thesis, strong Q4 earnings..." |
| Expected Return % | number | "18" (stored as 0.18) |
| Target Price | number | "$220" |
| Expected Hold Days | number | "60" |
| Stop Loss | number | "$170" |

- Section collapsed by default, toggle with "Add thesis +" link
- All fields optional -- user can add position without thesis (backward compatible)
- Convert expected return from user input (18) to API format (0.18) on submit

### 5. Frontend: PositionsTable Enhancement

Add columns after P&L %:

| Column | Display | Color Logic |
|--------|---------|-------------|
| Thesis | Truncated text (hover for full) | gray |
| Exp Return | "+18%" | - |
| Hold Status | "45/60d" or "90/60d" | green if ratio < 0.8, amber if 0.8-1.0, red if > 1.0 |

### 6. Frontend: Dashboard Drift Alerts

Add a new card "Thesis Check" on Dashboard between the breakdown chart and alerts:

- Show only positions WITH thesis that have a notable drift:
  - Hold time > 80% of expected: "AAPL: 48/60 days (approaching deadline)"
  - Hold time > 100% of expected: "AAPL: 90/60 days (30 days overdue)"
  - Return significantly exceeding target: "AAPL: +40% vs target +18% (consider taking profit)"
  - Return approaching stop loss: "AAPL: -8% (stop loss at -10%)"
- If no drifts, show "All positions tracking within thesis parameters"
- This is the **killer feature for demos** -- show this prominently

---

## Testing (tests/test_025_thesis_tracking.py)

1. `test_add_position_with_thesis` -- verify both tables populated
2. `test_add_position_without_thesis` -- backward compatible, no thesis record
3. `test_get_thesis` -- retrieve thesis for a position
4. `test_portfolio_includes_thesis_fields` -- GET /portfolio returns thesis data
5. `test_thesis_endpoint` -- GET /positions/AAPL/thesis returns thesis + computed drift
6. `test_expected_return_computed_from_target` -- if only target_price given, expected_return_pct is auto-computed
7. `test_hold_days_drift_calculation` -- position held 90 days with 60-day thesis → correct drift
8. `test_thesis_fields_optional` -- all thesis fields are optional in API

---

## Constraints

- Do NOT modify `db/database.py` -- the schema is already correct
- Do NOT modify `engine/drift_analyzer.py` -- it already works, just needs data
- ALL thesis fields are OPTIONAL -- adding a position without thesis must still work exactly as before
- Frontend form must be collapsible/hidden by default so it doesn't intimidate new users
- Hold status column: compute `holding_days` from `entry_date` on the frontend (already available in Position interface)

---

## Success Criteria

1. User adds position with thesis via frontend → thesis stored in DB → displayed in table
2. Dashboard shows drift alert when hold time exceeds expected
3. `GET /portfolio` returns thesis fields on each position
4. Adding position WITHOUT thesis still works (100% backward compatible)
5. All 8 tests pass
6. `tsc --noEmit` clean
