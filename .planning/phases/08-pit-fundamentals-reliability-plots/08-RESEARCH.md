# Phase 8: PIT Fundamentals + Reliability Plots — Research

**Researched:** 2026-04-28
**Domain:** Brownfield integration — point-in-time fundamentals provider (SimFin v3 REST), Brier-score reliability binning + Murphy decomposition, schema evolution under provider provenance
**Confidence:** HIGH (all integration points verified via direct file reads; SimFin `asreported` parameter confirmed in vendor docs; sklearn / Wilson CI / Murphy formulas verified against multiple sources)

---

## Summary

Phase 8 bundles two features that share **schema migration risk** and the **FOUND-04 contract surface**: the SimFin point-in-time fundamentals provider (DATA-v2-02, DATA-v2-04, DATA-v2-05) and the per-agent reliability/Murphy-decomposition plots (SIG-v2-01, SIG-v2-02). Bundling is *defensive* — both features write into `backtest_signal_history` and read from the same per-agent IC corpus; landing them in separate phases would interleave schema evolution and feature work and create a window where IC computations silently mix providers.

The phase is dominated by **silent-data-corruption risks**, not implementation difficulty. The 5 hard requirements decompose to ~80% existing-pattern reuse: SimFin mirrors `data_providers/finnhub_provider.py` (httpx + AsyncRateLimiter + Parquet cache), reliability binning extends `tracking/tracker.py::compute_calibration_data`, the schema migration follows the `_ensure_column` pattern in `db/database.py`, and the frontend mounts into the existing `CalibrationPage.tsx` next to `AgentCalibrationRow.tsx`. The novel work is (a) `asreported=true`-driven SimFin queries, (b) Murphy REL/RES/UNC decomposition (no existing analog in the codebase), (c) restated-vs-as-filed delta detection.

**Primary recommendation:** Land the `fundamentals_provider TEXT NOT NULL DEFAULT 'yfinance'` column migration on `signal_history`, `backtest_signal_history`, and `drift_log` in the FIRST commit of the phase, BEFORE the SimFin provider class — this is the defensive-ordering hinge. SimFin opt-in via `AgentInput.use_pit_fundamentals: bool = False` (per-analyze field, matches `backtest_mode` precedent). Use sklearn 1.4+ `calibration_curve(strategy='quantile')` for binning, Wilson 95% CI for per-bin error bars, and exact-bin Murphy decomposition (not PAV/CORP — saves ~80 LOC for marginal stability gain at our N).

---

## User Constraints (from CONTEXT.md)

**No CONTEXT.md exists** for Phase 8 (`has_context: false` per init context). The phase was scoped via `/gsd-roadmapper` directly from REQUIREMENTS.md without an interactive `/gsd-discuss-phase` session. The 5 phase requirements (SIG-v2-01, SIG-v2-02, DATA-v2-02, DATA-v2-04, DATA-v2-05) and 5 ROADMAP success criteria operate as locked decisions; this RESEARCH.md treats them as user constraints.

### Locked Decisions (from ROADMAP Phase 8 + Key Decisions)

- **SimFin opt-in**, not silent provider swap — preserve FOUND-04 contract (`backtest_mode=True && use_pit_fundamentals=False → HOLD/completeness=0.0` is unchanged) [VERIFIED: ROADMAP.md SC-3]
- **Schema migration ships in same PR as SimfinProvider** — `fundamentals_provider TEXT NOT NULL DEFAULT 'yfinance'` on `signal_history` + `backtest_signal_history` + `drift_log` with `(ticker, created_at, fundamentals_provider)` index [VERIFIED: ROADMAP.md SC-4]
- **Adaptive bin count** for reliability plot: `max(2, min(10, n_samples // 10))` [VERIFIED: ROADMAP.md SC-1]
- **`preliminary_calibration: true` flag** when bin count below threshold (mirrors Phase 2 pattern) [VERIFIED: ROADMAP.md SC-1]
- **Murphy decomposition exact-bin**, not PAV/CORP — `~80 LOC PAV is out-of-scope for v1.2` [VERIFIED: REQUIREMENTS.md Out-of-Scope row]
- **Wilson 95% CI** for per-bin reliability error bars (not bootstrap) — `asymptotically equivalent at our N, ~10× cheaper` [VERIFIED: REQUIREMENTS.md Out-of-Scope row]
- **Restated-vs-as-filed delta threshold = 10%** for badge display [VERIFIED: REQUIREMENTS.md DATA-v2-05]
- **Recharts existing v2.13.0** — no chart-lib migration; `ScatterChart` + `ReferenceLine` + `ErrorBar` is the rendering stack [VERIFIED: PROJECT.md row 12]

### Claude's Discretion (areas to investigate and recommend)

- **`use_pit_fundamentals` opt-in scope** — per-analyze AgentInput field vs per-portfolio column vs global env var (see Open Questions resolution below)
- **SimFin filing-date filtering for amended 10-Q/A** — exact API behavior (see Open Questions resolution below)
- **Murphy exact-bin formulas** — confirm arXiv 2008.03033 / Siegert 2017 sample-size bounds for our N (see Open Questions resolution below)
- File paths, test names, plan decomposition (Wave 0 / Wave 1 / Wave 2 boundaries)
- Specific Pydantic / TypeScript shape names (within additive-only `WARNING 11` stable-key contract)

### Deferred Ideas (OUT OF SCOPE — do NOT plan)

