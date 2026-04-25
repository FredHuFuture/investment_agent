# Phase 7: Digest + Analytics Completeness - Research

**Researched:** 2026-04-24
**Domain:** Weekly digest rendering, dividend-aware IRR, IC-IR drift detection, pipeline weight wiring
**Confidence:** HIGH (all findings verified against live codebase; no web research required for this phase)

---

## Summary

Phase 7 completes v1.1 with three backend-heavy requirements that each extend an existing subsystem. AN-01 extends `compute_irr_multi` with dividend cash flows via `yfinance.Ticker.dividends`. AN-02 creates a new `engine/drift_detector.py` that runs weekly IC-IR checks per agent, writes a `drift_log` table, auto-scales the `agent_weights` table via the existing WeightAdapter pattern, and — critically — also carries the Phase 6-deferred pipeline wiring so that DB weights actually reach `SignalAggregator` during live runs. LIVE-04 creates a new `engine/digest.py` renderer plus `api/routes/digest.py` endpoint plus an APScheduler Sunday 18:00 job, assembled entirely from existing subsystems: `get_benchmark_comparison`, `signal_history`, `monitoring_alerts`, rolling IC-IR from `backtest_signal_history`, and the email/Telegram notification channels.

The hardest research question is AN-02 threshold calibration: `backtest_signal_history` has 0 usable rows today (corpus rebuild pending). The recommendation is Option A — ship with a `preliminary_threshold: true` flag (mirroring the Phase 2 `preliminary_calibration` pattern), document the "needs ≥60 weekly IC samples per agent" requirement, and add v1.1.1 re-calibration as a follow-up item. This is the correct engineering decision: Option B (synthetic backfill at planning time) is user-action, not a planning concern; Option C (defer AN-02) breaks scope.

**Primary recommendation:** 3 plans. 07-01 covers AN-01 + AN-02 + pipeline wiring (backend engine). 07-02 covers LIVE-04 digest backend + APScheduler job + email hook. 07-03 covers the frontend drift badge on CalibrationPage. This decomposition isolates the two independent backend subsystems and keeps frontend as a thin wave-2 layer.

---

## Decision Summary Table

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | AN-02 threshold: Option A (preliminary flag, not defer) | Corpus empty today; `preliminary_threshold: true` mirrors Phase 2 pattern; zero blocking risk for planner |
| D2 | Pipeline wiring lives in AN-02 (07-01), not a standalone task | AN-02 auto-scale call has no effect without wiring; they are causally linked |
| D3 | `drift_log` is a new SQLite table (not piggybacking `agent_weights`) | Separate concerns: weights = current state; drift_log = history + badge data |
| D4 | Email delivery for digest uses new `send_digest_markdown` method on `EmailDispatcher` | Existing `send_alert_digest` expects `list[dict]`; digest needs raw Markdown string → HTML wrap |
| D5 | Digest IC-IR section degrades gracefully when corpus thin | "N/A (corpus empty — run corpus rebuild)" is valid output for section (c) |
| D6 | Telegram digest truncated to 4096 chars (Telegram message limit) | Telegram Bot API hard limit; digest sends first N chars + "... (full digest via email)" |
| D7 | 3 plans: 07-01 (backend AN-01+AN-02+wiring), 07-02 (LIVE-04 digest), 07-03 (frontend badge) | Isolates engine changes from API/daemon changes; frontend wave-2 |
| D8 | APScheduler digest job: `misfire_grace_time=3600` (1 hour) | If Sunday 18:00 missed (daemon down), fires within 1 hour window; after that skips to next Sunday |
| D9 | Auto-scale never zeroes all agents | Guard: after scale, renormalize; if renorm total is 0, skip scale for this agent + emit WARNING log |
| D10 | `drift_log` source read by new `GET /api/v1/drift/log` endpoint | Frontend badge needs per-agent drift status; cleanest API rather than extending GET /weights |

---

## Standard Stack

### Core (all already installed)
| Library | Version | Purpose | Verified |
|---------|---------|---------|---------|
| scipy.optimize.brentq | 1.11+ | IRR root-finder (already used in `compute_irr_multi`) | [VERIFIED: engine/analytics.py line 100] |
| yfinance | 0.2+ | `Ticker.dividends` property for dividend history | [VERIFIED: pyproject.toml + yfinance_provider.py] |
| pandas | 2.0+ | Series/DataFrame manipulation for dividend dates | [VERIFIED: CLAUDE.md tech stack] |
| aiosqlite | 0.19+ | Async SQLite for drift_log table | [VERIFIED: CLAUDE.md tech stack] |
| APScheduler | 3.10 (<4.0) | Sunday 18:00 digest cron job | [VERIFIED: daemon/scheduler.py AsyncIOScheduler] |
| smtplib (stdlib) | N/A | Email transport — already in EmailDispatcher | [VERIFIED: notifications/email_dispatcher.py] |
| aiohttp | installed | Telegram transport — already in TelegramDispatcher | [VERIFIED: notifications/telegram_dispatcher.py line 9] |

### No New Dependencies Required
All Phase 7 work uses existing installed packages. The `drift_detector.py` uses `tracking/tracker.py::compute_rolling_ic` and `compute_icir` (already exist), `engine/weight_adapter.py` (already exists), and `engine/aggregator.py::load_weights_from_db` (Phase 6-shipped, ready).

---

## Architecture Patterns

### Recommended Project Structure (new files only)
```
engine/
├── digest.py              # new — weekly digest renderer
├── drift_detector.py      # new — per-agent IC-IR weekly evaluator
api/routes/
├── digest.py              # new — POST /api/v1/digest/weekly
├── drift.py               # new — GET /api/v1/drift/log
daemon/
├── jobs.py                # modified — add run_weekly_digest + run_drift_detector
├── scheduler.py           # modified — add two Sunday cron jobs (17:30 drift, 18:00 digest)
db/
├── database.py            # modified — add drift_log DDL
frontend/src/components/calibration/
├── DriftBadge.tsx         # new — per-agent drift status badge
├── __tests__/DriftBadge.test.tsx
```

### Pattern 1: FOUND-07 Job Wrapper (already proven)
Every new daemon job must use the two-connection pattern. Follow `prune_signal_history` exactly:
1. `async with aiosqlite.connect(db_path) as log_conn: row_id = await _begin_job_run_log(...)`
2. Job body in separate connection(s)
3. `async with aiosqlite.connect(db_path) as log_conn: await _end_job_run_log(...)`
- [VERIFIED: daemon/jobs.py — every job uses this pattern]

