# Roadmap: Investment Agent

## Milestones

- ✅ **v1.0 Competitive Parity** — Phases 1-4 (shipped 2026-04-22)
- ✅ **v1.1 Live Validation** — Phases 5-7 (shipped 2026-04-25)
- 🚧 **v1.2 Trustworthy Signals** — Phases 8-10 (planned 2026-04-27)

## Phases

<details>
<summary>✅ v1.0 Competitive Parity (Phases 1-4) — SHIPPED 2026-04-22</summary>

- [x] Phase 1: Foundation Hardening (3/3 plans) — completed 2026-04-22
- [x] Phase 2: Signal Quality Upgrade (3/3 plans) — completed 2026-04-22
- [x] Phase 3: Data Coverage Expansion (4/4 plans) — completed 2026-04-22
- [x] Phase 4: Portfolio UI + Analytics Uplift (4/4 plans) — completed 2026-04-22

Full snapshot: `.planning/milestones/v1.0-ROADMAP.md` · Requirements: `.planning/milestones/v1.0-REQUIREMENTS.md`

</details>

<details>
<summary>✅ v1.1 Live Validation (Phases 5-7) — SHIPPED 2026-04-25</summary>

- [x] Phase 5: Corpus Population + Live Data Closeout (2/2 plans) — completed 2026-04-23
- [x] Phase 6: Calibration & Weights UI (3/3 plans) — completed 2026-04-24
- [x] Phase 7: Digest + Analytics Completeness (3/3 plans) — completed 2026-04-25

Full snapshot: `.planning/milestones/v1.1-ROADMAP.md` · Requirements: `.planning/milestones/v1.1-REQUIREMENTS.md`

</details>

<details>
<summary>🚧 v1.2 Trustworthy Signals (Phases 8-10) — PLANNED 2026-04-27</summary>

- [ ] **Phase 8: PIT Fundamentals + Reliability Plots** — SimFin point-in-time provider bundled with reliability/Murphy-decomposition plots; lands `fundamentals_provider` schema migration in same PR.
- [ ] **Phase 9: CoinGecko On-Chain Provider** — Live composite of dev/community signals replaces Factor 6 static yaml; introduces per-agent timeout primitive at the pipeline edge.
- [ ] **Phase 10: Drift-Threshold Validation Methodology** — Out-of-sample threshold validation panel + persisted `drift_thresholds` table + 4th `validated` DriftBadge state; ships *capability to validate*, not flipped flag.

</details>

### v1.2 Trustworthy Signals (Planned)

**Goal:** Promote calibration from "shipped" to "validated" — broaden free-tier inputs (SimFin point-in-time fundamentals + CoinGecko on-chain) and surface reliability plots + back-tested drift thresholds, closing v1.1's `preliminary_threshold` flag.

**Connecting narrative:** Broader inputs (SimFin + CoinGecko) feed tighter calibration (reliability plots), which produces the empirical basis for promoting the drift detector out of `preliminary_threshold`.

## Phase Details

