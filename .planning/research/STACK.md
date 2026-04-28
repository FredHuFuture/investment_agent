# Stack Research — v1.2 Trustworthy Signals

**Project:** Investment Agent — v1.2 milestone (subsequent / brownfield)
**Researched:** 2026-04-27
**Mode:** Stack additions for 4 NEW capabilities only — `.planning/PROJECT.md` `## Validated` section already covers v1.0+v1.1 stack
**Confidence:** HIGH (PyPI/GitHub release dates verified; SimFin SDK abandonment + CoinGecko Demo limits cross-checked against vendor docs)

---

## Executive Summary

Four v1.2 capabilities require stack changes. Three are **zero new heavy deps** by reusing what's already transitively installed (scipy, numpy, sklearn, recharts) or extending what's pinned (httpx). One requires **two small core deps** (`coingecko-sdk` + new HTTP client glue for SimFin v3 REST).

**Bottom line:**

| v1.2 Capability | New PyPI/npm Deps | Default-install Δ | Decision |
|---|---|---|---|
| SIG-v2-01 — Reliability plots | None — `scikit-learn>=1.6` already transitive via quantstats | 0 MB (already there) | **Promote `scikit-learn>=1.4` to direct dep** for explicit contract |
| DATA-v2-02 — SimFin point-in-time | None — pure httpx client (SimFin SDK abandoned, see below) | 0 MB | **Build thin async wrapper using existing `httpx`**, not `simfin` PyPI |
| DATA-v2-03 — CoinGecko on-chain | `coingecko-sdk>=1.14.2` (Apache-2.0, ~330 KB) | +0.3 MB | **Add to core deps** — official, async, Stainless-generated |
| DRIFT-v2-04 — Threshold validation | None — extend existing `backtesting/walk_forward.py` + `tracking/tracker.py` | 0 MB | **No new lib** — new utility module `engine/drift_validator.py` |

Total new install footprint: **~0.3 MB** (well under 50 MB threshold). No `[optional-extras]` needed.

**Key NOT-recommendations:**
- ❌ `simfin` PyPI SDK — last release 2024-04-03, project marked Inactive by Snyk, predates SimFin v3 API redesign
- ❌ `pycoingecko` (community wrapper) — not async, official `coingecko-sdk` superseded it Nov 2024
- ❌ `netcal` / `ReliabilityDiagram` PyPI packages — sklearn's `calibration_curve` is a single function call; pulling another lib for one binning operation is overkill
- ❌ Migration to ApexCharts / Chart.js for reliability plot — Recharts `ScatterChart` + reference line covers the diagonal-vs-curve plot natively (Phase 4 already chose Recharts; Recharts handles scatter+line)

---

## Recommended Stack

### Core Technologies (additions to `pyproject.toml [project] dependencies`)

| Technology | Version | Purpose | Why Recommended |
|---|---|---|---|
| `scikit-learn` | `>=1.4,<2.0` | `calibration_curve()` for reliability plot binning + `brier_score_loss` (cross-check against existing custom impl) | Already transitively installed (1.6.1 verified via `pip show`); promoting to direct dep makes the contract explicit and pins minimum required for `pos_label` kwarg (added in 1.1) and stable `strategy='quantile'` semantics. License BSD-3-Clause (compatible). Latest stable 1.8.0 (per scikit-learn.org). |
| `coingecko-sdk` | `>=1.14.2,<2.0` | Official CoinGecko REST client for `/coins/{id}` developer_data + community_data + `/coins/{id}/market_chart` for CryptoAgent network signals | Apache-2.0; native httpx (matches our async pattern); type-safe (Stainless-generated); supports `x-cg-demo-api-key` header authentication; install size 330 KB wheel. Released 2026-04-21 (within last 6 days, actively maintained). Supersedes the unmaintained `pycoingecko` community wrapper. |

### Indirect / promotion-only (no new install, just direct-dep declaration)