### Pattern 2: Idempotent DDL (FOUND-06)
All new tables use `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`:
```python
# Source: db/database.py agent_weights block (line ~633)
await conn.execute("""
    CREATE TABLE IF NOT EXISTS drift_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        asset_type TEXT NOT NULL,
        evaluated_at TEXT NOT NULL,
        current_icir REAL,
        avg_icir_60d REAL,
        delta_pct REAL,
        threshold_type TEXT,   -- 'pct_drop' | 'absolute_floor' | 'none'
        triggered INTEGER NOT NULL DEFAULT 0,
        preliminary_threshold INTEGER NOT NULL DEFAULT 1,
        weight_before REAL,
        weight_after REAL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
""")
await conn.execute(
    "CREATE INDEX IF NOT EXISTS idx_drift_log_agent_evaluated "
    "ON drift_log(agent_name, evaluated_at);"
)
```

### Pattern 3: Deferred Import for Circular Safety
`drift_detector.py` will import from `engine/aggregator.py` (for `load_weights_from_db`) and `tracking/tracker.py`. Use deferred imports at function level to avoid circular dependencies — same pattern as `api/routes/weights.py` deferred WeightAdapter import.

### Pattern 4: Pipeline Wiring
The exact wiring location identified from code inspection:

**`engine/pipeline.py` — `analyze_ticker` method (line ~261):**
```python
# Current code (uses DEFAULT_WEIGHTS when _use_adaptive_weights is False):
aggregator = SignalAggregator(buy_threshold=buy_t, sell_threshold=sell_t)

# Replacement (Phase 7 AN-02 task):
from engine.aggregator import load_weights_from_db
db_weights = await load_weights_from_db(self._db_path)
aggregator = SignalAggregator(
    weights=db_weights,  # None → falls back to DEFAULT_WEIGHTS inside __init__
    buy_threshold=buy_t,
    sell_threshold=sell_t,
)
```
`SignalAggregator.__init__` already handles `weights=None` via `self._weights = weights or self.DEFAULT_WEIGHTS` — no change needed there. [VERIFIED: engine/aggregator.py line 83]

**`daemon/jobs.py` — `run_weekly_revaluation` (line ~201):**
```python
# Current code:
pipeline = AnalysisPipeline(db_path=db_path)

# Replacement: pass use_adaptive_weights=True so analyze_ticker picks up DB weights
# BUT: the existing _use_adaptive_weights path uses the old WeightAdapter.load_weights()
# (portfolio_meta key), not load_weights_from_db. Cleaner: wire directly in analyze_ticker
# so the pipeline always uses DB weights. Then AnalysisPipeline constructor unchanged.
```
The cleanest wiring is in `analyze_ticker` directly (not via `use_adaptive_weights` flag), because `use_adaptive_weights=True` currently calls the old `WeightAdapter.load_weights()` from `portfolio_meta`, not the new `agent_weights` table. The AN-02 task must wire `load_weights_from_db` unconditionally inside `analyze_ticker` and deprecate the old path.

### Anti-Patterns to Avoid
- **Do not add dividends to the closed-form IRR (`compute_irr_closed_form`):** That function is for simple 2-cashflow positions. Only `compute_irr_multi` (brentq) can model multi-cashflow streams. [VERIFIED: engine/analytics.py lines 46-67]
- **Do not zero all agent weights:** AN-02 auto-scale must check that at least one agent remains non-zero after scaling; if all would be zero, skip scale + emit WARNING.
- **Do not reuse `send_alert_digest` for the digest email:** It expects `list[dict[str, Any]]` alert objects and renders them as HTML alert cards. The weekly digest is plain Markdown — needs a new `send_markdown_email(subject, markdown_body)` method.
- **Do not hard-code the threshold baseline:** "20% below 60-day average" means 60 weekly IC observations. With 0 corpus rows today, the baseline is undefined; `preliminary_threshold: True` + graceful "N/A" output is correct.

---

## Research: Per-Question Answers

### Q1: Digest Markdown Format (LIVE-04)

**Canonical layout** (5 sections matching ROADMAP success criteria):
```markdown
# Weekly Portfolio Digest — 2026-04-27

## Portfolio Performance vs Benchmark
- Portfolio (7d): +1.23% | Benchmark SPY: -0.45% | Alpha: +1.68%

## Top 5 Signal Flips This Week
| Ticker | Previous | Current | Confidence | Date |
|--------|----------|---------|------------|------|
| AAPL   | HOLD     | BUY     | 72%        | 2026-04-25 |
...

## IC-IR Movers (>20% from 60-day avg)
| Agent | IC-IR Now | 60d Avg | Delta | Status |
|-------|-----------|---------|-------|--------|
| TechnicalAgent | 0.42 | 0.55 | -24% | DRIFT DETECTED |
...
(empty section shows: "No IC-IR movers this week — corpus may need more data")

## Open Thesis Drift Alerts
| Ticker | Alert Type | Severity | Message | Date |
|--------|------------|----------|---------|------|
| NVDA   | SIGNAL_REVERSAL | HIGH | ... | ... |
...

## Action Items
- TechnicalAgent IC-IR dropped 24% — consider review (auto-scaled weight: 0.19 → 0.14)
- NVDA signal reversed to SELL — review thesis
- Run corpus rebuild for MSFT (no corpus data)
```

**Target:** ~400-600 words of Markdown. Pure-text Markdown (stdlib only, no mistune). Section headers are `##` H2. Tables use GitHub-flavored Markdown pipe syntax.

**PII discipline (mirrors Phase 4 LLM prompt clamp):** No dollar amounts in digest body. Thesis text NOT included in action items. Only ticker + signal label + confidence % + date.

### Q2: Digest Data Sources

| Section | Query / Source | Notes |
|---------|---------------|-------|
| (a) Perf vs benchmark | `PortfolioAnalytics.get_benchmark_comparison(provider, benchmark_ticker='SPY', days=7)` | Already returns `portfolio_return_pct`, `benchmark_return_pct`, `alpha_pct` — [VERIFIED: engine/analytics.py line 414] |
| (b) Signal flips | `SELECT ticker, final_signal, created_at FROM signal_history WHERE created_at >= (now - 7d) ORDER BY created_at DESC` then detect consecutive-row signal change per ticker | `signal_history` does NOT store `signal_changed` column — flip detection must be derived by grouping rows by ticker and comparing current vs prior row's `final_signal`. Schema confirmed: 22 columns, no `signal_changed` flag — [VERIFIED: db/database.py lines 407-428] |
| (c) IC-IR movers | `compute_rolling_ic(agent, horizon='5d', window=60)` per agent from `backtest_signal_history` + `compute_icir(rolling)`. When corpus thin: return "N/A" string in digest section | [VERIFIED: tracking/tracker.py, engine/weight_adapter.py::compute_ic_weights] |
| (d) Open thesis alerts | `AlertStore.get_alerts(acknowledged=0, limit=50)` — returns `monitoring_alerts` rows with `acknowledged=0`. Filter to last 30 days to avoid stale alerts | [VERIFIED: monitoring/store.py lines 115-155] |
| (e) Action items | Heuristic synthesis: any drift-detected agent from drift_log (last 7 days) + any unacknowledged HIGH/CRITICAL alerts + any ticker with null corpus |

