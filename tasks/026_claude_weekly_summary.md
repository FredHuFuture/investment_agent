# Task 026 -- Claude Weekly Portfolio Summary

## Objective

Add ONE LLM feature: a weekly portfolio summary written by Claude that reviews each position's thesis against recent market reality. This transforms the product from "indicator calculator" into a real "investment agent."

**User story**: "Every Sunday I get a summary: 'Your AAPL thesis is AI growth, but last week's earnings showed Services revenue (+20%) outpacing hardware. Your thesis may need updating. GS is tracking well -- your financials recovery thesis aligns with rising NIM data. BTC has held above $65K support for 3 weeks -- your halving cycle thesis remains intact.'"

**Scope discipline**: This is ONE agent doing ONE thing (weekly summary). NOT three agents (SentimentAgent + CatalystScanner + ValidationAgent). We can split later if needed.

---

## Scope

**Files to CREATE (3):**

| File | Purpose |
|------|---------|
| `agents/summary_agent.py` | `SummaryAgent` -- generates natural language portfolio review using Claude API |
| `api/routes/summary.py` | `POST /summary/generate`, `GET /summary/latest` endpoints |
| `tests/test_026_summary_agent.py` | 8 tests |

**Files to MODIFY (5):**

| File | Change |
|------|--------|
| `db/database.py` | Add `portfolio_summaries` table |
| `api/app.py` | Register summary router |
| `api/models.py` | Add `SummaryResponse` model |
| `daemon/jobs.py` | Add weekly summary job |
| `frontend/src/pages/DashboardPage.tsx` | Add "Weekly Summary" card |

---

## Detailed Requirements

### 1. Database: portfolio_summaries table (db/database.py)

```sql
CREATE TABLE IF NOT EXISTS portfolio_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_text TEXT NOT NULL,
    generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model TEXT NOT NULL,              -- e.g. 'claude-sonnet-4-20250514'
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    positions_covered TEXT NOT NULL    -- JSON list of tickers covered
);
```

### 2. SummaryAgent (agents/summary_agent.py)

```python
class SummaryAgent:
    """Generates weekly portfolio summaries using Claude API."""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model

    async def generate_summary(self, context: PortfolioContext) -> SummaryResult:
        """Generate a natural language portfolio review."""
```

**PortfolioContext** (what we send to Claude):

```python
@dataclass
class PortfolioContext:
    positions: list[PositionContext]  # Each position's data
    total_value: float
    cash_pct: float
    period: str  # "2026-03-04 to 2026-03-11"

@dataclass
class PositionContext:
    ticker: str
    asset_type: str
    quantity: float
    avg_cost: float
    current_price: float
    unrealized_pnl_pct: float
    holding_days: int
    # Thesis (if exists)
    thesis_text: str | None
    expected_return_pct: float | None
    expected_hold_days: int | None
    target_price: float | None
    stop_loss: float | None
    # Latest agent signals (from last analysis run)
    latest_signal: str | None  # "BUY" / "SELL" / "HOLD"
    latest_confidence: float | None
    # Price action this week
    week_return_pct: float | None  # price change in last 7 days
```

**Prompt design** (system prompt):

```
You are an investment analysis assistant. Review the portfolio below and write a concise weekly summary.

For each position:
1. If the user recorded a thesis, evaluate whether recent price action supports or contradicts it
2. Flag any positions where hold time exceeds the planned duration
3. Flag positions approaching stop loss or significantly exceeding target
4. Note any positions where the latest agent signal disagrees with the current holding

Keep it conversational but data-driven. Use specific numbers. 3-5 sentences per position.
End with a 1-2 sentence overall portfolio assessment.

IMPORTANT: You are NOT giving investment advice. You are helping the user evaluate their OWN thesis.
Do NOT recommend specific actions. Instead, flag observations and let the user decide.
```

**SummaryResult**:
```python
@dataclass
class SummaryResult:
    summary_text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float  # computed from token counts
    positions_covered: list[str]
```

**Cost tracking**: Claude Sonnet pricing. Estimate ~2K input tokens + ~500 output tokens per position. 5 positions ≈ $0.02-0.05 per summary. Log actual usage.