### Phase 8: PIT Fundamentals + Reliability Plots
**Goal**: Operator can opt into point-in-time fundamentals via SimFin and diagnose per-agent miscalibration via reliability plots + Murphy/Brier decomposition — without contaminating the existing `backtest_signal_history` corpus through silent provider mixing.
**Depends on**: Phase 7 (v1.1 — `corpus_rebuild_jobs` async-job pattern, `agent_weights` table, `/calibration` page mount)
**Requirements**: SIG-v2-01, SIG-v2-02, DATA-v2-02, DATA-v2-04, DATA-v2-05
**Success Criteria** (what must be TRUE):
  1. Operator can view a per-agent reliability plot on `/calibration` — predicted-confidence buckets vs realized-win-rate scatter with diagonal reference line, sample-size-as-bubble-area encoding, per-bin Wilson 95% CIs as error bars, and adaptive bin count (`max(2, min(10, n_samples // 10))`); below-threshold bins surface a `preliminary_calibration: true` flag with amber UI banner.
  2. Operator can view a Murphy/Brier decomposition card next to the reliability plot showing per-agent REL/RES/UNC values with hover-tooltip explanations.
  3. Operator can opt into SimFin point-in-time fundamentals via `use_pit_fundamentals: bool = False` on `AgentInput` — FOUND-04 contract is preserved as default (regression test `test_fundamental_agent_backtest_mode_default_unchanged` asserts `backtest_mode=True && use_pit_fundamentals=False → HOLD/completeness=0.0` is unchanged).
  4. Schema migration lands in the SAME PR as `SimfinProvider`: `signal_history`, `backtest_signal_history`, and `drift_log` gain `fundamentals_provider TEXT NOT NULL DEFAULT 'yfinance'` with `(ticker, created_at, fundamentals_provider)` index; IC and drift queries filter by provider; first `use_pit_fundamentals=True` observation triggers a one-shot SimFin-corpus rebuild via existing `corpus_rebuild_jobs` (Pitfall 4 — provider mixing in signal_history).
  5. When SimFin is enabled and `|restated_value − as_filed_value| > 10%` for a reported metric on an open position, the position card displays a "Restated" delta badge linking to a tooltip showing both values + filing date.
**Plans**: 4 plans
- [ ] 08-01-PLAN.md — Wave 0: Schema migration + tripwire tests + pyproject promotion (DATA-v2-04 schema half)
- [ ] 08-02-PLAN.md — Wave 1: SimfinProvider + AgentInput field + FundamentalAgent dual-condition routing + first-enable corpus rebuild trigger (DATA-v2-02 + DATA-v2-04 trigger half)
- [ ] 08-03-PLAN.md — Wave 2: tracker.py reliability + Murphy backend + /analytics/calibration include_reliability extension (SIG-v2-01 + SIG-v2-02 backend)
- [ ] 08-04-PLAN.md — Wave 3: Frontend ReliabilityPlot + MurphyDecompositionCard + RestatedDeltaBadge (SIG-v2-01 + SIG-v2-02 frontend + DATA-v2-05)
**UI hint**: yes

### Phase 9: CoinGecko On-Chain Provider
**Goal**: CryptoAgent's Factor 6 ("Network adoption") is driven by a live composite of CoinGecko dev/community signals instead of static yaml constants — and CoinGecko's tight rate budget never blocks the pipeline for sibling agents.
**Depends on**: Phase 8 (shares `fundamentals_provider`-style migration discipline; corpus rebuild infrastructure must exist before CryptoAgent IC distribution shifts)
**Requirements**: DATA-v2-03
**Success Criteria** (what must be TRUE):
  1. CryptoAgent's Factor 6 produces a live score from `commit_count_4_weeks` z-score + `reddit_subscribers` MoM growth + `telegram_channel_user_count` MoM growth via a NEW `data_providers/coingecko_provider.py`; Factor weight stays at 5%; static `config/crypto_adoption.yaml` becomes graceful fallback when provider unavailable or 429-rate-limited.
  2. Pipeline introduces an `asyncio.wait_for(timeout=10s)` per-agent timeout primitive at `engine/pipeline.py` (Pitfall 3 — CoinGecko 5-15/min rate limit blocks `asyncio.gather` for 60s by default); regression test `test_coingecko_timeout_does_not_block_other_agents` confirms a slow CoinGecko call does not stall sibling agents.
  3. "Powered by CoinGecko" attribution renders on `/calibration` and `/analyze` pages (CoinGecko ToS requirement); `data_providers/coingecko_provider.py` carries an inline comment documenting the attribution requirement so future cleanups don't strip it.
  4. `(CryptoAgent, btc/eth)` rows in `drift_thresholds` (or equivalent state) reset to `source='preliminary'` automatically the first time CoinGecko provider lands (Cross-2 mitigation — new on-chain inputs shift CryptoAgent IC distribution; thresholds tuned on the old distribution misfire on the new one).