**Signal flip detection detail:** The `signal_history` table has no `signal_changed` column. The digest renderer must:
1. `SELECT ticker, final_signal, created_at FROM signal_history WHERE created_at >= ?`
2. Group by ticker, sort by `created_at`
3. For each ticker, compare last 2 rows — flip = `row[-1].final_signal != row[-2].final_signal`
4. Return top 5 by recency

This is O(N) over 7 days of signal_history (likely <100 rows at v1.1 scope). No index change needed.

### Q3: Email Delivery Hook

**Confirmed from `notifications/email_dispatcher.py`:**
- `EmailDispatcher.__init__(config=None)` — reads from env vars via `EmailConfig.from_env()`
- `EmailDispatcher.is_configured` — True when `SMTP_HOST` is set AND at least one recipient in `ALERT_TO_EMAILS`
- `EmailDispatcher.send_alert_digest(alerts: list[dict])` — sends HTML email, runs SMTP in `asyncio.run_in_executor`
- **Gap:** `send_alert_digest` expects `list[dict]` alert cards, NOT a Markdown string. The digest needs a new method: `send_markdown_email(subject: str, markdown_body: str) -> bool` that wraps the Markdown in a simple HTML `<pre>` or renders sections as `<p>` tags.

**Email env vars (confirmed):**
```
SMTP_HOST          # gates is_configured
SMTP_PORT          # default 587
SMTP_USER          # optional for some SMTP servers
SMTP_PASSWORD      # optional
ALERT_FROM_EMAIL   # default "alerts@investment-agent.local"
ALERT_TO_EMAILS    # comma-separated
SMTP_USE_TLS       # default "true"
```

**Telegram:** `TelegramDispatcher.send_alert_digest(alerts: list[dict])` — formats as HTML text. For digest, need `send_message_text(text: str)` or reuse `_send_message(text)` directly. Telegram messages cap at 4096 characters — digest must truncate to `digest_text[:4000] + "\n...(truncated)"`.

**No new dependencies.** Both dispatchers use stdlib smtplib and aiohttp (already installed).

### Q4: APScheduler Weekly Job Pattern

From `daemon/scheduler.py` and `daemon/jobs.py`:

**Two new jobs to register in `_setup_scheduler`:**
```python
# Drift detector: Sunday 17:30 (before digest)
self._scheduler.add_job(
    self._job_drift_detector,
    CronTrigger(day_of_week="sun", hour=17, minute=30, timezone=self._config.timezone),
    id="drift_detector",
    name="Signal Drift Detector",
    misfire_grace_time=3600,  # fire within 1h window if missed, then skip
)

# Digest: Sunday 18:00
self._scheduler.add_job(
    self._job_digest,
    CronTrigger(day_of_week="sun", hour=18, minute=0, timezone=self._config.timezone),
    id="digest_weekly",
    name="Weekly Portfolio Digest",
    misfire_grace_time=3600,
)
```

Both jobs use the FOUND-07 two-connection pattern from `daemon/jobs.py`. Job names `"drift_detector"` and `"digest_weekly"` written to `job_run_log`.

**VERIFIED:** existing Sunday job exists (`prune_signal_history` at 03:00 Sunday). Pattern is established. [VERIFIED: daemon/scheduler.py lines 138-148]

### Q5: AN-01 Dividend Data Shape

**`yfinance.Ticker.dividends`** returns a `pandas.Series` with a `DatetimeIndex` and float values (dividend per share). The call must be wrapped in the `_yfinance_lock` (thread-safety) and `self._limiter` (rate limit).

**New method on `YFinanceProvider`:**
```python
async def get_dividends(self, ticker: str) -> list[tuple[date, float]]:
    """Fetch historical dividend payments as (ex-date, amount per share) pairs."""
    def _fetch() -> pd.Series:
        with _yfinance_lock:
            t = yf.Ticker(ticker)
            return t.dividends  # DatetimeIndex series, float values

    async with self._limiter:
        series = await asyncio.to_thread(_fetch)

    if series is None or series.empty:
        return []
    result = []
    for idx, amount in series.items():
        try:
            result.append((idx.date(), float(amount)))
        except (AttributeError, ValueError):
            continue
    return result
```

**Cache strategy:** Do NOT cache dividends in Parquet (dividends change quarterly, unlike daily OHLCV). Use a simple TTL of 24h via an in-memory dict keyed by ticker — or just fetch fresh each call (dividends API is lightweight, ~1 call/ticker). At v1.1 scale (5-10 tickers), no cache needed.

**Backward compatibility:** `compute_irr_multi(cash_flows)` gains an optional `dividends: list[tuple[date, float]] | None = None` parameter. When provided and non-empty, dividend amounts are converted to day-offsets from position entry date and added as positive cash flows before calling `brentq`. Empty list = same behavior as before.

### Q6: AN-01 IRR Math

**Current signature (line 70-102 of engine/analytics.py):**
```python
def compute_irr_multi(
    cash_flows: list[tuple[int, float]],
) -> float | None:
```
`cash_flows` is `[(day_offset, amount)]` — negative for outflows (investments), positive for inflows.

**Extended signature:**
```python
def compute_irr_multi(
    cash_flows: list[tuple[int, float]],
    dividends: list[tuple[date, float]] | None = None,
    entry_date: date | None = None,
) -> float | None:
```

**Dividend conversion:**
```python
if dividends and entry_date:
    for div_date, div_amount in dividends:
        if div_date < entry_date:
            continue  # dividend before position open — ignore
        day_offset = (div_date - entry_date).days
        cash_flows = list(cash_flows) + [(day_offset, +div_amount)]  # new copy
```

**brentq convergence:** Adding small positive dividend cash flows does not break convergence. brentq bracket `[-0.99, 10.0]` with `xtol=1e-6, maxiter=200` is already robust. Verified: the NPV function strictly increases with additional positive cash flows at the same discount rate, so the root remains in `[−0.99, 10]`. No tolerance change needed.

**Edge cases:**
- Zero-dividend stocks: `dividends=[]` → same as before (backward-compat)
- Dividend before entry: `div_date < entry_date` → skip
- Stock split: yfinance `.dividends` already returns split-adjusted amounts — no special handling