| Technology | Version | Purpose | Why Promote |
|---|---|---|---|
| `numpy` | `>=1.26,<3.0` | Reliability plot bin edges + drift validator percentile calcs (already used everywhere) | Currently transitively installed (2.2.6 verified). Promoting to direct dep prevents quantstats-driven version drift and makes the `np.histogram` / `np.percentile` contract explicit. License BSD-3-Clause. |
| `scipy` | `>=1.10,<2.0` | `pearsonr` already used in `tracking/tracker.py:389`; drift validator will add `wilcoxon` for paired threshold significance | Currently transitively installed (1.15.3 verified) and lazy-imported in `tracking/tracker.py`. Promoting makes the explicit contract that we depend on it directly (drift-threshold validation needs paired hypothesis tests). License BSD-3-Clause. |

### Supporting Libraries (no new installs — REUSE existing)

| Library | Version (existing) | Purpose | Integration Point |
|---|---|---|---|
| `httpx` | `>=0.27` | Async REST client for SimFin v3 API (`https://prod.simfin.com` / `/api/v3/companies/statements`) | Matches `data_providers/finnhub_provider.py` pattern (lines 79-90); same default_params auth approach; same `AsyncRateLimiter` decoration. **Build `data_providers/simfin_provider.py` as a thin httpx-only client — DO NOT install the abandoned `simfin` PyPI SDK.** |
| `pyarrow` | `>=14.0` | Parquet disk cache for SimFin statements (24h TTL — fundamentals don't change intraday) | Reuse `data_providers/parquet_cache.py::ParquetOHLCVCache` pattern (lines 34-128). New file `data_providers/simfin_cache.py` keyed `(ticker, statement_type, period, fyear)` matching FOUND-02 sibling pattern (`data_providers/dividend_cache.py` already exists at 87-145 of yfinance_provider.py). |
| `recharts` | `^2.13.0` | `ScatterChart` + `ReferenceLine` for reliability plot (predicted prob × realized win rate, with diagonal y=x reference) | Already in `frontend/package.json:18`. Already used in `ICSparkline.tsx`, `EquityCurveChart.tsx`, `LessonAnalytics.tsx`, `RegimeTimeline.tsx`, `BacktestComparison.tsx`. **Add new component `frontend/src/components/calibration/ReliabilityPlot.tsx` reusing the existing chart-color palette in `frontend/tailwind.config.ts`.** |
| `aiosqlite` | `>=0.19` | Drift validator persistence — extend existing `drift_log` table with new columns OR add `drift_threshold_validation` table | Already core. New migration in `db/database.py` adds either `validation_run_at`, `wilcoxon_p_value`, `n_samples_used` columns to `drift_log` OR a separate one-row-per-validation-run table. |

### Development Tools (no changes)

| Tool | Purpose | Notes |
|---|---|---|
| `pytest>=8.0` | Backend tests for new providers + reliability binning | Already in `[dev]` extra. Use existing `network` marker for live SimFin/CoinGecko round-trips (skipped in CI). |
| `vitest>=2.1.8` | Frontend tests for `ReliabilityPlot.tsx` | Already configured. Use the existing snapshot pattern (mirroring `ICSparkline.test.tsx` / `WeightsEditor.test.tsx` from v1.1 Phase 6). |

---

## Per-Capability Detailed Rationale

### SIG-v2-01: Calibration Reliability Plots

**Question:** Custom binning vs `scikit-learn.calibration_curve()` vs PyPI `netcal` / `ReliabilityDiagram` packages?

**Recommendation:** **`sklearn.calibration.calibration_curve`** + **Recharts `ScatterChart`** for the frontend. No new PyPI/npm installs.

**Rationale:**
1. **scikit-learn is already installed** (1.6.1 verified via `pip show`, transitively via `quantstats>=0.0.81 → numpy → ...`). Pinning it as a direct dep `>=1.4` (a) makes the contract explicit, (b) ensures the `pos_label` kwarg is available (added 1.1), (c) ensures `strategy='quantile'` is stable.
2. **`calibration_curve(y_true, y_prob, n_bins=10, strategy='quantile')`** is a 1-line replacement for the existing custom binning in `tracking/tracker.py::compute_calibration_data` (lines 96-135). Quantile binning prevents empty/sparse bins — important because our corpus is small (`MIN_SAMPLES_FOR_REAL_THRESHOLD=60` in `engine/drift_detector.py:32`).
3. **NOT `netcal`** (~5 MB wheel + scipy/sklearn/torch optional deps; over-engineered — netcal is for ML calibration research, we just need binning).
4. **NOT `ReliabilityDiagram`** PyPI package — last release 2020, abandoned, and trivially superseded by `calibration_curve`.
5. **Frontend: stay on Recharts** — `ScatterChart` + `ReferenceLine` (with `segment` prop for the y=x diagonal) covers the standard reliability-plot visual in ~80 LOC. Phase 4 ROADMAP decision (`.planning/PROJECT.md` line 172) already locked Recharts for analytics.

**Integration points:**
- Backend: extend `tracking/tracker.py::compute_calibration_data` (lines 96-135) to optionally return reliability-plot bins (delegated to `sklearn.calibration.calibration_curve` when `n_bins>=5`); add new endpoint `GET /api/v1/analytics/calibration/reliability?agent_name=...&horizon=5d` in `api/routes/analytics.py`.
- Frontend: new component `frontend/src/components/calibration/ReliabilityPlot.tsx` (sibling to `ICSparkline.tsx`); wire into `frontend/src/pages/CalibrationPage.tsx` next to the `CalibrationTable` (around line 17 of CalibrationPage.tsx).
- DB: NO schema change — bin computation is on-the-fly from `backtest_signal_history`.

**Cross-check:** Existing `compute_brier_score` in `tracking/tracker.py:320-350` already implements one-vs-rest Brier from scratch. v1.2 reliability-plot work should NOT migrate that to `sklearn.brier_score_loss` (would invalidate existing test fixtures); only the binning logic delegates to sklearn.

---

### DATA-v2-02: SimFin Point-in-Time Fundamentals

**Question:** `simfin` PyPI SDK vs raw httpx? ToS, free-tier limits, attribution?

**Recommendation:** **Raw `httpx` client (NEW file `data_providers/simfin_provider.py`).** Do NOT install the `simfin` PyPI SDK.

**Rationale (SDK rejection):**
1. **`simfin` PyPI SDK is abandoned.** Latest release **1.0.1 on 2024-04-03** (PyPI verified). [Snyk](https://snyk.io/advisor/python/simfin) explicitly classifies it as **Inactive** ("hasn't seen any new versions released to PyPI in the past 12 months, could be considered as a discontinued project"). The SDK predates SimFin's January 2024 backend migration to `https://prod.simfin.com` and the v3 REST API redesign documented at [simfin.com/en/technical-updates-to-api-v3-and-bulk-download](https://www.simfin.com/en/technical-updates-to-api-v3-and-bulk-download/).
2. **The SDK targets bulk-CSV downloads, not REST.** It downloads multi-GB datasets to local disk (good for academic research, bad for our 5-10 ticker per-position lookups where we need targeted as-reported quarter fetches).
3. **A 50-LOC httpx client is sufficient.** SimFin v3 REST is `GET https://prod.simfin.com/api/v3/companies/statements?ticker=AAPL&statement=pl&period=q1&fyear=2024&api-key=...` returning JSON. We already do this exact pattern in `data_providers/finnhub_provider.py:79-90`.

**SimFin Free Tier Constraints (verified via [simfin.com/en/prices/](https://www.simfin.com/en/prices/) and [SimFin support docs](https://www.simfin.com/en/blog/find-good-fundamental-data/)):**
- **Rate limit:** 2 calls/sec (Web-API) — 120/min — well within our existing `AsyncRateLimiter` capability
- **Coverage:** 5,000 US stocks; 5 years of fundamentals history; bulk download "delayed" (12 months) on free tier
- **Quota:** 500 high-speed credits/month — sufficient for solo-operator 5-10 positions × quarterly = 40 calls/quarter
- **Point-in-time:** SimFin sources from SEC XBRL filings; **as-reported** (not restated). The point-in-time guarantee comes from the *filing date* being preserved in the response — your code must filter by filing-date ≤ analysis-date to avoid look-ahead. **The free tier delay (~12 months) is actually FINE for our `backtest_mode=False` use** because backtests already use `backtest_mode=True` with cached fundamentals (FOUND-04 contract); SimFin closes the gap for *live* fundamentals where YFinance currently returns restated values silently.
- **Attribution:** SimFin ToS requires data not be redistributed; no on-screen attribution required for solo-operator use (verified against SimFin support FAQ — "use the data as long as you hold a valid subscription"). License: SDK MIT; *data redistribution prohibited*.

**Integration points:**
- New file: `data_providers/simfin_provider.py` — shape mirrors `finnhub_provider.py` (httpx.AsyncClient + AsyncRateLimiter class-level instance + lazy api_key warning).
- New file: `data_providers/simfin_cache.py` — Parquet disk cache, 24h TTL (fundamentals don't change intraday), key = `(ticker, statement_type, period, fyear)`. Mirrors `data_providers/dividend_cache.py:87-145` shape.
- Wire-in: `agents/fundamental.py` — when `agent_input.backtest_mode is False` AND `SIMFIN_API_KEY` is set, prefer SimFin over `YFinanceProvider.get_financials`. When key absent, log a warning and fall through to YFinance (graceful degradation, matches `MacroAgent` pattern for missing FRED_API_KEY).
- Config: `pyproject.toml` — NO new dep (httpx already pinned). `.env.example` — add `SIMFIN_API_KEY=` line with link to free signup.

**What NOT to do:** Do NOT use `simfin.load_income()` / `simfin.load_balance()` bulk APIs. Those download 200 MB+ Parquet datasets to `~/simfin_data/` per run. Wrong shape for our per-position async-await architecture.

---

### DATA-v2-03: CoinGecko On-Chain Provider

**Question:** `coingecko-sdk` (official) vs `pycoingecko` (community) vs raw httpx? Free-tier limits?

**Recommendation:** **`coingecko-sdk>=1.14.2,<2.0` as a core dep.**

**Rationale:**
1. **`coingecko-sdk` is the official, actively-maintained SDK.** Latest release **1.14.2 on 2026-04-21** (6 days old as of 2026-04-27). License Apache-2.0. Wheel size 330 KB. Generated by Stainless (CoinGecko's chosen SDK platform — see [github.com/coingecko/coingecko-python](https://github.com/coingecko/coingecko-python)).
2. **Native httpx, native async.** Direct match with our `httpx>=0.27` core dep — uses `AsyncCoingecko(...)` client that returns awaitables. No thread-pool wrappers needed (unlike yfinance).
3. **Native Demo API support.** The SDK accepts `demo_api_key=...` and `environment="demo"` constructor kwargs; SDK internally sets the `x-cg-demo-api-key` header (per CoinGecko docs at [docs.coingecko.com/v3.0.1/reference/authentication](https://docs.coingecko.com/v3.0.1/reference/authentication)).
4. **NOT `pycoingecko`** — community wrapper, sync-only (uses `requests`), supports demo key but lags official feature parity. Still maintained (3.2.0 on 2024-11-13) but the official SDK now exists.
5. **NOT raw httpx** — coingecko-sdk gives us type-safe response models (`CoinGet200Response`, `CoinDeveloperData`, `CoinCommunityData`) for free; rolling our own is busywork.

**CoinGecko Free Tier Constraints (verified via [docs.coingecko.com/docs/common-errors-rate-limit](https://docs.coingecko.com/docs/common-errors-rate-limit) and [coingecko.com/en/api/pricing](https://www.coingecko.com/en/api/pricing)):**
- **Demo API:** 30 calls/min (NOT 50 as the question hypothesized — the public unkeyed limit is 5-15/min and the Demo limit with API key is **30/min**)
- **Monthly quota:** 10,000 calls/month (sufficient for daily refresh × 50 cryptos)
- **Attribution:** REQUIRED — must "prominently display 'Data provided by CoinGecko' with a hyperlink" per ToS. **This means a one-line credit in the frontend `Footer` component or `CryptoAgent` reasoning text.**
- **Redistribution:** Prohibited — "cannot sell, rent, lease, sub-license, re-distribute or syndicate access to the CoinGecko API" — fine for solo-operator local-first use
- **Endpoints we'll use:** `/coins/{id}` returns `developer_data` (forks, stars, subscribers, commit_count_4_weeks, pull_requests_merged, contributors) AND `community_data` (telegram_channel_user_count, reddit_subscribers — Twitter discontinued per CoinGecko 2024 notice)
- **NOT Pro-only:** Developer activity + community metrics are on Demo tier (verified 2026-04-27 in coins-id reference)

**Integration points:**
- New file: `data_providers/coingecko_provider.py` — class `CoinGeckoProvider(DataProvider)`. Class-level `AsyncRateLimiter(max_calls=30, period_seconds=60.0)` matching the Demo limit (configurable via `COINGECKO_RATE_LIMIT` env var, mirroring `FinnhubProvider._limiter` pattern at `data_providers/finnhub_provider.py:61-64`).
- TTL cache: 24h for `developer_data` + `community_data` (slow-moving — daily refresh is plenty). Reuse in-memory `TTLCache` from `data_providers/cache.py` via `CachedProvider` wrapper, NOT Parquet (these are small JSON blobs, not OHLCV).
- Wire-in: `agents/crypto.py` — new factor in factor weights (`network_health` — currently `network_adoption` placeholder at line 50). Composite of (a) commit_count_4_weeks z-score vs trailing-90d, (b) reddit_subscribers MoM growth, (c) telegram_channel_user_count MoM growth. Add to `_DEFAULT_ADOPTION` dict so backtest_mode falls back gracefully.
- Config: `pyproject.toml` — add `coingecko-sdk>=1.14.2,<2.0` to core `[project] dependencies`. `.env.example` — add `COINGECKO_DEMO_API_KEY=` line.
- Frontend: footer attribution `<p>On-chain data provided by <a href="https://coingecko.com">CoinGecko</a></p>` in `frontend/src/components/layout/Footer.tsx` (or wherever existing Finnhub attribution lives).

**Caveat:** CoinGecko's `community_data` does NOT include Twitter follower counts since 2024 (confirmed in API docs). Reddit + Telegram are the only social signals available on Demo. This is OK — those are the higher-signal datapoints for crypto research anyway.

---

### DRIFT-v2-04: Drift-Threshold Validation Methodology

**Question:** Use existing `backtesting/walk_forward.py` + `corpus_rebuild_jobs` table or build a new utility?

**Recommendation:** **NEW utility `engine/drift_validator.py` extending existing infra.** Zero new dependencies.

**Rationale:**
1. **The thresholds in `engine/drift_detector.py:30-32` (`DRIFT_THRESHOLD_PCT=20.0`, `ICIR_FLOOR=0.5`) lack empirical backing.** Per `.planning/PROJECT.md` Key Decisions row 25 ("v1.1 Phase 7 drift-detector thresholds shipped as `preliminary_threshold` until 60+ weekly IC samples accumulate"), these were defensible defaults but not validated against the live corpus.
2. **The required validation is statistical, not architectural.** Given the corpus already exists (`backtest_signal_history` table — FOUND-04 + SIG-05) and IC-IR is computed via `tracking/tracker.py::compute_rolling_ic` (lines 356-424), the missing piece is a *retrospective grid search* over `(threshold_drop_pct, icir_floor)` ∈ {15, 20, 25, 30} × {0.3, 0.4, 0.5, 0.6} measuring (a) precision (% of trigger weeks followed by ≥10% IC-IR decline next 4 weeks) and (b) recall (% of decline weeks correctly flagged).
3. **`scipy.stats.wilcoxon`** (already lazy-imported via `scipy>=1.10`) gives us paired-sample significance testing for "is the IC-IR delta after a triggered week statistically lower than after a non-triggered week."
4. **Reuse `backtesting/walk_forward.py::generate_walk_forward_windows`** (lines 51-100) — its (train_end, oos_start) gap with `purge_days=5` is exactly the no-leakage boundary the drift validator needs.
5. **NOT a separate library** — `statsmodels` would add ~30 MB for `wilcoxon` we already have in scipy; `pingouin` is overkill.

**Integration points:**
- New file: `engine/drift_validator.py` — function `validate_drift_thresholds(db_path, candidate_grid: list[tuple[float, float]]) -> ValidationReport` returning per-(drop_pct, floor) precision/recall/Wilcoxon-p-value.
- Existing: imports `tracking.tracker.SignalTracker.compute_rolling_ic` directly; queries `backtest_signal_history` via `tracking.store.SignalStore`.
- DB: ALTER TABLE `drift_log` ADD COLUMN `validation_run_at` TEXT NULL (records the validation run that promoted this threshold). Migration in `db/database.py` mirroring the existing portfolio/agent_weights pattern.
- New endpoint: `POST /api/v1/drift/validate-thresholds` (long-running, returns 202 + job_id, consumes the `corpus_rebuild_jobs` async-job pattern from `api/routes/analytics.py::rebuild_corpus`).
- Frontend: extend `DriftBadge.tsx` (existing — `frontend/src/components/calibration/DriftBadge.tsx`) with a 4th state — `validated` (green badge replacing the amber `preliminary` once `validation_run_at` is non-null).
- The existing `corpus_rebuild_jobs` table can be **reused as-is** — same async-job semantics work for validation runs.

**What NOT to do:** Do NOT add `mlflow` or `optuna` for hyperparameter logging — the candidate grid is 16 points, exhaustive sweep takes seconds; logging to a JSON file under `data/drift_validation/runs/{timestamp}.json` is sufficient.

---

## Alternatives Considered (and Rejected)

### Reliability plot tooling

| Considered | Why Rejected |
|---|---|
| `netcal` (PyPI 1.3.0) | ~5 MB + transformers/torch optional deps; designed for ML model calibration research, not single-binning use case |
| `ReliabilityDiagram` (PyPI 0.0.6) | Last release 2020-12; abandoned; `calibration_curve` does the same thing in 1 sklearn function |
| Apple `relplot` (`apple/ml-calibration`) | Not on PyPI as of 2026-04; would require git+ install; uses kernel smoothing (overkill for ~60-sample corpus) |
| Custom binning in pandas | Already implemented in `tracking/tracker.py:96-135` for `compute_calibration_data`; sklearn is more battle-tested for the new reliability-plot endpoint |
| Migrate frontend to ApexCharts / Chart.js | Would invalidate ~600 lines of existing Recharts test fixtures (Phase 4 decision row 12 — `.planning/PROJECT.md`); Recharts ScatterChart + ReferenceLine handles diagonal-vs-curve adequately |

### SimFin clients

| Considered | Why Rejected |
|---|---|
| `simfin` PyPI SDK 1.0.1 | Last release 2024-04-03; Snyk classifies as Inactive; predates SimFin v3 API; bulk-download model wrong shape for per-position async lookups |
| `simfin-python` PyPI | Not the official package (third-party); adds dependency without value over httpx |
| `dlt-simfin` (dltHub) | ETL pipeline framework — wrong abstraction level; ~20 MB + sqlalchemy + duckdb deps |
| `pandas-datareader` | Doesn't support SimFin; would only help for FRED (already using `fredapi`) |

### CoinGecko clients

| Considered | Why Rejected |
|---|---|
| `pycoingecko` 3.2.0 | Sync-only (uses `requests`, not httpx); community wrapper supplanted by official SDK Nov 2024 |
| `coingecko-api` PyPI | Third-party; minimal coverage of `/coins/{id}` developer_data + community_data fields |
| `pycgapi` | Unofficial wrapper; less maintained than official SDK |
| `pycoingeckoasync` | Async port of pycoingecko; superseded by official `coingecko-sdk` async client |
| Raw httpx | Loses type safety; have to maintain JSON-shape contracts manually; 330 KB SDK saves ~200 LOC |

### Drift validator

| Considered | Why Rejected |
|---|---|
| `mlflow` | ~50 MB + S3/sklearn deps; overkill for 16-point candidate grid |
| `optuna` | ~10 MB; designed for Bayesian optimization (we want exhaustive grid for explainability) |
| `statsmodels` `wilcoxon` | ~30 MB; scipy.stats.wilcoxon already available |
| `pingouin` | ~5 MB; nice but redundant given scipy |

---

## Installation

```bash
# Backend — promote two transitive deps to direct + add CoinGecko SDK
pip install -e ".[dev]"  # already-installed, just for posterity

# After pyproject.toml edit:
# dependencies = [
#   ...existing...,
#   "scikit-learn>=1.4,<2.0",       # SIG-v2-01 reliability plot binning
#   "numpy>=1.26,<3.0",             # promote (was transitive)
#   "scipy>=1.10,<2.0",             # promote (was transitive — used in tracker.py:389)
#   "coingecko-sdk>=1.14.2,<2.0",   # DATA-v2-03 official CoinGecko client
# ]

pip install -e .

# Frontend — NO new deps; recharts already pinned at ^2.13.0
# (frontend/package.json line 18 unchanged)

# Environment — new optional API keys (all graceful-degrade if absent)
echo "SIMFIN_API_KEY=" >> .env.example
echo "COINGECKO_DEMO_API_KEY=" >> .env.example
echo "COINGECKO_RATE_LIMIT=30" >> .env.example
echo "SIMFIN_RATE_LIMIT=120" >> .env.example  # 2/sec
```

**Default-install impact:** **+0.3 MB** (coingecko-sdk wheel). scikit-learn / numpy / scipy promotions are 0 MB net (already transitively installed). **No `[optional-extras]` needed** — well under the 50 MB threshold.

---

## License Summary (all new + promoted deps)

| Library | License | Compatibility | Notes |
|---|---|---|---|
| `scikit-learn` | BSD-3-Clause | ✓ MIT-compatible | Already transitively installed |
| `numpy` | BSD-3-Clause | ✓ MIT-compatible | Already transitively installed |
| `scipy` | BSD-3-Clause | ✓ MIT-compatible | Already transitively installed; lazy-imported |
| `coingecko-sdk` | Apache-2.0 | ✓ MIT-compatible | New core dep, ~330 KB |
| SimFin DATA license | Proprietary (vendor ToS) | ⚠ Data redistribution prohibited | We don't redistribute — local-first solo-operator only |
| CoinGecko DATA license | Proprietary (vendor ToS) | ⚠ Attribution required + no redistribution | Add credit line in frontend Footer |

**No GPL/AGPL libraries introduced.** All BSD/MIT/Apache. Vendor data ToS (SimFin + CoinGecko) constrains redistribution but matches our local-first solo-operator constraint.

---

## What NOT to Add (anti-recommendations)

1. **`simfin` PyPI SDK** — abandoned April 2024, predates the v3 API redesign. Build a 50-LOC httpx client instead.
2. **`pycoingecko`** — sync-only community wrapper, superseded by official `coingecko-sdk` Nov 2024.
3. **`netcal`, `ReliabilityDiagram`, `relplot`** — over-engineered for a single-binning operation; sklearn's `calibration_curve` is 1 line.
4. **`mlflow`, `optuna`, `statsmodels`** — ~30-50 MB each for capabilities scipy already covers.
5. **Frontend chart-lib migration (ApexCharts / Chart.js / Plotly.js)** — Recharts ScatterChart + ReferenceLine handles reliability plots; Phase 4 already locked Recharts.
6. **`pandas-datareader`** — doesn't support SimFin; would only help for FRED (which we already cover via `fredapi>=0.5`).
7. **`yfinance` for fundamentals as point-in-time** — yfinance silently returns the *latest* restated values (this is the bug DATA-v2-02 exists to fix). Don't paper over it with caching alone.
8. **`requests` library** — we're async-first via httpx; do NOT introduce sync `requests` even for the SimFin client (would block the event loop on slow SimFin responses).

---

## Sources & Confidence

| Claim | Source | Confidence |
|---|---|---|
| `simfin` PyPI 1.0.1 last release 2024-04-03 | [PyPI simfin page](https://pypi.org/project/simfin/) verified 2026-04-27 | HIGH |
| `simfin` Snyk Inactive status | [Snyk advisor for simfin](https://snyk.io/advisor/python/simfin) | HIGH |
| SimFin v3 base URL `https://prod.simfin.com` | [SimFin January 2024 update blog](https://www.simfin.com/en/blog/major-simfin-update/) | HIGH |
| SimFin free-tier limits (2/sec, 5K stocks, 5y history, 500 credits/mo) | [simfin.com/en/prices](https://www.simfin.com/en/prices/) verified 2026-04-27 | HIGH |
| `coingecko-sdk` 1.14.2 released 2026-04-21, Apache-2.0 | [PyPI coingecko-sdk](https://pypi.org/project/coingecko-sdk/) verified 2026-04-27 | HIGH |
| `coingecko-sdk` async via httpx, supports Demo header auth | [github.com/coingecko/coingecko-python README](https://github.com/coingecko/coingecko-python) | HIGH |
| CoinGecko Demo: 30 calls/min, 10K/month, attribution required | [docs.coingecko.com/docs/common-errors-rate-limit](https://docs.coingecko.com/docs/common-errors-rate-limit) + [coingecko.com/en/api/pricing](https://www.coingecko.com/en/api/pricing) verified 2026-04-27 | HIGH |
| CoinGecko `/coins/{id}` includes developer_data + community_data on Demo tier | [docs.coingecko.com/v3.0.1/reference/coins-id](https://docs.coingecko.com/v3.0.1/reference/coins-id) verified 2026-04-27 | HIGH |
| sklearn.calibration.calibration_curve API (n_bins, strategy, pos_label) | [scikit-learn.org calibration_curve docs](https://scikit-learn.org/stable/modules/generated/sklearn.calibration.calibration_curve.html) | HIGH |
| sklearn 1.6.1 already installed transitively | `pip show scikit-learn` on 2026-04-27 | HIGH |
| scipy 1.15.3 / numpy 2.2.6 already installed | `pip show` on 2026-04-27 | HIGH |
| Recharts ScatterChart + ReferenceLine support | [recharts.github.io examples](https://recharts.github.io/en-US/examples/) | HIGH |
| `pycoingecko` 3.2.0 released 2024-11-13, sync-only | [PyPI pycoingecko](https://pypi.org/project/pycoingecko/) | HIGH |
| SimFin uses SEC XBRL filings (preserves filing date for PIT lookup) | [SimFin "Why is fundamental data hard" blog](https://www.simfin.com/en/blog/find-good-fundamental-data/) + [SimFin Medium API tutorial](https://simfin-official.medium.com/aggregating-financial-data-from-around-the-world-b9bffc7b463) | MEDIUM (vendor source — claims "as-reported" but free tier is 12-month delayed which complicates "real-time PIT") |

---

## Roadmap Implications

**Suggested phase ordering for v1.2 (informs gsd-roadmapper):**

1. **Phase 1 — Reliability plots (SIG-v2-01)** — pure additive, no new external API surface, smallest risk. Validates the calibration-page UX and surfaces empirical predicted-vs-realized gaps that motivate Phases 2-3.
2. **Phase 2 — SimFin point-in-time (DATA-v2-02)** — provider + cache + fundamental-agent wiring. Independent of CoinGecko. Blocks nothing else but unlocks fundamental signal trustworthiness.
3. **Phase 3 — CoinGecko on-chain (DATA-v2-03)** — provider + crypto-agent wiring + frontend attribution. Independent of Phase 2.
4. **Phase 4 — Drift-threshold validation (DRIFT-v2-04)** — REQUIRES Phases 1-3 to have run for at least the corpus duration so reliability plots reveal genuine drift signal. The validator promotes thresholds out of `preliminary_threshold` ONLY after Phases 1-3 have populated enough corpus rows.

**Phase ordering rationale:** Phases 1-3 are independent and can be parallelized if multi-track development resumes. Phase 4 is a synthesis phase that *closes* v1.1's deferred preliminary_threshold flag using empirical data from Phases 1-3.

**Research flags for downstream phases (gsd-roadmapper input):**
- Phase 2 (SimFin): needs phase-specific research on **filing-date filtering logic** — SimFin's `filed_at` field semantics + edge cases for amended 10-Q filings (10-Q/A) which carry the original filing date but differ in content
- Phase 3 (CoinGecko): needs phase-specific research on **CryptoAgent factor weights** — specifically how to z-score `commit_count_4_weeks` against asset-specific baselines (BTC vs ETH vs altcoins have very different commit rhythms)
- Phase 4 (Drift validator): needs phase-specific research on **multi-comparison correction** — 16-point grid search risks p-hacking; Bonferroni or FDR correction needed for Wilcoxon-derived thresholds
