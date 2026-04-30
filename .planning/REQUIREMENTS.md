# Requirements: Investment Agent — v1.2 Trustworthy Signals

**Defined:** 2026-04-27
**Core Value:** Drawdown protection via thesis-aware, regime-aware multi-agent signals — catching when a held position no longer matches the reason it was bought.
**Milestone Goal:** Promote calibration from "shipped" to "validated" — broaden free-tier inputs (SimFin point-in-time fundamentals + CoinGecko on-chain) and surface reliability plots + back-tested drift thresholds, closing v1.1's `preliminary_threshold` flag.
**Scope:** Tight (~3 phases / 10 requirements) combining Signal Quality v2 + Data Coverage v2 + v1.1 carry-forward research.

> Prior milestones archived: `.planning/milestones/v1.0-REQUIREMENTS.md` (25/25 reqs), `.planning/milestones/v1.1-REQUIREMENTS.md` (12/12 reqs).

---

## v1.2 Requirements

Requirements for milestone v1.2. Each maps to exactly one roadmap phase (filled by `gsd-roadmapper` during Step 10).

### Signal Quality v2 — Calibration depth

- [ ] **SIG-v2-01**: Operator can view a per-agent reliability plot on `/calibration` — predicted-confidence buckets vs realized-win-rate scatter with diagonal reference line, sample-size-as-bubble-area encoding, per-bin Wilson 95% CIs as error bars, and adaptive bin count (`max(2, min(10, n_samples // 10))`). Below-threshold bins surface a `preliminary_calibration: true` flag mirroring the Phase 2 pattern.
- [ ] **SIG-v2-02**: Operator can view a Murphy/Brier decomposition card alongside the reliability plot — REL (reliability), RES (resolution), UNC (uncertainty) values per agent, with hover-tooltip explaining what each component means in plain English (no OSS competitor offers this; differentiator vs Ghostfolio + Portfolio Performance + qlib).

### Data Coverage v2 — Provider depth

- [x] **DATA-v2-02**: Operator can opt into SimFin point-in-time fundamentals via a NEW `use_pit_fundamentals: bool = False` field on `AgentInput` — eliminates restatement bias from yfinance's restated fundamentals when set. FOUND-04 contract preserved as default (`backtest_mode=True && use_pit_fundamentals=False → HOLD/completeness=0.0`). Requires `SIMFIN_API_KEY` env var; logs lazy-key warning if missing.
- [ ] **DATA-v2-03**: CryptoAgent's Factor 6 ("Network adoption") replaces static `config/crypto_adoption.yaml` constants with a live composite of CoinGecko `commit_count_4_weeks` z-score + `reddit_subscribers` MoM growth + `telegram_channel_user_count` MoM growth via a NEW `data_providers/coingecko_provider.py`. Same 5% factor weight; static yaml becomes graceful fallback when provider unavailable. "Powered by CoinGecko" attribution rendered on `/calibration` and `/analyze` pages (ToS requirement).
- [x] **DATA-v2-04**: `signal_history`, `backtest_signal_history`, and `drift_log` schemas migrate to include a `fundamentals_provider TEXT NOT NULL DEFAULT 'yfinance'` column with idx `(ticker, created_at, fundamentals_provider)`. IC + drift queries filter by `fundamentals_provider`. First time `use_pit_fundamentals=True` is observed for a portfolio, the daemon triggers a one-shot SimFin-corpus rebuild via the existing `corpus_rebuild_jobs` async-job pattern. Mandatory to avoid Pitfall 4 (silent IC contamination from provider mixing).
- [x] **DATA-v2-05**: When SimFin is enabled and `|restated_value − as_filed_value| > 10%` for any reported metric on an open position, the position card displays a "Restated" delta badge linking to a tooltip showing both values + filing date. Surfaces the *value* of point-in-time fundamentals to the operator without requiring them to read backtest output.

### Drift Validation — v1.1 carry-forward

- [ ] **DRIFT-v2-01**: Operator can run `engine/drift_validator.py::validate_drift_thresholds(db_path, candidate_grid)` over an out-of-sample time-split (train ≤ 2024-06-30; validate ≥ 2024-07-01) walk-forward of the rebuilt corpus. The 16-point candidate grid `(drop_pct ∈ {15, 20, 25, 30}) × (floor ∈ {0.3, 0.4, 0.5, 0.6})` is scored per `(asset_type, agent_name)` cell using `scipy.stats.wilcoxon` paired-significance + 1000× bootstrap 95% CI on precision/recall. Phase 10 prerequisite check fails fast if `corpus_rebuild_jobs.completed_at` < the latest SimFin/CoinGecko feature-flag enable timestamp.
- [ ] **DRIFT-v2-02**: New `drift_thresholds` table persists per-`(asset_type, agent_name)` rows with columns `(drop_pct, floor, source ∈ {preliminary, validated, manual}, validation_run_at, ci_width)`. `engine/drift_detector.py` reads this table at runtime and falls back to hardcoded `>20%` / `<0.5` constants only when the row is missing. Reset to `source='preliminary'` automatically for `(CryptoAgent, btc/eth)` when CoinGecko first lands (Cross-2 mitigation).
- [ ] **DRIFT-v2-03**: `/calibration` mounts a NEW `DriftValidationPanel.tsx` showing per-agent precision/recall/CI-width with a one-click "Run Validation" button (`POST /api/v1/drift/validate-thresholds` returns 202 + `job_id` matching the existing async-job pattern). `DriftBadge.tsx` gains a 4th green `validated` state that replaces amber `preliminary` once `drift_thresholds.source = 'validated'` AND `ci_width < 10pp`. Until then, the panel displays "needs N more weeks" text derived from `MIN_SAMPLES_FOR_REAL_THRESHOLD - current_samples`.
- [ ] **DRIFT-v2-04**: A regression test `test_preliminary_threshold_promotion_requires_evidence` asserts the `validated` state cannot be reached without (a) a non-null `drift_thresholds.validation_run_at`, (b) `drift_thresholds.ci_width < 10pp`, AND (c) `MIN_SAMPLES_FOR_REAL_THRESHOLD` reached for the agent/asset_type. Test is permanently armed; flips green only if the operator runs validation against a sufficiently mature corpus.