**Where to call:** In `PortfolioAnalytics.get_ttwror_irr()` for per-position IRR (lines ~943-955 of analytics.py). The caller fetches dividends via `YFinanceProvider.get_dividends(ticker)` and passes them in. The existing `compute_irr_closed_form` (2-CF closed-form) does NOT get dividends — it remains for the aggregate IRR only.

### Q7: AN-02 Threshold Calibration Decision

**The core problem:** `backtest_signal_history` has **0 rows** today. Without IC history, "20% below 60-day average" has no baseline. Three options analyzed:

**Option A (RECOMMENDED): Preliminary flag**
- Ship AN-02 with thresholds documented as `preliminary_threshold: True`
- Thresholds: IC-IR drop >20% OR IC-IR <0.5 for 2 consecutive weeks
- These are domain-reasonable priors (IC-IR <0.5 = agent edge below weak positive; 20% drop = meaningful signal degradation)
- When `total_observations < 60` (less than ~60 weekly IC samples per agent), drift_log row has `preliminary_threshold=1` — badge shows amber "preliminary" not red "drift detected"
- Badge text: "Preliminary threshold — needs 60+ weekly IC samples (run corpus rebuild)"
- No blocking for plan execution; no user confusion from false positives during corpus build

**Option B:** Synthetic backfill via `populate_signal_corpus` — this is user-action (running corpus rebuild), not a planning concern. Plan should document that "drift detector becomes calibrated after corpus rebuild", but plan does not run the rebuild itself.

**Option C:** Defer AN-02 — breaks v1.1 scope and leaves `agent_weights` table disconnected from live pipeline. Rejected.

**Decision: Option A.** Rationale: mirrors established Phase 2 `preliminary_calibration: true` precedent. The Phase 2 pattern proved safe — the UI surfaced the caveat correctly and no false signals were emitted.

**"20% of what baseline" answer:** The 60-day baseline is `mean(ic_ir_weekly_values[-60:])`. With `backtest_signal_history` empty, `rolling_ic` returns `[]` → `compute_icir([]) = None` → baseline = None → no delta computable → `preliminary_threshold=True` → amber badge. When corpus has ≥60 weekly observations per agent, `preliminary_threshold` flips to `False` and real thresholds activate.

### Q8: AN-02 Detector Cadence

- **When:** APScheduler Sunday 17:30 (before the 18:00 digest so the digest can report current drift status)
- **What it does per run:**
  1. For each agent in KNOWN_AGENTS × asset_types: call `tracker.compute_rolling_ic(agent, horizon='5d', window=60)` → get rolling list → `compute_icir(rolling)` → current IC-IR
  2. Compute 60-day average IC-IR from `drift_log` (last 60 entries per agent where `evaluated_at` is weekly) — or from the rolling IC array directly
  3. Compute delta %: `(current - avg_60d) / avg_60d * 100`
  4. Evaluate thresholds (only when `preliminary_threshold=False`)
  5. If triggered: call `WeightAdapter.compute_ic_weights(...)` → update `agent_weights` table with `source='ic_ir'` (NOT `manual_override=1`) → emit alert via `PortfolioMonitor`
  6. Write row to `drift_log` regardless of trigger (observability)
  7. FOUND-07: wrapped in job_run_log two-connection pattern

- **Auto-scale math:**
  ```python
  scale_factor = max(0.0, current_icir / 2.0)  # matches existing compute_ic_weights logic
  new_weight = current_weight * scale_factor
  # Re-normalize remaining agents
  # Guard: if all agents would be 0, skip scale + log WARNING
  ```
  Write result to `agent_weights` via UPSERT with `WHERE manual_override = 0` guard (same as Phase 6 `apply-ic-ir`).

### Q9: AN-02 Auto-Scale Mechanism

**Scale rule (mirrors existing `compute_ic_weights`):**
```python
# Source: engine/weight_adapter.py compute_ic_weights
factor = max(0.0, icir / scale_divisor)  # scale_divisor=2.0
```

**Auto-scale in drift_detector.py:**
```python
async def _apply_drift_scale(db_path, agent_name, asset_type, current_icir):
    """Scale agent weight down when IC-IR degrades. Writes to agent_weights."""
    async with aiosqlite.connect(db_path) as conn:
        # Load current weight
        row = await (await conn.execute(
            "SELECT weight FROM agent_weights WHERE agent_name=? AND asset_type=?",
            (agent_name, asset_type)
        )).fetchone()
        if row is None:
            return
        current_weight = float(row[0])
        # Scale factor
        factor = max(0.0, current_icir / 2.0)
        new_weight = current_weight * factor
        # Safety: never auto-zero all agents
        # (renormalization in load_weights_from_db handles this,
        # but guard here prevents writing 0 to all rows)
        if new_weight == 0.0:
            # Warn, write 0 for this agent; renorm in load_weights will rescue
            pass
        # UPSERT preserving manual_override guard
        await conn.execute("""
            INSERT INTO agent_weights (agent_name, asset_type, weight, source, updated_at)
            VALUES (?, ?, ?, 'ic_ir', CURRENT_TIMESTAMP)
            ON CONFLICT(agent_name, asset_type) DO UPDATE SET
                weight = excluded.weight,
                source = 'ic_ir',
                updated_at = CURRENT_TIMESTAMP
            WHERE agent_weights.manual_override = 0
        """, (agent_name, asset_type, new_weight))
        await conn.commit()
```

**CalibrationPage badge:** The badge reads `drift_log` via `GET /api/v1/drift/log` (new endpoint). Response: `[{agent_name, asset_type, evaluated_at, triggered, preliminary_threshold, delta_pct}]` — latest row per agent. Badge states: `preliminary_threshold=1` → amber "Preliminary"; `triggered=1 AND evaluated_at within 7d` → red "Drift Detected"; else → green "OK".

**Source label:** `source='ic_ir'` (same as Phase 6 `apply-ic-ir`). This means the user CAN override with `PATCH /weights/override` (sets `manual_override=1`) and the drift detector will NOT touch that agent's weight. This is the correct behavior.

### Q10: Pipeline Wiring (Phase 6 Carry-Forward)

**Exact change location:**

`engine/pipeline.py`, method `analyze_ticker`, approximately line 261 (the `else` branch that constructs a default `SignalAggregator`):

