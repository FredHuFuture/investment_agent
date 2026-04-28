# v1.2 Trustworthy Signals — Pitfalls Research

**Domain:** Personal multi-agent investment system (brownfield, adding 4 features to existing v1.1 codebase)
**Researched:** 2026-04-27
**Confidence:** HIGH (claims grounded in existing code paths, official docs, and OSS practice; LOW where flagged)
**Scope:** Pitfalls SPECIFIC to adding the four v1.2 features to a system that ALREADY has multi-agent pipeline, regime-aware aggregator, auto-scaling drift detector with `preliminary_threshold`, `backtest_mode` look-ahead guard, `backtest_signal_history` corpus, and 889+ test floor.

The four features:
1. **SIG-v2-01** — Calibration reliability plots
2. **DATA-v2-02** — SimFin point-in-time fundamentals provider
3. **DATA-v2-03** — CoinGecko on-chain provider for CryptoAgent
4. **Drift-threshold validation methodology** (carry-forward from v1.1 Phase 7)

---

## Severity Legend

| Tag | Meaning | Examples |
|-----|---------|----------|
| **DATA-CORRUPTION** | Silently writes wrong data to DB; can't be detected by inspection | FOUND-04 contract bypass, retroactive Finnhub→SimFin metric divergence |
| **SILENT-FAILURE** | Wrong answer returned, no exception, no log line | Reliability plot binning hiding miscalibration, drift-threshold over-fit |
| **LOUD-FAILURE** | Crash, exception, or stalled pipeline (visible) | CoinGecko 429 storm, SimFin timeout blocking pipeline |
| **COSMETIC** | Confusing UX or misleading label only | Survivorship-bias warning text, attribution string typo |

---

## Critical Pitfalls

### Pitfall 1: SimFin Provider Invoked OUTSIDE backtest_mode Bypasses FOUND-04 Contract — DATA-CORRUPTION

**What goes wrong:**
The whole motivation for SimFin (DATA-v2-02) is point-in-time fundamentals — i.e., the data SimFin returns is *historically dated* (as it was reported on date X, not as currently restated). FOUND-04 in `agents/fundamental.py:56-77` short-circuits FundamentalAgent to HOLD with `data_completeness=0.0` whenever `backtest_mode=True`, because the existing yfinance provider serves restated financials.

The naive integration of SimFin would say: "Now that we have PIT data, we can run FundamentalAgent in `backtest_mode=True`." This is correct in spirit but BREAKS the FOUND-04 contract that the pipeline, weight aggregator, and `backtest_signal_history` corpus already rely on.

