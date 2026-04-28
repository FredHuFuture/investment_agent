# Architecture Research — v1.2 Trustworthy Signals

**Domain:** Brownfield integration into existing Investment Agent (FastAPI + APScheduler + aiosqlite + React/TS)
**Researched:** 2026-04-27
**Confidence:** HIGH — derived from direct file reads of existing modules; no external assumptions.

## Scope

This is **integration research, not greenfield architecture**. The Investment Agent is a mature codebase (889 tests, 15 frontend pages, 3 milestones shipped). This document answers ONE question: **how do the 4 v1.2 features slot into the existing system?**

Four target capabilities:

1. **SIG-v2-01** — Calibration reliability plots on `/calibration` page
2. **DATA-v2-02** — SimFin point-in-time fundamentals provider
3. **DATA-v2-03** — CoinGecko on-chain provider for CryptoAgent
4. **SIG-v2-04 / carry-forward** — Drift-threshold validation against live corpus

---

## Existing Architecture (load-bearing context)

### Layer Map

```
┌──────────────────────────────────────────────────────────────────┐
│                  React + TS frontend (15 pages)                   │
│   /calibration, /weights→Navigate, /portfolio, /backtest, ...    │
│   Recharts (sparklines, analytics) + LightweightCharts + SVG     │
└──────────────────────────────┬───────────────────────────────────┘
                               │  /api/v1/...  (HTTP, ApiError envelope)
┌──────────────────────────────▼───────────────────────────────────┐
│                       api/ — FastAPI routers                      │
│   analytics, calibration, drift, digest, weights, analyze, ...   │
│   30+ endpoints, dependency-injected db_path, Pydantic v2 models │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│         engine/  + tracking/ + portfolio/ + monitoring/           │
│   pipeline.py (orchestrator), aggregator.py (weighted vote),     │
│   drift_detector.py (Sun 17:30), llm_synthesis (opt-in),         │
│   tracker.py (Brier/IC/IC-IR), analytics.py (TTWROR/CVaR)        │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                       agents/ — BaseAgent ABC                     │
│   technical, fundamental, macro, sentiment, crypto, summary      │
│   Each: async analyze(AgentInput) -> AgentOutput                 │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                  data_providers/ — DataProvider ABC               │
│   yfinance, fred, ccxt, finnhub, edgar, news, web_news           │
│   CachedProvider (TTLCache + ParquetOHLCVCache + thundering-herd)│
│   AsyncRateLimiter (token bucket), DividendCache (24h Parquet)   │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│      SQLite (aiosqlite, WAL, connection pool)                     │
│   signal_history, backtest_signal_history, agent_weights,        │
│   drift_log, corpus_rebuild_jobs, job_run_log, alert_rules,      │
│   active_positions, trade_records, portfolio_snapshots, ...      │
└───────────────────────────────────────────────────────────────────┘
```

### Background scheduler (APScheduler — `daemon/scheduler.py`)

| Cron slot | Job | Source |
|-----------|-----|--------|
| Mon-Fri 17:00 ET | `run_daily_check` | `daemon/jobs.py` |
| Sat 10:00 ET | `run_weekly_revaluation` | `daemon/jobs.py` |
| Sun 17:30 ET | `run_drift_detector` (AN-02) | `daemon/jobs.py` → `engine/drift_detector.py` |
| Sun 18:00 ET | `run_weekly_digest` (LIVE-04) | `daemon/jobs.py` |

### Provider pattern (mandatory mirror)

Every existing provider obeys the same skeleton (verified across `finnhub_provider.py`, `edgar_provider.py`, `fred_provider.py`):

1. Class-level `AsyncRateLimiter` with vendor-specific budget (`_limiter = AsyncRateLimiter(max_calls=N, period_seconds=60.0)`)
2. `__init__(api_key=None, timeout=10.0)` — fall back to `os.getenv()`, warn (not raise) on missing key
3. `httpx.AsyncClient` with `params={"token": resolved_key}` so the secret is never in log lines
4. `_rate_limited_get(path, params)` → returns `{}` on 429, raises on other HTTP errors
5. Inherits from `data_providers/base.py::DataProvider` (abstract `get_price_history`, `get_current_price`, optional `get_financials`/`get_key_stats`)
6. Implements `is_point_in_time()` and `supported_asset_types()`
7. Optional `aclose()` for graceful httpx shutdown

### Cache pattern (mandatory mirror)

| Cache | Scope | TTL | File |
|-------|-------|-----|------|
| `TTLCache` (in-memory async) | Per-process, per-method | 5 min default, 15 min macro | `data_providers/cache.py` |
| `ParquetOHLCVCache` (disk) | Cross-process | 24h default, ticker × period × interval keyed | `data_providers/parquet_cache.py` |
| `DividendCache` (disk) | Cross-process | 24h, per-ticker | `data_providers/dividend_cache.py` |
| `sector_pe_cache` (disk JSON) | Cross-process | 24h | `data_providers/sector_pe_cache.py` |

CR-02 thundering-herd dedup is implemented in `CachedProvider.get_price_history` (`_inflight: dict[key, asyncio.Event]`). New providers writing to expensive endpoints should mirror this pattern.

### Frontend calibration mount point

`frontend/src/pages/CalibrationPage.tsx` already loads three APIs in parallel:
- `getCalibrationAnalytics()` → `/api/v1/analytics/calibration`
- `getWeightsV2()` → `/api/v1/weights`
- `getDriftLog()` → `/api/v1/drift/log`

Components:
- `CalibrationTable` (renders rows with empty-corpus CTA)
- `AgentCalibrationRow` (single row: agent | Brier | IC | IC-IR + DriftBadge | sparkline)
- `ICSparkline` (60×20px Recharts LineChart)
- `WeightsEditor` (Apply IC-IR + per-agent override toggle)
- `AssetTypeTabs` (stock | btc | eth)
- `DriftBadge` (3-state: null | amber-preliminary | red-triggered)