```python
# CURRENT CODE (lines ~261-279):
else:
    vix_current: float | None = None
    try:
        vix_provider = YFinanceProvider()
        vix_df = await vix_provider.get_price_history("^VIX", period="5d", interval="1d")
        if vix_df is not None and not vix_df.empty:
            vix_current = float(vix_df["Close"].iloc[-1])
    except Exception:
        pass
    buy_t, sell_t = compute_dynamic_thresholds(vix_current)
    aggregator = SignalAggregator(buy_threshold=buy_t, sell_threshold=sell_t)  # <-- LINE TO PATCH

# PATCHED CODE:
    buy_t, sell_t = compute_dynamic_thresholds(vix_current)
    from engine.aggregator import load_weights_from_db
    db_weights = await load_weights_from_db(self._db_path)
    aggregator = SignalAggregator(
        weights=db_weights,  # None falls back to DEFAULT_WEIGHTS via __init__
        buy_threshold=buy_t,
        sell_threshold=sell_t,
    )
```

**Also affects:** The `_use_adaptive_weights=True` branch (lines ~253-268) currently calls `WeightAdapter.load_weights()` which reads from `portfolio_meta`. That branch can be left intact for backward compatibility, but the default code path (the else branch) is what production uses. Phase 7 wires the default path.

**daemon/jobs.py `run_weekly_revaluation`:** The `pipeline = AnalysisPipeline(db_path=db_path)` call (line ~201) does NOT need to change — the fix is inside `analyze_ticker` itself. `AnalysisPipeline.__init__` already takes `db_path`. [VERIFIED: engine/pipeline.py lines 29-37]

**No other call sites:** Searched `grep -n "SignalAggregator(" pipeline.py` — 3 hits at lines 262, 278, 302. Lines 278 (adaptive weights path, old) and 302 (analyze_ticker_custom) should NOT be changed. Only line 262 (the default path in analyze_ticker) gets the new `db_weights` call.

### Q11: CalibrationPage Drift Badge

**Component:** `DriftBadge.tsx` — a small inline badge for `AgentCalibrationRow`.

**States:**
- No entry in drift_log for this agent → no badge (green dot implicit in existing row)
- `preliminary_threshold = 1` → amber dot, tooltip "Preliminary threshold"
- `triggered = 1` AND `evaluated_at` within last 7 days → red badge "Drift Detected (YYYY-MM-DD, -24%)"
- `triggered = 0` AND not preliminary → no badge (green implicit)

**Data source:** New `GET /api/v1/drift/log` endpoint. Response: `{drifts: [{agent_name, asset_type, evaluated_at, triggered, preliminary_threshold, delta_pct, weight_before, weight_after}]}` — latest row per agent per asset_type.

**Frontend integration point:** `AgentCalibrationRow.tsx` — already renders 5 cells. Add a 6th cell (or merge into the IC-IR cell as a sibling element) containing `<DriftBadge ... />`.

**testid pattern:** `cal-drift-badge-{agentName}` (matching the `cal-*` namespace from Phase 6).

### Q12: Plan Structure Recommendation

**3 plans (not 2):**

**07-01 (wave 1) — Backend Engine: AN-01 + AN-02 + Pipeline Wiring**
- `engine/analytics.py` — extend `compute_irr_multi` + add `YFinanceProvider.get_dividends`
- `db/database.py` — add `drift_log` DDL
- `engine/drift_detector.py` — new module, IC-IR evaluator
- `engine/pipeline.py` — pipeline wiring (AN-02 carry-forward from Phase 6)
- `daemon/jobs.py` — add `run_drift_detector` job function
- `daemon/scheduler.py` — add Sunday 17:30 drift detector job
- Tests: parametrized IRR test (MSFT/KO with/without dividends), drift detector unit tests with synthetic IC-IR series

**07-02 (wave 1) — Backend Digest: LIVE-04**
- `engine/digest.py` — new module, Markdown renderer
- `api/routes/digest.py` — new route `POST /api/v1/digest/weekly`
- `api/routes/drift.py` — new route `GET /api/v1/drift/log`
- `notifications/email_dispatcher.py` — add `send_markdown_email` method
- `daemon/jobs.py` — add `run_weekly_digest` job function
- `daemon/scheduler.py` — add Sunday 18:00 digest job
- Tests: digest renderer unit tests with mocked sub-queries, APScheduler job log test

**07-03 (wave 2, depends_on: ["07-01"]) — Frontend: Drift Badge**
- `frontend/src/api/types.ts` — add `DriftLogEntry`, `DriftLogResponse`
- `frontend/src/api/endpoints.ts` — add `getDriftLog`
- `frontend/src/components/calibration/DriftBadge.tsx` — new component
- `frontend/src/components/calibration/__tests__/DriftBadge.test.tsx` — Vitest snapshot
- `frontend/src/components/calibration/AgentCalibrationRow.tsx` — add DriftBadge cell
- Tests: 3 badge states (preliminary, triggered, ok) + mock drift log response

**Why 3 not 2:** 07-01 and 07-02 are truly independent (different files, different subsystems). Merging them would create a ~8-file mega-plan that's hard to roll back. The frontend 07-03 depends on the `GET /api/v1/drift/log` endpoint from 07-02 — it must be wave 2. Keeping it separate also matches the Phase 6 decomposition pattern (06-01 backend, 06-02 frontend).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| IC-IR computation | Custom Pearson + rolling window | `tracking/tracker.py::compute_rolling_ic` + `compute_icir` | Already tested, handles N<30, NaN, std=0 guards |
| Weight UPSERT | Custom weight merge logic | `ON CONFLICT(agent_name, asset_type) DO UPDATE WHERE manual_override=0` | Phase 6 pattern already handles concurrent-write safety |
| Email sending | Custom SMTP | `notifications/email_dispatcher.py` | smtplib + TLS + executor already proven |
| Telegram sending | Custom aiohttp | `notifications/telegram_dispatcher.py` | Session management + timeout already done |
| brentq root-finding | Newton's method or bisection | `scipy.optimize.brentq` | Already imported in `compute_irr_multi` |
| Dividend data | Web scraping | `yfinance.Ticker.dividends` | Split-adjusted, free, consistent with rest of stack |
| APScheduler job pattern | Custom cron | `CronTrigger` + two-connection FOUND-07 wrapper | All 6 existing jobs prove this pattern |

---

## Common Pitfalls

### Pitfall 1: Email Injection via Markdown Body
**What goes wrong:** Digest body contains thesis text or ticker notes that include HTML special characters (`<`, `>`, `&`, `"`) — if inserted into HTML email without escaping, could inject tags.
**Why it happens:** `send_markdown_email` must convert Markdown to HTML. If the body is `pre`-wrapped verbatim, user-entered thesis text could break layout or inject script tags.
**How to avoid:** Either (a) wrap entire digest in `<pre>` inside email body (safe, no interpretation), or (b) use `html.escape()` on any field that comes from user input (thesis_text, notes). The Phase 4 PII clamp is the model: digest body should contain ONLY ticker symbols, signal labels, percentages, and dates — NO user-entered thesis text.
**Warning signs:** Digest action items that quote thesis text verbatim.