### 3. Gathering Context (agents/summary_agent.py)

The agent needs a `build_context()` classmethod that gathers data from existing modules:

```python
@classmethod
async def build_context(cls, db_path: str) -> PortfolioContext:
    """Gather all data needed for the summary from existing DB."""
    mgr = PortfolioManager(db_path)
    portfolio = await mgr.get_portfolio()

    # For each position:
    # 1. Thesis data: from positions_thesis table (via manager, added in Task 025)
    # 2. Latest signal: from signal_history table (tracking/store.py)
    # 3. Week return: compute from current_price vs 7-day-ago price (yfinance)

    return PortfolioContext(...)
```

**Key**: Reuse existing modules. Do NOT duplicate data fetching logic.

### 4. API Endpoints (api/routes/summary.py)

**`POST /summary/generate`**:
- Triggers summary generation (async)
- Returns: SummaryResponse with full text + cost info
- Requires `ANTHROPIC_API_KEY` env var; returns 503 with clear message if not set

**`GET /summary/latest`**:
- Returns most recent saved summary from DB
- Returns 404 if no summaries exist yet

### 5. Daemon Integration (daemon/jobs.py)

Add to existing daemon job system:
- New job: `weekly_summary` -- runs every Sunday at 6pm (after markets close for the week)
- Uses existing APScheduler infrastructure from Task 014
- Only runs if ANTHROPIC_API_KEY is set; logs warning and skips otherwise
- Saves result to `portfolio_summaries` table

### 6. Frontend: Dashboard Summary Card

Add a card on Dashboard page (above or below the Thesis Check card from Task 025):

**"Weekly Summary"** card:
- If summary exists: show `summary_text` with `generated_at` timestamp
- Render markdown (the summary will use basic markdown: bold, bullet points)
- Show cost badge: "$0.03" in gray text
- "Regenerate" button → calls `POST /summary/generate`
- If no summary: show "No summary yet. Click 'Generate' to create one." with Generate button
- If no API key: show "Set ANTHROPIC_API_KEY to enable AI summaries" in amber warning
- Loading state while generating (can take 5-10 seconds)

---

## Testing (tests/test_026_summary_agent.py)

**Mock Claude API** -- do NOT make real API calls in tests.

1. `test_build_context` -- verify context gathering from DB (use test DB with fixtures)
2. `test_generate_summary_success` -- mock httpx response, verify SummaryResult
3. `test_generate_summary_no_api_key` -- raises clear error
4. `test_prompt_includes_thesis` -- verify thesis text appears in the prompt sent to Claude
5. `test_prompt_excludes_thesis_when_none` -- positions without thesis don't mention "thesis"
6. `test_cost_calculation` -- verify cost_usd from token counts
7. `test_summary_saved_to_db` -- verify DB write after generation
8. `test_api_endpoint_503_no_key` -- POST /summary/generate returns 503 without API key

---

## Dependencies

- **Task 025 (Thesis Tracking) must be done first** -- this task reads thesis data from positions
- `anthropic` Python SDK: add `anthropic>=0.42` to pyproject.toml dependencies
- `ANTHROPIC_API_KEY` env var (optional -- feature degrades gracefully without it)

---

## Constraints

- ONE agent, ONE feature. Do not build SentimentAgent or CatalystScanner in this task.
- Mock all Claude API calls in tests -- zero real API spending in CI
- Summary must include the disclaimer "This is not investment advice" at the end
- Cost per summary should stay under $0.10 for a 10-position portfolio
- If API call fails, save error to DB and show user-friendly message ("Summary generation failed. Will retry next week.")
- Summary text should be stored as-is from Claude, no post-processing

---

## Success Criteria

1. `POST /summary/generate` returns a natural language portfolio review
2. Summary references thesis text when available (the killer demo)
3. Cost tracked and displayed ($0.02-0.05 per summary)
4. Graceful degradation: everything works without API key, just no summary feature
5. Dashboard shows summary card with regenerate button
6. All 8 tests pass (with mocked API)
7. `tsc --noEmit` clean