Specifically:
- The aggregator currently expects `data_completeness=0.0` from FundamentalAgent during backtests — this is how it knows to renormalize weights across the remaining 4 agents (per FOUND-05's 12-case parametrized test).
- The `backtest_signal_history` corpus that v1.1 LIVE-01 populates was built with FundamentalAgent at completeness=0; flipping this to non-zero retroactively contaminates already-stored Brier/IC computations.
- FOUND-04 is not a single check — it's a defence-in-depth pair (line 56 early return + line 140 secondary `not agent_input.backtest_mode` guard for EDGAR). Adding SimFin without explicitly negotiating both checks creates inconsistency.

**Why it happens:**
The contract is enforced at one site (`agents/fundamental.py`), but its CONSEQUENCES live elsewhere — in `engine/signal_aggregator.py` weight renormalization, in the corpus, in WeightAdapter's IC-IR scaling. A developer adding SimFin sees only the FundamentalAgent file and reasons "the early return was needed because yfinance was non-PIT; SimFin is PIT, so the early return is unnecessary." They miss the downstream coupling.

**How to avoid (defensive code pattern):**

1. **Add a pinned regression test in Phase 8 that asserts the yfinance contract is preserved by default:**
   ```python
   # tests/test_phase8_simfin_provider.py
   async def test_fundamental_agent_backtest_mode_default_unchanged():
       """SimFin must be opt-in. backtest_mode=True without explicit
       provider injection must still return HOLD/completeness=0.0."""
       agent = FundamentalAgent(provider=YFinanceProvider())
       out = await agent.analyze(AgentInput(ticker="AAPL", backtest_mode=True))
       assert out.signal == Signal.HOLD
       assert out.data_completeness == 0.0
       assert "look-ahead bias" in out.warnings[0]
   ```

2. **Make SimFin opt-in via a NEW agent_input field, not a provider swap:**
   ```python
   # agents/models.py
   @dataclass
   class AgentInput:
       ticker: str
       asset_type: str
       backtest_mode: bool = False
       use_pit_fundamentals: bool = False  # NEW — default False
       backtest_date: date | None = None    # NEW — required when use_pit_fundamentals=True
   ```
   Then in `agents/fundamental.py`, the FOUND-04 short-circuit becomes:
   ```python
   if agent_input.backtest_mode and not agent_input.use_pit_fundamentals:
       return AgentOutput(signal=HOLD, data_completeness=0.0, ...)  # unchanged
   if agent_input.backtest_mode and agent_input.use_pit_fundamentals:
       if agent_input.backtest_date is None:
           raise ValueError("use_pit_fundamentals requires backtest_date")
       # NEW: invoke SimFin with as_of=backtest_date
   ```

3. **Add a corpus-versioning column** so old `backtest_signal_history` rows can be filtered out when the SimFin path is enabled — prevents mixing FundamentalAgent=HOLD rows (yfinance era) with FundamentalAgent=BUY/SELL rows (SimFin era) inside the same Brier/IC denominator.

**Warning signs:**
- After SimFin lands, `compute_brier_score("FundamentalAgent")` suddenly returns a non-None value where it returned None before (because completeness flipped from 0 to non-zero).
- Aggregated signal flips on a corpus-replay test that was previously stable.
- New Phase 8 review-fix issue along the lines of "FundamentalAgent now contributes to backtests, regression test fails with `assert signal == HOLD`".

**Phase to address:**
- **Phase 8 (SimFin)**: First-priority unit test before any provider integration code. Must be in initial PR, not a follow-up.
- **Phase 9/10 (drift validation)**: Re-validate that the corpus rebuild in v1.2 produces equivalent IC-IR series to v1.1 unless `use_pit_fundamentals=True` is explicitly enabled.

---

### Pitfall 2: Reliability Plot Binning Hides Miscalibration at Current Corpus Size — SILENT-FAILURE

**What goes wrong:**
A reliability plot (predicted-vs-realized accuracy) is sample-noisy by construction. Existing `tracking/tracker.py::compute_calibration_data` already uses 10%-wide buckets with `min_bucket_size=5` (lines 96-135), which is reasonable for the 6-bucket existing structure (30-40, 40-50, ..., 80-90). But SIG-v2-01 reliability plots — predicted *probability* vs realized win-rate — typically default to N=10 bins (scikit-learn `calibration_curve` n_bins default is 5).

Two failure modes:
- **Too few bins (e.g., 5):** `forward_return > 0` happens ~50% of the time naturally; with only 5 bins, a systematically over-confident agent that says "80% probable BUY" but is right 55% of the time gets averaged into a 60-80% bucket where surrounding noisy points hide the miscalibration.
- **Too many bins (e.g., 20):** With current `backtest_signal_history` corpus size (~10 rows live, ~750 rows in walk-forward synthetic per phase 2 plan), each bin has 0-3 samples. The plot looks like Swiss cheese with wild swings between bins, and the operator concludes the agent is "uncalibrated" when really the plot is sample-noise dominated.

The existing system already has `preliminary_calibration: true` flag (`api/routes/analytics.py` exposes it from `tracking/tracker.py`) for similar noise concerns. SIG-v2-01 needs the SAME pattern.

**Why it happens:**
`sklearn.calibration.calibration_curve(n_bins=10)` is the canonical example in every ML-calibration tutorial. Engineers copy it without thinking about the corpus size. The default LOOKS fine in development against a fat synthetic dataset, but fails in production against the operator's narrow live corpus.

**How to avoid (defensive code pattern):**

1. **Compute bins as a function of N, not a constant:**
   ```python
   # Recommendation: target ≥10 samples per bin, max 10 bins
   def _adaptive_bin_count(n_samples: int, min_per_bin: int = 10, max_bins: int = 10) -> int:
       return max(2, min(max_bins, n_samples // min_per_bin))
   ```
   For N=20: 2 bins. For N=50: 5 bins. For N=200: 10 bins (capped).

2. **Plumb `preliminary_calibration: true` through the reliability-plot endpoint exactly as Phase 2 did:**
   ```python
   # api/routes/analytics.py response
   {
       "reliability_curve": [...],
       "preliminary_calibration": true,  # IF n_bins < 5 OR min(bin_counts) < min_per_bin
       "n_bins_used": 3,
       "n_samples": 28,
       "min_samples_per_bin": min(bin_counts),
   }
   ```

3. **Frontend (CalibrationPage.tsx) MUST render an amber banner** when `preliminary_calibration: true`, mirroring the existing DriftBadge 3-state pattern. Don't render a falsely-confident "Your agent is well-calibrated" message on a plot built from 28 samples in 3 bins.

4. **Three-class signal handling (BUY/HOLD/SELL):** The existing Brier in `tracker.py:320-350` already excludes HOLD (one-vs-rest binary on directional signals only). Reliability plot must follow the SAME convention. Compute *two* curves:
   - `predicted_buy_prob` vs `actual_p(forward_return > 0)`
   - `predicted_sell_prob` vs `actual_p(forward_return < 0)`
   HOLDs are EXCLUDED from both. Document this in the API and UI; otherwise users will infer "HOLD signals are well-calibrated" from a plot that never included them.

**Warning signs:**
- Reliability plot shows wild zig-zag (not a smooth diagonal-ish line) at small N — sample-noise tell.
- Operator complains the plot "looks different every week" — N is on the cusp, bin assignments shift.
- A bin contains the literal value `100.0` (every sample in that bin won, an artifact of N=2-3 not real calibration).

**Phase to address:**
- **Phase 8 (Reliability Plots)**: Decide N→bins formula in research; encode in `tracker.py` with unit test `test_adaptive_bin_count`. Plumb `preliminary_calibration` flag in API response. Frontend banner in same phase, not deferred.

---

### Pitfall 3: CoinGecko Free-Tier Rate Limit (5-15/min) Blocks Pipeline asyncio.gather — LOUD-FAILURE

**What goes wrong:**
CoinGecko free public API allows **5-15 calls/minute** ([source](https://support.coingecko.com/hc/en-us/articles/4538771776153)) — vastly tighter than Finnhub's 60/min or FRED's effectively unlimited. The `engine/pipeline.py::_run_pipeline` runs all agents in parallel via `asyncio.gather(*all_tasks, return_exceptions=True)` (line 130). For a btc/eth analysis, CryptoAgent calls CoinGecko alongside Technical, Macro, Sentiment running in parallel.

Two failure modes:
- **First btc/eth analysis after rate-limit reset works fine; the second one within the minute returns HTTP 429.** With `return_exceptions=True` the exception is captured, but if CryptoAgent's catch-all wraps too late, the agent silently degrades to a HOLD output without flagging the data-source failure to the user.
- **Worse: the HTTP client default timeout is 1 minute** ([CoinGecko SDK docs](https://pypi.org/project/coingecko-sdk/)). If CoinGecko is just slow (not 429), one CryptoAgent call hanging for 60s blocks `asyncio.gather` from completing for the OTHER agents. Even though `return_exceptions=True` would catch a final timeout, the pipeline waits the full 60s for it. A user clicking "Analyze BTC" sees a stalled spinner for a minute.

**Why it happens:**
The existing pattern (Finnhub at 60/min) over-specs free-tier resilience for CoinGecko's actual budget. Devs assume the same async/rate-limit decorator will work; it does NOT — Finnhub's `AsyncRateLimiter` permits 60 calls in a sliding 60s window, but CoinGecko's hard ceiling of 5-15 means the limiter QUEUES rather than rejects, leading to multi-second waits inside the agent.

The brownfield pipeline has NO per-agent timeout wrapper — `asyncio.gather` waits for all tasks. A slow CoinGecko call becomes a slow analyze endpoint.

**How to avoid (defensive code pattern):**

1. **Wrap CoinGecko-dependent agent calls with `asyncio.wait_for` at the pipeline edge:**
   ```python
   # engine/pipeline.py — propose new helper
   async def _safe_agent_run(agent, agent_input, timeout_s=10.0):
       try:
           return await asyncio.wait_for(agent.analyze(agent_input), timeout=timeout_s)
       except asyncio.TimeoutError:
           return AgentOutput(
               agent_name=agent.name, signal=Signal.HOLD, confidence=30.0,
               reasoning=f"{agent.name} timed out after {timeout_s}s",
               warnings=[f"{agent.name} provider unavailable (timeout)"],
               data_completeness=0.0,
           )
   ```
   Apply CryptoAgent timeout=10s; allow yfinance/Finnhub to keep their existing budgets.

2. **Cache CoinGecko responses aggressively (24h TTL):**
   On-chain metrics (MVRV, network adoption, dev activity) move on weekly+ scales — caching a single ticker for 24h is rarely lossy and slashes API calls by ~24× for a daily-revaluation pattern.

   But: **CoinGecko's ToS says "if you must cache, refresh at least every 24 hours"** ([source](https://www.coingecko.com/en/api_terms)) — implies caching IS permitted but expects a max-age. Use the same Parquet-cache pattern as `DividendCache` (FOUND-02 sibling at `data/cache/coingecko/{coin_id}.parquet`).

3. **Decouple CryptoAgent from on-chain enrichment via a feature flag:**
   ```python
   # agents/crypto.py
   class CryptoAgent:
       def __init__(self, provider, oncoin_provider=None, enable_oncoin=True):
           self._oncoin = oncoin_provider if enable_oncoin else None
       async def analyze(self, agent_input):
           # 7-factor model unchanged
           if self._oncoin is None or not self._oncoin.is_available():
               # Fall back gracefully
               return self._analyze_price_only(agent_input)
   ```
   The existing 7-factor model still works without on-chain — degrading gracefully prevents a CoinGecko outage from breaking BTC analysis entirely.

4. **Defensive parsing for /coins/{id} payload:** The CoinGecko `/coins/{id}` response is large (~50 fields) and varies — some fields are null, some change shape. Use the existing `_to_float`, `_safe_extract` helpers from `agents/utils.py` that the FundamentalAgent already uses. NEVER do `data["market_data"]["current_price"]["usd"]` in a single dereference; chain `.get()` defensively. (Pattern: see `agents/fundamental.py::_extract_metrics` for the model.)

**Warning signs:**
- `analyze BTC-USD` p95 latency > 8s (existing yfinance-only path is < 2s).
- HTTP 429 rate from CoinGecko visible in logs but CryptoAgent still returns BUY/SELL — silent degradation.
- Backtest of crypto positions stalls partway through corpus rebuild (a single 60s timeout bleeds into the whole portfolio loop).

**Phase to address:**
- **Phase 9 (CoinGecko)**: Per-agent timeout wrapper added to pipeline (NOT deferred — critical for the brownfield pipeline contract). Cache + ToS-compliant 24h refresh + optional flag with graceful price-only fallback.

---

### Pitfall 4: SimFin Restatement Contract Inverted — Bullish Signal Pre-Restatement, Bearish Post-Restatement, NO Cache Invalidation — DATA-CORRUPTION

**What goes wrong:**
SimFin's PIT design DOES return different fundamentals than yfinance for ANY company that restated. Example: a company posts pre-restatement Q1 EPS of +$0.50, then restates to -$0.20 in Q3. SimFin (PIT) would return +$0.50 on a Q2-asof date, and -$0.20 on a Q4-asof date for the SAME date range. yfinance returns the restated -$0.20 always.

Cross-feature failure mode:
- An operator runs analyze on AAPL on `2025-06-15`. yfinance path returns BUY (using restated, looks-good metrics). Result is cached in `signal_history` and `backtest_signal_history`.
- Operator switches to SimFin in v1.2. Same ticker, same date — SimFin returns *as-of* `2025-06-15` un-restated metrics, which produce SELL.
- **Existing caches don't invalidate** because the cache key is `(ticker, date)`, NOT `(ticker, date, fundamentals_provider)`. The historical signal_history row is now WRONG for the active provider.
- Worse: drift detector (`engine/drift_detector.py:_get_avg_icir_60d`) computes 60-day rolling IC from this contaminated history. The detector starts triggering false drift alerts because IC computed against the inconsistent corpus is wildly wrong.

**Why it happens:**
The operator thinks "I'm just adding a better data source." The downstream coupling is invisible: caches, signal_history table, drift_log historical baseline — all keyed without provenance. Re-running historical signals with new providers is a known footgun in the OSS quant world (e.g., Quantopian's old PIT documentation explicitly calls this out).

**How to avoid (defensive code pattern):**

1. **Add `fundamentals_provider` column to `signal_history` and `backtest_signal_history`:**
   ```sql
   ALTER TABLE signal_history ADD COLUMN fundamentals_provider TEXT DEFAULT 'yfinance';
   ALTER TABLE backtest_signal_history ADD COLUMN fundamentals_provider TEXT DEFAULT 'yfinance';
   CREATE INDEX idx_signal_history_provider ON signal_history(ticker, created_at, fundamentals_provider);
   ```
   IC and drift computations MUST filter by provider. Migration is idempotent (default 'yfinance' for existing rows).

2. **Block the corpus rebuild from MIXING providers:**
   ```python
   # engine/drift_detector.py::_get_avg_icir_60d
   async def _get_avg_icir_60d(conn, agent_name, asset_type, fundamentals_provider="yfinance"):
       rows = await conn.execute(
           "SELECT current_icir FROM drift_log "
           "WHERE agent_name=? AND asset_type=? AND fundamentals_provider=? "
           "AND current_icir IS NOT NULL ORDER BY evaluated_at DESC LIMIT 60",
           (agent_name, asset_type, fundamentals_provider),
       )
   ```

3. **Force corpus rebuild on first SimFin enable:**
   When the operator first enables `use_pit_fundamentals=True`, the `POST /calibration/rebuild-corpus` endpoint MUST be re-run with `fundamentals_provider='simfin'`. Auto-trigger this from the settings change handler if possible.

4. **Surface the discrepancy in the UI explicitly:**
   When SimFin returns metrics that differ from yfinance by >X% on a date that was previously analyzed under yfinance, write a row to `signal_history_provenance` table and surface it on `/calibration` as "Provider switch — historical signals re-computed; see X tickers with material change."

**Warning signs:**
- After SimFin lands and a corpus rebuild runs, IC for FundamentalAgent abruptly steps to a new mean (e.g., from 0.04 → 0.18), with no underlying market regime change. Tell-tale of provider switchover effect.
- `drift_log.delta_pct` jumps > 50% on a single Sunday-cron run for FundamentalAgent's stock entries.
- User complains "SELL signal showed up on a position my journal note said was a BUY 6 months ago."

**Phase to address:**
- **Phase 8 (SimFin)**: Schema migration for `fundamentals_provider` column + IC/drift query filter MUST be in the same PR as the SimFin provider, not a follow-up. Add a regression test that asserts `evaluate_drift` returns identical results with provider='yfinance' before and after the migration.

---

### Pitfall 5: Drift-Threshold Validation Data-Snoops the Corpus It Tested Against — SILENT-FAILURE

**What goes wrong:**
The carry-forward task is to validate `>20%` IC-IR drop threshold and `<0.5` absolute floor against live data, "promoting" them out of `preliminary_threshold`. The natural workflow:
1. Compute weekly IC-IR for each (agent, asset_type) on the existing corpus.
2. Find the ground truth — "what was the actual ‘drift’ on dates where the user manually overrode weights?"
3. Tune `>20%` / `<0.5` to match.
4. Promote thresholds from `preliminary_threshold` to "real."

This is **circular**: you tune thresholds on the same data you then claim they detect drift on. It's the same trap as overfitting an ML model to its training set, then claiming it works on training-set predictions.

The MIN_SAMPLES_FOR_REAL_THRESHOLD=60 constant in `engine/drift_detector.py:32` exists *because* the team already knows weekly IC samples are scarce. With ~20-30 weeks of corpus data realistically available by v1.2, even ignoring data-snooping the sample size doesn't support real threshold validation on a single operator's portfolio.

**Why it happens:**
The natural research flow asks "what threshold reliably caught the drifts we know happened?" That phrasing IS data-snooping — the threshold is tuned on the answer. Researchers default to this without realizing it because there's only ONE corpus available and rerunning isn't possible.

Aggravating factor: the operator's portfolio has 5-10 US equities + a couple of crypto positions; results from a 7-position corpus do not generalize to a 50-position portfolio with 20+ sectors.

**How to avoid (defensive methodology pattern):**

1. **Out-of-sample split the corpus by TIME, not by ticker:**
   - Train threshold tuning on `backtest_signal_history` rows from `2022-01-01` to `2024-06-30`.
   - Validate ON `2024-07-01` to `2026-04-27` — never seen during tuning.
   - If thresholds tuned on training-set hold up on validation set with similar precision/recall, that's evidence (still weak, but real). If they degrade dramatically, thresholds are over-fit and stay `preliminary`.

2. **Bootstrap confidence intervals on threshold:**
   Don't pick a single number `>20%`. Resample the corpus 1000× with replacement, recompute "would this threshold have triggered" each time, and report the threshold's 95% confidence interval. If the interval is `[12%, 35%]`, the answer is "we don't have enough data to pick a tight threshold."

3. **Cross-portfolio validation (synthetic):**
   Use 3-5 well-known public portfolios (e.g., the SPDR sector ETFs as proxies, or a paper-traded LLM-recommended portfolio) and rerun the threshold against THEIR signal_history. If `>20%` works for the operator's portfolio but fails for an SPDR sector reconstruction, that's evidence the threshold is operator-specific and should stay `preliminary`.

4. **Honest "not yet" path:**
   The conservative outcome of validation is: "We don't have enough samples; thresholds REMAIN preliminary; we will revisit at v1.3 with 60+ weeks of weekly data." This is a valid v1.2 outcome, NOT a failure. Document it explicitly in PROJECT.md.

5. **Threshold-creep guard:**
   Ship a regression test that REQUIRES preliminary_threshold remain `True` until a documented condition is met:
   ```python
   def test_preliminary_threshold_promotion_requires_evidence():
       """Promoting drift thresholds out of preliminary requires documented validation.
       This test is intentionally a tripwire — the only way to flip it is to
       explicitly delete this test, forcing a discussion about why."""
       assert MIN_SAMPLES_FOR_REAL_THRESHOLD >= 60
       # When we do promote, this test gets a follow-up that asserts:
       # - validation set IC-IR samples >= 60
       # - bootstrap 95% CI on threshold is < 10pp wide
       # - cross-portfolio validation confirms threshold within 25% of operator's
   ```

**Warning signs:**
- Validation report says "thresholds work great, all 7 tickers!" — that's not validation, that's a mirror.
- A v1.2 PR proposes flipping `preliminary_threshold = False` as a hardcoded default with no validation set documented.
- Threshold tuning produces a value coincidentally close to `>20%` / `<0.5` — researcher's prior leaking into the tuning result.

**Phase to address:**
- **Phase 10 (Drift validation)**: Methodology must be agreed BEFORE tuning. Out-of-sample split + bootstrap + threshold-creep guard test. If sample size insufficient, explicit "remain preliminary" decision recorded in PROJECT.md as a Key Decision.

---

## Moderate Pitfalls

### Pitfall 6: CoinGecko On-Chain Adoption Bias Re-introduces a Bug Already Fixed — DATA-CORRUPTION

**What goes wrong:**
`CONCERNS.md:55-60` records that `CryptoAgent` previously had a "network adoption" weight of 10% which was a "static constant bias toward bullish signals" — fixed in commit `aaeb90b` by reducing to 5% and redistributing. Adding CoinGecko on-chain RE-OPENS this surface area: dev-activity, hash-rate, MVRV, exchange flows are all candidate "adoption-like" inputs that, if weighted naively, restore the bullish-bias bug.

**Why it happens:**
The commit message in `aaeb90b` describes the fix; the agent code today implements the fix; but the *reasoning* (why network-adoption is biased bullish in BTC) is not documented in the agent docstring. A v1.2 contributor adding CoinGecko sees a 7-factor model with weight room and naively assigns 10% to "on-chain adoption" again.

**How to avoid:**
- Add an inline comment in `agents/crypto.py` explaining the historical fix.
- Phase-9 RESEARCH.md must address: of CoinGecko's on-chain signals, which are bidirectional (e.g., MVRV >2.5 is bearish, < 1 is bullish — clear regime) and which are "adoption-like" (only-up biased). Bias-toward-bullish signals get max 3% individually; bidirectional signals can get up to 5%.
- Phase-9 regression test: assert that with all on-chain inputs at neutral/missing values, CryptoAgent's signal distribution over a 100-ticker simulation is symmetric (no >55%/45% skew toward BUY).

**Phase to address:** Phase 9 (CoinGecko).

---

### Pitfall 7: Reliability Plot Survivorship Bias Inherits the Existing Corpus Bias Silently — SILENT-FAILURE

**What goes wrong:**
The `backtest_signal_history` corpus is built from currently-tradeable tickers selected by the operator (~7 stocks + 2 crypto). Tickers that delisted, were acquired, or went bankrupt are NOT in the corpus. Reliability plots built on this corpus systematically OVER-state the calibration — agents will look "well-calibrated" because they never saw the failures.

The existing `/api/v1/analytics/calibration` endpoint already exposes `survivorship_bias_warning: true` flag (PROJECT.md line 39 references this). The reliability-plot endpoint MUST inherit and prominently surface this flag.

**Why it happens:**
The existing flag is designed for Brier/IC; reliability-plot copy-paste integration easily forgets to plumb it through to the new endpoint.

**How to avoid:**
- Add a contract test: `test_reliability_endpoint_inherits_survivorship_warning` that confirms the new endpoint's response includes `survivorship_bias_warning` whenever the underlying corpus query has it.
- Frontend renders a small "S" badge or note next to the plot title when this flag is set.
- Document on the frontend page: "Plot built from currently-tradeable tickers only; delisted / bankrupt stocks excluded."

**Phase to address:** Phase 8 (Reliability Plots).

---

### Pitfall 8: SimFin Free-Tier API Rate Limit Triggers DURING the v1.1 Async Corpus Rebuild — LOUD-FAILURE

**What goes wrong:**
v1.1 LIVE-01 introduced `POST /calibration/rebuild-corpus` with per-ticker progress, running in `_run_batch_rebuild`. If SimFin replaces the FundamentalAgent's data source for a corpus-wide rebuild, AND a corpus rebuild covers (e.g.) 50 tickers × 250 trading days, that's 12,500 SimFin API calls. Free-tier daily limit is bounded (SimFin doesn't publish a hard ceiling on the free tier, but pricing pages strongly imply daily caps for non-paid users [source](https://www.simfin.com/en/prices/)).

Without rate-limit awareness, the corpus rebuild gets a third of the way through, hits the limit, and fails with HTTP 429 cascading. Worse: the rebuild's existing rollback (`_run_batch_rebuild` DELETE on error from PROJECT.md line 42) can leave the corpus partially populated if 429 isn't classified as a fatal-rollback condition.

**Why it happens:**
SimFin's free tier ToS does not publish exact daily/per-minute caps in the way CoinGecko does. Easy to integrate without a rate limiter, especially if the developer test uses the PAID `simfin+` tier.

**How to avoid:**
- Wrap `SimfinProvider` calls with the existing `data_providers/rate_limiter.py::AsyncRateLimiter` set conservatively (e.g., 2/s, sliding 60s window of 60 calls — plenty even for slow free tier).
- Corpus rebuild MUST honor the existing FOUND-07 four-state machine — a 429 should set the job to FAILED and trigger the existing rollback DELETE, NOT loop indefinitely.
- Add a smoke test: `test_simfin_429_triggers_clean_rollback` using `respx`/`httpx` mock to confirm error path.
- If user is on the free tier, surface a UI estimate: "Rebuild will take ~6 hours at free-tier rate" before they kick off the job, so they can decide.

**Phase to address:** Phase 8 (SimFin).

---

### Pitfall 9: `[llm-local]` Pattern Mis-Applied to SimFin (Should Be Required, Not Optional) — COSMETIC then DATA-CORRUPTION

**What goes wrong:**
The project pattern for optional providers is `[llm-local]` (FinBERT) and similar — install only if user opts in. SimFin's natural fit is "optional point-in-time enhancement." But making SimFin optional means: in some installs, `use_pit_fundamentals=True` will silently fall back to yfinance (because the SimFin provider isn't installed), giving the operator a backtest they THINK is PIT but isn't.

**Why it happens:**
"Optional installs" pattern is good for heavy/large dependencies (PyTorch, FinBERT). For data providers that are required for a specific correctness property (PIT in this case), optional installation is a footgun.

**How to avoid:**
- SimFin Python client (`simfin` package) is small (Pandas-based, no native deps). Add to CORE dependencies, NOT optional `[llm-local]` extra.
- If installed but `SIMFIN_API_KEY` env var missing, the operator who tries `use_pit_fundamentals=True` should get a HARD error with a clear message ("Set SIMFIN_API_KEY or set use_pit_fundamentals=False"), NOT silent fallback to yfinance.
- Add a regression test: `test_simfin_provider_no_silent_yfinance_fallback`.

**Phase to address:** Phase 8 (SimFin).

---

### Pitfall 10: Reliability Plot Doesn't Distinguish Backtest-Corpus from Live-Corpus — UX/SILENT-FAILURE

**What goes wrong:**
v1.1 maintains TWO signal corpora: `signal_history` (live, daemon-populated, currently sparse ~10 rows) and `backtest_signal_history` (synthetic via backtester, populated by LIVE-01 corpus rebuild). Reliability plot built on backtest corpus is ABOUT historical hypothetical signals; reliability plot built on live corpus is ABOUT what the daemon actually emitted.

The operator viewing the plot must know WHICH one. Otherwise: "my live signals are well-calibrated" (when really only backtest signals were calibrated) — false confidence in live performance.

**Why it happens:**
Two corpora is a brownfield reality the operator already understands (it shipped in v1.1). New v1.2 reliability plot can default to either corpus and the choice is invisible.

**How to avoid:**
- Separate API endpoints: `GET /analytics/calibration/reliability?corpus=backtest` vs `corpus=live`. Default to `backtest` (more rows) but make it explicit.
- Frontend toggle on `/calibration` page allowing operator to switch corpora.
- Plot title MUST include the corpus source ("Backtest corpus reliability" vs "Live signal reliability").

**Phase to address:** Phase 8 (Reliability Plots).

---

### Pitfall 11: CoinGecko Attribution Forgotten — ToS VIOLATION (LOUD-FAILURE on audit)

**What goes wrong:**
CoinGecko's free-tier ToS requires displaying "Powered by CoinGecko" prominently in legible font (no smaller than size 10) and linking to coingecko.com/en/api ([source](https://www.coingecko.com/en/api_terms)). For a single-user local app this is low-stakes, but if the project moves toward shared deployment or any public-facing feature, omission is a ToS violation that could trigger API-key revocation.

**Why it happens:**
"Personal use only" attitude prevailing in the v1.2 milestone; ToS gets read superficially.

**How to avoid:**
- Add "Powered by CoinGecko" footer/badge on `/calibration` and `/analyze` pages whenever crypto on-chain data is displayed.
- Add a comment in `data_providers/coingecko_provider.py` noting the attribution requirement so it doesn't get removed in a future cleanup.

**Phase to address:** Phase 9 (CoinGecko).

---

## Minor Pitfalls

### Pitfall 12: Reliability Plot Confidence Calibration Conflated with Probability Calibration

**What goes wrong:**
Existing `tracker.py::compute_calibration_data` plots *confidence* (50, 60, 70...) as a proxy for *expected probability* on the X-axis. SIG-v2-01 reliability plots in the ML literature use *predicted probability* (after sigmoid/calibration mapping). These are NOT the same thing — a 70% confidence agent is not necessarily claiming 70% probability of correct directional move.

If implementers copy ML-literature reliability-plot code without converting confidence→probability, the diagonal "perfect calibration" line is meaningless.

**How to avoid:**
- Document the convention explicitly in the API: "X-axis = mean predicted confidence within bin, Y-axis = realized win-rate within bin."
- The existing tracker code uses `expected_win_rate = midpoint` — keep this convention; don't introduce a separate "probability" semantics.

**Phase to address:** Phase 8.

---

### Pitfall 13: SimFin Sector Mapping Differs from Existing 12-Sector Static Table

**What goes wrong:**
`agents/fundamental.py:25-38` has `SECTOR_PE_MEDIANS` keyed by 12 sector names ("technology", "financial services", etc.). yfinance and Finnhub use compatible-ish naming. SimFin uses the GICS 11-sector taxonomy with slightly different naming ("Information Technology" vs "Technology", no "Financial Services" — uses "Financials"). Adding SimFin without a mapping layer means `_score_pe_trailing` falls back to absolute thresholds for SimFin-sourced sector strings, even though static medians exist.

**How to avoid:**
- Add a `_SECTOR_ALIAS` map in `agents/fundamental.py` normalizing ("financials" → "financial services", "Information Technology" → "technology", etc.).
- `CONCERNS.md:209-216` already flags inconsistent yfinance sector naming as fragile. SimFin compounds it. Address in same PR.

**Phase to address:** Phase 8.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip `fundamentals_provider` column on signal_history | Faster Phase 8 ship | Pitfall 4 — corpus contamination, can't unmix providers later, requires data deletion to recover | Never — must land in same PR as SimFin |
| Use `n_bins=10` constant for reliability plot | Matches sklearn tutorial | Pitfall 2 — Swiss-cheese plots, false-confidence banner missing | Never with current corpus size |
| No per-agent timeout in pipeline | Reuses existing pattern | Pitfall 3 — CoinGecko 429/slow blocks all crypto analysis for 60s | Never — landing CoinGecko without timeout is a footgun |
| Make SimFin an optional `[pit-data]` extra | Smaller default install | Pitfall 9 — silent fallback to yfinance pretending to be PIT | Never; SimFin is small enough for core deps |
| Tune drift thresholds on full corpus | Faster validation phase | Pitfall 5 — circular validation, false-confidence "real" thresholds | Acceptable only with documented out-of-sample split + bootstrap CI |
| Skip CoinGecko attribution UI | Saves UI work | Pitfall 11 — API-key revocation if portfolio ever shared | Acceptable while strictly local-single-user |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| SimFin → FundamentalAgent | Treat SimFin as drop-in yfinance replacement; remove FOUND-04 short-circuit | Add `use_pit_fundamentals` flag; preserve FOUND-04 default; corpus column for provider |
| SimFin → backtest_signal_history | Mix yfinance and SimFin rows in same Brier/IC calculation | New column `fundamentals_provider`; filter at query time |
| CoinGecko → CryptoAgent | Add as required input; CryptoAgent fails if CoinGecko down | Optional flag with graceful price-only fallback; per-call 10s timeout |
| CoinGecko → asyncio.gather | No timeout on parallel agent runs | `asyncio.wait_for(timeout=10)` wrapper at pipeline edge |
| CoinGecko on-chain → CryptoAgent weights | Re-introduce 10% network-adoption bias | Document existing fix; cap each adoption-biased input at 3% |
| Reliability plot → existing endpoint | Re-implement calibration logic in new endpoint | Reuse `tracker.compute_calibration_data` + extend; preserve `preliminary_calibration` flag |
| Drift threshold validation → Phase 7 thresholds | Tune `>20%` / `<0.5` on the same corpus that proves them | Out-of-sample time-split + bootstrap CI + cross-portfolio sanity |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| CoinGecko slow call blocks gather | analyze BTC > 8s p95, all sibling agents waiting | `asyncio.wait_for(10s)` per-agent | Always at low rate-limit (5/min); occasional at 15/min |
| SimFin corpus rebuild bursts API limit | Rebuild fails after ~30% completion with 429 | `AsyncRateLimiter` 2/s; honor FOUND-07 rollback | Always for portfolios > 5 tickers |
| Reliability plot recompute on every page load | Plot endpoint > 200ms; CalibrationPage feels sluggish | Cache reliability response with same 24h TTL pattern as Brier | At ≥ 500 corpus rows |
| Drift validation bootstrap re-resamples synchronously | Validation script takes minutes | Use `numpy.random.choice` for vectorized resample | Always at 1000+ bootstrap iterations |

---

## "Looks Done But Isn't" Checklist

- [ ] **SimFin Provider:** Often missing `fundamentals_provider` column on signal_history → verify migration in same PR + IC-query filter applied
- [ ] **SimFin Provider:** Often missing FOUND-04 contract regression test → verify `test_fundamental_agent_backtest_mode_default_unchanged` exists and passes
- [ ] **SimFin Provider:** Often silent-fallback to yfinance when SIMFIN_API_KEY missing → verify hard-error raised, not soft-fallback
- [ ] **Reliability Plot:** Often default `n_bins=10` regardless of N → verify `_adaptive_bin_count` helper used
- [ ] **Reliability Plot:** Often missing `preliminary_calibration` flag → verify response includes flag and CalibrationPage renders amber banner
- [ ] **Reliability Plot:** Often hides survivorship-bias warning → verify endpoint inherits flag from underlying calibration query
- [ ] **Reliability Plot:** Often conflates backtest and live corpus → verify `?corpus=backtest|live` query param + UI toggle
- [ ] **CoinGecko Provider:** Often no timeout on agent call → verify `asyncio.wait_for` wrapper in pipeline
- [ ] **CoinGecko Provider:** Often missing 24h cache → verify Parquet cache at `data/cache/coingecko/` with cache_max_age=24h
- [ ] **CoinGecko Provider:** Often missing "Powered by CoinGecko" attribution → verify footer on /analyze and /calibration pages
- [ ] **CoinGecko Provider:** Often re-introduces network-adoption-bias bug → verify per-input cap ≤ 3% for adoption-like signals; symmetry test
- [ ] **Drift Threshold Validation:** Often data-snoops → verify out-of-sample time split documented in research; thresholds remain `preliminary` if sample size < 60
- [ ] **Drift Threshold Validation:** Often promotes thresholds without bootstrap CI → verify CI width < 10pp before promotion
- [ ] **Drift Threshold Validation:** Often produces "thresholds work great" report → verify cross-portfolio synthetic validation (SPDR ETFs) included

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| FOUND-04 contract bypass (Pitfall 1) | HIGH | (a) Identify all backtest_signal_history rows since SimFin merge; (b) Mark with `tainted=1`; (c) Re-run corpus rebuild from clean state; (d) Restore drift_log baseline from pre-merge snapshot. ~2 days work. |
| Reliability plot small-N false confidence (Pitfall 2) | LOW | Add `preliminary_calibration` flag retroactively; UI banner; no data corruption. ~half day. |
| CoinGecko 429 storm (Pitfall 3) | LOW | Add timeout + cache; deploy hotfix. ~half day. |
| Provider-mixing in signal_history (Pitfall 4) | HIGH | Same as Pitfall 1 recovery; add post-hoc `fundamentals_provider` column with best-effort backfill (most rows are yfinance era — safe default). ~2 days. |
| Drift threshold over-fit (Pitfall 5) | MEDIUM | Roll back `preliminary_threshold = False` flip in PROJECT.md/code; retain audit log of false promotions. ~1 day. |
| Network-adoption bias re-introduced (Pitfall 6) | LOW-MEDIUM | Run distribution-symmetry test; if failed, cap individual on-chain weights ≤3%. Backtest unaffected positions to confirm. ~1 day. |
| ToS violation without attribution (Pitfall 11) | LOW | Add attribution UI; if API key revoked, request reinstatement after compliance proof. ~half day if caught early. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Severity | Prevention Phase | Verification |
|---------|----------|------------------|--------------|
| 1. SimFin bypasses FOUND-04 | DATA-CORRUPTION | **Phase 8** | `test_fundamental_agent_backtest_mode_default_unchanged` passes on initial PR |
| 2. Reliability plot bin sizing | SILENT-FAILURE | **Phase 8** | `test_adaptive_bin_count`; `preliminary_calibration` flag in response; UI amber banner |
| 3. CoinGecko rate limit blocks pipeline | LOUD-FAILURE | **Phase 9** | Pipeline analyze p95 latency for BTC < 5s; `test_coingecko_timeout_does_not_block_other_agents` |
| 4. SimFin corpus contamination | DATA-CORRUPTION | **Phase 8** | `fundamentals_provider` column migration test; IC query filter test; corpus-rebuild forced on first SimFin enable |
| 5. Drift threshold data-snooping | SILENT-FAILURE | **Phase 10** | Out-of-sample split documented; bootstrap CI < 10pp; `test_preliminary_threshold_promotion_requires_evidence` tripwire |
| 6. CoinGecko adoption bias re-introduction | DATA-CORRUPTION | **Phase 9** | Symmetry test; per-input cap ≤3%; inline comment about historical fix |
| 7. Reliability plot survivorship bias | SILENT-FAILURE | **Phase 8** | `test_reliability_endpoint_inherits_survivorship_warning` |
| 8. SimFin rate limit during rebuild | LOUD-FAILURE | **Phase 8** | `AsyncRateLimiter` integration; `test_simfin_429_triggers_clean_rollback` |
| 9. SimFin optional install footgun | DATA-CORRUPTION | **Phase 8** | `test_simfin_provider_no_silent_yfinance_fallback` |
| 10. Backtest vs live corpus conflation | SILENT-FAILURE | **Phase 8** | API `?corpus=backtest|live` param; UI toggle; plot title disambiguation |
| 11. CoinGecko attribution missing | COSMETIC → ToS | **Phase 9** | UI footer present on pages displaying CoinGecko data |
| 12. Confidence vs probability conflation | COSMETIC | **Phase 8** | API doc string + comment explicit on convention |
| 13. SimFin sector naming mismatch | SILENT-FAILURE (low) | **Phase 8** | `_SECTOR_ALIAS` map; sector-coverage test |

---

## Cross-Feature Pitfalls (Most Important)

These pitfalls only manifest when multiple v1.2 features interact:

### Cross-1: SimFin + Drift Detector (Pitfall 4 reified)

**What:** Drift detector's `_get_avg_icir_60d` computes a baseline from drift_log history. If SimFin lands and operator enables PIT for ANY ticker, IC-IR shifts due to provider switch (not real drift). Detector triggers, scales weights down on FundamentalAgent, alerts user. False alarm.

**Prevention:** `fundamentals_provider` column on drift_log + filter at query time + force baseline reset on first SimFin enable. **Owned by Phase 8** (must land with SimFin).

**Verification:** `test_drift_detector_baseline_isolated_per_provider`.

### Cross-2: CoinGecko + Drift Detector

**What:** New CoinGecko on-chain inputs add 1-2 features to CryptoAgent. The drift detector's MIN_SAMPLES_FOR_REAL_THRESHOLD=60 is calibrated against the v1.1 7-factor crypto model. Adding new inputs shifts CryptoAgent's IC distribution; thresholds tuned against the old distribution misfire on the new one.

**Prevention:** When CryptoAgent's input space changes, drift detector for `(CryptoAgent, btc/eth)` MUST reset its `preliminary_threshold = True` regardless of sample count. Add a regression test.

**Phase:** Phase 9 owns the reset; Phase 10 owns ensuring threshold validation excludes the input-change transition window.

### Cross-3: Reliability Plot + CoinGecko + SimFin

**What:** Reliability plots are computed per (agent, asset_type). After Phase 9 + Phase 8, the underlying signal distributions for FundamentalAgent and CryptoAgent shift simultaneously. A reliability plot computed against a corpus that mixes pre- and post-v1.2 signals will look badly miscalibrated, but the cause is the corpus mix, not the agent.

**Prevention:** Phase 10 corpus rebuild is MANDATORY before any "agent X is miscalibrated" decision based on v1.2 reliability plots. Document this in the v1.2 release notes.

**Phase:** Phase 10 (validation) — the rebuild MUST come before plot interpretation.

### Cross-4: Drift Validation Promotes Thresholds + SimFin Corpus Rebuild Concurrent

**What:** Phase 10 wants to validate drift thresholds. Phase 8 introduces SimFin which forces corpus rebuild. If these run concurrently or out of order, threshold validation runs on a half-rebuilt corpus.

**Prevention:** Phase ordering MUST be Phase 8 (SimFin + corpus rebuild) → Phase 9 (CoinGecko + corpus rebuild) → Phase 10 (drift validation against fully-rebuilt corpus). Add a Phase 10 prerequisite check that asserts the corpus was last rebuilt AFTER the SimFin and CoinGecko provider feature flags landed.

**Phase:** Phase 10 (validation) verifies; Phase 8/9 do not need to enforce ordering directly because the prerequisite check in Phase 10 fails fast if violated.

---

## Sources

- [SimFin pricing & ToS](https://www.simfin.com/en/prices/) — free-tier license is personal/internal use only; paid `simfin+` for commercial.
- [SimFin technical updates / API v3](https://www.simfin.com/en/technical-updates-to-api-v3-and-bulk-download/) — API change cadence.
- [SimFin Python package](https://github.com/SimFin/simfin) — caching/storage patterns; "highly recommended to set the cache directory globally."
- [CoinGecko API ToS](https://www.coingecko.com/en/api_terms) — attribution + caching policy ("refresh at least every 24 hours") + commercial-use rules.
- [CoinGecko free-tier rate limit FAQ](https://support.coingecko.com/hc/en-us/articles/4538771776153) — 5-15 calls/minute.
- [CoinGecko API timeout & error docs](https://support.coingecko.com/hc/en-us/articles/23406416525209) — default 1-minute timeout.
- [CoinGecko-SDK PyPI](https://pypi.org/project/coingecko-sdk/) — async patterns; built-in retry/backoff.
- [scikit-learn calibration documentation](https://scikit-learn.org/stable/modules/calibration.html) — `n_bins=5` default; "more data for a bigger number"; pitfall about overlooking samples per bin.
- [scikit-learn calibration_curve API](https://scikit-learn.org/stable/modules/generated/sklearn.calibration.calibration_curve.html) — bin parametrization.
- [sharpely.in PIT backtesting blog](https://sharpely.in/blog/bias-free-backtesting-explained:-how-sharpely-uses-point-in-time-data-to-avoid-look-ahead-and-survivorship-bias) — restatement bias examples.
- [S&P Global PIT vs lagged fundamentals (PDF)](https://www.spglobal.com/content/dam/spglobal/mi/en/documents/general/sp-capitaliq-quantamental-point-in-time-vs-lagged-fundamentals.pdf) — restatement vs lag distinction.
- Internal: `engine/drift_detector.py` (NEVER-zero-all guard, MIN_SAMPLES_FOR_REAL_THRESHOLD=60, `manual_override` semantics).
- Internal: `agents/fundamental.py:56-77` (FOUND-04 short-circuit), `agents/fundamental.py:140-163` (defence-in-depth EDGAR guard).
- Internal: `tracking/tracker.py:96-135` (existing `compute_calibration_data` 10%-bucket + `min_bucket_size=5` pattern), `tracker.py:320-350` (Brier one-vs-rest binary excluding HOLD).
- Internal: `engine/pipeline.py:130` (`asyncio.gather(return_exceptions=True)` without per-agent timeout).
- Internal: `.planning/codebase/CONCERNS.md:55-60` (CryptoAgent network-adoption bias prior fix), `:209-216` (sector-naming fragility), `:264-267` (on-chain metrics gap acknowledged).
- Internal: `.planning/PROJECT.md` Key Decisions row "v1.1 drift-detector NEVER-zero-all guard" (whole-asset_type guard rationale), "Phase 7 `_clamp_pii` regex narrowing" (PII pattern precedent for SimFin/CoinGecko PII handling).

---

*Pitfalls research for: Investment Agent v1.2 Trustworthy Signals*
*Researched: 2026-04-27*