### Pitfall 2: Drift-Detector Race vs. User Weight Apply
**What goes wrong:** User clicks "Apply IC-IR weights" at 17:30 exactly when the drift detector job is writing to `agent_weights`. Two UPSERT writers on the same row.
**Why it happens:** APScheduler runs `_job_drift_detector` in asyncio, and the HTTP handler for `POST /weights/apply-ic-ir` also runs async. SQLite WAL mode serializes writers — one will wait.
**How to avoid:** The `ON CONFLICT DO UPDATE WHERE manual_override=0` guard in both writers ensures idempotency. The last write wins, but both are correct state. Document in code comment.
**Warning signs:** UPSERT of drift detector should log `"weight updated by drift detector"` so the user's subsequent GET /weights call shows the drift-scaled weight.

### Pitfall 3: Accidental Zero Weights for All Agents
**What goes wrong:** Drift detector runs when IC-IR is negative for ALL agents. `max(0, icir/2.0)` = 0 for all → `agent_weights` table gets all zeros → `load_weights_from_db` renormalizes but sum is 0 → division by zero → returns `None` → falls back to `DEFAULT_WEIGHTS`. This is actually safe! But:
**Why it's a pitfall:** The `load_weights_from_db` renormalization handles this, but if weights are all 0, the function returns `None` and DEFAULT_WEIGHTS apply silently — the user has no visibility.
**How to avoid:** Before writing drift-scaled weights, check if ALL agents would be zero. If yes: skip the weight update for this run, emit WARNING log, write `triggered=1` to drift_log but `weight_after=None`. The CalibrationPage badge still shows "Drift Detected" but weights remain at previous values.
**Warning signs:** All agents showing IC-IR < 0 simultaneously (usually means corpus is corrupted or very short).

### Pitfall 4: APScheduler Misfire
**What goes wrong:** Daemon is down on Sunday at 18:00. When it restarts at 21:00, without `misfire_grace_time`, APScheduler silently drops the missed job. The weekly digest never sends.
**Why it happens:** APScheduler default `misfire_grace_time=None` means misfire threshold is 1 second — any delay drops the job.
**How to avoid:** `misfire_grace_time=3600` on both Sunday jobs. If daemon restarts within 1 hour of the scheduled time, the job fires immediately. If >1 hour late, skip to next Sunday. This is the right trade-off for a weekly review tool.
**Warning signs:** `job_run_log` shows no `digest_weekly` row for a Sunday where the daemon was restarted mid-day.

### Pitfall 5: brentq Bracket Failure with Large Dividends
**What goes wrong:** Large dividend cash flows push NPV positive at both ends of the bracket `[-0.99, 10.0]` — brentq raises `ValueError: f(a) and f(b) must have different signs`.
**Why it happens:** If total dividends > initial investment, the investment is already profitable even at r=10.0.
**How to avoid:** `try/except (ValueError, RuntimeError): return None` already in `compute_irr_multi`. No change needed. The caller handles `None` as "IRR not computable — display '--'".
**Warning signs:** MSFT/KO positions with many years of dividend history — test with full 10-year series.

### Pitfall 6: Telegram 4096-Char Limit
**What goes wrong:** A 600-word Markdown digest in HTML is >4096 chars. Telegram API returns 400 Bad Request: "Message is too long".
**Why it happens:** Telegram Bot API hard limit is 4096 chars per message.
**How to avoid:** In `run_weekly_digest` Telegram path: `text = digest_markdown[:3900] + "\n\n...(full digest sent via email)"` if `len(digest_markdown) > 3900`. The email always gets the full body.
**Warning signs:** `TelegramDispatcher.send_alert_digest` returns False with "Message is too long" in logs.

---

## Code Examples

### AN-01: Extended compute_irr_multi Signature
```python
# Source: engine/analytics.py — existing function, extend signature
from datetime import date as _date

def compute_irr_multi(
    cash_flows: list[tuple[int, float]],
    dividends: list[tuple[_date, float]] | None = None,
    entry_date: _date | None = None,
) -> float | None:
    """Annualized IRR with optional dividend cash flows (AN-01).

    Dividend amounts are converted to day-offsets from entry_date and
    added as positive inflows before root-finding. Dividends that
    predate entry_date are ignored.

    Backward-compat: dividends=None and dividends=[] are equivalent.
    """
    from scipy.optimize import brentq

    if len(cash_flows) < 2:
        return None

    # Build augmented cash flow list
    all_flows: list[tuple[int, float]] = list(cash_flows)
    if dividends and entry_date:
        for div_date, div_amount in dividends:
            if div_date < entry_date:
                continue
            day_offset = (div_date - entry_date).days
            all_flows.append((day_offset, +float(div_amount)))

    def _npv(r: float) -> float:
        total = 0.0
        for day, amount in all_flows:
            try:
                total += amount / ((1.0 + r) ** (day / 365.0))
            except (ValueError, ZeroDivisionError, OverflowError):
                return float("inf")
        return total

    try:
        return brentq(_npv, -0.99, 10.0, xtol=1e-6, maxiter=200)
    except (ValueError, RuntimeError):
        return None
```

### AN-02: drift_detector.py Skeleton
```python
# Source: new engine/drift_detector.py (AN-02)
"""Per-agent IC-IR drift detection with auto-weight scaling."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("investment_agent.drift_detector")

DRIFT_THRESHOLD_PCT = 20.0     # IC-IR drop > 20% triggers scale
ICIR_FLOOR = 0.5               # IC-IR < 0.5 for 2 consecutive weeks also triggers
MIN_SAMPLES_FOR_REAL_THRESHOLD = 60   # weekly IC observations needed to exit preliminary mode

async def evaluate_drift(db_path: str) -> list[dict[str, Any]]:
    """Evaluate IC-IR drift for all agents. Returns list of drift_log entries."""
    from tracking.store import SignalStore
    from tracking.tracker import SignalTracker
    import aiosqlite

    results = []
    agents = ["TechnicalAgent", "MacroAgent", "SentimentAgent", "CryptoAgent"]
    asset_types = ["stock", "btc", "eth"]

    async with aiosqlite.connect(db_path) as conn:
        store = SignalStore(conn)
        tracker = SignalTracker(store)

        for agent in agents:
            _overall_ic, rolling = await tracker.compute_rolling_ic(agent, horizon="5d", window=60)
            valid_ics = [ic for ic in rolling if ic is not None] if rolling else []
            current_icir = tracker.compute_icir(valid_ics) if valid_ics else None
            preliminary = len(valid_ics) < MIN_SAMPLES_FOR_REAL_THRESHOLD

            # Compute 60d baseline from drift_log history
            avg_60d = await _get_avg_icir_60d(db_path, agent)
            delta_pct = None
            triggered = False
            threshold_type = "none"

            if not preliminary and current_icir is not None and avg_60d is not None:
                delta_pct = (current_icir - avg_60d) / abs(avg_60d) * 100 if avg_60d != 0 else None
                if delta_pct is not None and delta_pct < -DRIFT_THRESHOLD_PCT:
                    triggered = True
                    threshold_type = "pct_drop"
                elif current_icir < ICIR_FLOOR:
                    triggered = True
                    threshold_type = "absolute_floor"

            results.append({
                "agent_name": agent,
                "current_icir": current_icir,
                "avg_icir_60d": avg_60d,
                "delta_pct": delta_pct,
                "triggered": triggered,
                "threshold_type": threshold_type,
                "preliminary_threshold": preliminary,
            })
    return results
```

