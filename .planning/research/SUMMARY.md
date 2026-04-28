# Project Research Summary — v1.2 Trustworthy Signals

**Project:** Investment Agent (subsequent / brownfield milestone)
**Domain:** Personal multi-agent investment journal — calibration validation, point-in-time fundamentals, on-chain crypto signals, drift-threshold validation
**Researched:** 2026-04-27
**Confidence:** HIGH (all 4 researchers cross-checked against live code paths, vendor docs, and PyPI release dates verified 2026-04-27)
**Supersedes:** v1.0 SUMMARY.md (2026-04-21 competitive benchmarking) — that synthesis informed v1.0/v1.1 and is now archived

---

## Executive Summary

v1.2 adds 4 capabilities to a mature brownfield system (889 tests, 15 frontend pages, two shipped milestones). Three of the four are surgical extensions of existing patterns — a new provider mirroring `data_providers/finnhub_provider.py`, a new metric mirroring `tracking/tracker.py::compute_brier_score`, a new utility mirroring `engine/drift_detector.py`. The fourth — drift-threshold validation — closes v1.1's `preliminary_threshold` carry-forward by shipping the *capability to validate*, not necessarily *validated thresholds* (the live corpus will be ~13 weeks at ship time, below the 60-week floor).

The recommended approach is **three sequential phases ordered to neutralize cross-feature data-contamination risk first**: Phase 8 lands SimFin + Reliability Plots together (both touch FOUND-04 and the `backtest_signal_history` corpus schema, so they share the `fundamentals_provider` column migration), Phase 9 lands CoinGecko (independent dependency-wise, but its crypto-agent rewiring shifts CryptoAgent's IC distribution and must precede drift validation), Phase 10 closes the loop with drift-threshold validation methodology against a corpus that has been rebuilt under the new providers. Total new install footprint is ~0.3 MB (`coingecko-sdk`); SimFin uses raw httpx (the abandoned PyPI SDK is rejected); reliability plots reuse already-installed sklearn; drift validator reuses already-installed scipy. No frontend chart-lib migration.

The dominant risks are *silent data corruption* rather than implementation difficulty. **FOUND-04 contract bypass** (Pitfall 1) and **provider mixing in `signal_history`/`backtest_signal_history`** (Pitfall 4) are both DATA-CORRUPTION class — they would silently invalidate the calibration corpus that the whole "Trustworthy Signals" narrative rests on. Defensive code patterns (a `fundamentals_provider` schema column landed in the same PR as SimFin, a tripwire regression test on the FOUND-04 backtest_mode short-circuit, an `asyncio.wait_for(10s)` per-agent timeout for CoinGecko's 5-15/min rate limit) are non-negotiable for v1.2 to ship trustworthy. Drift-threshold validation must be **methodologically honest** — out-of-sample time-split, bootstrap CI, and an explicit "remain preliminary" acceptance path if the 60-week corpus floor isn't reached.

---

## Key Findings

### Recommended Stack

See `.planning/research/STACK.md` for full rationale and PyPI verification. Headline: **+0.3 MB total install footprint** for v1.2 — three transitively-installed deps get promoted to direct dependencies (sklearn, numpy, scipy) and one new official SDK is added (`coingecko-sdk`). The abandoned `simfin` PyPI SDK is **rejected** in favor of a 50-LOC httpx client.

**Core technologies (additions / promotions):**

- `scikit-learn>=1.4,<2.0`: SIG-v2-01 reliability plot binning via `sklearn.calibration.calibration_curve()` — already transitively installed (1.6.1 via quantstats); promote to direct dep for explicit contract on `pos_label` kwarg + `strategy='quantile'` semantics. License BSD-3-Clause.
- `coingecko-sdk>=1.14.2,<2.0`: DATA-v2-03 official async CoinGecko REST client — Apache-2.0, ~330 KB, native httpx, supports `x-cg-demo-api-key` header. Released 2026-04-21. Supersedes the unmaintained `pycoingecko`.
- `httpx>=0.27` (existing): DATA-v2-02 SimFin v3 REST client — pattern already established by `data_providers/finnhub_provider.py:79-90`. **Do NOT install the abandoned `simfin` PyPI SDK** (last release 2024-04-03, Snyk-flagged Inactive, predates SimFin v3 API).
- `scipy>=1.10,<2.0` (promote): DRIFT-v2-04 will add `scipy.stats.wilcoxon` for paired threshold significance testing — already lazy-imported in `tracking/tracker.py:389` for `pearsonr`.
- `recharts^2.13.0` (existing): Reliability plot renders via `<ScatterChart>` + `<ReferenceLine y=x>` + optional `<ErrorBar>` — Phase 4 already locked Recharts; no chart-lib migration.

**Anti-stack (rejected with reason):** `simfin` PyPI SDK (abandoned), `pycoingecko` (sync-only, supplanted), `netcal`/`ReliabilityDiagram` (over-engineered for one binning operation), `mlflow`/`optuna` (~50 MB for capabilities scipy already covers), `statsmodels` (~30 MB for `wilcoxon` scipy.stats already exposes), Apple `relplot` (uses kernel smoothing — overkill for sparse corpus), `pandas-datareader` (doesn't support SimFin).

### Expected Features

See `.planning/research/FEATURES.md` for table-stakes vs. differentiator analysis and OSS competitor patterns. The four v1.2 capabilities resolve to **5 P1 ship-list features** plus deferred extensions.

**Must have (table stakes — all P1, all required for v1.2 milestone goal):**
- Reliability plot per agent on `/calibration` — predicted-confidence vs realized-win-rate ScatterChart with diagonal reference line + sample-size annotations + per-bin Wilson CIs.
- Murphy/Brier decomposition card (REL/RES/UNC) next to the plot — tells the user *why* Brier is 0.18. No OSS competitor offers this.
- SimFin provider + `backtest_mode` opt-in routing — eliminates look-ahead bias from yfinance's restated fundamentals. FOUND-04 contract is *preserved*: SimFin is opt-in via a NEW `use_pit_fundamentals` field on `AgentInput`, not a silent provider swap.
- CoinGecko on-chain provider + CryptoAgent Factor 6 rewiring — replaces static `crypto_adoption.yaml` constants with live `commit_count_4_weeks` + `reddit_subscribers` deltas. No new factor; same 5% weight (rebalancing deferred to v1.3).
- Drift-threshold validation methodology + UI panel — `engine/drift_validator.py` + `drift_thresholds` table + `DriftValidationPanel.tsx` mounted in CalibrationPage. Ships *capability*, not necessarily flipped flag.

**Should have (deferred to v1.3 if user feedback confirms demand):**
- Restated-vs-as-filed delta badge on positions (when `|delta| > 10%`)
- Per-bin trend sparklines on reliability plot (30/60/90d rolling)
- Drift sensitivity heatmap (`(drop_pct × abs_floor)` colored by OOS Sharpe)

**Defer (v2+):**
- Bootstrap CIs replacing Wilson — Wilson is asymptotically equivalent for our N
- Glassnode/CryptoQuant paid integration — free-tier constraint binds
- Auto-tuning drift thresholds with hysteresis — threshold-thrashing risk
- Real-time on-chain refresh — free-tier rate limits

**Anti-features (commonly requested, problematic):**
- Switch *entire* fundamental pipeline to SimFin — single-provider failure surface; ~5y free-tier history. Use **layered routing**.
- Real-time on-chain refresh polling — 30/min Demo limit blown in 4 days at sub-minute polling.
- Auto-tune drift thresholds on every weekly run — threshold thrashing; defeats validation purpose.

### Architecture Approach

See `.planning/research/ARCHITECTURE.md` for full file-path index, integration points, and dependency graph. v1.2 is **brownfield integration into a 6-layer system** (frontend → routes → engine/tracking/portfolio → agents → data_providers → SQLite + APScheduler daemon). All 4 capabilities slot into existing patterns — no new layer is introduced.

**Major components (new + modified):**

1. **`data_providers/simfin_provider.py` (NEW)** — Class `SimfinProvider(DataProvider)` mirroring `FinnhubProvider`: class-level `AsyncRateLimiter(2/sec)`, httpx async client, `params={"api-key": resolved_key}`, lazy-key warning. Sibling `data_providers/simfin_cache.py` (NEW) is a Parquet disk cache mirroring `dividend_cache.py`, 24h TTL. Wired into `agents/fundamental.py` via opt-in `agent_input.use_pit_fundamentals` flag (FOUND-04 short-circuit preserved as default).

2. **`data_providers/coingecko_provider.py` (NEW)** — Class `CoinGeckoProvider(DataProvider)` using `coingecko-sdk` `AsyncCoingecko` client. Class-level `AsyncRateLimiter(30/min)` matching Demo tier. TTL cache (24h). Wired into `agents/crypto.py` Factor 6 — replaces `_score_network_adoption` static path; same 5% weight; static `crypto_adoption.yaml` becomes graceful fallback.

3. **`tracking/tracker.py` extension (MODIFY)** — New methods `compute_reliability_bins(agent, horizon, n_bins, min_bucket_size)` + `compute_ece(...)` + `compute_murphy_decomposition(...)`. All read from existing `backtest_signal_history` corpus. New endpoint shape: `GET /api/v1/analytics/calibration?include_reliability=true` (additive — preserves WARNING 11 stable-key contract). Frontend: NEW `frontend/src/components/calibration/ReliabilityPlot.tsx` (Recharts ScatterChart + ReferenceLine + bubble size = sample count) mounted as expandable drill-down on `AgentCalibrationRow.tsx`.

4. **`engine/drift_validator.py` (NEW)** — Function `validate_drift_thresholds(db_path, candidate_grid)` returning per-`(drop_pct, floor)` precision/recall/Wilcoxon-p-value. Reuses `backtesting/walk_forward.py::generate_walk_forward_windows` (`purge_days=5` for IC-feeding). New `drift_thresholds` table — per-`(asset_type, agent_name)` row with `source` ∈ `{preliminary, validated, manual}`. `engine/drift_detector.py` reads this table at runtime, falling back to hardcoded constants if empty.

5. **`db/database.py` migrations (MODIFY)** — Three idempotent migrations land in this milestone: (a) `signal_history.fundamentals_provider TEXT DEFAULT 'yfinance'`; (b) `backtest_signal_history.fundamentals_provider TEXT DEFAULT 'yfinance'` + index; (c) `drift_log.fundamentals_provider TEXT DEFAULT 'yfinance'` + new `drift_thresholds` table.

6. **`engine/pipeline.py` provider injection (MODIFY)** — When `os.getenv("SIMFIN_FOR_FUNDAMENTALS") == "true"`, inject `SimfinProvider` into `FundamentalAgent.set_pit_provider()`. When `COINGECKO_DEMO_API_KEY` set, inject `CoinGeckoProvider` into `CryptoAgent`. Both with try/except + pipeline_warnings fallback (matches `MacroAgent` pattern for missing FRED key). Plus per-agent `asyncio.wait_for(timeout=10s)` wrapper for CoinGecko.

### Critical Pitfalls

See `.planning/research/PITFALLS.md` for the full 13-pitfall catalog with severity, phase ownership, and recovery costs. Top 5 by severity:

1. **SimFin invoked outside `backtest_mode` bypasses FOUND-04 contract** (DATA-CORRUPTION) — Naive integration would lift the FundamentalAgent `backtest_mode=True` HOLD short-circuit when SimFin is the provider. This breaks `engine/signal_aggregator.py` weight renormalization (FOUND-05's 12-case parametrized test) and contaminates `backtest_signal_history` Brier/IC computations. **Avoid:** Make SimFin opt-in via NEW `agent_input.use_pit_fundamentals: bool = False` field; preserve FOUND-04 default; add tripwire regression test `test_fundamental_agent_backtest_mode_default_unchanged` in initial PR.

2. **Provider mixing in `signal_history`/`backtest_signal_history` without `fundamentals_provider` column** (DATA-CORRUPTION) — Cache key today is `(ticker, date)`, not `(ticker, date, fundamentals_provider)`. After SimFin lands, IC computed against pre-SimFin yfinance rows mixed with post-SimFin SimFin rows is silently wrong. **Avoid:** `fundamentals_provider` column migration MUST land in same PR as SimFin provider, with index on `(ticker, created_at, fundamentals_provider)`. IC and drift queries filter by provider. Force corpus rebuild on first SimFin enable.

3. **CoinGecko free-tier rate limit (5-15/min) blocks `asyncio.gather` for 60s** (LOUD-FAILURE) — `engine/pipeline.py:130` runs all agents in parallel via `asyncio.gather(*all_tasks, return_exceptions=True)` with NO per-agent timeout. CoinGecko's 60s default httpx timeout means a single slow call stalls the entire analyze endpoint. **Avoid:** Wrap CoinGecko-dependent calls with `asyncio.wait_for(timeout=10s)` at pipeline edge; 24h Parquet cache for `developer_data`/`community_data` (ToS-compliant per CoinGecko "must refresh at least every 24 hours"); CryptoAgent `enable_oncoin` flag with graceful price-only fallback.

4. **Reliability plot binning hides miscalibration at current corpus size** (SILENT-FAILURE) — `sklearn.calibration_curve(n_bins=10)` is the canonical tutorial example, but our `backtest_signal_history` corpus is ~10 rows live + ~750 rows synthetic. With 10 bins, each bin has 0-3 samples; plot looks like Swiss cheese; operator concludes "uncalibrated" when really sample-noise dominates. **Avoid:** Adaptive bin count `_adaptive_bin_count(n_samples, min_per_bin=10, max_bins=10)`. Plumb `preliminary_calibration: true` flag through reliability endpoint (mirrors Phase 2 pattern). Frontend renders amber banner when flag set.

5. **Drift-threshold validation data-snoops the corpus it tests against** (SILENT-FAILURE) — Natural research workflow ("tune `>20%` to match drift events that already happened in the corpus") IS data-snooping. With ~13 weeks of `drift_log` at v1.2 ship vs `MIN_SAMPLES_FOR_REAL_THRESHOLD=60`, even ignoring snoop the sample size doesn't support promotion. **Avoid:** (a) Out-of-sample time-split (train through 2024-06-30, validate 2024-07-01+); (b) Bootstrap 95% CI on threshold; (c) Tripwire test `test_preliminary_threshold_promotion_requires_evidence` that fails until validation set documented; (d) Honest "remain preliminary" acceptance path documented as Key Decision in PROJECT.md.

**Cross-feature pitfalls (multi-feature interaction — these only emerge under combined deployment):**

- **Cross-1 (SimFin + Drift Detector)**: Drift detector's `_get_avg_icir_60d` baseline shifts when SimFin lands — FALSE drift alert. Owned by Phase 8.
- **Cross-2 (CoinGecko + Drift Detector)**: New on-chain inputs shift CryptoAgent IC distribution; thresholds tuned on old distribution misfire. Owned by Phase 9 (reset `(CryptoAgent, btc/eth)` `preliminary_threshold = True` regardless of sample count).
- **Cross-3 (Reliability Plot + CoinGecko + SimFin)**: Reliability plot computed against corpus mixing pre- and post-v1.2 signals looks badly miscalibrated. Owned by Phase 10 (corpus rebuild MANDATORY before plot interpretation).
- **Cross-4 (Drift validation + corpus rebuild ordering)**: If validation runs on half-rebuilt corpus, results are garbage. Phase 10 prerequisite check fails fast if corpus rebuild post-dates SimFin/CoinGecko feature flags.

---

## Implications for Roadmap

The 4 researchers diverged on phase count: ARCHITECTURE.md proposed 4 phases, FEATURES.md and STACK.md proposed 3 phases (with reliability plots first), PITFALLS.md proposed 3 phases (with SimFin + reliability plots bundled first). User's stated scope is "tight (~3 phases / ~12 reqs)". **Recommendation: 3 phases adopting PITFALLS.md ordering**, because cross-feature data-corruption pitfalls (Cross-1 SimFin+drift baseline; Cross-3 reliability-plot mixed corpus) make sequential ordering more important than separation-of-concerns.

**Trade-off documented:** PITFALLS' bundling of SimFin + Reliability Plots into Phase 8 is the *defensive* choice — both features touch FOUND-04 and require the `fundamentals_provider` schema column, so landing them together avoids a migration-then-feature interleave. ARCHITECTURE's separated 4-phase ordering is *cleaner conceptually* but exceeds user scope and creates a Phase 8.5 problem (where does the schema migration land if SimFin and reliability plots ship in different phases?). The bundled approach is recommended.

### Phase 1 (Phase 8 in milestone-cumulative numbering) — SimFin + Reliability Plots

**Rationale:** These two features share schema-migration risk (the new `fundamentals_provider` column on `signal_history`/`backtest_signal_history`/`drift_log`) and both touch the FOUND-04 contract surface. Landing them together avoids the migration-then-feature interleave and lets the same PR carry: (a) schema migration, (b) `fundamentals_provider` filter on IC/drift queries, (c) FOUND-04 tripwire test, (d) corpus-rebuild-on-first-SimFin-enable, (e) reliability bin computation against the now-provider-aware corpus.

**Delivers:**
- `data_providers/simfin_provider.py` + `data_providers/simfin_cache.py` (Parquet, 24h TTL)
- `agent_input.use_pit_fundamentals: bool = False` field on `AgentInput`
- FOUND-04 contract preserved: `if backtest_mode and not use_pit_fundamentals → HOLD/completeness=0.0` (default unchanged)
- `tracking/tracker.py::compute_reliability_bins` + `compute_ece` + `compute_murphy_decomposition` (REL/RES/UNC)
- `GET /api/v1/analytics/calibration?include_reliability=true` extension (additive, preserves stable-key contract)
- `frontend/src/components/calibration/ReliabilityPlot.tsx` + `MurphyDecompositionCard.tsx`
- DB migrations: `fundamentals_provider TEXT DEFAULT 'yfinance'` on 3 tables + index
- Tripwire tests: `test_fundamental_agent_backtest_mode_default_unchanged`, `test_simfin_provider_no_silent_yfinance_fallback`, `test_adaptive_bin_count`

**Addresses (FEATURES.md):** SimFin provider P1 (table stake), Reliability plot P1 (table stake), Murphy decomposition P1 (differentiator)
**Uses (STACK.md):** `httpx>=0.27` (SimFin client), `scikit-learn>=1.4` promotion, `recharts` (existing)
**Implements (ARCHITECTURE.md):** SimfinProvider mirroring FinnhubProvider; tracker extension owning new methods alongside existing Brier/IC/IC-IR; ReliabilityPlot as expandable drill-down (not new column)
**Avoids (PITFALLS.md):** Pitfalls 1, 2, 4, 7, 8, 9, 10, 12, 13

**Estimated reqs:** 4-5

### Phase 2 (Phase 9) — CoinGecko On-Chain Provider

**Rationale:** Independent of Phase 8 dependency-wise — separate providers, separate agent. Comes second because (a) it's the smallest scope, (b) its CryptoAgent rewiring shifts the IC distribution that Phase 10's drift validation will measure against (Cross-2 pitfall), (c) its rate-limit timeout pattern (`asyncio.wait_for(10s)`) is a reusable defensive primitive.

**Delivers:**
- `data_providers/coingecko_provider.py` using `coingecko-sdk` `AsyncCoingecko` + class-level `AsyncRateLimiter(30/min)` matching Demo tier
- 24h TTL cache for `developer_data` + `community_data` (ToS-compliant)
- `agents/crypto.py` Factor 6 rewired with live composite of `commit_count_4_weeks` z-score + `reddit_subscribers` MoM growth + `telegram_channel_user_count` MoM growth. Same 5% weight; `config/crypto_adoption.yaml` becomes graceful fallback.
- `engine/pipeline.py` per-agent timeout wrapper `asyncio.wait_for(timeout=10s)`
- CryptoAgent `enable_oncoin` constructor flag with graceful price-only fallback
- "Powered by CoinGecko" attribution footer on `/calibration` and `/analyze` pages (ToS requirement)
- DB migration: reset `(CryptoAgent, btc/eth)` drift_thresholds.source = 'preliminary' to avoid Cross-2 pitfall
- Tripwire tests: `test_coingecko_timeout_does_not_block_other_agents`, `test_crypto_agent_factor6_symmetry`

**Addresses (FEATURES.md):** CoinGecko on-chain provider P1, combined community+developer activity score (differentiator)
**Uses (STACK.md):** `coingecko-sdk>=1.14.2,<2.0` (NEW core dep, +0.3 MB)
**Implements (ARCHITECTURE.md):** CoinGeckoProvider mirroring FinnhubProvider; option B (replace static factor) NOT option A (new 8th factor)
**Avoids (PITFALLS.md):** Pitfalls 3, 6, 11; Cross-2

**Estimated reqs:** 2-3

### Phase 3 (Phase 10) — Drift-Threshold Validation Methodology

**Rationale:** Depends on Phases 8+9 conceptually. The validation framework reuses `tracker.compute_rolling_ic` infrastructure that Phase 8 reliability plots also use; corpus must be rebuilt under SimFin+CoinGecko providers before validation can be honest. Without ECE/reliability already in the UI from Phase 8, operators cannot cross-check whether a "validated" threshold matches what they see in the calibration view.

**Delivers:**
- `engine/drift_validator.py` — `validate_drift_thresholds(db_path, candidate_grid)` returning per-`(drop_pct, floor)` precision/recall/Wilcoxon-p-value
- 16-point candidate grid: `(drop_pct ∈ {15, 20, 25, 30}) × (floor ∈ {0.3, 0.4, 0.5, 0.6})`
- Out-of-sample time split: train through 2024-06-30, validate 2024-07-01+. Bootstrap 1000× resample for 95% CI.
- `drift_thresholds` table — per-`(asset_type, agent_name)` row with `source` ∈ `{preliminary, validated, manual}`
- `POST /api/v1/drift/validate-thresholds` (long-running, returns 202 + job_id, reuses `corpus_rebuild_jobs` async-job pattern)
- `GET /api/v1/drift/validation` returning per-`(agent, asset_type)` precision/recall/CI-width
- `frontend/src/components/calibration/DriftValidationPanel.tsx` mounted in CalibrationPage
- `DriftBadge.tsx` 4th `validated` state (green) replaces amber `preliminary` once `validation_run_at` is non-null
- Phase 10 prerequisite check: assert corpus was rebuilt AFTER SimFin/CoinGecko feature flags landed
- Tripwire test: `test_preliminary_threshold_promotion_requires_evidence` — REQUIRES bootstrap 95% CI < 10pp wide before promotion

**Addresses (FEATURES.md):** Drift threshold validation P1 (carry-forward closure)
**Uses (STACK.md):** `scipy>=1.10` promotion (`scipy.stats.wilcoxon`); reuses `backtesting/walk_forward.py::generate_walk_forward_windows`
**Implements (ARCHITECTURE.md):** All three Q4 sub-paths (A: validation panel + endpoint; B: persisted thresholds table; C: lifecycle promote-flag)
**Avoids (PITFALLS.md):** Pitfall 5; Cross-4

**Critical caveat (must land in PROJECT.md Key Decisions):** v1.2 ships *capability to validate*, NOT *validated thresholds*. The cron-week corpus is ~13 weeks at ship time vs 60-week floor. Validation panel will display "needs N more weeks" until ~2026-07-XX. **Closeout for the v1.1 carry-forward = panel landing**, not flag flipping.

**Estimated reqs:** 3-4

### Phase Ordering Rationale

- **Why Phase 8 bundles SimFin + Reliability Plots:** Both touch FOUND-04 + `backtest_signal_history` schema. Sharing the `fundamentals_provider` column migration in one PR avoids a migration-then-feature interleave. PITFALLS Cross-1 + Pitfall 4 require the schema column to land in the same PR as SimFin.
- **Why CoinGecko comes second:** Independent of Phase 8, BUT Phase 9's CryptoAgent rewiring shifts CryptoAgent IC distribution (Cross-2). Doing CoinGecko before drift validation means Phase 10 can validate against a corpus that already reflects the v1.2 input space.
- **Why drift validation is last:** Closes the carry-forward by *capability*. Cannot honestly run before the corpus has been rebuilt under the new providers (Cross-3). The Phase 10 prerequisite check enforces this.
- **Why NOT 4 phases (ARCHITECTURE proposal):** User scope is "tight ~3 phases". The 4-phase proposal separates SimFin and reliability plots into Phase 8 + Phase 9, but neither is large enough to justify its own phase, and splitting them introduces the schema-migration-interleave problem.
- **Why NOT FEATURES/STACK ordering (Reliability → Providers → Drift):** That ordering does the smallest-risk feature first, but ignores Cross-1/Cross-3 — running reliability plots BEFORE SimFin lands means the corpus they read from will need rebuilding the moment SimFin ships.

### Research Flags

Phases likely needing deeper research during planning (`/gsd-research-phase`):

- **Phase 8 (SimFin + Reliability Plots):** Three open questions: (a) **SimFin filing-date filtering** for amended 10-Q/A filings (carry original filing date but differ in content); (b) **Murphy decomposition exact-bin vs PAV** — FEATURES suggests exact-bin for v1.2; confirm before implementation that arXiv 2008.03033 formulas suffice for our N-per-bin range; (c) **`use_pit_fundamentals` opt-in flag UX** — per-analyze, per-portfolio, or globally? Recommendation: per-analyze field on `AgentInput` matching `backtest_mode` precedent.

- **Phase 9 (CoinGecko):** Phase research on **CryptoAgent factor weights** specifically — how to z-score `commit_count_4_weeks` against asset-specific baselines (BTC vs ETH vs altcoins have different commit rhythms). Without phase-specific calibration, Factor 6 score becomes a BTC-biased indicator.

- **Phase 10 (Drift validation):** Phase research on **multi-comparison correction** — 16-point grid search risks p-hacking; Bonferroni or FDR correction needed for Wilcoxon-derived thresholds. Also confirm 16-point grid resolution before implementation (vs 64 — STACK recommends 16; 64 would pull in `optuna`, scope creep).

Phases with standard patterns (skip research-phase):
- None. All three phases benefit from focused phase research given the open-question density. **Recommend `/gsd-research-phase` for all three phases**, with Phase 8 having the densest open-question list.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All PyPI release dates verified 2026-04-27; SimFin SDK abandonment confirmed via Snyk; CoinGecko Demo limits cross-checked against vendor docs; sklearn/scipy/numpy already-installed status confirmed via `pip show` |
| Features | HIGH | Existing `tracking/tracker.py::compute_calibration_data` already implements 80% of the reliability-plot binning logic; `agents/fundamental.py:11-15` already documents the non-PIT gap; `agents/crypto.py:548` already documents the Factor 6 static-data gap; `engine/drift_detector.py:30-32` already documents the preliminary_threshold gap. Each "must have" feature is closing a self-acknowledged gap. |
| Architecture | HIGH | All file paths and integration points verified via direct file reads of the existing codebase; provider patterns (FinnhubProvider as template) are concrete and battle-tested; cache patterns (Parquet + TTLCache + thundering-herd dedup) are documented in v1.0 Phase 1 work. |
| Pitfalls | HIGH | All 13 pitfalls grounded in either (a) live code paths in the existing codebase, (b) explicit prior fixes documented in PROJECT.md / commit messages, or (c) vendor-published constraints. MEDIUM only on Pitfall 8 (SimFin free-tier exact daily cap not published — assumed conservative 2/sec). |

**Overall confidence:** HIGH

### Gaps to Address

1. **SimFin free-tier exact daily cap not published** — vendor pricing page implies daily caps but doesn't publish a hard ceiling. Mitigation: ship `AsyncRateLimiter(2/sec, 60s sliding window of 60 calls)` conservatively and surface "Rebuild will take ~6 hours at free-tier rate" UI estimate. Resolve in Phase 8 research with real rebuild against operator's portfolio.

2. **CoinGecko `community_data` Twitter follower discontinuation (2024)** — Reddit + Telegram are the only social signals on Demo tier. Factor weights need to be tuned without Twitter. Resolve in Phase 9 research by confirming Reddit + Telegram coverage for BTC/ETH on the operator's actual portfolio.

3. **Drift validator candidate grid resolution + multi-comparison correction** — STACK recommends 16-point grid. With 16 candidates × N agents × M asset_types, p-hacking risk is real. Resolve in Phase 10 research: pick Bonferroni vs FDR before tuning.

4. **v1.2 ships *capability* not *validated thresholds* — explicit operator communication needed** — validation panel will display "needs N more weeks" until ~2026-07-XX. Must be documented as a Key Decision in PROJECT.md so a future contributor doesn't see "preliminary" still flying and conclude v1.2 failed. Resolve at Phase 10 closeout.

5. **`use_pit_fundamentals` opt-in scope** — does the operator toggle per-analyze, per-portfolio, or globally? Phase 8 research must pick before implementation. Recommendation: per-analyze field on `AgentInput` (matches `backtest_mode` precedent).

---

## Sources

### Primary (HIGH confidence — verified 2026-04-27)

**Vendor documentation:**
- SimFin v3 API base URL — https://www.simfin.com/en/blog/major-simfin-update/
- SimFin pricing & free-tier limits — https://www.simfin.com/en/prices/ (2/sec, 5K stocks, 5y history, 500 credits/mo)
- SimFin Restated Date semantics — https://www.simfin.com/en/blog/find-good-fundamental-data/
- CoinGecko API endpoint overview — https://docs.coingecko.com/reference/endpoint-overview
- CoinGecko Demo rate limits — https://www.coingecko.com/en/api/pricing (30/min, 10K/month)
- CoinGecko ToS / attribution — https://www.coingecko.com/en/api_terms
- CoinGecko free-tier rate limit FAQ — https://support.coingecko.com/hc/en-us/articles/4538771776153
- scikit-learn calibration_curve API — https://scikit-learn.org/stable/modules/generated/sklearn.calibration.calibration_curve.html
- scikit-learn Probability Calibration documentation — https://scikit-learn.org/stable/modules/calibration.html

**PyPI release verification:**
- coingecko-sdk 1.14.2 (2026-04-21, Apache-2.0, ~330 KB) — https://pypi.org/project/coingecko-sdk/
- simfin 1.0.1 (2024-04-03, marked Inactive) — https://pypi.org/project/simfin/ + https://snyk.io/advisor/python/simfin
- pycoingecko 3.2.0 (2024-11-13, sync-only) — https://pypi.org/project/pycoingecko/
- coingecko-sdk GitHub — https://github.com/coingecko/coingecko-python (Stainless-generated)

**Existing codebase (direct file reads):**
- `agents/fundamental.py` — FundamentalAgent integration point + FOUND-04 contract (lines 56-77, 140-163)
- `agents/crypto.py` — 7-factor model + Factor 6 static path (lines 27-30, 50-53, 529-575)
- `data_providers/finnhub_provider.py` — provider pattern template (lines 79-90)
- `data_providers/cached_provider.py` + `parquet_cache.py` + `dividend_cache.py` — cache pattern templates
- `data_providers/rate_limiter.py` — `AsyncRateLimiter` token-bucket pattern
- `engine/pipeline.py:130` — `asyncio.gather(return_exceptions=True)` without per-agent timeout
- `engine/drift_detector.py:30-32` — threshold constants; MIN_SAMPLES_FOR_REAL_THRESHOLD=60; line 247 NEVER-zero-all guard
- `tracking/tracker.py` — Brier/IC/IC-IR + existing `compute_calibration_data` (lines 96-135, 320-350, 356-424)
- `backtesting/walk_forward.py` — `generate_walk_forward_windows` with purge_days=5 (lines 51-100)
- `frontend/src/pages/CalibrationPage.tsx` + `frontend/src/components/calibration/*`
- `.planning/PROJECT.md` — v1.2 milestone scope + 25-row Key Decisions table
- `.planning/codebase/CONCERNS.md` — pre-existing tech debt (lines 55-60, 209-216, 264-267)

### Secondary (MEDIUM confidence — peer-reviewed but not vendor-verified)

- Murphy decomposition formulas (REL/RES/UNC) — https://arxiv.org/pdf/2008.03033
- CORP method for stable reliability diagrams — https://www.pnas.org/doi/10.1073/pnas.2016191118
- ECE Expected Calibration Error formulation — https://towardsdatascience.com/expected-calibration-error-ece-a-step-by-step-visual-explanation-with-python-code-c3e9aa12937d/
- Walk-forward methodology — https://arxiv.org/html/2512.12924v1
- Bias-free backtesting + restatement bias quantification — https://sharpely.in/blog/bias-free-backtesting-explained
- S&P Global PIT vs lagged fundamentals — https://www.spglobal.com/content/dam/spglobal/mi/en/documents/general/sp-capitaliq-quantamental-point-in-time-vs-lagged-fundamentals.pdf

### Tertiary (LOW confidence — single-source community claims)

- SimFin free-tier daily cap not published — inferred from pricing-page tier structure; verify in Phase 8 with real rebuild
- CoinGecko 60s default httpx timeout — community claim from coingecko-sdk PyPI page
- Wilson interval asymptotic equivalence to bootstrap at N≥15 per bin — academic consensus but corpus-specific behavior not verified

---

*Research synthesis completed: 2026-04-27*
*Ready for roadmap: yes*
*Recommended next step: `/gsd-roadmapper` with this SUMMARY.md as primary input; expect 3 phases × 3-5 reqs = ~12 reqs total matching user's stated scope.*