---

## Question-by-question integration analysis

### Q1 — Reliability plots (SIG-v2-01)

**Current state.** The codebase has TWO calibration-flavored functions in `tracking/tracker.py`:

| Function | Source corpus | Bins on | Purpose | Used by |
|----------|---------------|---------|---------|---------|
| `compute_calibration_data()` | live `signal_history` (resolved WIN/LOSS) | confidence midpoint vs win-rate | LIVE win-rate calibration | `/signals/*` accuracy display (older) |
| `compute_brier_score()` + `compute_rolling_ic()` + `compute_icir()` | `backtest_signal_history` | per-agent | Phase 2 calibration metrics | `/api/v1/analytics/calibration` |

Reliability plots = **Brier-score decomposition into bins** (predicted-prob vs realized-frequency). Already implemented for confidence/win-rate in `compute_calibration_data` but ONLY against live `signal_history`.

#### Recommendation

**Where bin computation lives:** Extend `tracking/tracker.py` with a new method `compute_reliability_bins(agent_name, horizon, n_bins=10, min_bucket_size=20)`. **Do NOT create a new module** — `tracker.py` already owns the parallel methods (Brier, IC, IC-IR) over the same corpus and shares the `SignalStore.get_backtest_signals_by_agent` reader.

```python
# tracking/tracker.py — new method
async def compute_reliability_bins(
    self,
    agent_name: str,
    horizon: str = "5d",
    n_bins: int = 10,
    min_bucket_size: int = 20,
) -> list[dict[str, Any]] | None:
    """Reliability diagram bins for one agent.

    Bins predicted probability (confidence/100 normalized via Brier convention,
    HOLD excluded — reuses the AP-05 contract from compute_brier_score) and
    returns observed frequency of correct directional moves per bin.

    Returns [{bin_lo, bin_hi, n, predicted, observed, ece_contrib}, ...]
    or None if N < min_bucket_size globally.
    """
```

**Source corpus.** Use `backtest_signal_history` (NOT live `signal_history`). Rationale:
- Reliability plots need >= 200 directional samples per agent per bin to be meaningful — live corpus has ~10 rows as of 2026-04-21 (per CONCERNS.md)
- Existing Brier/IC/IC-IR pipeline already reads from `backtest_signal_history` via `SignalStore.get_backtest_signals_by_agent(agent_name, horizon)`
- Same N>=20 / N>=30 thresholds already in place; no new sparsity logic needed
- CalibrationPage already has the corpus-empty CTA + `Rebuild corpus` button — we get this UX for free

**API endpoint shape.** Two options analyzed; recommend **option B** (extend existing endpoint):

```
Option A (NEW endpoint):  GET /api/v1/analytics/reliability?agent={name}&horizon=5d
Option B (EXTEND):        GET /api/v1/analytics/calibration?include_reliability=true
```

**Pick option B.** Reasoning:
- CalibrationPage already calls `/analytics/calibration` and renders agents in a single table; reliability is "another column per agent", not a separate page
- Adds one optional query param, zero new routes, zero new types in `frontend/src/api/types.ts` other than appending `reliability_bins?: ReliabilityBin[]` to `AgentCalibrationEntry`
- Keeps the corpus_metadata `total_observations` flag relevant to both metrics — one network call surfaces empty-corpus state

Response shape (additive — preserves WARNING 11 stable-key contract):

```json
{
  "data": {
    "agents": {
      "TechnicalAgent": {
        "brier_score": 0.234,
        "ic_5d": 0.043,
        "ic_horizon": "5d",
        "ic_ir": 0.612,
        "sample_size": 142,
        "rolling_ic": [...],
        "reliability_bins": [
          {"bin_lo": 0.30, "bin_hi": 0.40, "n": 22, "predicted": 0.35, "observed": 0.41, "ece_contrib": 0.013}
        ],
        "ece": 0.087
      }
    },
    "horizon": "5d",
    "window_days": 60
  }
}
```

**Frontend mount point.** Add a NEW small component, not extend `AgentCalibrationRow`. Reasoning:
- The row is already 5 columns wide and tight; adding a histogram cell crowds it
- Reliability is most useful as a **drill-down**, not a constantly-visible micro-viz
- Other dashboards (e.g., qlib, Optuna) put reliability behind an expandable cell

```
frontend/src/components/calibration/
  ├── AgentCalibrationRow.tsx    [MODIFIED — add expandable triangle]
  ├── ReliabilityChart.tsx       [NEW — Recharts ScatterChart with diagonal y=x]
  └── ReliabilityModal.tsx       [NEW — optional, if expansion grows complex]
```

`ReliabilityChart` uses Recharts `ScatterChart` (already in `package.json`) with:
- X-axis: predicted probability bin midpoint (0.0–1.0)
- Y-axis: observed frequency (0.0–1.0)
- Reference line `y = x` (perfect calibration)
- Point size: bin sample count (n)
- Color: from `sparklineColor()` reuse (green/amber/red by ECE)

**ECE (Expected Calibration Error).** Add as a row-level metric next to IC-IR. Single number summarizing reliability:
```
ECE = sum_b ( |predicted_b - observed_b| × n_b / N_total )
```
This goes in `AgentCalibrationEntry.ece` and renders as a fourth metric column alongside Brier, IC, IC-IR.

**Files touched (Q1 summary):**