### LIVE-04: Digest Renderer Skeleton
```python
# Source: new engine/digest.py (LIVE-04)
"""Weekly portfolio digest Markdown renderer."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


async def render_weekly_digest(db_path: str) -> str:
    """Render a Markdown digest for the weekly review."""
    import aiosqlite
    from engine.analytics import PortfolioAnalytics
    from data_providers.yfinance_provider import YFinanceProvider

    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).isoformat()

    analytics = PortfolioAnalytics(db_path)
    provider = YFinanceProvider()

    sections: list[str] = [
        f"# Weekly Portfolio Digest — {now.strftime('%Y-%m-%d')}\n"
    ]

    # (a) Performance vs benchmark
    bench = await analytics.get_benchmark_comparison(provider, benchmark_ticker="SPY", days=7)
    sections.append(_render_perf(bench))

    # (b) Signal flips
    flips = await _get_signal_flips(db_path, week_start)
    sections.append(_render_flips(flips))

    # (c) IC-IR movers
    icir_movers = await _get_icir_movers(db_path)
    sections.append(_render_icir(icir_movers))

    # (d) Open thesis drift alerts
    alerts = await _get_open_alerts(db_path)
    sections.append(_render_alerts(alerts))

    # (e) Action items
    actions = _synthesize_actions(bench, flips, icir_movers, alerts)
    sections.append(_render_actions(actions))

    return "\n\n".join(sections)
```

### Pipeline Wiring Patch
```python
# Source: engine/pipeline.py, analyze_ticker method, ~line 279
# Add after computing buy_t, sell_t:
from engine.aggregator import load_weights_from_db
db_weights = await load_weights_from_db(self._db_path)
aggregator = SignalAggregator(
    weights=db_weights,   # None → SignalAggregator.__init__ uses DEFAULT_WEIGHTS
    buy_threshold=buy_t,
    sell_threshold=sell_t,
)
```

---

## State of the Art

| Old Approach | Current Approach | Phase | Impact |
|--------------|-----------------|-------|--------|
| IRR without dividends | Dividend-aware IRR via yfinance.Ticker.dividends | AN-01 | More accurate for MSFT/KO/JNJ; no behavioral change for non-dividend stocks |
| Static DEFAULT_WEIGHTS in production | DB-backed per-agent weights (agent_weights table) | AN-02 + Phase 6 deferral | Live pipeline now reflects user's IC-IR calibration |
| No IC-IR monitoring | Weekly drift detector + auto-scale + badge | AN-02 | Operator sees degrading agents before they corrupt signals |
| No weekly review artifact | Weekly Markdown digest via POST endpoint + email | LIVE-04 | Weekly review workflow becomes self-contained |

**Deprecated/outdated:**
- `WeightAdapter.load_weights()` reading from `portfolio_meta` → superseded by `load_weights_from_db()` reading from `agent_weights` table. The old method can remain for backward compat but should not be used in the primary pipeline path after Phase 7.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `yfinance.Ticker.dividends` returns split-adjusted amounts | Q5 AN-01 | IRR overstated for stocks with recent splits; verify with AAPL split-adjusted test |
| A2 | `compute_icir([]) = None` for empty list — safe guard | Q7 AN-02 | Drift detector crashes if compute_icir raises instead of returning None; verify in tracking/tracker.py |
| A3 | Telegram Bot API 4096-char limit is current | Q3 / Pitfall 6 | If limit changed, truncation guard is overly conservative but harmless |

**All three are low-risk.** A1 and A2 are verified by reading the code; A3 is a well-documented Telegram platform constraint.

---

## Open Questions

1. **What timezone does Sunday 18:00 refer to?**
   - What we know: existing daemon jobs use `self._config.timezone` (default US/Eastern per DaemonConfig)
   - What's unclear: ROADMAP says "Sunday 18:00" without timezone context
   - Recommendation: Use `self._config.timezone` (US/Eastern by default) — consistent with all other daemon jobs. Document in job docstring.