**Plans**: TBD

### Phase 10: Drift-Threshold Validation Methodology
**Goal**: Operator can run an out-of-sample drift-threshold validation against the rebuilt corpus and see per-`(agent, asset_type)` precision/recall + CI width on a `/calibration` panel — closing v1.1's `preliminary_threshold` carry-forward by shipping *capability to validate*, not necessarily flipped flags.
**Depends on**: Phase 8 (provider-aware corpus + reliability plots), Phase 9 (CryptoAgent IC distribution stabilized; corpus rebuilt under both new providers)
**Requirements**: DRIFT-v2-01, DRIFT-v2-02, DRIFT-v2-03, DRIFT-v2-04
**Success Criteria** (what must be TRUE):
  1. Operator can run `engine/drift_validator.py::validate_drift_thresholds(db_path, candidate_grid)` over an out-of-sample time-split (train ≤ 2024-06-30; validate ≥ 2024-07-01) walk-forward of the rebuilt corpus across the 16-point grid `(drop_pct ∈ {15,20,25,30}) × (floor ∈ {0.3,0.4,0.5,0.6})`, with `scipy.stats.wilcoxon` paired-significance + 1000× bootstrap 95% CI on precision/recall per `(asset_type, agent_name)` cell; **prerequisite check fails fast if `corpus_rebuild_jobs.completed_at` < the latest SimFin/CoinGecko feature-flag enable timestamp** (Cross-4 mitigation — validation must not run on a half-rebuilt corpus).
  2. New `drift_thresholds` table persists per-`(asset_type, agent_name)` rows with columns `(drop_pct, floor, source ∈ {preliminary, validated, manual}, validation_run_at, ci_width)`; `engine/drift_detector.py` reads this table at runtime and falls back to hardcoded `>20%` / `<0.5` constants only when the row is missing.
  3. `/calibration` page mounts `DriftValidationPanel.tsx` showing per-agent precision/recall/CI-width with a one-click "Run Validation" button (`POST /api/v1/drift/validate-thresholds` returns 202 + `job_id` matching the existing `corpus_rebuild_jobs` async-job pattern); `DriftBadge.tsx` gains a 4th green `validated` state that replaces amber `preliminary` only when `drift_thresholds.source = 'validated'` AND `ci_width < 10pp`.
  4. Tripwire regression test `test_preliminary_threshold_promotion_requires_evidence` is permanently armed and asserts the `validated` state cannot be reached without (a) non-null `drift_thresholds.validation_run_at`, (b) `drift_thresholds.ci_width < 10pp`, AND (c) `MIN_SAMPLES_FOR_REAL_THRESHOLD` reached; v1.2 closeout = panel landing with "needs N more weeks" text rendered against the ~13-week corpus, NOT a flipped flag.
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
|-------|-----------|----------------|----------|------------|
| 1. Foundation Hardening                   | v1.0 | 3/3 | Complete    | 2026-04-22 |
| 2. Signal Quality Upgrade                 | v1.0 | 3/3 | Complete    | 2026-04-22 |
| 3. Data Coverage Expansion                | v1.0 | 4/4 | Complete    | 2026-04-22 |
| 4. Portfolio UI + Analytics Uplift        | v1.0 | 4/4 | Complete    | 2026-04-22 |
| 5. Corpus Population + Live Data Closeout | v1.1 | 2/2 | Complete    | 2026-04-23 |
| 6. Calibration & Weights UI               | v1.1 | 3/3 | Complete    | 2026-04-24 |
| 7. Digest + Analytics Completeness        | v1.1 | 3/3 | Complete    | 2026-04-25 |
| 8. PIT Fundamentals + Reliability Plots   | v1.2 | 0/4 | Planning    | -          |
| 9. CoinGecko On-Chain Provider            | v1.2 | 0/0 | Not started | -          |
| 10. Drift-Threshold Validation Methodology| v1.2 | 0/0 | Not started | -          |
</content>
</invoke>
