# Feature Research — v1.2 Trustworthy Signals

**Domain:** Personal multi-agent investment-journal — calibration validation, free-tier data coverage, drift-threshold validation
**Researched:** 2026-04-27
**Confidence:** HIGH (Context7-equivalent: official SimFin docs, CoinGecko docs, scikit-learn calibration docs, peer-reviewed reliability-diagram literature)

This research scopes the four v1.2 features. The Investment Agent is a brownfield project — these features extend existing systems (`/calibration` page, `FundamentalAgent`, `CryptoAgent`, `engine/drift_detector.py`). Recommendations therefore reference exact files and patterns the v1.0/v1.1 codebase already supports.

## Feature Landscape

### Table Stakes (Users Expect These)

These are user-facing or correctness baselines that, if missing, would make the v1.2 milestone feel unfinished. The bar is "any reasonable observer of the existing `/calibration` page or backtester would assume this works."

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Reliability plot per agent (predicted-confidence vs realized-win-rate) | `/calibration` already shows Brier + IC + IC-IR; the binned curve is the *visual* companion all three metrics summarise. Without it the user gets numbers but no diagnosis ("which buckets are over-confident?"). Already partially implemented — `tracking/tracker.py::compute_calibration_data` returns `(bucket_midpoint, expected_win_rate, actual_win_rate, sample_size)`. | **MEDIUM** | Backend exists; missing pieces are (a) per-agent breakdown (current implementation aggregates across agents), (b) frontend chart rendering, (c) reference diagonal y=x. Two existing chart libs available (Recharts for analytics, LightweightCharts for candles) — Recharts `<ScatterChart>` + `<ReferenceLine y=x>` is the natural fit (reuse from existing analytics page). |
| Equal-width binning on confidence buckets (10-pt) | This is what `tracking/tracker.py::compute_calibration_data` *already does* (line 113: `bucket_start = int(conf // bucket_width) * bucket_width`). User would expect the plot to honour the same buckets the table shows. | **LOW** | Confidence range in this project is [30, 90] (clamped in `agents/fundamental.py:423` and `agents/crypto.py:148`), so 7 buckets max (30-40, 40-50, ..., 80-90). Equal-frequency (quantile) binning is *not* recommended here because (a) bucket-midpoint mapping to "expected win rate = midpoint%" relies on equal-width bins, (b) standard practice for finance dashboards (sklearn's default is `strategy='uniform'`). |
| Sample-size guard per bin (`min_bucket_size`) | `compute_calibration_data` already drops buckets with `total < min_bucket_size` (default 5). User would assume a bin showing "100% accuracy on 1 sample" is hidden — and it already is. | **LOW** | Verify the frontend honours empty buckets (no fake zeros). Use existing `sample_size` field per bucket. |
| SimFin point-in-time fundamentals when available | The `FundamentalAgent` warns "Non-PIT data" right now (`agents/fundamental.py:11-15`, `agents/fundamental.py:502`). Operator already sees this caveat — they expect a path to remove it. SimFin's `Restated Date` column is the textbook PIT solution. | **MEDIUM** | SimFin Python library reads parquet datasets; first call downloads a CSV to disk, subsequent calls are local. Free tier has 5+ years history. Wire as new provider mirroring `FinnhubProvider` pattern. |
| CoinGecko `coin/{id}` endpoint with `community_data=true&developer_data=true` | `CryptoAgent`'s Factor 6 currently uses **static constants** (`agents/crypto.py:27-30`) and emits a warning (`agents/crypto.py:548`: "Network adoption uses static constants… Factor weight reduced to 5%"). Operator already sees the warning — replacement with live data is the obvious fix. | **MEDIUM** | Free Demo plan: 30 calls/min, 10K calls/month, **no key required for `/coins/{id}`** but key recommended. Single endpoint covers both community (Twitter/Reddit/Telegram) and developer (GitHub commits/forks/stars/PRs). |
| Validated drift thresholds (replace `preliminary_threshold` with empirical values) | `engine/drift_detector.py:30-32` ships hardcoded `DRIFT_THRESHOLD_PCT = 20.0` and `ICIR_FLOOR = 0.5` with `preliminary_threshold=True` flag. Whole milestone narrative ("Trustworthy Signals") collapses if the user sees that flag at the end of v1.2. | **MEDIUM** | Methodology = walk-forward over `backtest_signal_history` corpus + grid-search (drop_pct, abs_floor) by max OOS Sharpe of "scale-down-when-flagged" rule. Already have walk-forward scaffold (`backtesting/walk_forward.py`). |
| Per-bin confidence intervals (Wilson or bootstrap) | Without CIs, a bin labelled "62% actual / 65% predicted" looks reliable when N=15. Standard practice in academic reliability literature (Bröcker & Smith, CORP method) and `sklearn` examples. | **MEDIUM** | Wilson score interval is closed-form (no bootstrap loop) — recommended. Render as error bars on Recharts ScatterChart (`<ErrorBar>` element). Add `wilson_lower`, `wilson_upper` fields server-side; computation is ~15 lines of Python. |

### Differentiators (Competitive Advantage)

Features where the Investment Agent can pull ahead of OSS comparables (Ghostfolio, Portfolio Performance) and align with research-grade libraries (qlib, vectorbt). These leverage the project's existing strength: it's *not* a portfolio tracker — it's a thesis-aware *signal-quality* tool.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Murphy/Brier decomposition surfaced alongside reliability plot | Brier = Reliability + Resolution − Uncertainty. Existing `tracking/tracker.py::compute_brier_score` returns the scalar; the *decomposition* tells the user *why* it's 0.18 (well-resolved but mis-calibrated, vs poorly-resolved but well-calibrated). Ghostfolio/Portfolio Performance show no calibration metrics at all — qlib only shows IC. | **MEDIUM** | Compute REL, RES, UNC server-side. ~30 lines: bin-by-bin sums of `(p - obs_rate)^2 * |B_m|`, `(obs_rate - base_rate)^2 * |B_m|`, `base_rate * (1-base_rate)`. Render as 3-row breakdown card next to the plot. |
| Combined community + developer activity score for crypto | CoinGecko's `coin/{id}` returns BOTH community (Reddit/Twitter momentum) and developer (GitHub commits last 4 weeks, PRs merged) in a single call. Most OSS crypto agents (cryptoanalysis libraries) use one or the other; Santiment/Glassnode require paid tiers for combined views. Free + reduced-scrape-burden = competitive moat. | **MEDIUM** | Score formula: weighted blend of (a) `commit_count_4_weeks` z-score vs trailing-90d distribution, (b) `pull_requests_merged` momentum, (c) `reddit_subscribers` percentile, (d) `twitter_followers` slope. Replace `_score_network_adoption` static logic with this. |
| SimFin restated-vs-as-filed reconciliation page (or API field) | Power feature: when SimFin publish-date and restated-date disagree by >10%, surface the divergence to the user. This is the "investment journal that fights back" voice — "the EPS number you're seeing today differs from what was reported when you opened the position." | **MEDIUM-HIGH** | Pull both `Publish Date` and `Restated Date` columns from SimFin's `income_quarterly` dataset. Add a metric `restatement_delta_pct = (restated_value - originally_filed_value) / originally_filed_value`. Display in a `RestatementBadge` component on the position-detail page when delta > 10%. |
| Drift-threshold sensitivity analysis on `/calibration` | Beyond just *replacing* `preliminary_threshold` with a single empirical value, expose the *sensitivity curve* — "raising the threshold from 15% to 25% would have caught 3 false positives but missed 1 true degradation." Operator-facing transparency. | **HIGH** | Heatmap (drop_pct × abs_floor) coloured by OOS Sharpe of the scale-down rule. Reuse the daily-PnL heatmap pattern (`frontend/src/components/.../DailyPnlHeatmap.tsx`). Backend grid-search: 10×10 = 100 walk-forward backtests; expensive but one-time per milestone. |
| Hybrid SimFin (PIT) + Finnhub (latest) routing | When `backtest_mode=true`, use SimFin point-in-time. When `backtest_mode=false` (live), use Finnhub-or-yfinance for the freshest data. Today's `FundamentalAgent` short-circuits in `backtest_mode` (HOLD with `data_completeness=0.0`) — SimFin lets the agent contribute *meaningful* signals during backtests. | **MEDIUM** | Add `backtest_mode` branch in `FundamentalAgent.analyze` after the existing FOUND-04 short-circuit: `if agent_input.backtest_mode and SIMFIN_API_KEY: use SimFin instead of yfinance`. The `data_completeness=0.0` short-circuit is replaced for backtest, kept as fallback. |
| Per-bin trend over time (rolling reliability plot) | Beyond a static reliability snapshot, show whether agents have *gotten more or less calibrated* over the last 30/60/90 days. The `ICSparkline` component pattern (already in `frontend/src/components/calibration/`) extended to per-bucket calibration error. | **MEDIUM** | Compute calibration error per bin per week from `backtest_signal_history`. Render as small multiples (one sparkline per bucket). Surfaces the diagnostic "the 70-80% bucket has been consistently mis-calibrated for 8 weeks." |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time on-chain data refresh (sub-minute) | "Markets move fast — I want fresh on-chain metrics now." | CoinGecko free Demo plan caps at 30 calls/min and 10K calls/month. Polling 2 cryptos × 60 minutes × 24 hours = 2,880 calls/day → exceeds monthly cap in 4 days. Defeats free-tier constraint. | **Daily refresh, 24h cache.** Network/dev metrics move slowly (`commit_count_4_weeks` updates weekly). Mirrors existing `DividendCache` pattern (Parquet sibling, 24h TTL). |
| Switch entire fundamental pipeline to SimFin | "If SimFin is point-in-time, why keep Finnhub or yfinance at all?" | (a) SimFin free tier has ~5 years history; older backtests need yfinance. (b) Finnhub gives sector P/E peer baskets that SimFin doesn't. (c) Single-provider failure = entire FundamentalAgent dark. | **Layered routing**: SimFin for `backtest_mode`, Finnhub for live sector P/E, yfinance as final fallback. Pattern matches existing `data_providers/sector_pe_cache.py:get_sector_pe_source` returning `"finnhub" / "yfinance" / "static"`. |
| Bootstrap confidence intervals on reliability bins | "More rigorous than Wilson — accounts for full distribution." | (a) 1,000 bootstrap samples × N bins × per-agent × per-asset_type = 4-figure compute per refresh. (b) `/calibration` is loaded weekly; latency budget is sub-second; bootstrap will hit 5-10s. (c) Wilson is closed-form and asymptotically equivalent for `n_per_bin ≥ 15`. | **Wilson score interval.** Standard for binomial proportions. ~3 lines of Python. Same statistical guarantees for our N. |
| Auto-tune drift thresholds on every weekly run | "Adaptive thresholds! The system should always use the latest empirical value." | (a) Threshold thrashing — week-to-week noise drives thresholds up/down by ±5%, triggering false drift alerts. (b) Defeats the purpose of *validation* (a moving target validates nothing). (c) Sliding into "p-hacking on operator's portfolio" — every threshold change is an in-sample fit. | **Validate once per milestone**, lock thresholds for the duration, document the corpus they were validated against. Re-validate at the next milestone if the corpus has materially grown. |
| Surface restated-vs-as-filed delta on every position | "Show me ALL the data revisions across my whole portfolio!" | (a) For most companies most quarters, deltas are <2% (rounding, footnote reclassifications). Wall of green badges = banner blindness. (b) Operator wants exceptions, not noise. | **Threshold-based surfacing only**: delta > 10% AND |delta| × thesis-position-size > $X. Mirrors the existing thesis-drift alerting pattern (`monitoring/`). |
| Glassnode/CryptoQuant integration | "These are the gold-standard on-chain platforms." | Both require paid tiers ($30-300/mo) for non-trivial endpoints. The project's `## Constraints` section explicitly says "Free/community data providers only." | **CoinGecko `coin/{id}` covers 80% of the value at 0% of the cost.** If operator outgrows it, paid Glassnode is a v2 conversation, not a v1.2 conversation. |

## Feature Dependencies

```
[Reliability Plot Backend (per-agent buckets + Wilson CIs)]
    └──requires──> [tracking/tracker.py::compute_calibration_data extension]
                       └──requires──> [backtest_signal_history corpus has agent-level confidence rows]
                                          (already TRUE — existing v1.1 corpus is per-agent)

[Reliability Plot Frontend (Recharts ScatterChart + diagonal + error bars)]
    └──requires──> [Reliability Plot Backend]
    └──reuses────> [Existing Recharts setup in /analytics page]

[Murphy Decomposition card]
    └──enhances──> [Reliability Plot Frontend]
    └──requires──> [Reliability Plot Backend (bin sample-sizes already collected)]

[SimFin Point-in-Time Provider]
    └──requires──> [New SimFinProvider class implementing existing DataProvider interface]
    └──requires──> [SIMFIN_API_KEY environment variable + .env.example update]

[FundamentalAgent backtest-mode SimFin routing]
    └──requires──> [SimFin Point-in-Time Provider]
    └──modifies──> [agents/fundamental.py FOUND-04 short-circuit (line 56-77)]

[Restated-vs-As-Filed Delta Badge]
    └──requires──> [SimFin Point-in-Time Provider]
    └──reuses────> [DriftBadge.tsx 3-state pattern]

[CoinGecko On-Chain Provider]
    └──requires──> [New CoinGeckoProvider class with 24h cache]
    └──reuses────> [Existing Parquet cache pattern (DividendCache)]

[CryptoAgent Network/Dev Activity Scoring]
    └──requires──> [CoinGecko On-Chain Provider]
    └──replaces──> [agents/crypto.py:_score_network_adoption (lines 529-575)]
    └──conflicts──> [Static CRYPTO_ADOPTION constants (config/crypto_adoption.yaml)]

[Drift Threshold Validation]
    └──requires──> [Mature backtest_signal_history corpus (>=60 weekly IC obs per agent)]
    └──requires──> [Walk-forward grid search over (drop_pct, abs_floor)]
    └──reuses────> [backtesting/walk_forward.py scaffold]
    └──modifies──> [engine/drift_detector.py constants (lines 30-32)]
    └──removes───> [preliminary_threshold flag once validated]

[Drift Sensitivity Heatmap]
    └──requires──> [Drift Threshold Validation grid-search results]
    └──reuses────> [DailyPnlHeatmap.tsx pattern]
```

### Dependency Notes

- **Reliability Plot Backend ← compute_calibration_data extension:** Current implementation in `tracking/tracker.py:96-135` returns aggregated buckets (across agents). Extension is per-agent: filter `resolved` by `agent_signals[].agent_name` before bucketing. Existing `lookback`, `bucket_width`, `min_bucket_size` parameters preserved.
- **CryptoAgent ← CoinGecko Provider:** This is a *replacement*, not an addition. The static `CRYPTO_ADOPTION` constants and the corresponding factor weight (5%) need to come back up to ~10% once dynamic data is real (the original 10% reduced to 5% in `agents/crypto.py:50-53` *because* the data was static). Validation: re-run weight optimisation against backtest corpus once dynamic data is wired.
- **Drift Threshold Validation ← Mature Corpus:** Cannot validate thresholds against a corpus too thin to support stable IC estimates. The `backtest_signal_history` table needs to be populated against multiple tickers across years to give the (drop_pct, abs_floor) grid-search statistical power. **This is the binding constraint** — even with zero engineering effort, validation cannot promote `preliminary_threshold` to validated until the corpus is mature. Gate: >=60 weekly IC observations per agent (matches `MIN_SAMPLES_FOR_REAL_THRESHOLD = 60` in `engine/drift_detector.py:32`).
- **SimFin and CoinGecko providers conflict with no existing module** — clean greenfield additions. The Restated-Delta feature *enhances* SimFin (would not exist without it).

## MVP Definition

### Launch With (v1.2 ship-list)

The "v1.2 Trustworthy Signals" goal in `.planning/PROJECT.md:88-97` is "promote calibration from shipped to validated." Minimum to deliver that goal:

- [ ] **Reliability plot per agent on `/calibration`** — predicted-confidence vs realized-win-rate ScatterChart with diagonal reference line + per-bin Wilson CIs + sample-size annotations. *Without this, the calibration story is numbers-only.*
- [ ] **SimFin provider + `backtest_mode` routing** — `SimFinProvider` class + `FundamentalAgent` uses it instead of returning HOLD when `backtest_mode=true`. *Without this, look-ahead bias remains the agent's blocker for backtests.*
- [ ] **CoinGecko provider + CryptoAgent network/dev scoring** — replace `_score_network_adoption` static logic with live `commit_count_4_weeks` + `reddit_subscribers` deltas. *Without this, Factor 6 stays at the apologetic 5% weight and the warning persists.*
- [ ] **Drift threshold validation** — grid-search (drop_pct, abs_floor) over walk-forward of mature corpus + lock validated values + remove `preliminary_threshold=True` from `engine/drift_detector.py`. *Without this, the v1.2 narrative collapses — the milestone goal LITERALLY mentions this carry-forward.*
- [ ] **Murphy/Brier decomposition card next to plot** — REL/RES/UNC breakdown. *Without this, the reliability plot is decorative; with it, the user understands which side of the Brier score is hurting.*

### Add After Validation (v1.x — defer to v1.3)

These extend v1.2 but aren't required for milestone goal completion. Trigger to add: post-v1.2 user feedback says "I see calibration data, now what?"

- [ ] **Restated-vs-as-filed delta badge on positions** — surfaces SimFin restatement noise when |delta| > 10%. *Trigger: user opens 5+ positions and reports "I want to know when the numbers I'm seeing differ from what I bought on."*
- [ ] **Per-bin trend sparklines** — calibration error rolling over 30/60/90 days. *Trigger: user reports "I want to know if calibration is getting worse over time, not just where it is now."*
- [ ] **Drift sensitivity heatmap** — (drop_pct × abs_floor) coloured by OOS Sharpe. *Trigger: operator wants to tune their own thresholds, not just see the validated default.*
- [ ] **MarketAux news/sentiment** — listed as deferred in `.planning/PROJECT.md:103`. *Trigger: SentimentAgent's IC degrades below 0.3 (currently it leans on FinBERT alone).*

### Future Consideration (v2+)

- [ ] **Glassnode/CryptoQuant paid integration** — *defer because:* free constraint binds; CoinGecko covers 80% of the value.
- [ ] **Bootstrap CIs replacing Wilson** — *defer because:* Wilson is asymptotically equivalent for our N-per-bin range; bootstrap adds compute cost without statistical gain.
- [ ] **Per-position SimFin restatement reconciliation page** — *defer because:* needs the v1.x badge feature first to validate operator demand.
- [ ] **Auto-tuning drift thresholds with hysteresis** — *defer because:* threshold thrashing risk; manual re-validation each milestone is the safer pattern.
- [ ] **Real-time on-chain refresh** — *defer because:* free-tier rate limits, low signal-to-noise on sub-daily metrics.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Reliability plot per agent (ScatterChart + diagonal + Wilson CIs) | HIGH | MEDIUM | **P1** |
| SimFin provider + `backtest_mode` routing | HIGH | MEDIUM | **P1** |
| CoinGecko on-chain provider + CryptoAgent rewiring | HIGH | MEDIUM | **P1** |
| Drift threshold grid-search validation | HIGH | MEDIUM-HIGH | **P1** |
| Murphy/Brier decomposition card | MEDIUM | LOW-MEDIUM | **P1** |
| Restated-vs-as-filed delta badge | MEDIUM | MEDIUM | **P2** |
| Per-bin trend sparklines | MEDIUM | MEDIUM | **P2** |
| Drift sensitivity heatmap | MEDIUM | HIGH | **P2** |
| Bootstrap CIs (replacing Wilson) | LOW | HIGH | **P3** |
| Glassnode/CryptoQuant integration | LOW (constrained) | HIGH ($) | **P3** |
| Auto-tuning drift thresholds | LOW | HIGH | **P3** |

**Priority key:**
- **P1**: Required for v1.2 milestone goal ("Trustworthy Signals"). All five P1s are needed; dropping any breaks the connecting narrative ("broader inputs -> tighter calibration -> empirical drift thresholds").
- **P2**: Strong v1.3 candidates if user feedback supports them.
- **P3**: Defer pending product-market signal or constraint relaxation.

## Concrete UX Walkthrough — Reliability Plots (P1, user-facing)

The reliability plot is the user-facing piece — the other 3 features are mostly backend. Here's what the operator sees:

1. **Operator opens `/calibration` (existing page)** at the start of their weekly review. Today they see:
   - Calibration metrics table (per-agent: Brier / IC / IC-IR / 90-day rolling-IC sparkline / drift badge).
   - Weights editor (Current vs Suggested IC-IR weights, per-agent exclude toggle).
2. **New v1.2 section appears between table and weights editor**: "Reliability Diagnostic" header.
3. **For each agent (TechnicalAgent, FundamentalAgent, etc.)**, expanded view shows a Recharts `<ScatterChart>`:
   - **X-axis**: Predicted confidence bucket (35, 45, 55, 65, 75, 85 — midpoints of 30-40, 40-50, ...).
   - **Y-axis**: Realized win-rate (%) with Wilson 95% CI error bars.
   - **Diagonal reference line**: y = x ("perfect calibration").
   - **Above-diagonal points** = under-confident agent (predicts 60%, actually right 75% — could be more confident).
   - **Below-diagonal points** = over-confident agent (predicts 80%, actually right 55% — should hedge).
   - **Bubble size** = sample-size in bin (proportional to `sample_size`).
   - **Hover tooltip**: "Bucket 70-80%, n=23, observed 65% +/- 9% (Wilson CI), expected 75%."
4. **Murphy decomposition card** sits next to the plot:
   ```
   Brier Score: 0.18
     Reliability (lower=better): 0.04   <- well-calibrated
     Resolution (higher=better): 0.08   <- decent discrimination
     Uncertainty (constant):     0.22   <- base-rate noise
   ```
   - Operator immediately sees "Brier is 0.18 because of base-rate noise, not mis-calibration — agent is fine."
5. **"Well-calibrated" visual signature**: All bin points hug the diagonal within their CI; reliability component is small (<0.05); resolution component is large (>0.05). When poorly calibrated: points systematically above or below diagonal; reliability component balloons.
6. **Below the plot, an empty-corpus CTA** (consistent with existing v1.1 pattern in `CalibrationTable.tsx`): if `sample_size < min_bucket_size` for all bins -> "Need more signal history. Trigger backtest corpus rebuild?" -> reuses existing `rebuildCalibrationCorpus()` API.

This walkthrough reuses (a) `useApi` + caching, (b) Recharts (already a dep), (c) the `useState` + `useToast` pattern, (d) the empty-state CTA pattern from `CalibrationTable.tsx`. New surface area: ~1 component (`ReliabilityPlot.tsx`) + ~1 helper (`MurphyDecompositionCard.tsx`).

## Competitor / OSS-Pattern Analysis

The "Borrow Patterns From" column maps each feature to specific OSS code/conventions worth lifting.

| Feature | Ghostfolio | Portfolio Performance | qlib | vectorbt | Riskfolio-Lib | scikit-learn | Our Approach |
|---------|------------|----------------------|------|----------|---------------|--------------|--------------|
| Reliability plot | Not present (no signal-quality concept) | Not present (no calibration) | IC tables only, no reliability plots | Not present (backtester, not signal QA) | Not present | **`CalibrationDisplay` from `sklearn.calibration` is the canonical pattern**: bins predicted vs observed, optional `n_bins=10` and `strategy='uniform'`. **Borrow**: API surface (`from_predictions(y_true, y_prob, n_bins, strategy)`), defaults, axis labels. | Mirror sklearn's API in our `compute_reliability_plot` helper but extend with `wilson_lower/upper` per bin. |
| Murphy/Brier decomposition | Not present | Not present | Not present (computes IC, not Brier) | Not present | Not present | scikit-learn's `brier_score_loss` returns scalar only — does NOT decompose. **Borrow**: the *concept* from Murphy 1973; implement decomposition ourselves (~30 lines). Reference: arXiv:2008.03033 "Evaluating probabilistic classifiers" provides exact CORP-decomposition formulas. | Implement REL/RES/UNC server-side using exact-bin formulas (no PAV needed for v1; PAV is a v2 nice-to-have). |
| Point-in-time fundamentals | Imports CSV positions, no fundamental data | Position tracker only | Implicitly PIT (Alpha158/Alpha360 are constructed PIT) | Backtest-time data assumed clean by user | Optimisation library, no fundamentals | Not in scope (general ML library) | **SimFin Python library** (`pip install simfin`): `sf.load_income(variant='quarterly')` returns DataFrame with `Restated Date`. Pattern: `SimFinProvider.get_financials(ticker, as_of_date)` filters rows where `Publish Date <= as_of_date AND (Restated Date IS NULL OR Restated Date <= as_of_date)`. |
| On-chain crypto signals | No crypto-native analytics (just price tracking) | Same — basic position tracking | No crypto module | Generic backtester (would need wrapper) | Not crypto-specific | Not in scope | **CoinGecko `pycoingecko` Python library** + `coin/{id}?community_data=true&developer_data=true`. Returns `developer_data.commit_count_4_weeks`, `community_data.reddit_subscribers`, `community_data.twitter_followers`. **Pattern to borrow**: `data_providers/finnhub_provider.py` rate-limit + cache wrapper. |
| Drift detection / threshold validation | Not present | Not present | **qlib has IC-based factor selection** with `IC_max >= 0.99` redundancy threshold (per their R&D-Agent-Quant paper) — but this is in-sample. | Walk-forward splitter classes (rolling, expanding, time-anchored, random/block bootstrap) — production-ready. **Borrow**: their `Splitter` API surface. | Not present | Not in scope | **Pattern**: vectorbt's walk-forward + grid search over (drop_pct, abs_floor). Our existing `backtesting/walk_forward.py` uses 30/10 windows + `purge_days=5` for IC-feeding — matches vectorbt's Purged-K-Fold pattern. |
| Reliability diagram CIs | Not present | Not present | Not present | Not present | Not present | sklearn's `CalibrationDisplay` does NOT include CIs — known gap (sklearn issue #23132 tracks PAV-based stable diagrams). **Borrow**: Wilson interval formula from `statsmodels.stats.proportion.proportion_confint(method='wilson')`. | Add Wilson CIs as a strict differentiator vs sklearn's default — small code, large credibility win. |

### OSS Library Adoption Recommendations

- **`simfin` Python package** (Apache-2.0 license, pure-Python, tiny dep tree). Add to `[all]` extras in `pyproject.toml` + a new `[simfin]` optional extra so default install stays slim. Pattern matches how `transformers`/`torch` were gated behind `[llm-local]` in v1.0.
- **`pycoingecko` Python package** (MIT license, 18 KB). Pure-Python wrapper. Add to *core* dependencies (no optional gate) — small enough that always-installing it costs nothing, and CryptoAgent depends on it whenever `btc`/`eth` is analysed.
- **`scipy.stats`** (already a dep via `tracking/tracker.py:389` for `pearsonr`). Wilson CIs come from `statsmodels.stats.proportion.proportion_confint` — we'd need to add `statsmodels` (~70 MB transitive — heavy). **Better: write Wilson formula directly** (~5 lines using `scipy.stats.norm.ppf`).
- **No new chart library**: stick with Recharts (already used by `/analytics`) — `<ScatterChart>` + `<ReferenceLine>` + `<ErrorBar>` covers reliability plots perfectly. Phase 4 ROADMAP key decision in `.planning/PROJECT.md:172` already locks this.

## Sources

### Reliability Diagrams & Calibration
- [Stable reliability diagrams for probabilistic classifiers — PNAS](https://www.pnas.org/doi/10.1073/pnas.2016191118) — CORP method using PAV algorithm; introduces stable diagrams and decomposition.
- [Evaluating probabilistic classifiers: Reliability diagrams and score decompositions revisited (arXiv 2008.03033)](https://arxiv.org/pdf/2008.03033) — formulas for Brier decomposition into reliability/resolution/uncertainty.
- [scikit-learn Probability Calibration documentation](https://scikit-learn.org/stable/modules/calibration.html) — canonical Python API for calibration curves.
- [scikit-learn calibration_curve API](https://scikit-learn.org/stable/modules/generated/sklearn.calibration.calibration_curve.html) — `n_bins`, `strategy='uniform'|'quantile'`.
- [scikit-learn issue #23132: Add PAV algorithm for calibration_curve](https://github.com/scikit-learn/scikit-learn/issues/23132) — confirms PAV not in sklearn yet; our implementation isn't blocked by upstream gap.
- [Expected Calibration Error (ECE) — Towards Data Science](https://towardsdatascience.com/expected-calibration-error-ece-a-step-by-step-visual-explanation-with-python-code-c3e9aa12937d/) — ECE/MCE formulas with binning.
- [Understanding Model Calibration — ICLR Blogposts 2025](https://iclr-blogposts.github.io/2025/blog/calibration/) — visual explanation of binning trade-offs.
- [scores library — Isotonic Regression and Reliability Diagrams](https://scores.readthedocs.io/en/stable/tutorials/Isotonic_Regression_And_Reliability_Diagrams.html) — Python `isoreg` module for PAV-calibrated reliability diagrams.

### SimFin Point-in-Time Fundamentals
- [SimFin Python API documentation](https://simfin.readthedocs.io/) — Python library reference.
- [SimFin GitHub repo](https://github.com/SimFin/simfin) — open-source Apache-2.0 Python wrapper.
- [SimFin tutorials repo](https://github.com/SimFin/simfin-tutorials) — usage patterns including `sf.load_income(variant='quarterly')`.
- [SimFin: Why it is so difficult to find good fundamental data](https://www.simfin.com/en/blog/find-good-fundamental-data/) — covers Restated Date semantics.
- [SimFin pricing page](https://www.simfin.com/en/prices/) — confirms free tier with sufficient history for v1.2 scope.
- [Bias-free backtesting (sharpely.in)](https://sharpely.in/blog/bias-free-backtesting-explained:-how-sharpely-uses-point-in-time-data-to-avoid-look-ahead-and-survivorship-bias) — context for why PIT matters; quantified bias of 1-4% annual returns.

### CoinGecko On-Chain Provider
- [CoinGecko API endpoint overview](https://docs.coingecko.com/reference/endpoint-overview) — `/coins/{id}` parameters including `community_data`, `developer_data`.
- [CoinGecko API pricing — Demo plan rate limits](https://www.coingecko.com/en/api/pricing) — 30 calls/min, 10K/month confirmed.
- [pycoingecko (Python wrapper)](https://github.com/man-c/pycoingecko) — MIT-licensed Python wrapper for CoinGecko API.
- [CoinGecko: Best Crypto Data API for Developers — GitHub Activity Rankings 2026](https://www.coingecko.com/learn/best-crypto-data-api-ranked) — confirms developer_data tracking covers GitHub forks/stars/PRs/commits.
- [CoinGecko on-chain analysis explainer](https://www.coingecko.com/learn/on-chain-analysis) — confirms which metrics the API surfaces.
- [Bitcoin price direction prediction using on-chain data and feature selection — ScienceDirect](https://www.sciencedirect.com/science/article/pii/S266682702500057X) — research-grade evidence (82% prediction accuracy with on-chain features) supporting v1.2 inclusion.
- [Real-time onchain signals — Nansen](https://www.nansen.ai/post/real-time-onchain-signals-decoding-crypto-market-forecasting-with-blockchain-analysis) — industry view on which on-chain metrics are alpha-positive.

### Drift Threshold Validation
- [Interpretable Hypothesis-Driven Trading: A Walk-Forward Validation Framework (arXiv 2512.12924)](https://arxiv.org/html/2512.12924v1) — walk-forward methodology for trading-signal validation.
- [Backtesting Series Episode 2: Cross-Validation techniques (BSIC)](https://bsic.it/backtesting-series-episode-2-cross-validation-techniques/) — Purged K-Fold and time-series CV patterns.
- [Autoregressive Drift Detection Method (QuantInsti blog)](https://blog.quantinsti.com/autoregressive-drift-detection-method/) — concept-drift literature applied to trading.
- [Backtest overfitting in the machine learning era (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110) — comparison of OOS testing methods; relevant to threshold validation.
- [CFA Institute: Investment Model Validation Guide](https://rpc.cfainstitute.org/sites/default/files/-/media/documents/article/rf-brief/investment-model-validation.pdf) — practitioner standards for model validation.

### OSS Comparables
- [Ghostfolio (GitHub)](https://github.com/ghostfolio/ghostfolio) — open-source wealth-management tracker; **no calibration features**.
- [microsoft/qlib](https://github.com/microsoft/qlib) — AI quant platform; uses IC thresholds for factor selection, no reliability plots.
- [vectorbt (GitHub)](https://github.com/polakowo/vectorbt) — backtesting engine with walk-forward splitter classes worth borrowing API patterns from.
- [Riskfolio-Lib](https://riskfolio-lib.readthedocs.io/) — portfolio optimisation library; no signal-quality features.

---
*Feature research for: v1.2 Trustworthy Signals — Investment Agent*
*Researched: 2026-04-27*