| Action | File |
|--------|------|
| MODIFY | `tracking/tracker.py` (+ `compute_reliability_bins`, + `compute_ece`) |
| MODIFY | `tracking/store.py` (no changes — uses existing `get_backtest_signals_by_agent`) |
| MODIFY | `api/routes/calibration.py` (+ `include_reliability` query param, + ECE field) |
| MODIFY | `api/models.py` (+ Pydantic models for `ReliabilityBin`) |
| MODIFY | `frontend/src/api/types.ts` (+ `reliability_bins`, + `ece`) |
| MODIFY | `frontend/src/components/calibration/AgentCalibrationRow.tsx` (+ expandable + ECE column) |
| MODIFY | `frontend/src/components/calibration/CalibrationTable.tsx` (+ ECE header) |
| NEW | `frontend/src/components/calibration/ReliabilityChart.tsx` |
| NEW | `tests/test_tracker_reliability.py` (Brier-decomposition correctness) |
| NEW | `frontend/src/components/calibration/__tests__/ReliabilityChart.test.tsx` |

---

### Q2 — SimFin provider (DATA-v2-02)

**Current state.**
- `agents/fundamental.py` calls `self._provider.get_key_stats(ticker)` and `self._provider.get_financials(ticker)` — provider is **injected**, not hardcoded
- The injected provider in production is a `CachedProvider(YFinanceProvider())` (from `data_providers/factory.py::get_provider("stock")`)
- `agents/fundamental.py` is the ONLY production call site for these methods (Tech/Macro/Crypto don't read fundamentals)
- The agent has a `NON_PIT_WARNING` constant emitting "Data sourced from yfinance (non-point-in-time)" — already self-documenting that PIT is the gap
- `FOUND-04` short-circuits FundamentalAgent in `backtest_mode` because yfinance returns restated financials — this is precisely the gap SimFin fills

#### Recommendation

**Module placement.** Mirror Finnhub exactly: `data_providers/simfin_provider.py`. New class `SimfinProvider(DataProvider)`. Implements `get_financials(ticker, period)` and `get_key_stats(ticker)`. **Does NOT implement `get_price_history`** (raise `NotImplementedError`, same as Finnhub).

**Cache strategy.** SimFin distributes data primarily as bulk Parquet/CSV files (free tier: ~quarterly bulk download). Two-layer cache:

1. **On-disk Parquet cache** at `data/cache/simfin/` — bulk CSV downloaded once per ~quarter, parsed lazily by ticker. Mirror `ParquetOHLCVCache` skeleton + Windows atomic-rename + 3-retry pattern.
   - File: `data_providers/simfin_cache.py` (NEW — parallels `parquet_cache.py` and `dividend_cache.py`)
   - TTL: 90 days (quarterly bulk drops) — but invalidate manually via SimFin's date-stamped bulk file
2. **In-memory `TTLCache`** via `CachedProvider` wrapper — same 5-minute TTL applies for repeated `get_key_stats` calls within a request

**Cost assumption verification.** SimFin's free tier: API requires registration + free key, bulk CSV downloads available without auth. No paid tier required for v1.2 scope per Constraints. Verify before Phase 8 implementation by checking `https://simfin.com/data/access/api`.

**Routing logic.** Three options — recommend **option C** (config flag + automatic fallback):

| Option | Pros | Cons |
|--------|------|------|
| A. Always use SimFin when `SIMFIN_API_KEY` set | Simple | Locks user out of yfinance fast path; 24h Parquet cache hides sparse-coverage gaps |
| B. New routing layer in `factory.py` | Centralized | Adds another factory; routing logic spreads across factory + cached_provider |
| C. **Config flag (`SIMFIN_FOR_FUNDAMENTALS=true`) + automatic ticker-coverage fallback** | Single switch; graceful degradation per-ticker | Slightly more code in `fundamental.py` |

**Pick option C.** Reasoning:
- SimFin coverage is solid for US equities but thin for ADRs / small caps — automatic fallback is safer than hard switch
- Config flag respects existing project pattern (`ENABLE_LLM_SYNTHESIS`, `INVESTMENT_AGENT_CACHE_DISABLED`)
- One change to `agents/fundamental.py` (try-SimFin → catch-and-fallback-to-yfinance) plus one provider injection in `engine/pipeline.py` — bounded blast radius

```python
# engine/pipeline.py — modified section
if asset_type == "stock":
    fundamental_agent = FundamentalAgent(primary_provider)  # yfinance for prices/key_stats fallback
    # NEW: if SimFin enabled, attach as PIT-preferred provider for fundamentals
    if os.getenv("SIMFIN_FOR_FUNDAMENTALS") == "true":
        try:
            from data_providers.simfin_provider import SimfinProvider
            fundamental_agent.set_pit_provider(SimfinProvider())
        except Exception as exc:
            pipeline_warnings.append(f"SimFin disabled: {exc}")
    agents.append(fundamental_agent)
```

```python
# agents/fundamental.py — modified call site
async def analyze(self, agent_input: AgentInput) -> AgentOutput:
    # ... backtest_mode short-circuit ...

    # PIT-preferred provider when available, else yfinance
    if self._pit_provider is not None and not agent_input.backtest_mode:
        # SimFin path
        try:
            key_stats = await self._pit_provider.get_key_stats(agent_input.ticker)
            financials = await self._pit_provider.get_financials(agent_input.ticker)
            warnings.append("PIT data sourced from SimFin.")  # supersedes NON_PIT_WARNING
        except Exception as exc:
            self._logger.warning("SimFin lookup failed for %s, falling back to yfinance: %s", ...)
            key_stats = await self._provider.get_key_stats(...)
            financials = await self._provider.get_financials(...)
            warnings.append(NON_PIT_WARNING)
    else:
        # Existing yfinance path
        key_stats = await self._provider.get_key_stats(...)
        ...
```

**Critical detail — backtest_mode + SimFin.** If SimFin truly delivers point-in-time data, the FOUND-04 backtest_mode short-circuit could be **conditionally lifted** when SimFin is the active provider. This is a **separate REQ** (let's call it DATA-v2-02b) and should NOT be bundled with the basic provider work — it changes contract semantics for the FOUND-04 regression test (`test_synthesis_skipped_in_backtest_mode` analog).

**Files touched (Q2 summary):**

| Action | File |
|--------|------|
| NEW | `data_providers/simfin_provider.py` |
| NEW | `data_providers/simfin_cache.py` (mirrors `parquet_cache.py`) |
| MODIFY | `data_providers/__init__.py` (export `SimfinProvider`) |
| MODIFY | `agents/fundamental.py` (+ `set_pit_provider`, + dual-path branch) |
| MODIFY | `engine/pipeline.py` (+ inject SimfinProvider when env flag set) |
| MODIFY | `pyproject.toml` (+ `simfin` optional dep — likely add to `[all]` extra; consider new `[fundamentals-pit]` extra) |
| NEW | `tests/test_simfin_provider.py` |
| NEW | `tests/test_fundamental_agent_simfin_routing.py` |

---

### Q3 — CoinGecko provider (DATA-v2-03)

**Current state.**
- `agents/crypto.py` is a 7-factor model — Factor 6 (`_score_network_adoption`) currently uses **STATIC constants** loaded from `config/crypto_adoption.yaml` (age_years, ETF status, regulatory, bear_survivals)
- The agent emits a warning: `"Network adoption uses static constants (not live chain data). Factor weight reduced to 5%."`
- CONCERNS.md flags this as a **"Missing Critical Feature"**: "On-chain metrics for crypto analysis... CryptoAgent uses price-based metrics only. No access to on-chain data (MVRV ratio, SOPR, exchange flows)"
- Existing CCXT provider handles exchange-specific endpoints (funding rate, order book) but NOT on-chain data
- Crypto factor weight `network_adoption: 0.05` is currently the lowest weighted factor — this is the lever to grow

#### Recommendation

**Module placement.** New file `data_providers/coingecko_provider.py`. Class `CoinGeckoProvider(DataProvider)`. Mirrors Finnhub exactly. Free tier: 10-30 req/min on demo API (no key required for `/coins/markets` etc.); paid tier `/coins/{id}/community_data` and `/coins/{id}/developer_data` also accessible without key on demo throttle.

```python
class CoinGeckoProvider(DataProvider):
    _limiter = AsyncRateLimiter(
        max_calls=int(os.getenv("COINGECKO_RATE_LIMIT", "10")),
        period_seconds=60.0,
    )

    async def get_on_chain_metrics(self, asset: str) -> dict:
        """Returns {community_score, dev_score, watchlist_count, sentiment_pct, ...}.

        Maps asset string ('btc' / 'eth') to CoinGecko coin_id ('bitcoin' / 'ethereum').
        """
```

**Methods needed for v1.2:**
- `get_on_chain_metrics(asset)` — community_data + developer_data + market_data subset
- `get_price_history(...)` → `NotImplementedError` (yfinance/CCXT keeps OHLCV ownership; we want on-chain only)
- `get_current_price(...)` → optional fallback (CoinGecko `/simple/price`); skip in v1.2 to keep scope tight

**On-chain signal integration into CryptoAgent.** Three options:

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A. New 8th factor | Add `_score_on_chain_activity` factor with new weight | Clean addition; ranks alongside others | Forces re-balancing of all 7 weights — every existing test in `test_crypto_agent.py` must update |
| B. **Replace `_score_network_adoption` from static → live data** | Same factor, same 5% weight, just real numbers | No weight rebalancing; warning string drops | Naming drift — "adoption" semantics change |
| C. Sub-method merged into existing factor | Mix on-chain into Factor 7 (cycle_timing) | No new code paths | Conflates cycle vs adoption signals |

**Pick option B.** Reasoning:
- Factor 6 was REDUCED from 10% → 5% in commit aaeb90b precisely because it was "a fixed bias rather than a dynamic signal". CoinGecko data restores it to dynamic.
- Aligns with CONCERNS.md's "On-chain metrics" missing feature without re-architecting weights
- No regression test churn — existing `_score_network_adoption` tests just need new mock fixtures
- After validation, reliability plots (Q1) tell us whether to bump the 5% weight back up

**Optional weight rebalance (deferred).** If reliability plots show `network_adoption_score` IC > 0.05, propose option A in v1.3 with empirical justification. Don't do this in v1.2.

**Confidence weighting.** On-chain signals share the existing Factor 6 weight (5%) — they don't get an independent confidence weight. The composite score → confidence formula at `agents/crypto.py:147` (`confidence = 50 + (abs(composite) - 20) * (40/80)`) already absorbs them via the weighted sum.

**Caching.** Mirror Finnhub: `_limiter` shared at class level + httpx async client. CoinGecko data updates frequently (5-min cadence) so use a **shorter TTL** than the macro 15-min default — recommend 1 hour for community/dev scores, 5 min for market data subset (matches `_DEFAULT_TTL`). Wrap in `CachedProvider`.

**Files touched (Q3 summary):**

| Action | File |
|--------|------|
| NEW | `data_providers/coingecko_provider.py` |
| MODIFY | `data_providers/__init__.py` (export `CoinGeckoProvider`) |
| MODIFY | `agents/crypto.py` (replace `_score_network_adoption` static path with live data; keep static fallback when provider missing/429s) |
| MODIFY | `engine/pipeline.py` (inject `CoinGeckoProvider` into CryptoAgent when COINGECKO env active — likely auto-enabled, no flag, since free tier doesn't require key) |
| MODIFY | `agents/__init__.py` if CryptoAgent's constructor signature changes |
| NEW | `tests/test_coingecko_provider.py` |
| MODIFY | `tests/test_crypto_agent.py` (Factor 6 mock fixtures: live → static fallback) |
| MODIFY | `config/crypto_adoption.yaml` (becomes the **fallback** values, not primary; rename comment) |

---

### Q4 — Drift-threshold validation (carry-forward from v1.1 Phase 7)

**Current state.**
- `engine/drift_detector.py` ships with hardcoded thresholds: `DRIFT_THRESHOLD_PCT = 20.0` and `ICIR_FLOOR = 0.5`
- These are flagged with `preliminary_threshold=True` whenever `MIN_SAMPLES_FOR_REAL_THRESHOLD=60` weekly observations haven't accumulated
- `drift_log` table records every weekly evaluation (Sunday 17:30 cron) — this is the corpus for validation
- v1.1 Key Decision (line 183): _"Revisit in v1.2 once 60+ weeks of weekly drift_detector runs accumulate"_
- The corpus is `drift_log` itself, NOT `backtest_signal_history` — the validation question is "did the 20%/0.5 threshold catch real degradation?", which only makes sense against accumulated live drift evaluations
- HOWEVER — at most 13 weeks of drift_log will exist by v1.2 ship (cron started 2026-04-25 with v1.1; v1.2 ships ~2026-05-15). The 60-week target is **not achievable in this milestone**.

#### Recommendation — three sub-paths

**Sub-path A: Productized validation panel (UI + endpoint).** This is what the user wants in the long run. **Do this** in v1.2.

- New API: `GET /api/v1/drift/validation` returns metrics on threshold accuracy: precision (true triggers / all triggers), recall (caught degradation / all degradation), false-positive rate against hindsight ground truth from `backtest_signal_history` IC-IR over the same windows
- New page: `/drift-validation` (or panel embedded in `/calibration`)
- Validation logic in NEW module `engine/drift_validation.py` (parallel to `engine/drift_detector.py` — same domain, different concern)
- `drift_log` rows joined against `backtest_signal_history` rolling IC-IR (computed via existing `tracker.compute_rolling_ic`) for ground truth — does the threshold trigger correlate with subsequent IC-IR collapse?

**Sub-path B: Persisted validated thresholds.** Keep current hardcoded values, but **add a `drift_thresholds` table** — minimal schema:

```sql
CREATE TABLE drift_thresholds (
    asset_type TEXT NOT NULL,
    agent_name TEXT,                    -- NULL = applies to all agents
    threshold_pct REAL NOT NULL,         -- e.g. 20.0
    icir_floor REAL NOT NULL,            -- e.g. 0.5
    source TEXT NOT NULL,                -- 'preliminary' | 'validated' | 'manual'
    sample_size INTEGER,                 -- weeks of drift_log used
    validated_at TEXT,
    PRIMARY KEY (asset_type, agent_name)
);
```

`engine/drift_detector.py` reads this table at runtime, falling back to hardcoded `DRIFT_THRESHOLD_PCT = 20.0` if the table is empty (back-compat). The validation panel (sub-path A) can WRITE to this table once enough corpus accumulates — bridging the gap from preliminary → validated.

**Sub-path C: Promote `preliminary_threshold` flag to `validated`.** Once sub-path A's validation panel runs and >= MIN_SAMPLES_FOR_REAL_THRESHOLD samples exist with reasonable precision/recall, the panel flips a per-(agent, asset_type) row in `drift_thresholds.source = 'validated'`. The drift detector reads this and stops emitting `preliminary_threshold=True` for that pair.

**Recommendation: do all three.** They're tightly coupled — A is the framework, B is the persistence, C is the lifecycle. Skipping any one creates carrying tech debt.

**Critical caveat (must be in PROJECT.md).** Even with v1.2's full validation framework, the cron-week corpus is 13 weeks at ship time. **The `validated` flag will not flip during v1.2 phase execution.** The deliverable is *capability to validate*, not *validated thresholds*. The validation panel will display "needs N more weeks of data" until 2026-07-XX or so. This is acceptable — the carry-forward closes when capability is shipped, not when threshold flips.

**Files touched (Q4 summary):**

| Action | File |
|--------|------|
| NEW | `engine/drift_validation.py` (precision/recall computation against backtest_signal_history) |
| MODIFY | `api/routes/drift.py` (extend with `GET /api/v1/drift/validation`) |
| MODIFY | `db/database.py` (add `drift_thresholds` table migration) |
| MODIFY | `engine/drift_detector.py` (read `drift_thresholds` table, fall back to constants) |
| MODIFY | `frontend/src/pages/CalibrationPage.tsx` (mount validation panel below CalibrationTable) |
| NEW | `frontend/src/components/calibration/DriftValidationPanel.tsx` |
| NEW | `tests/test_drift_validation.py` |
| NEW | `tests/test_drift_thresholds_table.py` |

---

## Build order — phase decomposition

Five phases, ordered by dependency. Phases 8-10 are the v1.2 milestone; Phase 11 is reserved for closeout/UAT/v1.3 prep.

### Phase 8 — Provider plumbing (DATA-v2-02 + DATA-v2-03)

**Why first:** Provider work is independent of UI. Reliability plots (Q1) need broader/cleaner corpus; thresholds (Q4) need more data points. Both benefit from earlier provider integration so the corpus accumulating between Phase 8 ship and Phase 10 ship has higher signal/noise.

**Scope:**
- SimfinProvider + simfin_cache + agent routing
- CoinGeckoProvider + Factor 6 swap (static → live)
- pyproject extras (`[fundamentals-pit]`, `[crypto-onchain]` — or fold into `[all]`)
- Tests: provider-level + agent-routing tests

**Independence claim:** Phase 8 ships without ANY frontend changes. The pipeline silently picks up SimFin/CoinGecko data; FundamentalAgent/CryptoAgent existing tests + new routing tests assert correctness.

**Estimated reqs:** 2 (DATA-v2-02, DATA-v2-03). Possibly 3 if SimFin backtest_mode integration is split (DATA-v2-02b).

### Phase 9 — Reliability plots (SIG-v2-01)

**Why second:** Depends on Phase 8 only weakly (reliability plots compute from `backtest_signal_history`, which exists today; Phase 8 broadens future corpus but doesn't gate Phase 9). Could parallel with Phase 8 if researcher wants — but tests are easier to write when fundamentals quality has stabilized (avoids "is it the new provider or the new metric?" ambiguity).

**Scope:**
- `tracker.compute_reliability_bins` + `compute_ece`
- API `/analytics/calibration?include_reliability=true` extension
- Frontend ReliabilityChart component + AgentCalibrationRow expand
- Backend + frontend tests

**Estimated reqs:** 1 (SIG-v2-01).

### Phase 10 — Drift-threshold validation (carry-forward)

**Why third:** Depends on Phase 9 conceptually. The validation framework (precision/recall against IC-IR ground truth) reuses the same `tracker.compute_rolling_ic` infrastructure that Q1 leans on. Doing Q1 first builds confidence that the metric framework is correct before validating it.

**Scope:**
- `drift_thresholds` table + DB migration
- `engine/drift_validation.py` precision/recall logic
- `/api/v1/drift/validation` endpoint
- `DriftValidationPanel.tsx` mounted in `CalibrationPage`
- Tests covering "preliminary corpus, no flip" + "synthetic full corpus, flips happen"

**Estimated reqs:** 1 (SIG-v2-04 carry-forward).

### Phase 11 — Polish + UAT

Reserved for: documentation, operator scripts (mirror `tests/test_close_*.py` skipif pattern), HUMAN-UAT.md trackers, milestone retrospective. No new requirements.

### Dependency graph

```
                 ┌─────────────────────────────────┐
                 │ Phase 8: Providers               │
                 │  - SimFin                        │
                 │  - CoinGecko                     │
                 └────────────┬────────────────────┘
                              │
                 ┌────────────▼────────────────────┐
                 │ Phase 9: Reliability plots       │  <- can also happen in parallel
                 │  - tracker.compute_reliability   │     with Phase 8 if desired;
                 │  - ECE metric                    │     listed sequential for clarity
                 │  - ReliabilityChart UI           │
                 └────────────┬────────────────────┘
                              │
                 ┌────────────▼────────────────────┐
                 │ Phase 10: Drift validation       │
                 │  - drift_thresholds table        │
                 │  - engine/drift_validation.py    │
                 │  - DriftValidationPanel UI       │
                 └────────────┬────────────────────┘
                              │
                 ┌────────────▼────────────────────┐
                 │ Phase 11: Polish + UAT (no new   │
                 │           reqs, just closeout)   │
                 └──────────────────────────────────┘
```

**Why NOT parallelize Phases 8 and 9:** Phase 9 ECE column will be tested against current corpus — testing against a corpus that might shift (when SimFin lights up FundamentalAgent in non-backtest_mode) introduces noise in regression tests. Sequential keeps confidence in each phase's ship signal.

**Why NOT do Phase 10 before reliability plots:** Phase 10's validation panel reports threshold accuracy. Without ECE/reliability already in the UI, operators cannot cross-check whether a "validated" threshold matches what they see in the calibration view. Showing both surfaces side-by-side (validation panel UNDER calibration table) requires the reliability work to land first.

---

## Data flow diagram — request through new pipeline

### Live analyze request (POST /analyze/{ticker} for stock)

```
User clicks "Analyze AAPL"
  -> POST /api/v1/analyze/AAPL?asset_type=stock
  -> api/routes/analyze.py
       AnalysisPipeline.analyze_ticker("AAPL", "stock", portfolio)
         -> engine/pipeline.py::_run_pipeline
             -> primary_provider = CachedProvider(YFinanceProvider())
             -> agents:
                 TechnicalAgent(primary_provider)
                 FundamentalAgent(primary_provider)
                   |- if SIMFIN_FOR_FUNDAMENTALS=true
                   |    |- SimfinProvider.get_key_stats(AAPL)
                   |    `- SimfinProvider.get_financials(AAPL, "annual")
                   |      -> simfin_cache (Parquet) -> SimFin API (rate-limited)
                   |      -> warning: "PIT data sourced from SimFin"
                   |- else (or SimFin failed):
                   |    `- yfinance via CachedProvider (existing path)
                   |      -> warning: NON_PIT_WARNING
                   `- existing scoring + insider tilt path unchanged
                 MacroAgent(FredProvider, YFinanceProvider)  [unchanged]
                 SentimentAgent(...)  [unchanged]
             -> asyncio.gather(*agents)
             -> SignalAggregator.aggregate (reads agent_weights from DB)
             -> regime detection [unchanged]
             -> portfolio_overlay [unchanged]
             -> llm_synthesis (opt-in) [unchanged]
         -> AggregatedSignal returned to frontend
```

### Live analyze request (BTC)

```
User clicks "Analyze BTC"
  -> POST /api/v1/analyze/BTC?asset_type=btc
  -> AnalysisPipeline.analyze_ticker
       -> primary_provider = YFinanceProvider (BTC-USD mapping)
       -> CryptoAgent(primary_provider, on_chain_provider=CoinGeckoProvider())
            |- Factor 1-5 unchanged (price/momentum/volatility/liquidity/macro)
            |- Factor 6: _score_network_adoption
            |    |- try: CoinGeckoProvider.get_on_chain_metrics("btc")
            |    |      -> community_score, dev_score, watchlist_count, sentiment_pct
            |    |      -> derive score from live signals (vs static yaml today)
            |    |- except: fall back to crypto_adoption.yaml constants
            |    |   -> warning: "On-chain provider unavailable; using static fallback"
            |    `- return _clamp(score), metrics
            `- Factor 7 unchanged
       -> composite score -> signal/confidence -> AggregatedSignal
```

### Sunday cron — drift detector + new validation

```
Sunday 17:30 ET
  -> daemon/scheduler.py triggers run_drift_detector
  -> engine/drift_detector.evaluate_drift(db_path)
       FOR each (agent, asset_type) in KNOWN_AGENTS x KNOWN_ASSET_TYPES:
           -> tracker.compute_rolling_ic from backtest_signal_history
           -- NEW: read drift_thresholds table for this (agent, asset_type)
           --   if row exists with source='validated': use those thresholds
           --   else: use DRIFT_THRESHOLD_PCT=20.0 / ICIR_FLOOR=0.5 (current behavior)
           -> check delta_pct vs threshold
           -> check current_icir vs floor
           -> if triggered: _apply_drift_scale (NEVER-zero-all guard, manual_override preserve)
           -> write drift_log row (preliminary_threshold = source != 'validated')

Saturday 09:00 ET (NEW — optional cron)
  -> run_drift_validation
  -> engine/drift_validation.compute_validation_metrics(db_path)
       FOR each (agent, asset_type):
           -> load drift_log entries (last N weeks)
           -> load backtest_signal_history rolling IC-IR (ground truth)
           -> compute precision = (drift_log.triggered AND IC-IR collapsed within N weeks) / triggered_total
           -> compute recall = same / IC-IR collapses
           -> if N >= MIN_SAMPLES_FOR_REAL_THRESHOLD:
                -> write to drift_thresholds (source='validated', threshold_pct=X)
           -> expose via GET /api/v1/drift/validation
```

### Frontend reliability plot drill-down

```
User opens /calibration page
  -> CalibrationPage useApi(getCalibrationAnalytics) [unchanged endpoint, NEW reliability_bins field]
  -> CalibrationTable renders rows [+ NEW ECE column]
  -> User clicks expand triangle on TechnicalAgent row
  -> AgentCalibrationRow.expanded state = true
  -> ReliabilityChart renders:
        ScatterChart with bin midpoints (X) vs observed frequency (Y)
        + reference line y=x (perfect calibration)
        + point size = bin sample count
        + color = ECE band (green/amber/red)
  -> Tooltip shows: "Bin 0.5-0.6: predicted 55%, observed 42%, n=78"
```

---

## Integration points — file path index

### New files (Phase 8 — Providers)

```
data_providers/
├── simfin_provider.py            [NEW — Q2]
├── simfin_cache.py               [NEW — Q2; mirrors parquet_cache.py]
└── coingecko_provider.py         [NEW — Q3]

tests/
├── test_simfin_provider.py       [NEW]
├── test_coingecko_provider.py    [NEW]
└── test_fundamental_agent_simfin_routing.py  [NEW]
```

### New files (Phase 9 — Reliability plots)

```
frontend/src/components/calibration/
└── ReliabilityChart.tsx          [NEW — Q1]

tests/
└── test_tracker_reliability.py   [NEW]

frontend/src/components/calibration/__tests__/
└── ReliabilityChart.test.tsx     [NEW]
```

### New files (Phase 10 — Drift validation)

```
engine/
└── drift_validation.py           [NEW — Q4]

frontend/src/components/calibration/
└── DriftValidationPanel.tsx      [NEW — Q4]

tests/
├── test_drift_validation.py      [NEW]
└── test_drift_thresholds_table.py [NEW]
```

### Modified files (cumulative across phases)

```
agents/
├── crypto.py                     [MODIFIED — Q3, Phase 8]
└── fundamental.py                [MODIFIED — Q2, Phase 8]

api/
├── app.py                        [MODIFIED — register new routers if any]
├── models.py                     [MODIFIED — Q1 + Q4 Pydantic shapes]
└── routes/
    ├── calibration.py            [MODIFIED — Q1, Phase 9: include_reliability param]
    └── drift.py                  [MODIFIED — Q4, Phase 10: GET /validation]

config/
└── crypto_adoption.yaml          [MODIFIED — Q3, Phase 8: becomes fallback]

data_providers/
└── __init__.py                   [MODIFIED — exports]

db/
└── database.py                   [MODIFIED — Q4, Phase 10: drift_thresholds migration]

engine/
├── drift_detector.py             [MODIFIED — Q4, Phase 10: read drift_thresholds]
└── pipeline.py                   [MODIFIED — Q2 + Q3, Phase 8: inject providers]

frontend/src/
├── api/types.ts                  [MODIFIED — Q1 + Q4: new types]
├── pages/CalibrationPage.tsx     [MODIFIED — Q4, Phase 10: mount validation panel]
└── components/calibration/
    ├── AgentCalibrationRow.tsx   [MODIFIED — Q1, Phase 9: expandable + ECE column]
    └── CalibrationTable.tsx      [MODIFIED — Q1, Phase 9: ECE header]

pyproject.toml                    [MODIFIED — Q2 + Q3: new optional extras]

tests/
└── test_crypto_agent.py          [MODIFIED — Q3, Phase 8: Factor 6 mock fixtures]
```

---

## Risks and trade-offs

### Risk 1: SimFin coverage gap

**What might go wrong:** SimFin free tier covers ~3000 US stocks reliably; ADRs, small caps, recent IPOs are spotty. Operator portfolios may have 30%+ tickers fall through to yfinance.

**Mitigation:** Automatic per-ticker fallback (option C in Q2). Log warning but continue. Surface coverage stat in `/health` endpoint.

### Risk 2: CoinGecko free-tier rate limit

**What might go wrong:** 10-30 req/min free tier. CryptoAgent runs once per analyze + once weekly per held position. With 5 BTC/ETH positions and weekly digest, potential burst of 10 calls in <1s.

**Mitigation:** TTLCache 1-hour TTL for community/dev scores. Daemon job runs sequentially, not parallel. Existing `AsyncRateLimiter` token-bucket already serializes.

### Risk 3: ECE binning sensitivity

**What might go wrong:** Reliability plots with 10 bins on a 200-row corpus = 20 samples/bin average — bin variance is high; ECE numbers may be misleadingly precise (e.g., "ECE = 0.142" when ±0.05 is the real uncertainty).

**Mitigation:** Apply N>=20 per-bin floor (matches existing `compute_calibration_data` pattern). Surface bin sample size in tooltip. Add "preliminary_calibration: true" flag when total N < 200, mirroring Phase 2 contract.

### Risk 4: Drift validation depends on corpus that won't exist

**What might go wrong:** As noted in Q4: 13 weeks of `drift_log` at v1.2 ship; 60 needed for `validated` flag. Validation panel ships with permanent "preliminary, need 47 more weeks" UI.

**Mitigation:** Be transparent — call out in PROJECT.md "Key Decisions" that v1.2 ships *capability* not *validated thresholds*. The closeout for the carry-forward is the panel landing, not the flag flipping.

### Risk 5: SimFin licensing for backtests

**What might go wrong:** SimFin terms-of-service may restrict redistribution. Operator running historical backtests creates derived data — is that distributable?

**Mitigation:** Verify SimFin TOS during Phase 8 research. If restrictive, document in `pyproject.toml` extra description ("non-commercial / personal use only — see SimFin TOS"). Mirror Finnhub's existing free-tier disclaimer pattern.

---

## Anti-patterns to avoid

### Anti-pattern 1: Adding a new provider factory parallel to `data_providers/factory.py`

**What people might do:** Create `factory_v2.py` with SimFin/CoinGecko-aware routing.

**Why it's wrong:** Splits routing logic across two factories; future readers must check both.

**Do this instead:** Inject providers explicitly at the agent construction point in `engine/pipeline.py` (just below where `MacroAgent`/`SentimentAgent` are conditionally appended). The `factory.get_provider()` stays single-source-of-truth for the primary provider.

### Anti-pattern 2: Coupling reliability plots to live `signal_history`

**What people might do:** Argue "reliability is a LIVE metric — should pull from `signal_history`".

**Why it's wrong:** Live `signal_history` is sparse (10 rows as of 2026-04-21 per CONCERNS.md). Existing Brier/IC/IC-IR uses `backtest_signal_history` for the same reason. Splitting sources = drift across charts.

**Do this instead:** Reuse `SignalStore.get_backtest_signals_by_agent`. When live `signal_history` accumulates 200+ rows, revisit in v1.3+ (and probably retire `backtest_signal_history` entirely as the calibration corpus).

### Anti-pattern 3: Adding on-chain as a NEW factor in CryptoAgent

**What people might do:** Add `_score_on_chain_activity` as an 8th factor with its own weight.

**Why it's wrong:** Forces every weight in `FACTOR_WEIGHTS` dict to renormalize; every regression test in `test_crypto_agent.py` updates; introduces subjective weight choice with no empirical backing.

**Do this instead:** Replace static path inside existing Factor 6 (`_score_network_adoption`). Same 5% weight. Defer weight rebalancing to v1.3 once reliability plots show whether on-chain signal merits more weight.

### Anti-pattern 4: Hardcoding new `drift_thresholds` defaults

**What people might do:** After validation, replace `DRIFT_THRESHOLD_PCT = 20.0` constant with `DRIFT_THRESHOLD_PCT = 18.0` (or whatever validation found).

**Why it's wrong:** Constant changes ship as code, require deploys, can't differ per (agent, asset_type) — but real validated thresholds DO differ by combo (TechnicalAgent vs MacroAgent have different signal/noise profiles).

**Do this instead:** Use the `drift_thresholds` table (sub-path B from Q4). Per-(agent, asset_type) row. Validation panel writes; detector reads. Constants stay as fallback for cold-start.

---

## Suggested phase boundaries (recap for roadmapper)

| Phase | Title | Reqs | Frontend? | Backend-only? | Independent? |
|-------|-------|------|-----------|---------------|--------------|
| 8 | Providers (SimFin + CoinGecko) | DATA-v2-02 + DATA-v2-03 | NO | YES | YES — could ship without 9 or 10 |
| 9 | Reliability plots | SIG-v2-01 | YES | NO | Weakly depends on 8 (corpus quality) |
| 10 | Drift-threshold validation | SIG-v2-04 (carry-forward) | YES | YES | Depends on 9 (UI mounting) |
| 11 | Polish + UAT closeout | none | mixed | mixed | Sequential after 10 |

Total: ~4 reqs across ~4 phases (matches scoping note in PROJECT.md "~3 phases / ~12 reqs" — but the request hint of 12 reqs seems high for a 4-feature milestone; expect roadmapper to break each REQ into 2-3 sub-reqs to land at ~12).

---

## Sources

- `agents/fundamental.py` — FundamentalAgent integration point + FOUND-04 contract
- `agents/crypto.py` — CryptoAgent 7-factor model + Factor 6 static path
- `data_providers/finnhub_provider.py` — provider pattern template
- `data_providers/cached_provider.py` + `parquet_cache.py` + `dividend_cache.py` — cache pattern templates
- `data_providers/rate_limiter.py` — token-bucket pattern
- `engine/pipeline.py` — agent construction + provider injection point
- `engine/drift_detector.py` — drift detection scaffold; threshold constants
- `tracking/tracker.py` — Brier/IC/IC-IR + existing `compute_calibration_data`
- `tracking/store.py` — `get_backtest_signals_by_agent` reader
- `api/routes/calibration.py` — current `/analytics/calibration` shape + WARNING 11 contract
- `api/routes/drift.py` — current `/api/v1/drift/log` endpoint
- `api/app.py` — router registration point
- `frontend/src/pages/CalibrationPage.tsx` — frontend mount + tab structure
- `frontend/src/components/calibration/*` — existing component family
- `.planning/PROJECT.md` — milestone scope + Key Decisions
- `.planning/codebase/CONCERNS.md` — pre-existing tech debt + missing-feature list

Confidence: HIGH. All findings are grounded in direct file reads of the existing codebase. No external library research was needed (the question was integration, not greenfield design). External provider docs (SimFin/CoinGecko) carry MEDIUM confidence pending Phase 8 verification, but the integration *pattern* (mirror Finnhub) is HIGH confidence.

---
*Architecture research for: v1.2 Trustworthy Signals — brownfield integration into existing Investment Agent*
*Researched: 2026-04-27*