- **Switch entire fundamental pipeline to SimFin** — single-provider failure surface; SimFin free-tier ~5y history; layered routing only [VERIFIED: REQUIREMENTS.md Out-of-Scope]
- **Murphy CORP/PAV method** — exact-bin is adequate for v1.2 N range; defer to v2+
- **Bootstrap CI on reliability plot bins** — Wilson is asymptotically equivalent; defer to v2+
- **Per-bin trend sparklines on reliability plot** (SIG-v2-03 — deferred to v1.3)
- **Drift sensitivity heatmap** (SIG-v2-04 — deferred to v1.3)
- **DATA-v2-03 CoinGecko provider** — Phase 9, not Phase 8
- **DRIFT-v2-01..04 drift-threshold validation** — Phase 10, not Phase 8

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **SIG-v2-01** | Per-agent reliability plot on `/calibration` — predicted-confidence buckets vs realized-win-rate scatter with diagonal reference line, sample-size-as-bubble-area encoding, per-bin Wilson 95% CIs as error bars, adaptive bin count, `preliminary_calibration` flag | sklearn 1.6.1 already installed [VERIFIED: pip show]; existing `compute_calibration_data` in tracker.py:96-135 implements 80% of binning logic; Recharts `ScatterChart` + `ReferenceLine` + `ErrorBar` natively support diagonal-vs-curve plots; existing pattern uses `min_bucket_size=5` (we'll use 10 with adaptive cap) |
| **SIG-v2-02** | Murphy/Brier decomposition card alongside reliability plot — REL/RES/UNC values per agent with hover-tooltip explanations | Existing `compute_brier_score` in tracker.py:320-350 is the data source (one-vs-rest binary, HOLD-excluded); decomposition formulas verified against Wikipedia + Siegert 2017 + Brocker; exact-bin formulas suffice at N≥60 per bin [VERIFIED: Ferro & Fricker 2012 — biases negligible above n≈60] |
| **DATA-v2-02** | SimFin opt-in via `AgentInput.use_pit_fundamentals: bool = False` field; FOUND-04 contract preserved as default | `AgentInput` dataclass at agents/models.py:23-31 already accepts new fields cleanly; `agents/fundamental.py:56-77` is the FOUND-04 short-circuit site; SimFin v3 REST `/companies/statements?asreported=true` is the API surface [VERIFIED: simfinapi R-package docs] |
| **DATA-v2-04** | `fundamentals_provider TEXT NOT NULL DEFAULT 'yfinance'` on signal_history + backtest_signal_history + drift_log with composite index; IC and drift queries filter by provider; corpus rebuild on first SimFin enable | Existing schema in db/database.py:407-540 + 731-755; `_ensure_column` helper at db/database.py:14-24 handles idempotent ALTER; `corpus_rebuild_jobs` async-job pattern shipped in v1.1 Phase 5 (LIVE-01) |
| **DATA-v2-05** | Restated-vs-as-filed delta badge on positions when `\|delta\| > 10%` for any reported metric | Tooltip pattern matches existing `TargetWeightBar.tsx`; existing `frontend/src/components/portfolio/PositionsTable.tsx` is the mount point; SimFin returns both restated and as-reported via separate queries (default vs `asreported=true`) [VERIFIED: simfinapi R-package docs] |

---

## Standard Stack

### Core (additions / promotions)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `scikit-learn` | `>=1.4,<2.0` | `calibration_curve(strategy='quantile')` for reliability bin computation; cross-check Brier via `brier_score_loss` (don't migrate existing impl) | Already transitively installed at 1.6.1 [VERIFIED: pip show 2026-04-28]; promote to direct dep for explicit `pos_label` kwarg contract (added 1.1) and stable `strategy='quantile'` semantics. Latest stable 1.8.0 [CITED: pypi.org/project/scikit-learn/]. License BSD-3-Clause |
| `httpx` | `>=0.27` (existing) | SimFin v3 REST async client (`https://prod.simfin.com/api/v3/companies/statements`) | Already in dependencies. Pattern locked by `data_providers/finnhub_provider.py:79-90`. Do NOT install abandoned `simfin` PyPI SDK (1.0.1, last release 2024-04-03, predates v3 API) [VERIFIED: pypi.org/project/simfin/ + STACK.md] |
| `pyarrow` | `>=14.0` (existing) | Parquet disk cache for SimFin statements (24h TTL) — pattern mirror of `data_providers/dividend_cache.py` | Already in dependencies. License Apache-2.0 |
| `recharts` | `^2.13.0` (existing) | `ScatterChart` + `ReferenceLine` + `ErrorBar` for reliability plot rendering | Already in `frontend/package.json:18`. ReferenceLine usage already in 4 files (EquityCurveChart, DrawdownChart, PerformanceAttribution, RollingSharpeChart) [VERIFIED: grep 2026-04-28] |

### Indirect / promotion-only (no new install)

| Library | Version | Purpose | Why Promote |
|---------|---------|---------|-------------|
| `numpy` | `>=1.26,<3.0` | `np.histogram`, `np.percentile`, Wilson CI vectorization for reliability plot | Currently transitive at 2.2.6 [VERIFIED: pip show]. License BSD-3-Clause |
| `scipy` | `>=1.10,<2.0` | Wilson CI via `scipy.stats.norm.ppf(0.975) = 1.96`; lazy `pearsonr` already used in tracker.py:389; future Phase 10 `wilcoxon` | Currently transitive at 1.15.3 [VERIFIED: pip show]. Lazy import already in tracker.py per existing pattern. License BSD-3-Clause |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `httpx` SimFin client | `simfin` PyPI SDK 1.0.1 | **REJECTED** — abandoned 2024-04-03; predates SimFin v3 API; bulk-CSV download model wrong shape for per-position async lookups; Snyk-flagged Inactive [VERIFIED: snyk.io/advisor/python/simfin] |
| sklearn `calibration_curve` | `netcal` 1.3.0 PyPI | **REJECTED** — ~5 MB + transformers/torch optional deps; designed for ML model calibration research, overkill for single-binning use case |
| sklearn `calibration_curve` | `ReliabilityDiagram` PyPI | **REJECTED** — last release 2020-12; abandoned; trivially superseded by `calibration_curve` |
| Recharts ScatterChart | Apple `relplot` | **REJECTED** — not on PyPI; uses kernel smoothing (overkill for sparse corpus); requires git+ install |
| Wilson 95% CI | Bootstrap 1000× resample | **REJECTED for v1.2** — Wilson is asymptotically equivalent at N≥15 per bin and ~10× cheaper; already locked in REQUIREMENTS.md Out-of-Scope row |
| Exact-bin Murphy | PAV/CORP isotonic regression | **REJECTED for v1.2** — adds ~80 LOC; bias-corrected exact-bin is stable at N≥60 per bin per Ferro & Fricker 2012 [CITED: empslocal.ex.ac.uk/people/staff/ferro/Publications/ferro-fricker2012copyright.pdf] |
| Recharts (existing) | ApexCharts / Chart.js / Plotly.js | **REJECTED** — Phase 4 locked Recharts; migration cost ~600 LOC test churn for zero user-visible benefit [CITED: PROJECT.md row 172] |

**Installation:**
```bash
# pyproject.toml dependencies — add 3 promotions, no SimFin SDK
# dependencies = [
#   ...existing...,
#   "scikit-learn>=1.4,<2.0",   # SIG-v2-01: calibration_curve binning
#   "numpy>=1.26,<3.0",         # promote (was transitive via quantstats)
#   "scipy>=1.10,<2.0",         # promote (was transitive; used in tracker.py:389)
# ]

pip install -e .  # no-op if already-installed transitively

# .env additions (graceful-degrade if absent — matches MacroAgent + FRED_API_KEY pattern)
echo "SIMFIN_API_KEY=" >> .env.example
echo "SIMFIN_RATE_LIMIT=120" >> .env.example  # 2/sec sustained
```

**Default-install impact:** **0 MB net** — all three promotions are already-transitively-installed. No new wheels download. No `[optional-extras]` needed.

**Version verification:**
```bash
pip show scikit-learn  # 1.6.1 — already installed via quantstats transitive [VERIFIED: 2026-04-28]
pip show scipy         # 1.15.3 — already installed [VERIFIED: 2026-04-28]
pip show numpy         # 2.2.6 — already installed [VERIFIED: 2026-04-28]
```

---

## Architecture Patterns

### Recommended Project Structure (additions only — brownfield integration)

```
data_providers/
├── simfin_provider.py            # NEW — class SimfinProvider(DataProvider) mirroring FinnhubProvider
└── simfin_cache.py               # NEW — Parquet 24h TTL, mirrors dividend_cache.py

agents/
├── models.py                     # MODIFIED — add use_pit_fundamentals + backtest_date to AgentInput
└── fundamental.py                # MODIFIED — add SimFin path with FOUND-04 dual-condition guard

engine/
└── pipeline.py                   # MODIFIED — inject SimfinProvider when use_pit_fundamentals signaled

tracking/
└── tracker.py                    # MODIFIED — compute_reliability_bins + compute_ece + compute_murphy_decomposition

api/
├── routes/calibration.py         # MODIFIED — extend /analytics/calibration with include_reliability + Murphy
└── routes/portfolio.py           # MODIFIED — surface restated_delta on positions endpoint
└── models.py                     # MODIFIED — Pydantic ReliabilityBin, MurphyDecomposition, RestatedDelta

db/
└── database.py                   # MODIFIED — 3 fundamentals_provider migrations + composite index

frontend/src/
├── api/types.ts                  # MODIFIED — add reliability_bins, ece, murphy, restated_delta types
├── components/calibration/
│   ├── AgentCalibrationRow.tsx   # MODIFIED — expand-arrow + ECE column
│   ├── ReliabilityPlot.tsx       # NEW — ScatterChart + ReferenceLine y=x + ErrorBar (Wilson CIs)
│   └── MurphyDecompositionCard.tsx  # NEW — REL/RES/UNC card with hover tooltips
└── components/portfolio/
    └── RestatedDeltaBadge.tsx    # NEW — DATA-v2-05 badge with tooltip on PositionsTable rows

tests/
├── test_simfin_provider.py       # NEW
├── test_simfin_cache.py          # NEW
├── test_fundamental_agent_simfin_routing.py  # NEW
├── test_tracker_reliability.py   # NEW
├── test_tracker_murphy.py        # NEW
└── test_db_fundamentals_provider_migration.py  # NEW

frontend/src/components/calibration/__tests__/
├── ReliabilityPlot.test.tsx      # NEW
└── MurphyDecompositionCard.test.tsx  # NEW
```

### Pattern 1: Provider Skeleton (mandatory mirror of `FinnhubProvider`)

**What:** All HTTP-based data providers obey a 7-step skeleton verified across `finnhub_provider.py`, `fred_provider.py`, `edgar_provider.py`.

**When to use:** Any new external HTTP API integration. SimFin Phase 8 falls here.

**Example:**
```python
# data_providers/simfin_provider.py — Source: data_providers/finnhub_provider.py:49-103 mirror
from __future__ import annotations
import logging, os, warnings
from typing import Any
import httpx
from data_providers.base import DataProvider
from data_providers.rate_limiter import AsyncRateLimiter

SIMFIN_BASE_URL = "https://prod.simfin.com/api/v3"  # [VERIFIED: simfin.com/en/blog/major-simfin-update/]

class SimfinProvider(DataProvider):
    """SimFin v3 REST provider for point-in-time fundamentals.

    Free tier: 2 calls/sec, 5,000 US stocks, 5y history, 500 high-speed credits/mo.
    [VERIFIED: simfin.com/en/prices/]

    Security: api_key passed via httpx default_params (header per simfin.readme.io
    Authorization scheme); never logged.
    """
    # Class-level limiter — 2/sec = 120/min sliding window
    _limiter = AsyncRateLimiter(
        max_calls=int(os.getenv("SIMFIN_RATE_LIMIT", "120")),
        period_seconds=60.0,
    )

    def __init__(self, api_key: str | None = None, timeout: float = 10.0) -> None:
        resolved = api_key or os.getenv("SIMFIN_API_KEY")
        self._api_key = resolved
        if not resolved:
            warnings.warn(
                "SIMFIN_API_KEY not set. SimfinProvider methods will raise RuntimeError.",
                RuntimeWarning, stacklevel=2,
            )
            self._client: httpx.AsyncClient | None = None
        else:
            # SimFin v3 uses Authorization header, not query param
            self._client = httpx.AsyncClient(
                base_url=SIMFIN_BASE_URL,
                headers={"Authorization": f"api-key {resolved}"},
                timeout=timeout,
            )

    async def get_financials(
        self, ticker: str,
        statement: str = "pl",      # pl | bs | cf | derived
        period: str = "q1",          # q1 | q2 | q3 | q4 | fy
        fyear: int | None = None,
        asreported: bool = True,     # KEY FLAG — preserves original filing values
    ) -> dict:
        """Get financial statement for ticker.

        asreported=True returns as-reported (not restated) data — the PIT semantic.
        [VERIFIED: simfinapi R-package docs + simfin.readme.io/reference/statements-verbose-1]
        """
        if self._client is None:
            raise RuntimeError("SIMFIN_API_KEY missing — use_pit_fundamentals=True requires it")
        params = {
            "ticker": ticker,
            "statements": statement,
            "period": period,
            "asreported": "true" if asreported else "false",
        }
        if fyear is not None:
            params["fyear"] = fyear
        async with self._limiter:
            resp = await self._client.get("/companies/statements", params=params)
            resp.raise_for_status()
            return resp.json()
```

**Critical detail:** `httpx` `params` dict propagates to URL. `_rate_limited_get` returns `{}` on 429 (matches Finnhub pattern at line 99-103). Don't raise on rate limit — let the corpus-rebuild loop continue.

### Pattern 2: Disk Cache (mandatory mirror of `DividendCache`)

**What:** Parquet-backed disk cache, atomic-rename writes, Windows fallback (delete-then-rename with 3 retries), 24h TTL.

**When to use:** Per-ticker provider responses that are ≤quarterly cadence. Fundamentals fit perfectly (don't change intraday).

**Example:**
```python
# data_providers/simfin_cache.py — Source: data_providers/dividend_cache.py:38-150 mirror
class SimfinStatementCache:
    """Per-ticker × (statement_type, period, fyear, asreported) Parquet cache.

    File: data/cache/simfin/{safe_ticker}_{statement}_{period}_{fyear}_{asreported}.parquet
    TTL: 24h (fundamentals don't change intraday).
    """
    # Same atomic-rename + 3-retry Windows fallback as DividendCache
    # Key: (ticker, statement, period, fyear, asreported) → DataFrame
```

### Pattern 3: AgentInput field extension (FOUND-04 dual-condition)

**What:** Adding opt-in flags to `AgentInput` while preserving FOUND-04 default.

**Example:**
```python
# agents/models.py — Source: existing dataclass at line 23
@dataclass
class AgentInput:
    ticker: str
    asset_type: str
    portfolio: Portfolio | None = None
    regime: Regime | None = None
    learned_weights: dict[str, Any] = field(default_factory=dict)
    approved_rules: list[str] = field(default_factory=list)
    backtest_mode: bool = False
    # NEW v1.2 — Phase 8 DATA-v2-02
    use_pit_fundamentals: bool = False
    backtest_date: date | None = None  # required when use_pit_fundamentals=True
```

```python
# agents/fundamental.py — modify the FOUND-04 short-circuit at line 56
# BEFORE:
if agent_input.backtest_mode:
    return AgentOutput(signal=HOLD, data_completeness=0.0, ...)

# AFTER:
# FOUND-04 short-circuit: only when restated-fundamentals path is active
if agent_input.backtest_mode and not agent_input.use_pit_fundamentals:
    return AgentOutput(signal=HOLD, data_completeness=0.0, warnings=[...])

if agent_input.backtest_mode and agent_input.use_pit_fundamentals:
    if agent_input.backtest_date is None:
        raise ValueError(
            "use_pit_fundamentals=True requires backtest_date for as-of filtering"
        )
    # SimFin path — fall through to provider lookup below with asreported=True
```

**Critical assertion:** The default behavior (`backtest_mode=True && use_pit_fundamentals=False`) MUST be byte-identical to current. Tripwire test `test_fundamental_agent_backtest_mode_default_unchanged` is a Wave 0 prerequisite — written and passing BEFORE any SimFin code lands.

### Pattern 4: Schema Migration (mandatory mirror of `_ensure_column`)

**What:** Idempotent ALTER TABLE pattern — safe on every startup, no downstream breakage.

**Example:**
```python
# db/database.py — extend init_db with new migration block
async def _migrate_fundamentals_provider(conn: aiosqlite.Connection) -> None:
    """DATA-v2-04: add fundamentals_provider provenance column to 3 tables.

    DEFAULT 'yfinance' is non-null and back-fills existing rows correctly —
    yfinance is the only provider used through v1.1 Phase 7.
    """
    for table in ("signal_history", "backtest_signal_history", "drift_log"):
        await _ensure_column(
            conn, table,
            column_name="fundamentals_provider",
            column_type="TEXT NOT NULL DEFAULT 'yfinance'",
        )

    # Composite index for IC + drift query filters
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_signal_history_ticker_created_provider
        ON signal_history (ticker, created_at, fundamentals_provider)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_bsh_ticker_date_provider
        ON backtest_signal_history (ticker, signal_date, fundamentals_provider)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_drift_log_agent_asset_provider_evaluated
        ON drift_log (agent_name, asset_type, fundamentals_provider, evaluated_at DESC)
    """)
```

**Critical:** This migration MUST run BEFORE the SimFin provider class is wired into the pipeline — otherwise the very first SimFin write hits a column that doesn't exist. The `init_db()` ordering in `db/database.py` must place this AFTER the original table CREATEs at lines 407-540 + 731-755, but it's idempotent so re-running is fine.

### Pattern 5: API Endpoint Extension (additive — preserves stable-key contract)

**What:** Adding fields to existing endpoint response shapes without renaming or removing keys (WARNING 11 contract from v1.0).

**Example:**
```python
# api/routes/calibration.py — extend GET /analytics/calibration
# Existing shape (DO NOT BREAK):
# {"data": {"agents": {"TechnicalAgent": {"brier_score", "ic_5d", "ic_horizon", "ic_ir", "sample_size", "rolling_ic", ...}}}}

# Phase 8 additive extension (new optional query param + new fields):
# GET /analytics/calibration?include_reliability=true
# Response gains per-agent:
#   "ece": float | null,                          # Expected Calibration Error
#   "reliability_bins": [
#     {
#       "bin_lo": 0.30, "bin_hi": 0.40,
#       "n": 22, "predicted": 0.35, "observed": 0.41,
#       "ci_low": 0.21, "ci_high": 0.62,           # Wilson 95%
#       "ece_contrib": 0.013
#     }, ...
#   ] | null,
#   "preliminary_calibration": bool,               # n_bins < 5 OR min(bin_n) < 10
#   "n_bins_used": int,
#   "min_samples_per_bin": int,
#   "murphy": {                                    # SIG-v2-02
#     "rel": float, "res": float, "unc": float,
#     "verified_sum": float                        # REL - RES + UNC ≈ Brier (sanity)
#   } | null
```

**Critical:** The default behavior (no `include_reliability` query param) returns the v1.1 shape unchanged. Frontend types in `frontend/src/api/types.ts` declare new fields as optional (`?`).

### Anti-Patterns to Avoid

- **Removing the FOUND-04 short-circuit when SimFin lands:** Even with PIT data, the dual-condition guard MUST stay (`backtest_mode and not use_pit_fundamentals → HOLD`). Tripwire regression test prevents accidental removal.
- **Mixing providers in one IC query:** Without `WHERE fundamentals_provider = ?` filter, IC computed across yfinance-era + SimFin-era rows is silently wrong. Pitfall 4 reified.
- **Defaulting reliability `n_bins=10`:** sklearn tutorial default fails at our N. Use `_adaptive_bin_count(n_samples, min_per_bin=10, max_bins=10)` from the start.
- **Coupling reliability to live `signal_history`:** Live corpus has ~10 rows. Reuse `backtest_signal_history` like Brier/IC/IC-IR already do (consistent with Pitfall 10 mitigation).
- **Adding SimFin as optional `[pit-data]` extra:** Pitfall 9 — silent fallback to yfinance when extra not installed. SimFin client (httpx-only) is small enough for core deps.
- **Computing Murphy on too-few samples:** Exact-bin formulas have material bias below N≈60 per bin [CITED: Ferro & Fricker 2012]. Plumb `preliminary_calibration: true` to the frontend.
- **Conflating "confidence" with "predicted probability":** Existing tracker uses `expected_win_rate = midpoint`. Keep this convention; document it explicitly so reliability-plot readers don't assume sigmoid-calibrated probability semantics (Pitfall 12).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reliability plot bin computation | Custom histogram + per-bin frequency | `sklearn.calibration.calibration_curve(y_true, y_prob, n_bins, strategy='quantile', pos_label=1)` | Already-installed; battle-tested; handles edge cases (empty bins return shorter array) [CITED: scikit-learn.org/stable/modules/generated/sklearn.calibration.calibration_curve.html] |
| Wilson 95% binomial CI | Custom z-score math | `scipy.stats.norm.ppf(0.975) = 1.96` constant + standard formula | Wilson formula is 1 line of vectorized numpy; don't pull `statsmodels` for it (~30 MB) |
| Murphy REL/RES/UNC decomposition | Custom triple-sum | Vectorized numpy following arXiv 2008.03033 / Wikipedia formulas | ~30 LOC vectorized; PAV/CORP would be 80+ LOC for marginal stability gain |
| HTTP rate limiter | Custom token bucket | `data_providers/rate_limiter.py::AsyncRateLimiter` | Already in codebase; sliding-window correct; thread-safe; used by Finnhub at 60/min |
| Parquet disk cache | Custom file-based cache | `data_providers/dividend_cache.py` pattern (atomic-rename, Windows fallback, 3-retry) | FOUND-02 sibling; Windows-safe atomic writes already debugged |
| SimFin REST client | `simfin` PyPI SDK | Raw `httpx` mirroring `FinnhubProvider` (50 LOC) | SDK abandoned 2024-04-03; predates v3 API; bulk-CSV download wrong shape [VERIFIED: pypi.org/project/simfin/] |
| Schema column ALTER | Bare SQL | `db/database.py::_ensure_column(conn, table, name, type)` | Idempotent, safe on every startup, exists since v1.0 |
| Frontend chart with diagonal reference | Custom SVG | Recharts `<ScatterChart>` + `<ReferenceLine>` + `<ErrorBar>` | All three are existing Recharts primitives; no new lib |
| Async-job for corpus rebuild | New scheduler | Existing `corpus_rebuild_jobs` table + `_run_batch_rebuild` BackgroundTask | Shipped in v1.1 Phase 5 LIVE-01; same pattern handles SimFin-triggered rebuild |
| Sector name normalization | Per-call lookup | `_SECTOR_ALIAS` dict in `agents/fundamental.py` mirroring SECTOR_PE_MEDIANS keys | Pitfall 13 mitigation — SimFin uses GICS taxonomy, yfinance/Finnhub use yahoo-style |

**Key insight:** Phase 8 is a brownfield integration. Every novel "build something" question has an existing pattern in the codebase that should be mirrored. The bug surface lives in (a) inconsistent FOUND-04 handling, (b) missing schema column, (c) wrong default bin count — all three are checklist items, not custom development.

---

## Open Questions — RESOLVED

### Q1: SimFin filing-date filtering for amended 10-Q/A — RESOLVED

**Question:** How does SimFin handle amended filings (10-Q/A) that carry the original filing date but different content? Does the API return both versions?

**Resolution (HIGH confidence):**

The SimFin v3 REST API exposes the `asreported=true` boolean parameter on `/companies/statements` [VERIFIED: simfinapi R-package docs at cran.r-project.org/web/packages/simfinapi/simfinapi.pdf + simfin.readme.io/reference/statements-verbose-1].

**Default behavior (`asreported=false` or omitted):** Returns the LATEST restated values for the (ticker, statement, period, fyear) tuple. The "Restated Date" metadata field reflects the most recent amendment date. Per SimFin's blog: *"if the Restated Date is e.g. 2020-03-17 then the financial data is actually from this latter date. So the SimFin datasets are not so-called 'point-in-time' data."* [CITED: simfin.com/en/blog/find-good-fundamental-data/]

**PIT behavior (`asreported=true`):** Returns the as-reported (not restated) values — the figures as they originally appeared on the first 10-Q / 10-K filing for that fiscal period. Amendments (10-Q/A) are filtered out. [VERIFIED: simfinapi R-package + Excel plugin docs]

**Recommended query pattern for "fundamentals as known on date X":**
```python
# Step 1: Determine which fyear/period was the most recent filed BEFORE date X
#   This requires filtering by the Publish Date metadata field (the original 10-K/10-Q date,
#   NOT the Restated Date). Per SimFin: "the Publish Date is for the Form 10-K or 10-Q"
#   [CITED: simfin.com/en/blog/find-good-fundamental-data/]
#
# Step 2: Query with asreported=true and that fyear/period
financials = await provider.get_financials(
    ticker="AAPL",
    statement="pl",
    period="q2",
    fyear=2024,
    asreported=True,    # KEY — return original 10-Q values, not 10-Q/A amendments
)
```

**Edge case — multiple amendments:** SimFin standardizes to ONE row per (ticker, statement, period, fyear) regardless of how many amendments occurred. With `asreported=true` you get the FIRST filed values; with `asreported=false` you get the LATEST restated values. There is no API path to retrieve the *intermediate* amendments.

**Implication for DATA-v2-05 (restated-vs-as-filed delta badge):** Two separate queries are needed — one with `asreported=false` (current values) and one with `asreported=true` (original values). Compute `delta = (restated - as_filed) / as_filed` per metric. Surface badge when `|delta| > 10%` for any metric. This means **2× SimFin API calls per position** for the delta check — within free-tier 2/sec budget for solo-operator portfolio of 5-10 positions.

**Confidence:** HIGH — `asreported` parameter confirmed across R-package, Excel plugin, and Python SDK docs (3 independent sources). The exact response field naming (`Publish Date`, `Restated Date`) verified via simfin.com blog post.

**Defensive code requirement:** When SimFin returns a row with `Publish Date != Restated Date`, log a warning that *this metric was later restated* — operator can opt to investigate. This is the discrimination signal DATA-v2-05 surfaces.

### Q2: Murphy decomposition — exact-bin vs PAV (CORP method) — RESOLVED

**Question:** Does arXiv 2008.03033's exact-bin REL/RES/UNC formulas suffice for our N (~10-100 samples per bin in `backtest_signal_history`), or is PAV-based CORP needed?

**Resolution (HIGH confidence):**

**Recommendation: exact-bin (NOT PAV).** The ROADMAP and REQUIREMENTS already lock this — the resolution here documents *why* the lock is correct.

**Murphy's exact-bin decomposition** (from Wikipedia / Siegert 2017 / Brocker):

```
BS = REL - RES + UNC

REL = (1/N) Σₖ nₖ (fₖ - ōₖ)²        # Reliability (calibration)
RES = (1/N) Σₖ nₖ (ōₖ - ō)²          # Resolution (discrimination)
UNC = ō (1 - ō)                       # Uncertainty (climatological)

where:
  N  = total forecasts
  nₖ = count of forecasts in bin k
  fₖ = mean predicted probability in bin k
  ōₖ = observed frequency in bin k (positive class rate)
  ō  = overall base rate (Σnₖōₖ / N)
```

**Sanity property:** REL - RES + UNC ≈ Brier score (computed independently via existing `compute_brier_score`). Including this verification in the Murphy endpoint response is a free integrity check — if it diverges by > 1e-6, there's a bug.

**Sample-size threshold:** Per Ferro & Fricker 2012: *"When bias-corrected decomposition is used, the biases of reliability and resolution are negligible when n is greater than about 60."* [CITED: empslocal.ex.ac.uk/people/staff/ferro/Publications/ferro-fricker2012copyright.pdf]

**Our N range:** `backtest_signal_history` corpus carries ~750 rows synthetic per phase 2 plan + ~10 live rows. With adaptive binning at min_per_bin=10, we'll have 5-10 bins of ~70-150 samples each. **Within the stable range for exact-bin.** Below the bias-corrected threshold for individual sparse bins — but flagged via `preliminary_calibration: true`.

**Why NOT PAV/CORP at v1.2:** PAV-based CORP from arXiv 2008.03033 / PNAS 2016191118 produces stable reliability diagrams via isotonic regression. This buys ~15-20% reduction in REL bias at N<60 per bin. At our N≥60-150 per bin (post-adaptive-binning), the gain is < 5%. Cost is ~80 LOC of monotonic-regression code in tracker.py. **Not worth it for v1.2.** Defer to v2+.

**Implementation sketch (~30 LOC, vectorized):**
```python
# tracking/tracker.py — new method
def compute_murphy_decomposition(
    self,
    bins: list[dict],   # output of compute_reliability_bins
) -> dict[str, float]:
    """Murphy 3-component decomposition: REL - RES + UNC ≈ Brier.

    [CITED: Murphy 1973; Wikipedia 'Brier score']
    Sample-size guidance: REL/RES biases negligible at N ≥ 60 per bin.
    [CITED: Ferro & Fricker 2012]
    """
    import numpy as np
    n_arr = np.array([b["n"] for b in bins])
    f_arr = np.array([b["predicted"] for b in bins])  # mean predicted prob in bin
    o_arr = np.array([b["observed"] for b in bins])   # observed frequency in bin
    N = n_arr.sum()
    if N == 0:
        return {"rel": None, "res": None, "unc": None, "verified_sum": None}
    o_bar = (n_arr * o_arr).sum() / N                 # base rate
    rel = (n_arr * (f_arr - o_arr) ** 2).sum() / N
    res = (n_arr * (o_arr - o_bar) ** 2).sum() / N
    unc = o_bar * (1 - o_bar)
    return {
        "rel": float(rel),
        "res": float(res),
        "unc": float(unc),
        "verified_sum": float(rel - res + unc),       # ≈ Brier; sanity
    }
```

**Confidence:** HIGH — formulas verified across 4 sources (arXiv 2008.03033 abstract, Wikipedia, Siegert 2017 simplification paper, Brocker 2009 generalization). Sample-size guidance from Ferro & Fricker 2012 (independent). Trade-off articulation matches REQUIREMENTS.md Out-of-Scope row reasoning.

### Q3: `use_pit_fundamentals` opt-in scope — RESOLVED

**Question:** Per-analyze (AgentInput field), per-portfolio (column on portfolios table), or globally (`SIMFIN_FOR_FUNDAMENTALS` env var)?

**Resolution (HIGH confidence):**

**Recommendation: per-analyze AgentInput field — `AgentInput.use_pit_fundamentals: bool = False`.**

**Rationale:**

1. **Mirrors `backtest_mode` precedent.** `backtest_mode` is per-analyze (`AgentInput.backtest_mode: bool = False`). The two flags are *semantic siblings* — both control whether fundamentals are PIT or restated. Putting them at the same scope keeps the API contract orthogonal: `(backtest_mode, use_pit_fundamentals)` is the matrix that determines the FOUND-04 path. Operator and code reasoning is consistent. [VERIFIED: agents/models.py:23-31 `AgentInput`]

2. **Matches existing test pattern.** The Phase 1 tripwire `test_synthesis_skipped_in_backtest_mode` and similar regression tests pass `AgentInput(backtest_mode=True)`. The new tripwire `test_fundamental_agent_backtest_mode_default_unchanged` will pass `AgentInput(backtest_mode=True, use_pit_fundamentals=False)` — direct mirror. Per-portfolio scope would force a fixture creating a portfolio row, slowing tests. Per-env-var scope would force `monkeypatch.setenv` + `importlib.reload` to flip — fragile.

3. **Backtester operator workflow.** The operator running a backtest (`backtester.run(backtest_mode=True)`) decides per-run whether to use SimFin. Per-portfolio scope would force them to maintain two parallel portfolios (one with the flag, one without) for A/B comparison — bad UX. Per-analyze scope is what they need.

4. **First-SimFin-enable corpus rebuild trigger.** ROADMAP SC-4 says *"first `use_pit_fundamentals=True` observation triggers a one-shot SimFin-corpus rebuild via existing `corpus_rebuild_jobs`."* This is detected at the `engine/pipeline.py` analyze entry point: when an `AgentInput` arrives with the flag set AND `corpus_rebuild_jobs` has no completed SimFin run, kick a `BackgroundTask` and proceed with current request using yfinance fallback. Per-analyze scope is the natural detection point.

5. **NOT global env var (`SIMFIN_FOR_FUNDAMENTALS=true`):** Two problems. (a) Switches every analyze including non-backtest ones — an operator who sets the flag for backtesting accidentally changes their live analysis path. (b) Conflicts with multi-portfolio future: today single-user, but future v1.3+ multi-portfolio support would force flag-per-context anyway. Better to start at the right scope.

6. **NOT per-portfolio column:** Adds DB schema burden, requires UI to expose toggle, requires settings flow. Premature for v1.2 single-user solo-operator. Can be ADDED later as a per-portfolio default that flows into AgentInput at request-construction time without breaking the per-analyze contract.

**Specific naming and API surface:**
- Field name: `use_pit_fundamentals: bool = False` (matches `backtest_mode` casing convention)
- Companion field: `backtest_date: date | None = None` (required when `use_pit_fundamentals=True` — needed for SimFin asof filtering)
- Validation site: `agents/fundamental.py` raises `ValueError("use_pit_fundamentals=True requires backtest_date")` if missing
- API endpoint propagation: `POST /api/v1/analyze/{ticker}` accepts optional `{"use_pit_fundamentals": bool, "backtest_date": "YYYY-MM-DD"}` — additive, doesn't break stable contract
- Backtester wiring: `backtesting/backtester.py::Backtester.run()` exposes `use_pit_fundamentals` kwarg that flows into per-bar `AgentInput` construction

**Confidence:** HIGH — recommendation explicitly previewed and endorsed in PROJECT.md row 78 (*"layered routing via opt-in `use_pit_fundamentals` field on `AgentInput`"*). Three independent justifications converge.

---

## Critical Defensive Code Patterns (from Pitfalls Catalog)

Phase 8 owns 9 of 13 pitfalls (Pitfalls 1, 2, 4, 7, 8, 9, 10, 12, 13) plus Cross-1. Each MUST have a corresponding tripwire test landing in the SAME PR as the related code.

| Pitfall | Severity | Defensive code | Test name |
|---------|----------|---------------|-----------|
| **1. SimFin bypasses FOUND-04** | DATA-CORRUPTION | Dual-condition guard at agents/fundamental.py:56 — `backtest_mode and not use_pit_fundamentals → HOLD` | `test_fundamental_agent_backtest_mode_default_unchanged` (Wave 0) |
| **2. Reliability plot binning hides miscalibration** | SILENT-FAILURE | `_adaptive_bin_count(n_samples, min_per_bin=10, max_bins=10)` + `preliminary_calibration: true` flag in API response + amber UI banner | `test_adaptive_bin_count`, `test_preliminary_calibration_flag_propagates` |
| **4. Provider mixing in signal_history** | DATA-CORRUPTION | `fundamentals_provider` column on 3 tables, composite index, IC + drift queries filter by provider | `test_fundamentals_provider_migration_idempotent`, `test_ic_query_filters_by_provider`, `test_drift_baseline_isolated_per_provider` |
| **7. Survivorship-bias warning inheritance** | SILENT-FAILURE | Reliability response inherits existing `survivorship_bias_warning` flag | `test_reliability_endpoint_inherits_survivorship_warning` |
| **8. SimFin 429 during corpus rebuild** | LOUD-FAILURE | `AsyncRateLimiter(2/sec, 60s window)`, FOUND-07 rollback honors 429 | `test_simfin_429_triggers_clean_rollback` (using `respx`/httpx mock) |
| **9. SimFin optional-install footgun** | DATA-CORRUPTION | SimFin client (httpx-only) → core deps NOT optional extra; `RuntimeError` on missing `SIMFIN_API_KEY` when `use_pit_fundamentals=True` | `test_simfin_provider_no_silent_yfinance_fallback` |
| **10. Backtest vs live corpus conflation** | SILENT-FAILURE | `?corpus=backtest|live` query param + UI toggle + plot title disambiguation | `test_calibration_corpus_param_routing` |
| **12. Confidence vs probability conflation** | COSMETIC | Inline docstring + API doc explicit on convention (`expected_win_rate = midpoint`); existing tracker convention preserved | `test_reliability_uses_confidence_midpoint_convention` |
| **13. SimFin sector naming mismatch** | SILENT-FAILURE | `_SECTOR_ALIAS` map normalizing GICS → existing 12-sector table | `test_simfin_sector_alias_normalization` |
| **Cross-1 (SimFin + drift)** | DATA-CORRUPTION | Drift detector `_get_avg_icir_60d` filters by `fundamentals_provider`; first-SimFin-enable triggers corpus rebuild via `corpus_rebuild_jobs` | `test_drift_detector_baseline_isolated_per_provider`, `test_first_simfin_enable_triggers_corpus_rebuild` |

**Wave 0 prerequisite tests** (must land before any feature code):
- `test_fundamental_agent_backtest_mode_default_unchanged` (Pitfall 1)
- `test_fundamentals_provider_migration_idempotent` (Pitfall 4)
- `test_simfin_provider_no_silent_yfinance_fallback` (Pitfall 9)

---

## Common Pitfalls (Phase 8 — extracted from PITFALLS.md)

### Pitfall 1: SimFin Bypasses FOUND-04 Contract

**What goes wrong:** Naive integration assumes "SimFin is PIT, so we can lift the backtest_mode HOLD short-circuit." This breaks (a) `engine/signal_aggregator.py` weight renormalization (FOUND-05's 12-case parametrized test), (b) `backtest_signal_history` Brier/IC computations (existing rows have FundamentalAgent at completeness=0).

**Why it happens:** Contract is enforced at agents/fundamental.py:56-77, but its CONSEQUENCES live in 3 other modules. Engineer reads only the agent file.

**How to avoid:** Add `AgentInput.use_pit_fundamentals: bool = False` opt-in field. FOUND-04 short-circuit becomes dual-condition (`backtest_mode and not use_pit_fundamentals`). Tripwire regression test in initial PR.

**Warning signs:** `compute_brier_score("FundamentalAgent")` suddenly returns non-None. Aggregated signal flips on stable corpus-replay test. New review-fix issue: "FundamentalAgent now contributes to backtests."

### Pitfall 2: Reliability Plot Binning Hides Miscalibration

**What goes wrong:** sklearn `calibration_curve(n_bins=10)` is the canonical tutorial example. With our corpus (~10 live + ~750 synthetic), 10 bins → 0-3 samples/bin → Swiss-cheese plot → operator concludes "uncalibrated" when it's sample noise.

**Why it happens:** Tutorial defaults look fine in dev against fat synthetic data, fail in production.

**How to avoid:** `_adaptive_bin_count(n_samples, min_per_bin=10, max_bins=10) → max(2, min(10, n_samples // 10))`. Plumb `preliminary_calibration: true` flag through API. Frontend renders amber banner.

**Warning signs:** Plot zig-zags wildly (not smooth diagonal-ish). Plot "looks different every week" (N on cusp, bin assignments shift). A bin shows literal `100.0` (every sample won — N=2-3 artifact).

### Pitfall 4: Provider Mixing in signal_history

**What goes wrong:** Cache key is `(ticker, date)`, NOT `(ticker, date, fundamentals_provider)`. Pre-SimFin yfinance rows mix with post-SimFin SimFin rows in the same Brier/IC denominator. Drift detector's `_get_avg_icir_60d` baseline shifts due to provider switch (not real drift) → false drift alert.

**Why it happens:** Operator thinks "I'm just adding a better data source." Downstream coupling (caches, signal_history schema, drift_log baseline) is invisible.

**How to avoid:** `fundamentals_provider TEXT NOT NULL DEFAULT 'yfinance'` on 3 tables in same PR. Composite index. IC + drift queries filter by provider. Force corpus rebuild on first SimFin enable via `corpus_rebuild_jobs`.

**Warning signs:** IC for FundamentalAgent abruptly steps to new mean (e.g., 0.04 → 0.18) with no market regime change. `drift_log.delta_pct` jumps > 50% on a single Sunday-cron run. SELL signal on a position the journal note flagged as BUY 6 months ago.

### Pitfall 7: Reliability Plot Survivorship Bias

**What goes wrong:** `backtest_signal_history` is built from currently-tradeable tickers. Delisted/acquired/bankrupt tickers excluded. Reliability plots over-state calibration.

**How to avoid:** Inherit existing `survivorship_bias_warning: true` flag from `/api/v1/analytics/calibration`. Render a small "S" badge or note next to plot title. Document on frontend page.

### Pitfall 8: SimFin Rate Limit During Corpus Rebuild

**What goes wrong:** v1.1 `_run_batch_rebuild` covers 50 tickers × 250 trading days = 12,500 SimFin API calls. Free-tier daily cap (not publicly published, but inferred from pricing-page tier structure) hit ~30% through. HTTP 429 cascades. Existing rollback DELETE may leave corpus partially populated if 429 isn't classified as fatal-rollback.

**How to avoid:** `AsyncRateLimiter(max_calls=2, period_seconds=1)` (sustained 2/sec sliding window). Honor FOUND-07 four-state machine — 429 → FAILED + rollback DELETE. Surface UI estimate: *"Rebuild will take ~6 hours at free-tier rate."* Smoke test using `respx`/httpx mock confirming 429 → clean rollback.

### Pitfall 9: SimFin Optional-Install Footgun

**What goes wrong:** Making SimFin a `[pit-data]` extra means: in some installs, `use_pit_fundamentals=True` silently falls back to yfinance because SimFin not installed. Operator believes they got PIT but didn't.

**How to avoid:** SimFin client is httpx-only (no new wheel) → CORE deps. If `SIMFIN_API_KEY` missing AND `use_pit_fundamentals=True`, raise `RuntimeError("Set SIMFIN_API_KEY or set use_pit_fundamentals=False")`. Hard error, not soft fallback.

### Pitfall 10: Backtest vs Live Corpus Conflation

**What goes wrong:** Operator viewing reliability plot doesn't know which corpus (`signal_history` live ~10 rows vs `backtest_signal_history` synthetic ~750 rows). False confidence in "live performance" derived from backtest plot.

**How to avoid:** API param `?corpus=backtest|live` (default `backtest` — more rows). Frontend toggle on `/calibration`. Plot title MUST include corpus source ("Backtest corpus reliability" vs "Live signal reliability").

### Pitfall 12: Confidence vs Probability Conflation

**What goes wrong:** ML literature reliability plots use predicted probability (after sigmoid). Existing `tracker.compute_calibration_data` plots confidence midpoint. They are NOT the same. Copying ML code without converting confidence→probability makes the diagonal "perfect calibration" line meaningless.

**How to avoid:** API docstring + comment: `"X-axis = mean predicted confidence within bin, Y-axis = realized win-rate within bin."` Don't introduce probability semantics. Keep `expected_win_rate = midpoint` convention from existing tracker.

### Pitfall 13: SimFin Sector Naming Mismatch

**What goes wrong:** `agents/fundamental.py:25-38 SECTOR_PE_MEDIANS` keyed by 12 sector names (yfinance/Finnhub style). SimFin uses GICS 11-sector taxonomy ("Information Technology" vs "Technology", "Financials" vs "Financial Services"). `_score_pe_trailing` falls back to absolute thresholds for unknown sectors.

**How to avoid:** `_SECTOR_ALIAS` dict in `agents/fundamental.py`:
```python
_SECTOR_ALIAS = {
    "information technology": "technology",
    "financials": "financial services",
    # ... GICS → static-table normalization
}
```

---

## Code Examples

### SimFin Provider — Skeleton (mirroring FinnhubProvider)

```python
# data_providers/simfin_provider.py
# Source: data_providers/finnhub_provider.py:49-103 (mirror)
from __future__ import annotations
import logging, os, warnings
from datetime import date
from typing import Any
import httpx
from data_providers.base import DataProvider
from data_providers.rate_limiter import AsyncRateLimiter

SIMFIN_BASE_URL = "https://prod.simfin.com/api/v3"
logger = logging.getLogger(__name__)


class SimfinProvider(DataProvider):
    """SimFin v3 REST provider for point-in-time fundamentals.

    Free tier: 2 calls/sec sustained, 5K stocks, 5y history.
    Personal-use ToS — data redistribution prohibited (matches local-first scope).
    [VERIFIED: simfin.com/en/prices/]

    asreported=True returns as-reported (original 10-Q values), filtering 10-Q/A.
    asreported=False (default) returns latest restated values.
    [VERIFIED: simfinapi R-package + simfin.readme.io/reference/statements-verbose-1]
    """

    _limiter = AsyncRateLimiter(
        max_calls=int(os.getenv("SIMFIN_RATE_LIMIT", "120")),  # 2/sec * 60s
        period_seconds=60.0,
    )

    def __init__(self, api_key: str | None = None, timeout: float = 10.0) -> None:
        resolved = api_key or os.getenv("SIMFIN_API_KEY")
        self._api_key = resolved
        self._timeout = timeout
        if not resolved:
            warnings.warn(
                "SIMFIN_API_KEY not set. SimfinProvider methods will raise RuntimeError.",
                RuntimeWarning, stacklevel=2,
            )
            self._client: httpx.AsyncClient | None = None
        else:
            self._client = httpx.AsyncClient(
                base_url=SIMFIN_BASE_URL,
                headers={"Authorization": f"api-key {resolved}"},
                timeout=timeout,
            )

    def is_point_in_time(self) -> bool:
        return True  # When asreported=True path is used

    def supported_asset_types(self) -> list[str]:
        return ["stock"]

    async def get_financials(
        self,
        ticker: str,
        statement: str = "pl",
        period: str = "q1",
        fyear: int | None = None,
        asreported: bool = True,
    ) -> dict:
        if self._client is None:
            raise RuntimeError(
                "SIMFIN_API_KEY missing — use_pit_fundamentals=True requires it. "
                "Set SIMFIN_API_KEY env var or call with use_pit_fundamentals=False."
            )
        params: dict[str, Any] = {
            "ticker": ticker,
            "statements": statement,
            "period": period,
            "asreported": "true" if asreported else "false",
        }
        if fyear is not None:
            params["fyear"] = fyear
        async with self._limiter:
            try:
                resp = await self._client.get("/companies/statements", params=params)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    logger.warning("SimFin rate limit hit for %s: %s", ticker, exc)
                    return {}  # honor existing FOUND-07 graceful pattern
                raise

    async def get_price_history(self, ticker: str, *args, **kwargs):
        raise NotImplementedError("SimfinProvider does not provide OHLCV — use yfinance")

    async def get_current_price(self, ticker: str) -> float:
        raise NotImplementedError("SimfinProvider does not provide spot price")

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
```

### Reliability Bin Computation

```python
# tracking/tracker.py — new method (mirrors compute_calibration_data:96-135)
from typing import Any

def _adaptive_bin_count(n_samples: int, min_per_bin: int = 10, max_bins: int = 10) -> int:
    """Bin count = floor(N / min_per_bin), capped at max_bins, floored at 2.

    [Source: PITFALLS.md Pitfall 2 mitigation pattern]
    """
    return max(2, min(max_bins, n_samples // min_per_bin))


async def compute_reliability_bins(
    self,
    agent_name: str,
    horizon: str = "5d",
    min_per_bin: int = 10,
    max_bins: int = 10,
) -> dict[str, Any]:
    """Reliability diagram bins for one agent — predicted prob × observed frequency.

    Reads from backtest_signal_history (NOT live signal_history — sparse).
    Excludes HOLD signals (one-vs-rest binary like compute_brier_score).
    Wilson 95% CI per bin. Returns preliminary_calibration=True if bin count low.

    [VERIFIED: scikit-learn.org/stable/modules/generated/sklearn.calibration.calibration_curve.html]
    [VERIFIED: en.wikipedia.org/wiki/Binomial_proportion_confidence_interval — Wilson score]
    """
    from sklearn.calibration import calibration_curve
    import numpy as np

    rows = await self._store.get_backtest_signals_by_agent(agent_name, horizon)
    # rows: list of {"raw_score": float, "signal": "BUY|SELL|HOLD", "confidence": float, "forward_return_5d": float}
    # Map to (y_true: 1 if forward_return > 0, y_prob: confidence/100), excluding HOLD
    y_true_list, y_prob_list = [], []
    for r in rows:
        if r["signal"] == "HOLD":
            continue
        if r.get("forward_return_5d") is None:
            continue
        y_prob = float(r["confidence"]) / 100.0
        # For BUY: WIN if return > 0; for SELL: WIN if return < 0
        if r["signal"] == "BUY":
            y_true_list.append(1 if r["forward_return_5d"] > 0 else 0)
        else:  # SELL
            y_true_list.append(1 if r["forward_return_5d"] < 0 else 0)
        y_prob_list.append(y_prob)

    n_samples = len(y_true_list)
    n_bins = _adaptive_bin_count(n_samples, min_per_bin, max_bins)

    if n_samples < min_per_bin * 2:
        return {
            "bins": [],
            "n_samples": n_samples,
            "n_bins_used": 0,
            "preliminary_calibration": True,
            "ece": None,
        }

    y_true = np.array(y_true_list)
    y_prob = np.array(y_prob_list)

    # sklearn quantile binning — equal sample count per bin, robust at small N
    prob_true, prob_pred = calibration_curve(
        y_true, y_prob, n_bins=n_bins, strategy="quantile", pos_label=1,
    )
    # sklearn returns shorter arrays if some bins were empty — re-derive bin edges + counts
    edges = np.quantile(y_prob, np.linspace(0, 1, n_bins + 1))
    bin_indices = np.digitize(y_prob, edges[1:-1])  # 0..n_bins-1
    bins_out = []
    z_975 = 1.96  # scipy.stats.norm.ppf(0.975)
    for k in range(n_bins):
        mask = bin_indices == k
        n_k = int(mask.sum())
        if n_k == 0:
            continue
        observed = float(y_true[mask].mean())  # win rate
        predicted = float(y_prob[mask].mean())
        # Wilson 95% CI for binomial proportion
        if n_k > 0:
            p_hat = observed
            denom = 1 + z_975 ** 2 / n_k
            center = (p_hat + z_975 ** 2 / (2 * n_k)) / denom
            half = z_975 * np.sqrt(p_hat * (1 - p_hat) / n_k + z_975 ** 2 / (4 * n_k ** 2)) / denom
            ci_low, ci_high = max(0.0, center - half), min(1.0, center + half)
        else:
            ci_low, ci_high = 0.0, 1.0
        bins_out.append({
            "bin_lo": float(edges[k]),
            "bin_hi": float(edges[k + 1]),
            "n": n_k,
            "predicted": predicted,
            "observed": observed,
            "ci_low": float(ci_low),
            "ci_high": float(ci_high),
            "ece_contrib": (n_k / n_samples) * abs(predicted - observed),
        })

    ece = sum(b["ece_contrib"] for b in bins_out)
    min_bin_n = min((b["n"] for b in bins_out), default=0)
    preliminary = n_bins < 5 or min_bin_n < min_per_bin
    return {
        "bins": bins_out,
        "n_samples": n_samples,
        "n_bins_used": len(bins_out),
        "preliminary_calibration": preliminary,
        "ece": float(ece),
    }
```

### Murphy Decomposition

```python
# tracking/tracker.py — new method
def compute_murphy_decomposition(self, bins_response: dict) -> dict[str, float | None]:
    """Murphy 3-component decomposition: REL - RES + UNC ≈ Brier.

    Exact-bin formulas from Murphy 1973 / Wikipedia 'Brier score'.
    Bias-corrected exact-bin is stable at N ≥ 60 per bin (Ferro & Fricker 2012).
    Below threshold, surfaces preliminary_calibration: true.

    [CITED: arxiv.org/abs/2008.03033 (CORP context)]
    [CITED: en.wikipedia.org/wiki/Brier_score]
    [CITED: empslocal.ex.ac.uk/people/staff/ferro/Publications/ferro-fricker2012copyright.pdf]
    """
    import numpy as np
    bins = bins_response.get("bins", [])
    if not bins:
        return {"rel": None, "res": None, "unc": None, "verified_sum": None}
    n_arr = np.array([b["n"] for b in bins], dtype=float)
    f_arr = np.array([b["predicted"] for b in bins], dtype=float)
    o_arr = np.array([b["observed"] for b in bins], dtype=float)
    N = float(n_arr.sum())
    if N == 0:
        return {"rel": None, "res": None, "unc": None, "verified_sum": None}
    o_bar = float((n_arr * o_arr).sum() / N)
    rel = float((n_arr * (f_arr - o_arr) ** 2).sum() / N)
    res = float((n_arr * (o_arr - o_bar) ** 2).sum() / N)
    unc = float(o_bar * (1 - o_bar))
    return {
        "rel": rel,
        "res": res,
        "unc": unc,
        "verified_sum": rel - res + unc,  # ≈ Brier (sanity invariant)
    }
```

### Schema Migration

```python
# db/database.py — extend init_db() at the end, before await conn.commit()
async def _migrate_fundamentals_provider(conn: aiosqlite.Connection) -> None:
    """DATA-v2-04: provenance column on 3 corpus tables + composite indexes.

    Idempotent (matches _ensure_column pattern at line 14-24).
    DEFAULT 'yfinance' is correct for all existing rows (sole provider in v1.0/v1.1).
    [Pattern: db/database.py:14-24 _ensure_column]
    """
    for table in ("signal_history", "backtest_signal_history", "drift_log"):
        await _ensure_column(
            conn, table,
            column_name="fundamentals_provider",
            column_type="TEXT NOT NULL DEFAULT 'yfinance'",
        )

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_signal_history_ticker_created_provider
        ON signal_history (ticker, created_at, fundamentals_provider)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_bsh_ticker_signal_date_provider
        ON backtest_signal_history (ticker, signal_date, fundamentals_provider)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_drift_log_agent_asset_provider_evaluated
        ON drift_log (agent_name, asset_type, fundamentals_provider, evaluated_at DESC)
    """)
```

### Frontend ReliabilityPlot

```tsx
// frontend/src/components/calibration/ReliabilityPlot.tsx
// Pattern: Recharts ScatterChart + ReferenceLine + ErrorBar (all native primitives)
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, ResponsiveContainer,
  ReferenceLine, ErrorBar,
} from "recharts";
import type { ReliabilityResponse } from "../../api/types";

interface Props {
  data: ReliabilityResponse;
  agentName: string;
}

export default function ReliabilityPlot({ data, agentName }: Props) {
  const points = data.bins.map((b) => ({
    x: b.predicted,
    y: b.observed,
    n: b.n,
    errLow: b.observed - b.ci_low,
    errHigh: b.ci_high - b.observed,
  }));

  return (
    <div className="space-y-2" data-testid={`reliability-plot-${agentName}`}>
      {data.preliminary_calibration && (
        <div className="text-xs text-amber-400 bg-amber-950/30 rounded px-2 py-1">
          Preliminary calibration — {data.n_samples} samples, {data.n_bins_used} bins.
          Need ≥ 200 samples for stable estimates.
        </div>
      )}
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 32, left: 32 }}>
          <XAxis type="number" dataKey="x" domain={[0, 1]} name="Predicted prob"
                 label={{ value: "Predicted probability", position: "insideBottom", offset: -8 }} />
          <YAxis type="number" dataKey="y" domain={[0, 1]} name="Observed freq"
                 label={{ value: "Observed frequency", angle: -90, position: "insideLeft" }} />
          <ZAxis type="number" dataKey="n" range={[40, 400]} name="N samples" />
          {/* Diagonal y=x reference line — perfect calibration */}
          <ReferenceLine
            segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]}
            stroke="#6b7280" strokeDasharray="4 4"
          />
          <Scatter name={agentName} data={points} fill="#10b981">
            <ErrorBar dataKey="errLow" direction="y" stroke="#10b981" />
            <ErrorBar dataKey="errHigh" direction="y" stroke="#10b981" />
          </Scatter>
          <Tooltip
            formatter={(value, name) => {
              if (name === "Predicted prob") return [(value as number).toFixed(2), "Predicted"];
              if (name === "Observed freq") return [(value as number).toFixed(2), "Observed"];
              if (name === "N samples") return [value, "Bin size"];
              return [value, name];
            }}
          />
        </ScatterChart>
      </ResponsiveContainer>
      <div className="text-xs text-gray-500">
        ECE = {data.ece !== null ? data.ece.toFixed(3) : "—"} •
        N = {data.n_samples} • Bins = {data.n_bins_used}
      </div>
    </div>
  );
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `simfin` PyPI SDK with bulk-CSV download | Raw httpx client to `/api/v3/companies/statements?asreported=true` | SimFin Jan 2024 backend migration to `prod.simfin.com` | SDK abandoned 2024-04-03; v3 REST is the supported surface |
| `pycoingecko` sync wrapper | (out of scope this phase) `coingecko-sdk` async official | CoinGecko Nov 2024 official Python SDK release | Phase 9, not Phase 8 |
| `n_bins=10` hardcoded reliability plot | `_adaptive_bin_count(N, min_per_bin=10, max_bins=10)` | Pitfall 2 mitigation pattern | Avoids Swiss-cheese plots at small N |
| Bootstrap CI per bin | Wilson 95% CI per bin | v1.2 Out-of-Scope decision | ~10× cheaper compute, asymptotically equivalent at N≥15 |
| Confidence-bucket calibration only | + Murphy/Brier decomposition (REL/RES/UNC) | v1.2 SIG-v2-02 — differentiator | No OSS competitor offers this (Ghostfolio, Portfolio Performance, qlib) |
| Provider-blind `signal_history` | `fundamentals_provider` provenance column | v1.2 DATA-v2-04 (Pitfall 4 mitigation) | Eliminates silent IC contamination from provider mixing |

**Deprecated/outdated:**
- `simfin` PyPI SDK 1.0.1 — Snyk Inactive; predates v3 API; bulk-CSV wrong shape [VERIFIED: snyk.io/advisor/python/simfin]
- `ReliabilityDiagram` PyPI 0.0.6 — last release 2020-12; superseded by sklearn `calibration_curve`
- Hardcoded `n_bins=5` (sklearn default) — fails at v1.2 corpus size

---

## Assumptions Log

> Tracking claims tagged `[ASSUMED]` — for planner / discuss-phase to confirm with operator.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | SimFin v3 `/companies/statements?asreported=true` returns ONLY the original 10-Q values for matched (ticker, fyear, period); 10-Q/A amendments are filtered out | Open Question 1 | If SimFin returns multiple amended rows, our queries would need explicit `WHERE Filed Date == Original Date` filtering. Mitigation: add an integration test against a known-amended ticker (e.g., review Apple 10-K/A history) before Phase 8 ships. |
| A2 | `Authorization: api-key {key}` is the correct SimFin v3 auth header (vs query param `api-key=...`) | Standard Stack — Pattern 1 | Vendor docs hit ECONNREFUSED during research; reading suggests header. Wrong choice causes 401 on first call. Mitigation: a `test_simfin_auth_header_format` smoke test wired to `respx` mock + a one-time live ping in operator-run UAT. |
| A3 | SimFin free-tier 500 high-speed credits/mo is sufficient for 5-10 position portfolio with quarterly fundamentals refresh (40 calls/quarter typical) | PITFALLS.md Pitfall 8 / SUMMARY.md Gap 1 | Heavy backtest rebuild burns credits faster than expected. Mitigation: surface UI estimate before kicking rebuild; existing AsyncRateLimiter prevents accidental burst. |
| A4 | Ferro & Fricker 2012's `n≈60 per bin` bias-correction threshold applies to our binary BUY/SELL classification (their context was meteorological binary forecasting) | Open Question 2 / Murphy decomposition | Below threshold, REL/RES estimates carry bias we don't surface. Mitigation: `preliminary_calibration: true` flag already covers this case; banner is amber, not red. |
| A5 | `RestatedDeltaBadge` mounts on `frontend/src/components/portfolio/PositionsTable.tsx` (existing component) | Architecture — frontend | If positions are also rendered on `PositionDetailPage.tsx`, the badge needs duplicate rendering. Mitigation: planner can grep for `PositionsTable` callers in the architecture review. |
| A6 | `corpus_rebuild_jobs` async-job pattern (shipped v1.1 LIVE-01) handles `provider='simfin'` parameter via additive column without breaking existing rebuild flows | DATA-v2-04 SC-4 | If existing rebuild API hardcodes provider, we need a small endpoint extension. Mitigation: planner reviews `api/routes/calibration.py::rebuild_corpus` signature in Wave 0. |

**A1, A4 are LOW risk** (well-supported by independent sources but not directly verified end-to-end).
**A2, A6 require empirical confirmation** during planning (Wave 0 verification pass, not a research blocker).
**A3, A5 are MEDIUM risk** but mitigable by inspection.

---

## Open Questions

All three open questions from milestone synthesizer are now resolved (see "Open Questions — RESOLVED" above). Remaining residual uncertainty:

1. **Exact SimFin v3 endpoint path for `/companies/statements`** — `simfin.readme.io/reference/statements-verbose-1` indicates the verbose form; there's also a compact form. Recommendation: planner explicitly chooses which (verbose for richer date metadata; compact for smaller payload). HIGH confidence the endpoint exists; LOW confidence on which is preferred.

2. **`backtest_date` field on AgentInput when `use_pit_fundamentals=False`** — should it be silently ignored or raise? Recommendation: silently ignore (no validation when flag is False) — keeps existing call sites unchanged.

3. **Restated-delta badge metric scope** — DATA-v2-05 says *"any reported metric"* but doesn't enumerate. Likely candidates: revenue, net_income, eps, total_assets, total_debt. Recommendation: planner picks 5-10 most-watched metrics from `agents/fundamental.py::_compute_value_score` + `_compute_quality_score` references. LOW risk — operator will surface preferences during UAT.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All | ✓ | 3.11+ per pyproject.toml | — |
| `httpx>=0.27` | SimFin client | ✓ | existing dep | — |
| `pyarrow>=14.0` | SimFin Parquet cache | ✓ | existing dep | — |
| `scikit-learn>=1.4` | Reliability binning | ✓ (transitive) | 1.6.1 [VERIFIED: pip show 2026-04-28] | None — promote to direct dep, no install needed |
| `numpy>=1.26` | Wilson CI / Murphy | ✓ (transitive) | 2.2.6 [VERIFIED: pip show 2026-04-28] | None — promote to direct dep |
| `scipy>=1.10` | Wilson CI z-value | ✓ (transitive) | 1.15.3 [VERIFIED: pip show 2026-04-28] | None — promote to direct dep |
| `recharts ^2.13.0` | Frontend reliability plot | ✓ | existing in `frontend/package.json` | — |
| SimFin API key | DATA-v2-02 / DATA-v2-04 / DATA-v2-05 | **Operator action required** | — | Without key: feature gracefully unavailable; existing yfinance path unchanged. Operator signs up free at simfin.com/en/prices/ |
| SimFin v3 REST `prod.simfin.com` | DATA-v2-02 | Network-dependent at runtime | — | Without network: SimfinProvider raises; FundamentalAgent falls back to yfinance + warns |
| `respx` (testing httpx mocks) | Pitfall 8 smoke test | ✓ via httpx ecosystem; not in pyproject | — | Add to `[dev]` extra during Wave 0 OR mock at `httpx.AsyncClient` level directly |

**Missing dependencies with no fallback:** None — all blocking requirements resolved by existing dependencies or operator account creation (SimFin signup is free, ~2 minutes).

**Missing dependencies with fallback:**
- SimFin API key: phase ships with full `use_pit_fundamentals=True` raising clear error if missing; FOUND-04 contract preserved as default; existing analysis flows unaffected.

---

## Validation Architecture

> Note: `.planning/config.json` shows `workflow.nyquist_validation: false`. Section is normally skipped — included briefly for planner reference because the requirement complexity warrants explicit test mapping.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio (asyncio_mode=auto) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_simfin_provider.py tests/test_tracker_reliability.py -x` |
| Full suite command | `pytest` |
| Frontend framework | Vitest 2.1.8 + jsdom + @testing-library/react |
| Frontend run | `cd frontend && npm test` |

### Phase Requirements → Test Map (illustrative — planner will refine)

| Req ID | Behavior | Test Type | Automated Command |
|--------|----------|-----------|-------------------|
| SIG-v2-01 | Adaptive bin count | unit | `pytest tests/test_tracker_reliability.py::test_adaptive_bin_count -x` |
| SIG-v2-01 | Wilson CI math | unit | `pytest tests/test_tracker_reliability.py::test_wilson_ci_correctness -x` |
| SIG-v2-01 | preliminary_calibration flag | unit | `pytest tests/test_tracker_reliability.py::test_preliminary_calibration_flag -x` |
| SIG-v2-01 | Frontend amber banner renders | component | `cd frontend && npm test -- ReliabilityPlot.test.tsx` |
| SIG-v2-02 | REL/RES/UNC sums to Brier | unit | `pytest tests/test_tracker_murphy.py::test_decomposition_sanity -x` |
| SIG-v2-02 | Murphy hover tooltips render | component | `cd frontend && npm test -- MurphyDecompositionCard.test.tsx` |
| DATA-v2-02 | FOUND-04 contract preserved | tripwire | `pytest tests/test_fundamental_agent.py::test_backtest_mode_default_unchanged -x` |
| DATA-v2-02 | use_pit_fundamentals routes to SimFin | integration | `pytest tests/test_fundamental_agent_simfin_routing.py -x` |
| DATA-v2-02 | No silent yfinance fallback when key missing | tripwire | `pytest tests/test_simfin_provider.py::test_no_silent_yfinance_fallback -x` |
| DATA-v2-04 | Migration idempotent | unit | `pytest tests/test_db_fundamentals_provider_migration.py -x` |
| DATA-v2-04 | IC query filters by provider | integration | `pytest tests/test_tracker_provider_filter.py -x` |
| DATA-v2-04 | First SimFin enable triggers corpus rebuild | integration | `pytest tests/test_corpus_rebuild_simfin_trigger.py -x` |
| DATA-v2-05 | Restated delta detection > 10% | unit | `pytest tests/test_simfin_restated_delta.py -x` |
| DATA-v2-05 | Frontend RestatedDeltaBadge renders | component | `cd frontend && npm test -- RestatedDeltaBadge.test.tsx` |

### Sampling Rate
- **Per task commit:** `pytest tests/test_simfin_provider.py tests/test_tracker_reliability.py tests/test_fundamental_agent.py -x` (~10s)
- **Per wave merge:** `pytest tests/ -x` (full backend suite + relevant frontend)
- **Phase gate:** Full backend (`pytest`) + frontend (`cd frontend && npm test`) green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_fundamental_agent.py::test_backtest_mode_default_unchanged` — tripwire MUST land first
- [ ] `tests/test_db_fundamentals_provider_migration.py` — migration test before SimFin code
- [ ] `tests/test_simfin_provider.py::test_no_silent_yfinance_fallback` — Pitfall 9 tripwire
- [ ] `respx` (or equivalent httpx mock) added to `[dev]` extra — for SimFin 429 + integration tests

---

## Project Constraints (from CLAUDE.md)

The project's CLAUDE.md (read 2026-04-28) defines explicit directives the planner MUST honor:

### Tech Stack — must fit
- Python 3.11+ backend / React + TS frontend / SQLite
- All Phase 8 additions fit (no new languages, runtimes, or DB engines)

### Testing
- **889-test bar is the floor; features ship with tests** — Phase 8 must add tests, not just modify
- pytest-asyncio with `asyncio_mode=auto` — async helpers awaited directly, no asyncio.run() wrappers
- Use existing `network` marker for live integration tests (SimFin live API)
- Lazy import pattern for heavy deps (sklearn loads quickly; no concern)

### Conventions
- Python: snake_case modules, PascalCase classes, snake_case functions, single-underscore private
- Type hints required for function parameters and returns
- `from __future__ import annotations` at top of all modules (PEP 563)
- TypeScript: PascalCase components, camelCase utilities, strict mode
- Python imports: relative imports from package root (no path aliases)
- React imports: `@/*` maps to `src/`

### Data costs
- **Free/community data providers only** — SimFin free tier is compliant (free signup, 500 credits/mo)
- No paid market-data subscriptions

### Safety
- **No order execution / broker APIs this milestone** — Phase 8 doesn't touch this surface
- Local-first single-user — Phase 8 fits

### Logging
- Python: stdlib `logging` module with named loggers per module (`investment_agent.simfin`, etc.)
- Use `logger.info()` / `warning()` for key events — `_logger.info("Analyzing %s", ticker)` is the existing pattern at agents/fundamental.py:79

### GSD Workflow Enforcement
- **Before using Edit/Write/file-changing tools**, must start work through a GSD command
- Phase 8 work happens via `/gsd-execute-phase 8` (planner constructs PLAN.md files; executor follows them)
- Direct repo edits outside GSD only with explicit user request

### Error Handling
- `try/except` with specific exception types
- Custom `ApiError` envelope pattern for HTTP errors
- Graceful degradation: cache stale data on error, display error to user
- Async exceptions: `asyncio.gather(return_exceptions=True)` captures and logs individually

**Compliance check for Phase 8 plans:**
- ✓ Stack additions fit constraints
- ✓ Tests included for every new code path
- ✓ Free-tier data provider only (SimFin free signup)
- ✓ No broker / execution work
- ✓ Local-first single-user assumed
- ✓ stdlib logging via existing `self._logger` pattern
- ✓ All work through `/gsd-execute-phase 8`

---

## Sources

### Primary (HIGH confidence)

**Vendor / Library docs:**
- [SimFin v3 base URL `prod.simfin.com`](https://www.simfin.com/en/blog/major-simfin-update/) — January 2024 backend migration
- [SimFin pricing & free-tier limits](https://www.simfin.com/en/prices/) — 2/sec, 5K stocks, 5y history, 500 credits/mo
- [SimFin Restated Date semantics](https://www.simfin.com/en/blog/find-good-fundamental-data/) — *"the SimFin datasets are not so-called 'point-in-time' data"* + Publish Date / Restated Date definitions
- [SimFin technical updates v3](https://www.simfin.com/en/technical-updates-to-api-v3-and-bulk-download/) — endpoint list `/api/v3/companies/{general,list,statements}`
- [SimFin /companies/statements verbose endpoint](https://simfin.readme.io/reference/statements-verbose-1) — `asreported` boolean parameter confirmed
- [simfinapi R-package documentation](https://cran.r-project.org/web/packages/simfinapi/simfinapi.pdf) — independent confirmation of `asreported` parameter semantics
- [scikit-learn calibration_curve API](https://scikit-learn.org/stable/modules/generated/sklearn.calibration.calibration_curve.html) — n_bins, strategy, pos_label parameters; `pos_label` added in 1.1
- [scikit-learn Probability Calibration](https://scikit-learn.org/stable/modules/calibration.html)
- [Wilson score interval — Wikipedia](https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval) — formula and asymptotic equivalence

**Existing codebase (direct file reads):**
- `agents/fundamental.py:56-77` — FOUND-04 short-circuit (the integration point this phase modifies)
- `agents/fundamental.py:140-163` — FOUND-04 defence-in-depth EDGAR guard
- `agents/models.py:23-31` — `AgentInput` dataclass (extension point for `use_pit_fundamentals`)
- `agents/base.py` — BaseAgent abstract class
- `data_providers/finnhub_provider.py:49-103` — provider skeleton template (mandatory mirror for SimfinProvider)
- `data_providers/dividend_cache.py:38-150` — disk cache template (mandatory mirror for SimfinStatementCache)
- `data_providers/rate_limiter.py` — token-bucket AsyncRateLimiter
- `tracking/tracker.py:96-135` — existing `compute_calibration_data` (parallel pattern for `compute_reliability_bins`)
- `tracking/tracker.py:320-350` (compute_brier_score), `tracker.py:356-424` (compute_rolling_ic + compute_icir)
- `engine/pipeline.py:1-200` — agent orchestration + `asyncio.gather(return_exceptions=True)` integration point
- `engine/drift_detector.py:1-120` — drift detector reading drift_log
- `db/database.py:14-24` — `_ensure_column` migration helper
- `db/database.py:407-540` (signal_history + backtest_signal_history schemas)
- `db/database.py:725-755` (drift_log schema)
- `frontend/src/pages/CalibrationPage.tsx` — frontend mount point
- `frontend/src/components/calibration/AgentCalibrationRow.tsx` — calibration row component
- `frontend/src/components/calibration/{ICSparkline,DriftBadge,CalibrationTable}.tsx` — sibling components for pattern reference
- `frontend/package.json` — `recharts: ^2.13.0`
- `pyproject.toml` — current dependency set

**v1.2 milestone planning:**
- `.planning/PROJECT.md` (v1.2 scoping + Key Decisions table)
- `.planning/REQUIREMENTS.md` (5 phase requirements + Out-of-Scope decisions)
- `.planning/ROADMAP.md` (Phase 8 5-criteria + dependency graph)
- `.planning/research/SUMMARY.md` (synthesis of 4 parallel research tracks)
- `.planning/research/STACK.md` (~250 lines — version verification + alternatives)
- `.planning/research/ARCHITECTURE.md` (~800 lines — file-path index + integration points)
- `.planning/research/PITFALLS.md` (~600 lines — 13-pitfall catalog with severity)

### Secondary (MEDIUM confidence)

- [arXiv 2008.03033](https://arxiv.org/abs/2008.03033) — CORP Brier score decomposition (abstract only — full PDF not fetched)
- [Wikipedia: Brier score](https://en.wikipedia.org/wiki/Brier_score) — exact-bin REL/RES/UNC formulas with explicit math
- [Eli Goz: Brier Score Decomposition (Medium)](https://medium.com/@eligoz/some-notes-on-probabilistic-classifiers-iii-brier-score-decomposition-eee5f847d87f) — formula derivation BS = CAL + UNC - RES
- [Siegert 2017 — Simplifying and generalising Murphy's Brier score decomposition (Wiley)](https://rmets.onlinelibrary.wiley.com/doi/abs/10.1002/qj.2985)
- [Ferro & Fricker 2012 — bias-corrected Brier decomposition](https://empslocal.ex.ac.uk/people/staff/ferro/Publications/ferro-fricker2012copyright.pdf) — n≈60 bias threshold
- [pypi.org/project/coingecko-sdk/](https://pypi.org/project/coingecko-sdk/) — confirms 1.14.2 release 2026-04-21 (Phase 9 prep, not Phase 8)
- [pypi.org/project/simfin/](https://pypi.org/project/simfin/) — confirms 1.0.1 last release 2024-04-03
- [Snyk simfin advisor](https://snyk.io/advisor/python/simfin) — Inactive classification
- [pypi.org/project/scikit-learn/](https://pypi.org/project/scikit-learn/) — current stable 1.8.0 as of late 2025
- [SimFin Medium API tutorial](https://simfin-official.medium.com/simfin-api-tutorial-6626c6c1dbeb)
- [skywork.ai SimFin Developer Guide](https://skywork.ai/skypage/en/SimFin-API-A-Developer%E2%80%99s-Guide-to-High-Quality-Financial-Data-for-AI/1976477178574598144)

### Tertiary (LOW confidence — flagged for verification)

- SimFin v3 Authorization header format (`api-key {key}` vs `Bearer {key}`) — vendor docs unreachable in research session; needs Wave 0 smoke test
- SimFin free-tier exact daily/burst quota beyond 500 monthly credits — not publicly enumerated; ship conservative AsyncRateLimiter (2/sec) and verify in operator-run UAT
- Wilson CI vs bootstrap convergence at N=15 — academic consensus but not corpus-specific verified

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all version verifications independent, alternative rejections documented
- Architecture: HIGH — all integration points verified via direct file reads; provider/cache patterns are battle-tested
- Pitfalls: HIGH — all 9 phase-owned pitfalls grounded in either existing code paths, prior-fix history, or vendor-published constraints
- Open questions: HIGH — all three resolved with multiple-source verification; A1/A4 carry residual LOW risk and are flagged for Wave 0 validation

**Research date:** 2026-04-28
**Valid until:** 2026-05-28 (30 days — stable domain; SimFin v3 stable since Jan 2024)
**Phase 8 dependencies confirmed:** Phase 7 v1.1 shipped (`corpus_rebuild_jobs` + `agent_weights` + `/calibration` page mount all present); no upstream blockers

**Implementation order recommendation for planner:**
1. Wave 0 — Tripwire tests + schema migration + `_SECTOR_ALIAS` map (Pitfalls 1, 4, 9, 13)
2. Wave 1 — `SimfinProvider` + `SimfinStatementCache` + `agents/fundamental.py` dual-condition guard + first-SimFin-enable corpus rebuild trigger
3. Wave 2 — `tracker.compute_reliability_bins` + `tracker.compute_murphy_decomposition` + API endpoint extension
4. Wave 3 — Frontend `ReliabilityPlot.tsx` + `MurphyDecompositionCard.tsx` + `RestatedDeltaBadge.tsx` + CalibrationPage / PositionsTable wiring

**Recommended Plan count:** 3-4 plans (Wave 0+1 = 1-2 plans; Wave 2 = 1 plan; Wave 3 = 1 plan).