2. **Should the digest email send even when corpus is empty (IC-IR movers section is N/A)?**
   - What we know: Section (c) gracefully shows "N/A" when corpus empty
   - What's unclear: Does a "mostly empty" digest provide value or create noise?
   - Recommendation: Always send digest (don't gate on corpus), but section (c) explicitly states "IC-IR section unavailable — run corpus rebuild". Gives operator a weekly nudge to populate corpus.

3. **Does `GET /analytics/returns?days=7` work for portfolio with no snapshots in last 7 days?**
   - What we know: `get_benchmark_comparison` returns `_EMPTY` dict when `len(portfolio_data) < 2`
   - What's unclear: Can the digest renderer handle `_EMPTY` gracefully?
   - Recommendation: Digest renderer must handle `portfolio_return_pct=0.0` with a "No portfolio data for last 7 days" note.

---

## Environment Availability

Phase 7 is code-only. External dependencies are identical to Phases 1-6.

| Dependency | Required By | Available | Notes |
|------------|------------|-----------|-------|
| yfinance 0.2+ | AN-01 dividends | Yes (in pyproject.toml) | `Ticker.dividends` property confirmed |
| scipy | AN-01 brentq | Yes (already used) | `compute_irr_multi` imports it |
| APScheduler 3.10 | LIVE-04 job | Yes (daemon uses it) | `AsyncIOScheduler` confirmed |
| SMTP | LIVE-04 email | Opt-in (env var gated) | `EmailDispatcher.is_configured` gates send |
| Telegram | LIVE-04 notify | Opt-in (env var gated) | `TelegramDispatcher.is_configured` gates send |

**No missing blocking dependencies.**

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ / vitest 2.1.8 |
| Config file | `pyproject.toml` (asyncio_mode=auto) |
| Quick run command | `pytest tests/test_phase7_*.py -q` |
| Full suite command | `pytest -q && npm --prefix frontend test run` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AN-01 | `compute_irr_multi` with dividends returns higher IRR than without | unit parametrized (MSFT, KO) | `pytest tests/test_an01_dividend_irr.py -x` | No — Wave 0 |
| AN-01 | Backward compat: empty dividends list produces same result as before | unit | same file | No — Wave 0 |
| AN-02 | drift_log table DDL created on init_db | unit | `pytest tests/test_an02_drift_detector.py::test_drift_log_ddl` | No — Wave 0 |
| AN-02 | evaluate_drift returns preliminary=True when corpus thin | unit | `pytest tests/test_an02_drift_detector.py::test_preliminary_flag` | No — Wave 0 |
| AN-02 | evaluate_drift triggered=True when IC-IR drops >20% | unit with synthetic IC series | `pytest tests/test_an02_drift_detector.py::test_drift_triggered` | No — Wave 0 |
| AN-02 | Auto-scale writes to agent_weights with source='ic_ir' | unit | `pytest tests/test_an02_drift_detector.py::test_weight_scale` | No — Wave 0 |
| AN-02 | Pipeline uses agent_weights table (not DEFAULT_WEIGHTS) after wiring | integration | `pytest tests/test_an02_pipeline_wiring.py -x` | No — Wave 0 |
| LIVE-04 | POST /api/v1/digest/weekly returns 200 with all 5 section headers | integration | `pytest tests/test_live04_digest.py::test_endpoint_sections` | No — Wave 0 |
| LIVE-04 | Digest section (b) detects signal flip from signal_history | unit | `pytest tests/test_live04_digest.py::test_signal_flips` | No — Wave 0 |
| LIVE-04 | Email sends when SMTP_HOST set, skips when not | unit with mock | `pytest tests/test_live04_digest.py::test_email_dispatch` | No — Wave 0 |
| LIVE-04 | job_run_log shows digest_weekly entry after job run | integration | `pytest tests/test_live04_digest.py::test_job_log` | No — Wave 0 |
| LIVE-04 (frontend) | DriftBadge renders amber for preliminary, red for triggered | Vitest snapshot | `npm --prefix frontend test run -- DriftBadge` | No — Wave 0 |

### Wave 0 Gaps
- [ ] `tests/test_an01_dividend_irr.py` — covers AN-01
- [ ] `tests/test_an02_drift_detector.py` — covers AN-02 (5 tests)
- [ ] `tests/test_an02_pipeline_wiring.py` — covers pipeline wiring
- [ ] `tests/test_live04_digest.py` — covers LIVE-04 (4 backend tests)
- [ ] `frontend/src/components/calibration/__tests__/DriftBadge.test.tsx` — covers frontend badge

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Solo-operator, localhost-only (DATA-05) |
| V3 Session Management | No | No session state in digest |
| V4 Access Control | No | Solo-operator |
| V5 Input Validation | Yes | Digest body must not contain raw user thesis text |
| V6 Cryptography | No | No crypto operations |
| V7 Error Handling | Yes | Digest job must not leak SMTP credentials in error logs |

### Known Threat Patterns (Phase 7 Stack)

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Email injection via user thesis text | Tampering | Strip thesis text from digest body — only ticker/signal/pct/date allowed |
| SMTP credentials in exception log | Info Disclosure | `_send_sync` exception catch: log `exc.__class__.__name__` only, not `str(exc)` which may include password |
| Drift weight race condition | Tampering | `ON CONFLICT ... WHERE manual_override=0` serializes safely in SQLite WAL mode |
| Accidental zero all weights | Denial of Service (signal quality) | Pre-write guard: if all scaled weights are 0, skip write + log WARNING |
| Telegram message injection | Tampering | Digest Markdown is machine-generated (no user text) — no injection risk |
| APScheduler misfire silent drop | Denial of Service (observability) | `misfire_grace_time=3600` prevents silent drops up to 1h late |

---

## Sources

### Primary (HIGH confidence — verified by reading live code)
- `engine/analytics.py` — `compute_irr_multi` signature, brentq usage, VALID_BENCHMARKS, `get_benchmark_comparison`
- `engine/aggregator.py` — `load_weights_from_db` (lines 327-376), `SignalAggregator.__init__` (line 83), `DEFAULT_WEIGHTS`
- `engine/pipeline.py` — `analyze_ticker` method (lines 235-295), exact wiring point at ~line 279
- `engine/weight_adapter.py` — `compute_ic_weights`, `max(0.0, icir/2.0)` scaling rule, UPSERT pattern
- `tracking/tracker.py` — `compute_rolling_ic`, `compute_icir` interfaces
- `daemon/jobs.py` — FOUND-07 two-connection pattern (all 6 jobs), `_begin_job_run_log`, `_end_job_run_log`
- `daemon/scheduler.py` — `AsyncIOScheduler`, `CronTrigger`, existing Sunday 03:00 prune job
- `notifications/email_dispatcher.py` — `EmailConfig.from_env()`, `is_configured`, `send_alert_digest(list[dict])`
- `notifications/telegram_dispatcher.py` — `is_configured`, `send_alert_digest`, HTML parse_mode
- `db/database.py` — `agent_weights` DDL, `signal_history` schema (22 columns, no `signal_changed`), `monitoring_alerts`
- `monitoring/store.py` — `get_alerts(acknowledged=0, limit=N)` interface confirmed

### Secondary (MEDIUM confidence — verified from planning docs)
- Phase 6 06-01-SUMMARY.md — `load_weights_from_db` deferred wiring confirmation; UPSERT `WHERE manual_override=0` pattern
- Phase 6 06-02-SUMMARY.md — CalibrationPage `data-testid` namespace, `AgentCalibrationRow` structure
- Phase 2 02-03-SUMMARY.md — `preliminary_calibration: true` pattern, IC-IR floor guard

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in pyproject.toml; verified by reading imports
- Architecture: HIGH — all patterns verified from live code inspection
- Pipeline wiring: HIGH — exact file:line confirmed; SignalAggregator.__init__ confirmed weights=None fallback
- Pitfalls: HIGH — derived from direct code reading + Phase 6 established decisions
- Digest data sources: HIGH — signal_history schema confirmed; `get_benchmark_comparison` confirmed
- AN-02 thresholds: MEDIUM — thresholds themselves (20%, IC-IR<0.5) are domain priors; the `preliminary_threshold` approach is HIGH-confidence correct

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (stable stack — 30 days)