---

## Future Requirements

Deferred to v1.3+ pending operator feedback or corpus maturity.

### Signal Quality v2 (deferred)

- **SIG-v2-03**: Per-bin trend sparklines on reliability plot (30/60/90d rolling) — should-have, deferred to v1.3 if scope tightens.
- **SIG-v2-04**: Drift sensitivity heatmap (`drop_pct × abs_floor` colored by OOS Sharpe) — nice-to-have for drift validation, deferred to avoid expanding Phase 10 scope.
- **SIG-v2-05**: Regime-conditioned adaptive RSI (originally in v1.2 candidate themes) — out-of-scope this milestone; revisit v1.3.
- **SIG-v2-06**: Trade-shuffle Monte Carlo (originally in v1.2 candidate themes) — out-of-scope this milestone; revisit v1.3.

### Data Coverage v2 (deferred)

- **DATA-v2-01**: MarketAux news + sentiment provider — deferred from v1.2 selection; revisit v1.3 if SentimentAgent IC shows continued degradation after FinBERT-only operation.
- **DATA-v2-06**: Glassnode / CryptoQuant paid integration for institutional-grade on-chain — free-tier constraint binds this milestone.

### Drift Validation (deferred)

- **DRIFT-v2-05**: Auto-tuning drift thresholds with hysteresis on every weekly run — threshold-thrashing risk; explicitly anti-feature for v1.2 (see Out of Scope below).

### Other deferred themes (from v1.1 retrospective)

- **DEPLOY-v2-01**: Docker + docker-compose deployment story — entire theme deferred (user chose Signal/Data focus for v1.2).
- **DEPLOY-v2-02**: OpenTelemetry / Prometheus instrumentation — deferred.
- **DEPLOY-v2-03**: `pandas-ta-classic` migration — deferred (pandas_ta FutureWarnings still tolerable).
- **UI-v2-01..05**: Allocation donuts / CSV import wizard / alert-threshold UI / Riskfolio-Lib position sizing / QuantStats tearsheet — entire UX-depth theme deferred.

---

## Out of Scope

Explicitly excluded from v1.2. Documented to prevent scope creep and re-litigation.

| Feature | Reason |
|---------|--------|
| Switching the *entire* fundamental pipeline to SimFin | Single-provider failure surface; SimFin free tier ~5y history only. Use **layered routing** with FundamentalAgent picking SimFin only when `use_pit_fundamentals=True`. |
| Real-time on-chain refresh polling (sub-minute) | CoinGecko Demo tier 30/min limit; sub-minute polling exhausts quota in 4 days. 24h Parquet cache is the maximum sensible cadence. |
| Auto-tuning drift thresholds on every weekly run | Threshold thrashing defeats the validation purpose; promotion must be deliberate, not continuous. Captured in DRIFT-v2-05 future req as anti-feature. |
| Promoting drift thresholds to `validated` based on the v1.2 corpus alone | Corpus is ~13 weeks at ship vs 60-week floor. v1.2 ships *capability to validate*, not *validated thresholds*. Honest "remain preliminary" outcome is a v1.2 success, not a failure. **Documented as Key Decision in PROJECT.md.** |
| Bootstrap CI on reliability plot bins (replacing Wilson) | Wilson is asymptotically equivalent for our N (≥15 per bin) and ~10× cheaper to compute. Defer to v2+ if N grows. |
| Murphy CORP method (PAV-based stable diagrams) replacing exact-bin | Exact-bin is adequate for our hundreds-per-bucket range; PAV-based CORP is the academic gold standard but adds ~80 lines for marginal stability gain. Defer to v2+. |
| Twitter follower count in CoinGecko Factor 6 | CoinGecko discontinued Twitter follower data in 2024 on Demo tier; Reddit + Telegram only. |
| Drift threshold promotion via UI button | Promotion requires explicit `drift_thresholds.source = 'validated'` UPDATE via DRIFT-v2-04 tripwire test passing — UI button is too easy to mis-click. CLI/script-only path. |
| Order execution / broker integration | Out-of-scope project-wide; revisited only after milestone goal review. |
| Multi-tenant SaaS / mobile app | Out-of-scope project-wide; this milestone stays solo-operator local-first. |

---

## Traceability

Which phases cover which requirements. Updated by `gsd-roadmapper` in Step 10 of `/gsd-new-milestone`.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SIG-v2-01 | Phase 8 | Pending |
| SIG-v2-02 | Phase 8 | Pending |
| DATA-v2-02 | Phase 8 | Complete |
| DATA-v2-03 | Phase 9 | Pending |
| DATA-v2-04 | Phase 8 | Complete |
| DATA-v2-05 | Phase 8 | Complete |
| DRIFT-v2-01 | Phase 10 | Pending |
| DRIFT-v2-02 | Phase 10 | Pending |
| DRIFT-v2-03 | Phase 10 | Pending |
| DRIFT-v2-04 | Phase 10 | Pending |

**Coverage:**
- v1.2 requirements: 10 total
- Mapped to phases: 10 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-27*
*Last updated: 2026-04-27 — traceability filled by gsd-roadmapper (Phases 8/9/10 mapping)*
